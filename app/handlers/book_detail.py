# -*- coding: utf-8 -*-
"""
搜书神器 V2 - 书籍详情处理器 (重构版)
处理书籍详情展示、收藏、下载等操作

关键改进:
1. 书籍详情消息包含实际的文件附件
2. 文件通过 send_document 直接发送
3. 备份服务集成，确保文件可恢复
"""

import asyncio

from typing import Optional
from datetime import datetime

from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

from app.core.config import get_settings
from app.core.logger import logger
from app.core.database import get_session_factory
from app.core.deeplink import encode_payload
from app.core.text import escape_html
from app.core.models import Book, File, FileRef, BookTag, Tag, User, Favorite, DownloadLog
from sqlalchemy import select, update, func
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError

book_detail_router = Router(name="book_detail")

def format_size(size_bytes: int) -> str:
    """格式化文件大小"""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        kb = round(size_bytes / 1024, 1)
        return f"{int(kb)}KB" if float(kb).is_integer() else f"{kb:.1f}KB"
    elif size_bytes < 1024 * 1024 * 1024:
        mb = round(size_bytes / (1024 * 1024), 1)
        return f"{int(mb)}MB" if float(mb).is_integer() else f"{mb:.1f}MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f}GB"


def format_date(dt: Optional[datetime]) -> str:
    """格式化日期"""
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


def build_user_book_keyboard(*, book_id: int, is_fav: bool) -> InlineKeyboardMarkup:
    fav_text = "💚收藏" if is_fav else "🤍收藏"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=fav_text, callback_data=f"book:fav:{book_id}"),
                InlineKeyboardButton(text="+书单", callback_data=f"book:booklist:{book_id}"),
                InlineKeyboardButton(text="💬评价", callback_data=f"book:review:{book_id}"),
            ],
            [
                InlineKeyboardButton(text="+加标签", callback_data=f"book:tagadd:{book_id}"),
                InlineKeyboardButton(text="💡我相似", callback_data=f"book:similar:{book_id}"),
                InlineKeyboardButton(text="...更多", callback_data=f"book:more:{book_id}"),
            ],
        ]
    )


def build_booklist_keyboard(*, book_id: int, count: int, selected: bool) -> InlineKeyboardMarkup:
    item_text = f"{'✅' if selected else ''}[{count}本] 我喜欢的书籍"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="++新建", callback_data=f"book:booklist_new:{book_id}"),
                InlineKeyboardButton(text="<返回", callback_data=f"book:booklist_back:{book_id}"),
            ],
            [InlineKeyboardButton(text=item_text, callback_data=f"book:booklist_sel:{book_id}")],
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
        f"文库: {language_display} | {fmt_display} | {file_size} | {format_word_count(word_count)}字 | {book.rating_count}R | {book.comment_count}笔",
        "",
        f"统计: {book.view_count}热度 | {book.download_count}下载 | {book.like_count}点赞 | {book.favorite_count}收藏",
        f"评分: {float(book.rating_score or 0.0):.2f}分({int(book.rating_count or 0)}人)",
        f"质量: {float(book.quality_score or 0.0):.2f}分({int(book.rating_count or 0)}人)",
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

    compact = [line for line in lines if line != description]
    caption = "\n".join(compact)
    return caption[:980]


async def send_book_card(
    *,
    bot: Bot,
    chat_id: int,
    book_id: int,
    from_user=None,
) -> None:
    try:
        book = await asyncio.wait_for(get_book_from_db(book_id), timeout=5)
    except Exception as e:
        logger.warning(f"获取书籍失败: {e}")
        await bot.send_message(chat_id, "❌ 当前服务繁忙，请稍后重试")
        return

    if not book or not book.file:
        await bot.send_message(chat_id, "❌ 书籍或文件信息不存在")
        return

    file_refs = list(book.file.file_refs) if book.file else []
    primary_ref = pick_primary_file_ref(file_refs)
    backup_ref = pick_backup_ref(file_refs)

    if not primary_ref and not backup_ref:
        await bot.send_message(chat_id, "❌ 文件暂不可用")
        return

    caption = build_book_caption(book, bot_username=get_settings().bot_username)

    is_admin = False
    is_fav = False
    if from_user is not None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            u = await session.scalar(select(User).where(User.id == from_user.id))
            if u and u.is_banned:
                await bot.send_message(chat_id, "❌ 账号已被限制使用")
                return
            if book.is_vip_only and not (u and u.is_vip):
                await bot.send_message(chat_id, "🔒 本书仅会员可获取")
                return
            is_admin = bool(u and u.is_admin)
            fav = await session.scalar(
                select(Favorite).where(
                    Favorite.user_id == from_user.id,
                    Favorite.book_id == book_id,
                )
            )
            is_fav = fav is not None

    if is_admin:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="频道", callback_data="book:channel"),
                InlineKeyboardButton(text="群组", callback_data="book:group"),
                InlineKeyboardButton(text="反馈", callback_data="book:feedback"),
                InlineKeyboardButton(text="捐赠", callback_data="book:donate"),
            ],
            [
                InlineKeyboardButton(text="删除标签", callback_data=f"book:tagdel:{book_id}"),
                InlineKeyboardButton(text="举报书籍", callback_data=f"book:report:{book_id}"),
                InlineKeyboardButton(text="编辑书籍", callback_data=f"book:edit:{book_id}"),
            ],
            [
                InlineKeyboardButton(text="编辑历史", callback_data=f"book:history:{book_id}"),
                InlineKeyboardButton(text="❌关闭", callback_data="close"),
                InlineKeyboardButton(text="◀️返回", callback_data="close"),
            ],
        ])
    else:
        keyboard = build_user_book_keyboard(book_id=book_id, is_fav=is_fav)

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
        except TypeError:
            try:
                await bot.forward_message(
                    chat_id=chat_id,
                    from_chat_id=backup_ref.channel_id,
                    message_id=backup_ref.message_id,
                )
                await bot.send_message(chat_id=chat_id, text=caption, reply_markup=keyboard)
                sent = True
            except Exception as e:
                logger.error(f"从备份转发失败: {e}")
        except Exception as e:
            logger.error(f"从备份复制失败: {e}")

    if sent and from_user is not None:
        await record_download(
            user_id=from_user.id,
            username=from_user.username,
            first_name=from_user.first_name,
            last_name=from_user.last_name,
            book_id=book_id,
            file_hash=book.file_hash,
        )


@book_detail_router.callback_query(F.data.startswith("book:"))
async def on_book_callback(callback: CallbackQuery):
    """处理书籍相关的回调"""
    data = callback.data
    action = data.replace("book:", "")

    try:
        if action.startswith("detail:"):
            book_id = int(action.replace("detail:", ""))
            await show_book_detail(callback, book_id)
        elif action.startswith("download:"):
            book_id = int(action.replace("download:", ""))
            await handle_download(callback, book_id)
        elif action.startswith("fav:"):
            book_id = int(action.replace("fav:", ""))
            await handle_favorite(callback, book_id)
        elif action.startswith("booklist:"):
            book_id = int(action.replace("booklist:", ""))
            await show_booklist_menu(callback, book_id)
        elif action.startswith("booklist_back:"):
            book_id = int(action.replace("booklist_back:", ""))
            await hide_booklist_menu(callback, book_id)
        elif action.startswith("booklist_new:"):
            await callback.answer("功能开发中...", show_alert=True)
        elif action.startswith("booklist_sel:"):
            book_id = int(action.replace("booklist_sel:", ""))
            await handle_booklist_select(callback, book_id)
        elif action.startswith("report:"):
            book_id = int(action.replace("report:", ""))
            await handle_report(callback, book_id)
        elif action.startswith("tagdel:"):
            await callback.answer("功能开发中...", show_alert=True)
        elif action.startswith("tagadd:"):
            await callback.answer("功能开发中...", show_alert=True)
        elif action.startswith("similar:"):
            await callback.answer("功能开发中...", show_alert=True)
        elif action.startswith("more:"):
            await callback.answer("功能开发中...", show_alert=True)
        elif action.startswith("history:"):
            await callback.answer("功能开发中...", show_alert=True)
        elif action.startswith("edit:"):
            await callback.answer("功能开发中...", show_alert=True)
        elif action.startswith("review:"):
            await callback.answer("功能开发中...", show_alert=True)
        elif action.startswith("share:"):
            await callback.answer("功能开发中...", show_alert=True)
        elif action == "channel":
            await callback.answer("@BookFather", show_alert=True)
        elif action == "group":
            await callback.answer("群组入口暂未配置", show_alert=True)
        elif action == "feedback":
            await callback.answer("请私聊反馈给管理员", show_alert=True)
        elif action == "donate":
            await callback.answer("功能开发中...", show_alert=True)
        else:
            await callback.answer("⚠️ 未知的操作")
    except Exception as e:
        logger.error(f"处理书籍回调失败: {e}", exc_info=True)
        await callback.answer("❌ 操作失败，请重试")


async def show_book_detail(callback: CallbackQuery, book_id: int):
    await send_book_card(
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        book_id=book_id,
        from_user=callback.from_user,
    )
    await callback.answer()


async def handle_download(callback: CallbackQuery, book_id: int):
    """处理下载请求"""
    await send_book_card(
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        book_id=book_id,
        from_user=callback.from_user,
    )
    await callback.answer("✅ 已发送")


async def handle_favorite(callback: CallbackQuery, book_id: int):
    """处理收藏请求"""
    session_factory = get_session_factory()
    async with session_factory() as session:
        stmt = select(User).where(User.id == callback.from_user.id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            user = User(
                id=callback.from_user.id,
                username=callback.from_user.username,
                first_name=callback.from_user.first_name,
                last_name=callback.from_user.last_name,
                coins=0,
                upload_count=0,
                download_count=0,
                search_count=0,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
        if user.is_banned:
            await callback.answer("❌ 账号已被限制使用", show_alert=True)
            return

        stmt = select(Favorite).where(
            Favorite.user_id == user.id,
            Favorite.book_id == book_id,
        )
        result = await session.execute(stmt)
        fav = result.scalar_one_or_none()

        stmt = select(Book).where(Book.id == book_id)
        result = await session.execute(stmt)
        book = result.scalar_one_or_none()
        if not book:
            await callback.answer("❌ 书籍不存在", show_alert=True)
            return

        if fav:
            await session.delete(fav)
            await session.execute(
                update(Book)
                .where(Book.id == book_id, Book.favorite_count > 0)
                .values(favorite_count=Book.favorite_count - 1)
            )
            await session.commit()
            try:
                await callback.message.edit_reply_markup(
                    reply_markup=build_user_book_keyboard(book_id=book_id, is_fav=False)
                )
            except Exception:
                pass
            await callback.answer("已取消收藏")
            return

        try:
            session.add(Favorite(user_id=user.id, book_id=book_id))
            await session.execute(
                update(Book)
                .where(Book.id == book_id)
                .values(favorite_count=Book.favorite_count + 1)
            )
            await session.commit()
        except IntegrityError:
            await session.rollback()
            try:
                await callback.message.edit_reply_markup(
                    reply_markup=build_user_book_keyboard(book_id=book_id, is_fav=True)
                )
            except Exception:
                pass
            await callback.answer("已添加到我喜欢的书籍")
            return

    try:
        await callback.message.edit_reply_markup(
            reply_markup=build_user_book_keyboard(book_id=book_id, is_fav=True)
        )
    except Exception:
        pass
    await callback.answer("已添加到我喜欢的书籍")


async def show_booklist_menu(callback: CallbackQuery, book_id: int) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        fav = await session.scalar(
            select(Favorite).where(
                Favorite.user_id == callback.from_user.id,
                Favorite.book_id == book_id,
            )
        )
        fav_count = await session.scalar(
            select(func.count()).select_from(Favorite).where(Favorite.user_id == callback.from_user.id)
        )
        count = int(fav_count or 0)
        is_selected = fav is not None

    try:
        await callback.message.edit_reply_markup(
            reply_markup=build_booklist_keyboard(book_id=book_id, count=count, selected=is_selected)
        )
    except TelegramBadRequest:
        pass
    await callback.answer()


async def hide_booklist_menu(callback: CallbackQuery, book_id: int) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        fav = await session.scalar(
            select(Favorite).where(
                Favorite.user_id == callback.from_user.id,
                Favorite.book_id == book_id,
            )
        )
    try:
        await callback.message.edit_reply_markup(
            reply_markup=build_user_book_keyboard(book_id=book_id, is_fav=fav is not None)
        )
    except TelegramBadRequest:
        pass
    await callback.answer()


async def handle_booklist_select(callback: CallbackQuery, book_id: int) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.id == callback.from_user.id))
        if not user:
            user = User(
                id=callback.from_user.id,
                username=callback.from_user.username,
                first_name=callback.from_user.first_name,
                last_name=callback.from_user.last_name,
                coins=0,
                upload_count=0,
                download_count=0,
                search_count=0,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
        if user.is_banned:
            await callback.answer("❌ 账号已被限制使用", show_alert=True)
            return

        fav = await session.scalar(
            select(Favorite).where(
                Favorite.user_id == callback.from_user.id,
                Favorite.book_id == book_id,
            )
        )
        if fav is not None:
            await callback.answer("已添加到我喜欢的书籍")
            return

        try:
            session.add(Favorite(user_id=callback.from_user.id, book_id=book_id))
            await session.execute(
                update(Book)
                .where(Book.id == book_id)
                .values(favorite_count=Book.favorite_count + 1)
            )
            await session.commit()
        except IntegrityError:
            await session.rollback()

        fav_count = await session.scalar(
            select(func.count()).select_from(Favorite).where(Favorite.user_id == callback.from_user.id)
        )
        count = int(fav_count or 0)

    try:
        await callback.message.edit_reply_markup(
            reply_markup=build_booklist_keyboard(book_id=book_id, count=count, selected=True)
        )
    except TelegramBadRequest:
        pass
    await callback.answer("已添加到我喜欢的书籍")


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
        stmt = select(User).where(User.id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            user = User(
                id=user_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                coins=0,
                upload_count=0,
                download_count=0,
                search_count=0,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

        stmt = select(Book).where(Book.id == book_id)
        result = await session.execute(stmt)
        book = result.scalar_one_or_none()
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
    """处理举报请求"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🚫 侵权/色情",
                callback_data=f"report:{book_id}:infringement"
            ),
        ],
        [
            InlineKeyboardButton(
                text="📛 政治敏感",
                callback_data=f"report:{book_id}:political"
            ),
        ],
        [
            InlineKeyboardButton(
                text="🗑️ 垃圾内容",
                callback_data=f"report:{book_id}:spam"
            ),
        ],
        [
            InlineKeyboardButton(text="❌ 取消", callback_data=f"book:detail:{book_id}"),
        ],
    ])

    await callback.message.answer(
        "⚠️ <b>举报书籍</b>\n\n"
        "请选择举报原因:",
        reply_markup=keyboard
    )
    await callback.answer()

@book_detail_router.callback_query(F.data.startswith("report:"))
async def on_report_reason(callback: CallbackQuery):
    parts = (callback.data or "").split(":", 2)
    if len(parts) != 3:
        await callback.answer("⚠️ 无效的举报数据", show_alert=True)
        return
    _, book_id_raw, reason = parts
    try:
        book_id = int(book_id_raw)
    except ValueError:
        await callback.answer("⚠️ 无效的书籍ID", show_alert=True)
        return

    logger.warning(
        f"收到举报: book_id={book_id} reason={reason} from_user={callback.from_user.id}"
    )
    await callback.answer("✅ 已收到举报", show_alert=True)
