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
from aiogram.exceptions import TelegramBadRequest

from app.core.logger import logger
from app.core.database import get_session_factory
from app.core.models import Book, File, FileRef, BookTag, Tag, User, Favorite, DownloadLog
from sqlalchemy import select
from sqlalchemy.orm import selectinload

book_detail_router = Router(name="book_detail")

def format_size(size_bytes: int) -> str:
    """格式化文件大小"""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f}MB"
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
        elif action.startswith("report:"):
            book_id = int(action.replace("report:", ""))
            await handle_report(callback, book_id)
        elif action.startswith("review:"):
            await callback.answer("功能开发中...", show_alert=True)
        elif action.startswith("share:"):
            await callback.answer("功能开发中...", show_alert=True)
        else:
            await callback.answer("⚠️ 未知的操作")
    except Exception as e:
        logger.error(f"处理书籍回调失败: {e}", exc_info=True)
        await callback.answer("❌ 操作失败，请重试")


async def show_book_detail(callback: CallbackQuery, book_id: int):
    """
    显示书籍详情
    """
    await callback.answer("⏳ 加载中...")
    try:
        book = await asyncio.wait_for(get_book_from_db(book_id), timeout=3)
    except Exception as e:
        logger.warning(f"获取书籍详情失败: {e}")
        await callback.answer("❌ 当前服务繁忙，请稍后重试", show_alert=True)
        return

    if not book:
        await callback.answer("❌ 书籍信息获取失败")
        return

    file_refs = list(book.file.file_refs) if book.file else []
    primary_ref = pick_primary_file_ref(file_refs)
    backup_ref = pick_backup_ref(file_refs)

    # 构建详情文本
    tags = [bt.tag.name for bt in (book.book_tags or []) if bt.tag and bt.tag.name]
    tags_display = " ".join([f"#{t}" for t in tags[:20]]) if tags else "暂无标签"
    description = book.description or "暂无简介"
    if len(description) > 300:
        description = description[:300] + "..."

    uploader_name = "未知"
    if book.uploader:
        uploader_name = book.uploader.username or f"{book.uploader.first_name}{book.uploader.last_name or ''}".strip() or "未知"

    file_format = book.file.format.value if book.file and book.file.format else "未知"
    file_size = format_size(book.file.size) if book.file else "未知"
    word_count = book.file.word_count if book.file else 0

    display_filename = f"{book.title}.{book.file.extension}" if book.file and book.file.extension else book.title

    detail_text = (
        f"📄 <b>{display_filename}</b>\n\n"
        f"书名：<b>{book.title}</b>\n"
        f"作者：{book.author}\n"
        f"格式：{file_format.upper() if file_format != '未知' else '未知'}\n"
        f"大小：{file_size}\n"
        f"字数：{word_count}\n\n"
        f"统计：{book.view_count}浏览｜{book.download_count}下载｜{book.favorite_count}收藏\n"
        f"评分：{book.rating_score:.2f}({book.rating_count}人)｜质量：{book.quality_score:.2f}\n\n"
        f"标签：{tags_display}\n\n"
        f"简介：\n{description}\n\n"
        f"创建：{format_date(book.created_at)}\n"
        f"更新：{format_date(book.updated_at)}\n"
        f"上传：{uploader_name}"
    )

    # 构建操作键盘
    keyboard_rows: list[list[InlineKeyboardButton]] = []
    can_download = bool(primary_ref or (backup_ref and backup_ref.channel_id and backup_ref.message_id))
    if can_download:
        keyboard_rows.append([
            InlineKeyboardButton(
                text="⬇️ 立即下载",
                callback_data=f"book:download:{book_id}",
            ),
        ])
    else:
        detail_text += "\n\n⚠️ <b>文件暂不可用</b>\n请稍后重试或联系管理员"

    keyboard_rows.append([
        InlineKeyboardButton(
            text="❤️ 收藏",
            callback_data=f"book:fav:{book_id}",
        ),
        InlineKeyboardButton(
            text="📝 评论",
            callback_data=f"book:review:{book_id}",
        ),
    ])
    keyboard_rows.append([
        InlineKeyboardButton(
            text="⚠️ 举报",
            callback_data=f"book:report:{book_id}",
        ),
        InlineKeyboardButton(
            text="🔗 分享",
            callback_data=f"book:share:{book_id}",
        ),
    ])
    keyboard_rows.append([
        InlineKeyboardButton(text="❌ 关闭", callback_data="close"),
        InlineKeyboardButton(text="◀️ 返回", callback_data="close"),
    ])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    try:
        await callback.message.answer(detail_text, reply_markup=keyboard)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await callback.answer()
        else:
            raise


async def handle_download(callback: CallbackQuery, book_id: int):
    """处理下载请求"""
    await callback.answer("⏳ 正在准备文件...")
    try:
        book = await asyncio.wait_for(get_book_from_db(book_id), timeout=3)
    except Exception as e:
        logger.warning(f"获取下载信息失败: {e}")
        await callback.answer("❌ 当前服务繁忙，请稍后重试", show_alert=True)
        return
    if not book or not book.file:
        await callback.answer("❌ 文件信息不存在")
        return

    file_refs = list(book.file.file_refs) if book.file else []
    primary_ref = pick_primary_file_ref(file_refs)
    backup_ref = pick_backup_ref(file_refs)

    if not primary_ref and not backup_ref:
        await callback.answer("❌ 文件暂时不可用")
        return

    try:
        if primary_ref:
            await callback.bot.send_document(
                chat_id=callback.message.chat.id,
                document=primary_ref.tg_file_id,
            )
            await record_download(
                user_id=callback.from_user.id,
                username=callback.from_user.username,
                first_name=callback.from_user.first_name,
                last_name=callback.from_user.last_name,
                book_id=book_id,
                file_hash=book.file_hash,
            )
            await callback.answer("✅ 文件已发送")
            return
    except Exception as e:
        logger.warning(f"直接发送文件失败: {e}")

    if backup_ref and backup_ref.channel_id and backup_ref.message_id:
        try:
            await callback.bot.forward_message(
                chat_id=callback.message.chat.id,
                from_chat_id=backup_ref.channel_id,
                message_id=backup_ref.message_id,
            )
            await record_download(
                user_id=callback.from_user.id,
                username=callback.from_user.username,
                first_name=callback.from_user.first_name,
                last_name=callback.from_user.last_name,
                book_id=book_id,
                file_hash=book.file_hash,
            )
            await callback.answer("✅ 文件已从备份恢复")
            return
        except Exception as e:
            logger.error(f"从备份频道转发失败: {e}")

    await callback.answer("❌ 文件下载失败")


async def handle_favorite(callback: CallbackQuery, book_id: int):
    """处理收藏请求"""
    await callback.answer("⏳ 处理中...")
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
            if book.favorite_count and book.favorite_count > 0:
                book.favorite_count -= 1
            await session.commit()
            await callback.answer("💔 已取消收藏", show_alert=True)
            return

        session.add(Favorite(user_id=user.id, book_id=book_id))
        book.favorite_count += 1
        await session.commit()

    await callback.answer("❤️ 已添加到收藏夹", show_alert=True)


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


async def handle_report(callback: CallbackQuery, book_id: str):
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

    await callback.message.edit_text(
        "⚠️ <b>举报书籍</b>\n\n"
        "请选择举报原因:",
        reply_markup=keyboard
    )
    await callback.answer()


@book_detail_router.callback_query(F.data == "goto:search")
async def on_goto_search(callback: CallbackQuery):
    """跳转到搜索"""
    await callback.message.edit_text(
        "🔍 <b>开始搜索</b>\n\n"
        "请直接发送关键词，或使用:\n"
        "• <code>/s 关键词</code> - 搜索书名/作者\n"
        "• <code>/ss 关键词</code> - 搜索标签/主角"
    )
    await callback.answer()
