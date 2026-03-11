# -*- coding: utf-8 -*-
"""
搜书神器 V2 - 书籍详情处理器
处理书籍详情展示、书单、评价、相似推荐、标签申请与管理员编辑
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.core.deeplink import encode_payload
from app.core.logger import logger
from app.core.models import (
    Book,
    BookList,
    BookReview,
    BookTag,
    DownloadLog,
    Favorite,
    File,
    FileRef,
    TagApplication,
    User,
)
from app.core.text import escape_html
from app.services.book_ops import (
    SimilarBooksResult,
    add_book_to_booklist,
    create_booklist,
    delete_booklist,
    edit_book_field,
    ensure_user_record,
    get_book_edit_history,
    get_public_booklist,
    get_recent_reviews,
    get_similar_books,
    list_user_booklists,
    remove_book_from_booklist,
    remove_tag_from_book,
    rename_booklist,
    review_tag_application,
    submit_tag_application,
    sync_book_to_search,
    toggle_booklist_public,
    upsert_review,
)

book_detail_router = Router(name="book_detail")


@dataclass
class PendingAction:
    action: str
    payload: dict[str, Any]
    expires_at: datetime


PENDING_ACTIONS: dict[int, PendingAction] = {}
PENDING_TTL = timedelta(minutes=10)


def set_pending_action(user_id: int, action: str, **payload: Any) -> None:
    PENDING_ACTIONS[user_id] = PendingAction(
        action=action,
        payload=payload,
        expires_at=datetime.now() + PENDING_TTL,
    )


def clear_pending_action(user_id: int) -> None:
    PENDING_ACTIONS.pop(user_id, None)


def peek_pending_action(user_id: int) -> Optional[PendingAction]:
    row = PENDING_ACTIONS.get(user_id)
    if not row:
        return None
    if row.expires_at < datetime.now():
        PENDING_ACTIONS.pop(user_id, None)
        return None
    return row


def format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes}B"
    if size_bytes < 1024 * 1024:
        kb = round(size_bytes / 1024, 1)
        return f"{int(kb)}KB" if float(kb).is_integer() else f"{kb:.1f}KB"
    if size_bytes < 1024 * 1024 * 1024:
        mb = round(size_bytes / (1024 * 1024), 1)
        return f"{int(mb)}MB" if float(mb).is_integer() else f"{mb:.1f}MB"
    return f"{size_bytes / (1024 * 1024 * 1024):.1f}GB"


def format_date(dt: Optional[datetime]) -> str:
    if not dt:
        return "未知"
    try:
        return dt.strftime("%Y/%m/%d %H:%M:%S")
    except Exception:
        return "未知"


def format_word_count(count: int) -> str:
    if count < 10000:
        return f"{count}"
    if count < 100000000:
        value = count / 10000
        value = int(value * 10) / 10
        return f"{value:.1f}万"
    return f"{count / 100000000:.1f}亿"


def pick_primary_file_ref(file_refs: list[FileRef]) -> Optional[FileRef]:
    for ref in file_refs:
        if ref.is_active and ref.is_primary and ref.tg_file_id:
            return ref
    for ref in file_refs:
        if ref.is_active and ref.tg_file_id:
            return ref
    return None


def pick_backup_ref(file_refs: list[FileRef]) -> Optional[FileRef]:
    for ref in file_refs:
        if ref.is_active and ref.is_backup and ref.channel_id and ref.message_id:
            return ref
    for ref in file_refs:
        if ref.is_active and ref.channel_id and ref.message_id:
            return ref
    return None


def build_user_book_keyboard(*, book_id: int, is_fav: bool, is_admin: bool = False) -> InlineKeyboardMarkup:
    fav_text = "已收藏" if is_fav else "收藏"
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(text=fav_text, callback_data=f"book:fav:{book_id}"),
            InlineKeyboardButton(text="加入书单", callback_data=f"book:booklist:{book_id}"),
            InlineKeyboardButton(text="评价", callback_data=f"book:review:{book_id}"),
        ],
        [
            InlineKeyboardButton(text="加标签", callback_data=f"book:tagadd:{book_id}"),
            InlineKeyboardButton(text="相似", callback_data=f"book:similar:{book_id}:1"),
            InlineKeyboardButton(text="更多", callback_data=f"book:more:{book_id}"),
        ],
        [InlineKeyboardButton(text="下载本书", callback_data=f"book:download:{book_id}")],
    ]
    if is_admin:
        rows.append(
            [
                InlineKeyboardButton(text="编辑", callback_data=f"book:admin_edit:{book_id}"),
                InlineKeyboardButton(text="历史", callback_data=f"book:admin_history:{book_id}"),
                InlineKeyboardButton(text="审核标签", callback_data=f"book:admin_tag_queue:{book_id}"),
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_more_keyboard(*, book_id: int, is_admin: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="我的书单", callback_data=f"book:booklist_overview:{book_id}"),
            InlineKeyboardButton(text="查看短评", callback_data=f"book:review_list:{book_id}:1"),
        ],
        [
            InlineKeyboardButton(text="分享链接", callback_data=f"book:share:{book_id}"),
            InlineKeyboardButton(text="举报", callback_data=f"book:report:{book_id}"),
        ],
        [InlineKeyboardButton(text="返回详情", callback_data=f"book:restore:{book_id}")],
    ]
    if is_admin:
        rows.insert(
            1,
            [
                InlineKeyboardButton(text="管理编辑", callback_data=f"book:admin_edit:{book_id}"),
                InlineKeyboardButton(text="标签审核", callback_data=f"book:admin_tag_queue:{book_id}"),
            ],
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_booklist_keyboard(
    *,
    book_id: int,
    booklists: list[BookList],
    selected_ids: set[int],
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for row in booklists:
        count = len(row.items or [])
        prefix = "✅ " if row.id in selected_ids else ""
        suffix = " (默认)" if row.is_default else ""
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{prefix}[{count}本] {row.name}{suffix}",
                    callback_data=f"book:booklist_toggle:{book_id}:{row.id}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(text="新建书单", callback_data=f"book:booklist_new:{book_id}"),
            InlineKeyboardButton(text="书单总览", callback_data=f"book:booklist_overview:{book_id}"),
        ]
    )
    rows.append([InlineKeyboardButton(text="返回详情", callback_data=f"book:restore:{book_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_booklist_overview_keyboard(*, book_id: int, booklists: list[BookList]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for row in booklists:
        public_text = "公开" if row.is_public else "私有"
        rows.append(
            [
                InlineKeyboardButton(text=row.name, callback_data=f"book:booklist_view:{book_id}:{row.id}"),
                InlineKeyboardButton(text=public_text, callback_data=f"book:booklist_share:{book_id}:{row.id}"),
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(text="新建", callback_data=f"book:booklist_new:{book_id}"),
            InlineKeyboardButton(text="返回详情", callback_data=f"book:restore:{book_id}"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_single_booklist_manage_keyboard(*, book_id: int, list_id: int, is_default: bool) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="切换公开状态", callback_data=f"book:booklist_share:{book_id}:{list_id}")],
        [InlineKeyboardButton(text="重命名", callback_data=f"book:booklist_rename:{book_id}:{list_id}")],
    ]
    if not is_default:
        rows.append([InlineKeyboardButton(text="删除书单", callback_data=f"book:booklist_delete:{book_id}:{list_id}")])
    rows.append([InlineKeyboardButton(text="返回书单总览", callback_data=f"book:booklist_overview:{book_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_review_rating_keyboard(*, book_id: int, current_rating: Optional[int] = None) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"{'✅' if current_rating == rating else ''}{rating}星",
                callback_data=f"book:review_rate:{book_id}:{rating}",
            )
            for rating in range(1, 6)
        ],
        [InlineKeyboardButton(text="查看短评", callback_data=f"book:review_list:{book_id}:1")],
        [InlineKeyboardButton(text="返回详情", callback_data=f"book:restore:{book_id}")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_review_list_keyboard(*, book_id: int, page: int, total: int, per_page: int = 5) -> InlineKeyboardMarkup:
    total_pages = max((total + per_page - 1) // per_page, 1)
    rows: list[list[InlineKeyboardButton]] = []
    nav: list[InlineKeyboardButton] = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="上一页", callback_data=f"book:review_list:{book_id}:{page - 1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton(text="下一页", callback_data=f"book:review_list:{book_id}:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="我要评价", callback_data=f"book:review:{book_id}")])
    rows.append([InlineKeyboardButton(text="返回详情", callback_data=f"book:restore:{book_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_similar_keyboard(*, book_id: int, page: int, result: SimilarBooksResult, per_page: int = 5) -> InlineKeyboardMarkup:
    total_pages = max((result.total + per_page - 1) // per_page, 1)
    rows: list[list[InlineKeyboardButton]] = []
    for item in result.items:
        rows.append([InlineKeyboardButton(text=item.title[:40], callback_data=f"book:detail:{item.id}")])
    nav: list[InlineKeyboardButton] = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="上一页", callback_data=f"book:similar:{book_id}:{page - 1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton(text="下一页", callback_data=f"book:similar:{book_id}:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="返回详情", callback_data=f"book:restore:{book_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_admin_tag_queue_keyboard(
    *,
    book_id: int,
    items: list[TagApplication],
    current_tags: Optional[list[tuple[int, str]]] = None,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for tag_id, tag_name in current_tags or []:
        rows.append([InlineKeyboardButton(text=f"删除 #{tag_name}", callback_data=f"book:admin_tag_remove:{book_id}:{tag_id}")])
    for row in items:
        rows.append(
            [
                InlineKeyboardButton(text=f"通过 #{row.tag_name}", callback_data=f"book:admin_tag_approve:{book_id}:{row.id}"),
                InlineKeyboardButton(text="拒绝", callback_data=f"book:admin_tag_reject:{book_id}:{row.id}"),
            ]
        )
    rows.append([InlineKeyboardButton(text="返回详情", callback_data=f"book:restore:{book_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_admin_edit_keyboard(*, book_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="标题", callback_data=f"book:admin_edit_field:{book_id}:title"),
                InlineKeyboardButton(text="作者", callback_data=f"book:admin_edit_field:{book_id}:author"),
            ],
            [
                InlineKeyboardButton(text="简介", callback_data=f"book:admin_edit_field:{book_id}:description"),
                InlineKeyboardButton(text="成人分级", callback_data=f"book:admin_edit_field:{book_id}:is_18plus"),
            ],
            [
                InlineKeyboardButton(text="VIP标记", callback_data=f"book:admin_edit_field:{book_id}:is_vip_only"),
                InlineKeyboardButton(text="编辑历史", callback_data=f"book:admin_history:{book_id}"),
            ],
            [InlineKeyboardButton(text="返回详情", callback_data=f"book:restore:{book_id}")],
        ]
    )


async def get_book_from_db(book_id: int) -> Optional[Book]:
    session_factory = get_session_factory()
    async with session_factory() as session:
        stmt = (
            select(Book)
            .where(Book.id == book_id)
            .options(
                selectinload(Book.file).selectinload(File.file_refs),
                selectinload(Book.uploader),
                selectinload(Book.book_tags).selectinload(BookTag.tag),
            )
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


def build_book_caption(book: Book, *, bot_username: str = "") -> str:
    tags = [bt.tag.name for bt in (book.book_tags or []) if bt.tag and bt.tag.name]
    tags_display = " ".join([f"#{escape_html(t)}" for t in tags[:30]]) if tags else "暂无标签"

    description = (book.description or "暂无简介").strip()
    if len(description) > 350:
        description = description[:350] + "..."

    uploader_name = "未知"
    if book.uploader:
        uploader_name = (
            book.uploader.username
            or f"{book.uploader.first_name}{book.uploader.last_name or ''}".strip()
            or "未知"
        )
    uploader_name = escape_html(uploader_name)

    file_format = book.file.format.value if book.file and book.file.format else "未知"
    file_size = format_size(book.file.size) if book.file else "未知"
    word_count = book.file.word_count if book.file else 0
    language = book.language or (book.file.language if book.file else None) or ""

    def format_language(v: str) -> str:
        key = v.strip().lower().replace("_", "-")
        if key in {"zh", "zh-cn", "zh-hans", "zh-hans-cn"}:
            return "简体中文"
        if key in {"zh-tw", "zh-hk", "zh-hant", "zh-hant-tw", "zh-hant-hk"}:
            return "繁体中文"
        if key in {"en", "en-us", "en-gb"}:
            return "英文"
        return escape_html(v) if v else "未知"

    fmt_display = file_format.upper() if file_format != "未知" else "未知"
    safe_title = escape_html(book.title)
    safe_author = escape_html(book.author or "Unknown")
    safe_description = escape_html(description)
    language_display = format_language(language)
    bot_username = (bot_username or "").lstrip("@")
    title_display = safe_title
    author_display = safe_author
    if bot_username:
        title_link = f"https://t.me/{bot_username}?start=book_{book.id}"
        title_display = f"<a href=\"{escape_html(title_link)}\">{safe_title}</a>"
        author_token = encode_payload(book.author or "")
        if author_token:
            author_link = f"https://t.me/{bot_username}?start=au_{author_token}"
            author_display = f"<a href=\"{escape_html(author_link)}\">{safe_author}</a>"

    lines = [
        f"书名: {title_display}",
        f"作者: {author_display}",
        f"文库: {language_display} | {fmt_display} | {file_size} | {format_word_count(word_count)}字 | {book.rating_count}R | {book.comment_count}评",
        "",
        f"统计: {book.view_count}热度 | {book.download_count}下载 | {book.like_count}点赞 | {book.favorite_count}收藏",
        f"评分: {float(book.rating_score or 0.0):.2f}分 ({int(book.rating_count or 0)}人)",
        f"质量: {float(book.quality_score or 0.0):.2f}分 ({int(book.rating_count or 0)}人)",
        "",
        f"标签: {tags_display}",
        "",
        f"<blockquote>{safe_description}</blockquote>",
        "",
        f"创建: {format_date(book.created_at)}",
        f"更新: {format_date(book.updated_at)}",
        f"上传: {uploader_name}",
    ]
    caption = "\n".join(lines)
    if len(caption) <= 980:
        return caption
    return caption[:980]


async def get_user_context(user_id: int, book_id: int) -> tuple[bool, bool]:
    session_factory = get_session_factory()
    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.id == user_id))
        is_admin = bool(user and user.is_admin)
        fav = await session.scalar(select(Favorite).where(Favorite.user_id == user_id, Favorite.book_id == book_id))
        return is_admin, fav is not None


async def send_book_card(*, bot: Bot, chat_id: int, book_id: int, from_user=None) -> None:
    try:
        book = await asyncio.wait_for(get_book_from_db(book_id), timeout=5)
    except Exception as e:
        logger.warning(f"获取书籍失败: {e}")
        await bot.send_message(chat_id, "当前服务繁忙，请稍后重试")
        return

    if not book or not book.file:
        await bot.send_message(chat_id, "书籍或文件信息不存在")
        return

    file_refs = list(book.file.file_refs) if book.file else []
    primary_ref = pick_primary_file_ref(file_refs)
    backup_ref = pick_backup_ref(file_refs)
    if not primary_ref and not backup_ref:
        await bot.send_message(chat_id, "文件暂不可用")
        return

    caption = build_book_caption(book, bot_username=get_settings().bot_username)

    is_admin = False
    is_fav = False
    if from_user is not None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            user = await session.scalar(select(User).where(User.id == from_user.id))
            if user and user.is_banned:
                await bot.send_message(chat_id, "账号已被限制使用")
                return
            if book.is_vip_only and not (user and user.is_vip):
                await bot.send_message(chat_id, "本书仅会员可获取")
                return
            is_admin = bool(user and user.is_admin)
            fav = await session.scalar(
                select(Favorite).where(Favorite.user_id == from_user.id, Favorite.book_id == book_id)
            )
            is_fav = fav is not None

    keyboard = build_user_book_keyboard(book_id=book_id, is_fav=is_fav, is_admin=is_admin)

    sent = False
    if primary_ref and primary_ref.tg_file_id:
        try:
            await bot.send_document(
                chat_id=chat_id,
                document=primary_ref.tg_file_id,
                caption=caption,
                reply_markup=keyboard,
            )
            sent = True
        except Exception as e:
            logger.warning(f"发送文件失败: {e}")

    if not sent and backup_ref and backup_ref.channel_id and backup_ref.message_id:
        try:
            await bot.copy_message(
                chat_id=chat_id,
                from_chat_id=backup_ref.channel_id,
                message_id=backup_ref.message_id,
                caption=caption,
                reply_markup=keyboard,
            )
            sent = True
        except Exception as e:
            logger.error(f"备份复制失败: {e}")

    if sent and from_user is not None:
        await record_download(
            user_id=from_user.id,
            username=from_user.username,
            first_name=from_user.first_name,
            last_name=from_user.last_name,
            book_id=book_id,
            file_hash=book.file_hash,
        )


async def show_public_booklist(*, bot: Bot, chat_id: int, share_token: str) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        booklist = await get_public_booklist(session, share_token)
        if not booklist:
            await bot.send_message(chat_id, "公开书单不存在或已关闭分享")
            return

        item_lines: list[str] = []
        for idx, item in enumerate(booklist.items[:20], start=1):
            if item.book:
                item_lines.append(f"{idx:02d}. {escape_html(item.book.title)}")
        content = "\n".join(item_lines) if item_lines else "当前书单暂无内容"
        await bot.send_message(
            chat_id,
            f"📚 公开书单：<b>{escape_html(booklist.name)}</b>\n\n{content}",
        )


@book_detail_router.message(F.text & ~F.text.startswith("/"))
async def on_pending_text(message: Message):
    pending = peek_pending_action(message.from_user.id)
    if not pending:
        return

    clear_pending_action(message.from_user.id)
    text = (message.text or "").strip()
    if text.lower() in {"取消", "cancel", "/cancel"}:
        await message.answer("已取消当前操作")
        return

    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            if pending.action == "booklist_create":
                await ensure_user_record(
                    session,
                    user_id=message.from_user.id,
                    username=message.from_user.username,
                    first_name=message.from_user.first_name,
                    last_name=message.from_user.last_name,
                )
                booklist = await create_booklist(session, message.from_user.id, text)
                book_id = int(pending.payload["book_id"])
                await add_book_to_booklist(session, list_id=booklist.id, book_id=book_id, added_by=message.from_user.id)
                await session.commit()
                await message.answer(f"已创建书单《{escape_html(booklist.name)}》并加入当前书籍")
                return

            if pending.action == "booklist_rename":
                row = await rename_booklist(
                    session,
                    user_id=message.from_user.id,
                    list_id=int(pending.payload["list_id"]),
                    new_name=text,
                )
                await session.commit()
                await message.answer(f"书单已重命名为：{escape_html(row.name)}")
                return

            if pending.action == "review_comment":
                book_id = int(pending.payload["book_id"])
                rating = int(pending.payload["rating"])
                await ensure_user_record(
                    session,
                    user_id=message.from_user.id,
                    username=message.from_user.username,
                    first_name=message.from_user.first_name,
                    last_name=message.from_user.last_name,
                )
                comment = None if text in {"-", "跳过", "无"} else text
                await upsert_review(
                    session,
                    user_id=message.from_user.id,
                    book_id=book_id,
                    rating=rating,
                    comment=comment,
                )
                await session.commit()
                await sync_book_to_search(session, book_id=book_id)
                await message.answer("评价已保存")
                return

            if pending.action == "tag_apply":
                book_id = int(pending.payload["book_id"])
                await ensure_user_record(
                    session,
                    user_id=message.from_user.id,
                    username=message.from_user.username,
                    first_name=message.from_user.first_name,
                    last_name=message.from_user.last_name,
                )
                row = await submit_tag_application(
                    session,
                    user_id=message.from_user.id,
                    book_id=book_id,
                    tag_name=text,
                )
                await session.commit()
                await message.answer(f"标签申请已提交：#{escape_html(row.tag_name)}")
                return

            if pending.action == "admin_edit":
                book_id = int(pending.payload["book_id"])
                field_name = str(pending.payload["field_name"])
                user = await session.scalar(select(User).where(User.id == message.from_user.id))
                if not user or not user.is_admin:
                    await message.answer("仅管理员可执行该操作")
                    return
                await edit_book_field(
                    session,
                    book_id=book_id,
                    editor_id=message.from_user.id,
                    field_name=field_name,
                    raw_value=text,
                )
                await session.commit()
                await sync_book_to_search(session, book_id=book_id)
                await message.answer("书籍信息已更新")
                return
        except ValueError as e:
            await session.rollback()
            await message.answer(f"⚠️ {escape_html(str(e))}")
            return
        except IntegrityError:
            await session.rollback()
            await message.answer("⚠️ 数据冲突，请重试")
            return
        except Exception as e:
            await session.rollback()
            logger.error(f"处理待输入操作失败: {e}", exc_info=True)
            await message.answer("操作失败，请稍后重试")
            return


@book_detail_router.callback_query(F.data.startswith("book:"))
async def on_book_callback(callback: CallbackQuery):
    data = callback.data or ""
    action = data.replace("book:", "", 1)

    try:
        if action.startswith("detail:"):
            await show_book_detail(callback, int(action.split(":")[1]))
        elif action.startswith("download:"):
            await handle_download(callback, int(action.split(":")[1]))
        elif action.startswith("restore:"):
            await restore_keyboard(callback, int(action.split(":")[1]))
        elif action.startswith("fav:"):
            await handle_favorite(callback, int(action.split(":")[1]))
        elif action.startswith("booklist:"):
            await handle_booklist_callback(callback, action)
        elif action.startswith("review:"):
            await handle_review_callback(callback, action)
        elif action.startswith("similar:"):
            _, _, book_id, page = action.split(":")
            await show_similar_books(callback, int(book_id), int(page))
        elif action.startswith("tagadd:"):
            await prompt_tag_application(callback, int(action.split(":")[1]))
        elif action.startswith("more:"):
            await show_more_menu(callback, int(action.split(":")[1]))
        elif action.startswith("share:"):
            await handle_share_book(callback, int(action.split(":")[1]))
        elif action.startswith("admin_edit:"):
            await show_admin_edit_menu(callback, int(action.split(":")[1]))
        elif action.startswith("admin_edit_field:"):
            _, _, book_id, field_name = action.split(":")
            await prompt_admin_edit(callback, int(book_id), field_name)
        elif action.startswith("admin_history:"):
            await show_admin_history(callback, int(action.split(":")[1]))
        elif action.startswith("admin_tag_queue:"):
            await show_admin_tag_queue(callback, int(action.split(":")[1]))
        elif action.startswith("admin_tag_approve:"):
            _, _, book_id, application_id = action.split(":")
            await handle_admin_tag_review(callback, int(book_id), int(application_id), True)
        elif action.startswith("admin_tag_reject:"):
            _, _, book_id, application_id = action.split(":")
            await handle_admin_tag_review(callback, int(book_id), int(application_id), False)
        elif action.startswith("admin_tag_remove:"):
            _, _, book_id, tag_id = action.split(":")
            await handle_admin_tag_remove(callback, int(book_id), int(tag_id))
        elif action.startswith("report:"):
            await handle_report(callback, int(action.split(":")[1]))
        elif action == "channel":
            await callback.answer("@BookFather", show_alert=True)
        elif action == "group":
            await callback.answer("群组入口暂未配置", show_alert=True)
        elif action == "feedback":
            await callback.answer("请私聊反馈给管理员", show_alert=True)
        else:
            await callback.answer("未知操作", show_alert=True)
    except Exception as e:
        logger.error(f"处理书籍回调失败: {e}", exc_info=True)
        await callback.answer("操作失败，请重试", show_alert=True)


async def show_book_detail(callback: CallbackQuery, book_id: int):
    await send_book_card(
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        book_id=book_id,
        from_user=callback.from_user,
    )
    await callback.answer()


async def restore_keyboard(callback: CallbackQuery, book_id: int) -> None:
    is_admin, is_fav = await get_user_context(callback.from_user.id, book_id)
    try:
        await callback.message.edit_reply_markup(
            reply_markup=build_user_book_keyboard(book_id=book_id, is_fav=is_fav, is_admin=is_admin)
        )
    except TelegramBadRequest:
        pass
    await callback.answer()


async def handle_download(callback: CallbackQuery, book_id: int):
    await send_book_card(
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        book_id=book_id,
        from_user=callback.from_user,
    )
    await callback.answer("已发送")


async def handle_favorite(callback: CallbackQuery, book_id: int):
    session_factory = get_session_factory()
    async with session_factory() as session:
        user = await ensure_user_record(
            session,
            user_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
            last_name=callback.from_user.last_name,
        )
        if user.is_banned:
            await callback.answer("账号已被限制使用", show_alert=True)
            return

        fav = await session.scalar(
            select(Favorite).where(Favorite.user_id == user.id, Favorite.book_id == book_id)
        )
        book = await session.scalar(select(Book).where(Book.id == book_id))
        if not book:
            await callback.answer("书籍不存在", show_alert=True)
            return

        if fav:
            await session.delete(fav)
            await session.execute(
                update(Book).where(Book.id == book_id, Book.favorite_count > 0).values(
                    favorite_count=Book.favorite_count - 1
                )
            )
            await session.commit()
            try:
                await callback.message.edit_reply_markup(
                    reply_markup=build_user_book_keyboard(book_id=book_id, is_fav=False, is_admin=bool(user.is_admin))
                )
            except Exception:
                pass
            await callback.answer("已取消收藏")
            return

        try:
            session.add(Favorite(user_id=user.id, book_id=book_id))
            await session.execute(
                update(Book).where(Book.id == book_id).values(favorite_count=Book.favorite_count + 1)
            )
            await session.commit()
        except IntegrityError:
            await session.rollback()

    try:
        await callback.message.edit_reply_markup(
            reply_markup=build_user_book_keyboard(book_id=book_id, is_fav=True, is_admin=bool(user.is_admin))
        )
    except Exception:
        pass
    await callback.answer("已加入收藏")


async def get_booklist_selection(session, user_id: int, book_id: int) -> tuple[list[BookList], set[int]]:
    booklists = await list_user_booklists(session, user_id)
    selected_ids: set[int] = set()
    for row in booklists:
        for item in row.items or []:
            if item.book_id == book_id:
                selected_ids.add(row.id)
                break
    return booklists, selected_ids


async def handle_booklist_callback(callback: CallbackQuery, action: str) -> None:
    parts = action.split(":")
    mode = parts[1]

    if mode == "overview":
        await show_booklist_overview(callback, int(parts[2]))
        return
    if mode == "new":
        book_id = int(parts[2])
        set_pending_action(callback.from_user.id, "booklist_create", book_id=book_id)
        await callback.answer()
        await callback.message.answer("请输入新书单名称，10分钟内有效。发送“取消”可放弃。")
        return
    if mode == "toggle":
        _, _, book_id_raw, list_id_raw = parts
        await toggle_book_in_booklist(callback, int(book_id_raw), int(list_id_raw))
        return
    if mode == "view":
        _, _, book_id_raw, list_id_raw = parts
        await show_single_booklist(callback, int(book_id_raw), int(list_id_raw))
        return
    if mode == "rename":
        _, _, book_id_raw, list_id_raw = parts
        set_pending_action(callback.from_user.id, "booklist_rename", book_id=int(book_id_raw), list_id=int(list_id_raw))
        await callback.answer()
        await callback.message.answer("请输入新的书单名称，10分钟内有效。发送“取消”可放弃。")
        return
    if mode == "delete":
        _, _, book_id_raw, list_id_raw = parts
        await delete_single_booklist(callback, int(book_id_raw), int(list_id_raw))
        return
    if mode == "share":
        _, _, book_id_raw, list_id_raw = parts
        await toggle_single_booklist_share(callback, int(book_id_raw), int(list_id_raw))
        return

    await show_booklist_menu(callback, int(parts[2]))


async def show_booklist_menu(callback: CallbackQuery, book_id: int) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        await ensure_user_record(
            session,
            user_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
            last_name=callback.from_user.last_name,
        )
        booklists, selected_ids = await get_booklist_selection(session, callback.from_user.id, book_id)
        await session.commit()
    try:
        await callback.message.edit_reply_markup(
            reply_markup=build_booklist_keyboard(book_id=book_id, booklists=booklists, selected_ids=selected_ids)
        )
    except TelegramBadRequest:
        pass
    await callback.answer()


async def toggle_book_in_booklist(callback: CallbackQuery, book_id: int, list_id: int) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        await ensure_user_record(
            session,
            user_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
            last_name=callback.from_user.last_name,
        )
        booklist = await session.scalar(select(BookList).where(BookList.id == list_id, BookList.user_id == callback.from_user.id))
        if not booklist:
            await callback.answer("书单不存在", show_alert=True)
            return
        removed = await remove_book_from_booklist(session, list_id=list_id, book_id=book_id)
        if removed:
            await session.commit()
            result_message = "已从书单移除"
        else:
            await add_book_to_booklist(session, list_id=list_id, book_id=book_id, added_by=callback.from_user.id)
            await session.commit()
            result_message = "已加入书单"
        booklists, selected_ids = await get_booklist_selection(session, callback.from_user.id, book_id)
    try:
        await callback.message.edit_reply_markup(
            reply_markup=build_booklist_keyboard(book_id=book_id, booklists=booklists, selected_ids=selected_ids)
        )
    except TelegramBadRequest:
        pass
    await callback.answer(result_message)


async def show_booklist_overview(callback: CallbackQuery, book_id: int) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        await ensure_user_record(
            session,
            user_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
            last_name=callback.from_user.last_name,
        )
        booklists = await list_user_booklists(session, callback.from_user.id)
        lines = ["📚 <b>我的书单</b>"]
        for row in booklists:
            public_text = "公开" if row.is_public else "私有"
            lines.append(f"• {escape_html(row.name)} - {len(row.items or [])} 本 - {public_text}")
        await callback.message.answer(
            "\n".join(lines),
            reply_markup=build_booklist_overview_keyboard(book_id=book_id, booklists=booklists),
        )
    await callback.answer()


async def show_single_booklist(callback: CallbackQuery, book_id: int, list_id: int) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        booklist = await session.scalar(
            select(BookList)
            .where(BookList.id == list_id, BookList.user_id == callback.from_user.id)
            .options(selectinload(BookList.items))
        )
        if not booklist:
            await callback.answer("书单不存在", show_alert=True)
            return
        title_lines = [f"📚 <b>{escape_html(booklist.name)}</b>"]
        for idx, item in enumerate(booklist.items[:20], start=1):
            book = await session.scalar(select(Book).where(Book.id == item.book_id))
            if book:
                title_lines.append(f"{idx:02d}. {escape_html(book.title)}")
        if len(title_lines) == 1:
            title_lines.append("当前书单暂无内容")
        if booklist.is_public and booklist.share_token:
            username = get_settings().bot_username.lstrip("@")
            title_lines.append(f"\n分享链接: https://t.me/{username}?start=list_{booklist.share_token}")
        await callback.message.answer(
            "\n".join(title_lines),
            reply_markup=build_single_booklist_manage_keyboard(
                book_id=book_id,
                list_id=list_id,
                is_default=bool(booklist.is_default),
            ),
        )
    await callback.answer()


async def toggle_single_booklist_share(callback: CallbackQuery, book_id: int, list_id: int) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        row = await toggle_booklist_public(session, user_id=callback.from_user.id, list_id=list_id)
        await session.commit()
        if row.is_public and row.share_token:
            username = get_settings().bot_username.lstrip("@")
            message = f"书单已公开分享： https://t.me/{username}?start=list_{row.share_token}"
        else:
            message = "书单已关闭公开分享"
    await callback.message.answer(message)
    await show_single_booklist(callback, book_id, list_id)


async def delete_single_booklist(callback: CallbackQuery, book_id: int, list_id: int) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        await delete_booklist(session, user_id=callback.from_user.id, list_id=list_id)
        await session.commit()
    await callback.message.answer("书单已删除")
    await show_booklist_overview(callback, book_id)


async def handle_review_callback(callback: CallbackQuery, action: str) -> None:
    parts = action.split(":")
    mode = parts[1]
    book_id = int(parts[2])

    if mode == "review":
        await show_review_menu(callback, book_id)
        return
    if mode == "review_rate":
        rating = int(parts[3])
        set_pending_action(callback.from_user.id, "review_comment", book_id=book_id, rating=rating)
        await callback.answer()
        await callback.message.answer(
            f"你选择了 {rating} 星，请发送短评内容。\n发送 “-” 表示只评分不写短评，发送“取消”可放弃。"
        )
        return
    if mode == "review_list":
        await show_review_list(callback, book_id, int(parts[3]))
        return


async def show_review_menu(callback: CallbackQuery, book_id: int) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        await ensure_user_record(
            session,
            user_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
            last_name=callback.from_user.last_name,
        )
        existing = await session.scalar(
            select(BookReview).where(BookReview.user_id == callback.from_user.id, BookReview.book_id == book_id)
        )
    await callback.message.answer(
        "请选择评分星级：",
        reply_markup=build_review_rating_keyboard(
            book_id=book_id,
            current_rating=int(existing.rating) if existing else None,
        ),
    )
    await callback.answer()


async def show_review_list(callback: CallbackQuery, book_id: int, page: int) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        rows, total = await get_recent_reviews(session, book_id=book_id, page=page, per_page=5)
        lines = ["📝 <b>最近短评</b>"]
        if not rows:
            lines.append("暂无短评，欢迎成为第一个评价的人。")
        for row in rows:
            lines.append(f"• {row.rating}星 - {escape_html((row.comment or '').strip())}")
        await callback.message.answer(
            "\n".join(lines),
            reply_markup=build_review_list_keyboard(book_id=book_id, page=page, total=total),
        )
    await callback.answer()


async def prompt_tag_application(callback: CallbackQuery, book_id: int) -> None:
    set_pending_action(callback.from_user.id, "tag_apply", book_id=book_id)
    await callback.answer()
    await callback.message.answer("请输入要申请的标签名称，10分钟内有效。发送“取消”可放弃。")


async def show_similar_books(callback: CallbackQuery, book_id: int, page: int) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await get_similar_books(session, book_id=book_id, page=page, per_page=5)
    tags = f"标签命中：{', '.join(result.tag_names[:5])}" if result.tag_names else "标签不足，已回退作者/热门推荐"
    text = f"🔎 <b>相似推荐</b>\n{tags}\n共找到 {result.total} 条候选"
    await callback.message.answer(
        text,
        reply_markup=build_similar_keyboard(book_id=book_id, page=page, result=result),
    )
    await callback.answer()


async def show_more_menu(callback: CallbackQuery, book_id: int) -> None:
    is_admin, _ = await get_user_context(callback.from_user.id, book_id)
    try:
        await callback.message.edit_reply_markup(reply_markup=build_more_keyboard(book_id=book_id, is_admin=is_admin))
    except TelegramBadRequest:
        pass
    await callback.answer()


async def handle_share_book(callback: CallbackQuery, book_id: int) -> None:
    username = get_settings().bot_username.lstrip("@")
    if not username:
        await callback.answer("当前未配置 Bot 用户名", show_alert=True)
        return
    await callback.answer(f"https://t.me/{username}?start=book_{book_id}", show_alert=True)


async def ensure_admin(callback: CallbackQuery) -> bool:
    session_factory = get_session_factory()
    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.id == callback.from_user.id))
        return bool(user and user.is_admin)


async def show_admin_edit_menu(callback: CallbackQuery, book_id: int) -> None:
    if not await ensure_admin(callback):
        await callback.answer("仅管理员可执行该操作", show_alert=True)
        return
    await callback.message.answer("请选择要编辑的字段：", reply_markup=build_admin_edit_keyboard(book_id=book_id))
    await callback.answer()


async def prompt_admin_edit(callback: CallbackQuery, book_id: int, field_name: str) -> None:
    if not await ensure_admin(callback):
        await callback.answer("仅管理员可执行该操作", show_alert=True)
        return
    field_cn = {
        "title": "标题",
        "author": "作者",
        "description": "简介",
        "is_18plus": "成人分级(是/否)",
        "is_vip_only": "VIP标记(是/否)",
    }.get(field_name, field_name)
    set_pending_action(callback.from_user.id, "admin_edit", book_id=book_id, field_name=field_name)
    await callback.answer()
    await callback.message.answer(f"请输入新的{field_cn}，10分钟内有效。发送“取消”可放弃。")


async def show_admin_history(callback: CallbackQuery, book_id: int) -> None:
    if not await ensure_admin(callback):
        await callback.answer("仅管理员可执行该操作", show_alert=True)
        return
    session_factory = get_session_factory()
    async with session_factory() as session:
        rows = await get_book_edit_history(session, book_id=book_id, limit=10)
    lines = ["🕘 <b>最近编辑历史</b>"]
    if not rows:
        lines.append("暂无编辑记录")
    for row in rows:
        lines.append(
            f"• {escape_html(row.field_name)}: {escape_html(row.old_value or '')} -> {escape_html(row.new_value or '')}"
        )
    await callback.message.answer("\n".join(lines), reply_markup=build_admin_edit_keyboard(book_id=book_id))
    await callback.answer()


async def show_admin_tag_queue(callback: CallbackQuery, book_id: int) -> None:
    if not await ensure_admin(callback):
        await callback.answer("仅管理员可执行该操作", show_alert=True)
        return
    session_factory = get_session_factory()
    async with session_factory() as session:
        book = await session.scalar(
            select(Book)
            .where(Book.id == book_id)
            .options(selectinload(Book.book_tags).selectinload(BookTag.tag))
        )
        items = (
            await session.execute(
                select(TagApplication)
                .where(TagApplication.book_id == book_id, TagApplication.status == "pending")
                .order_by(TagApplication.created_at.asc())
                .limit(10)
            )
        ).scalars().all()
    lines = ["🏷️ <b>标签审核队列</b>"]
    if not items:
        lines.append("当前没有待审核标签。")
    else:
        for row in items:
            lines.append(f"• #{escape_html(row.tag_name)} - 用户 {row.user_id}")
    current_tags = []
    if book:
        current_tags = [
            (bt.tag_id, bt.tag.name)
            for bt in (book.book_tags or [])
            if bt.tag and bt.tag.name
        ]
        if current_tags:
            lines.append("")
            lines.append("当前已生效标签：")
            for _, tag_name in current_tags:
                lines.append(f"• #{escape_html(tag_name)}")
    await callback.message.answer(
        "\n".join(lines),
        reply_markup=build_admin_tag_queue_keyboard(book_id=book_id, items=list(items), current_tags=current_tags),
    )
    await callback.answer()


async def handle_admin_tag_review(callback: CallbackQuery, book_id: int, application_id: int, approve: bool) -> None:
    if not await ensure_admin(callback):
        await callback.answer("仅管理员可执行该操作", show_alert=True)
        return
    session_factory = get_session_factory()
    async with session_factory() as session:
        await review_tag_application(
            session,
            application_id=application_id,
            admin_id=callback.from_user.id,
            approve=approve,
        )
        await session.commit()
        await sync_book_to_search(session, book_id=book_id)
    await callback.message.answer("已处理标签申请")
    await show_admin_tag_queue(callback, book_id)


async def handle_admin_tag_remove(callback: CallbackQuery, book_id: int, tag_id: int) -> None:
    if not await ensure_admin(callback):
        await callback.answer("仅管理员可执行该操作", show_alert=True)
        return
    session_factory = get_session_factory()
    async with session_factory() as session:
        await remove_tag_from_book(session, book_id=book_id, tag_id=tag_id, admin_id=callback.from_user.id)
        await session.commit()
        await sync_book_to_search(session, book_id=book_id)
    await callback.message.answer("标签已移除")


async def record_download(
    *,
    user_id: int,
    username: Optional[str],
    first_name: str,
    last_name: Optional[str],
    book_id: int,
    file_hash: str,
) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        user = await ensure_user_record(
            session,
            user_id=user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
        )
        book = await session.scalar(select(Book).where(Book.id == book_id))
        if book:
            book.download_count += 1
        user.download_count += 1
        session.add(
            DownloadLog(
                user_id=user_id,
                book_id=book_id,
                file_hash=file_hash,
                cost_coins=0,
                is_free=True,
            )
        )
        await session.commit()


async def handle_report(callback: CallbackQuery, book_id: int):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="侵权/色情", callback_data=f"report:{book_id}:infringement")],
            [InlineKeyboardButton(text="政治敏感", callback_data=f"report:{book_id}:political")],
            [InlineKeyboardButton(text="垃圾内容", callback_data=f"report:{book_id}:spam")],
            [InlineKeyboardButton(text="返回详情", callback_data=f"book:restore:{book_id}")],
        ]
    )
    await callback.message.answer("请选择举报原因：", reply_markup=keyboard)
    await callback.answer()


@book_detail_router.callback_query(F.data.startswith("report:"))
async def on_report_reason(callback: CallbackQuery):
    parts = (callback.data or "").split(":", 2)
    if len(parts) != 3:
        await callback.answer("无效的举报数据", show_alert=True)
        return
    _, book_id_raw, reason = parts
    try:
        book_id = int(book_id_raw)
    except ValueError:
        await callback.answer("无效的书籍ID", show_alert=True)
        return

    logger.warning(f"收到举报: book_id={book_id} reason={reason} from_user={callback.from_user.id}")
    await callback.answer("已收到举报", show_alert=True)
