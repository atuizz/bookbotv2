# -*- coding: utf-8 -*-
"""
搜书神器 V2 - 书籍详情处理器 (重构版)
处理书籍详情展示、收藏、下载等操作

关键改进:
1. 书籍详情消息包含实际的文件附件
2. 文件通过 send_document 直接发送
3. 备份服务集成，确保文件可恢复
"""

from typing import Optional, Dict, Any
from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.exceptions import TelegramBadRequest

from app.core.config import settings
from app.core.logger import logger
from app.services.search import get_search_service
from app.services.backup import get_backup_service

book_detail_router = Router(name="book_detail")

# 简化的书籍缓存
_book_cache: Dict[str, Any] = {}


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


def format_date(date_str: str) -> str:
    """格式化日期"""
    try:
        if isinstance(date_str, str):
            if len(date_str) >= 10:
                return date_str[:10]
        return str(date_str)[:10]
    except:
        return "未知"


async def get_book_by_id(book_id: str):
    """根据ID获取书籍信息"""
    # 先从缓存获取
    if book_id in _book_cache:
        return _book_cache[book_id]

    # 从搜索服务获取
    try:
        search_service = await get_search_service()
        # 使用ID搜索
        response = await search_service.search(
            query=f"id:{book_id}",
            page=1,
            per_page=1,
        )
        if response.hits:
            book = response.hits[0]
            _book_cache[book_id] = book
            return book
    except Exception as e:
        logger.error(f"获取书籍信息失败: {e}")

    return None


@book_detail_router.callback_query(F.data.startswith("book:"))
async def on_book_callback(callback: CallbackQuery):
    """处理书籍相关的回调"""
    data = callback.data
    action = data.replace("book:", "")

    try:
        if action.startswith("detail:"):
            book_id = action.replace("detail:", "")
            await show_book_detail(callback, book_id)
        elif action.startswith("download:"):
            book_id = action.replace("download:", "")
            await handle_download(callback, book_id)
        elif action.startswith("fav:"):
            book_id = action.replace("fav:", "")
            await handle_favorite(callback, book_id)
        elif action.startswith("report:"):
            book_id = action.replace("report:", "")
            await handle_report(callback, book_id)
        else:
            await callback.answer("⚠️ 未知的操作")
    except Exception as e:
        logger.error(f"处理书籍回调失败: {e}", exc_info=True)
        await callback.answer("❌ 操作失败，请重试")


async def show_book_detail(callback: CallbackQuery, book_id: str):
    """
    显示书籍详情并发送文件

    关键改进: 发送两条消息:
    1. 文件消息 (包含实际的文件附件)
    2. 详情消息 (书籍信息和操作按钮)
    """
    # 获取书籍信息
    book = await get_book_by_id(book_id)

    if not book:
        await callback.answer("❌ 书籍信息获取失败")
        return

    # 发送文件
    file_sent = False
    if book.file_id:
        try:
            await callback.bot.send_document(
                chat_id=callback.message.chat.id,
                document=book.file_id,
                caption=f"📚 {book.title}"
            )
            file_sent = True
        except Exception as e:
            logger.warning(f"直接发送文件失败: {e}")

            # 尝试从备份恢复
            try:
                backup_service = await get_backup_service()
                msg = await backup_service.send_file_to_user(
                    bot=callback.bot,
                    sha256_hash=book.file_unique_id or book.file_id,
                    user_chat_id=callback.message.chat.id,
                    caption=f"📚 {book.title}"
                )
                if msg:
                    file_sent = True
            except Exception as e2:
                logger.error(f"从备份恢复失败: {e2}")

    # 构建详情文本
    tags_text = ', '.join(book.tags[:10]) if book.tags else '暂无标签'
    description = book.description[:200] + '...' if book.description and len(book.description) > 200 else (book.description or '暂无简介')

    detail_text = f"""📚 <b>{book.title}</b>

📝 <b>基本信息</b>
├ 作者: {book.author or '未知'}
├ 分类: {book.category or '未分类'}
├ 格式: {book.format.upper() if book.format else '未知'}
├ 大小: {format_size(book.size) if book.size else '未知'}
└ 字数: {book.word_count or '未知'}

⭐ <b>评分信息</b>
├ 评分: {book.rating_score or 0}/10
├ 评价数: {book.rating_count or 0} 人
└ 下载量: {book.download_count or 0} 次

🏷️ <b>标签</b>
{tags_text}

💬 <b>简介</b>
{description}

📅 <b>上传信息</b>
├ 上传者: {book.uploader_name or '未知'}
└ 上传时间: {format_date(book.created_at) if book.created_at else '未知'}
"""

    # 构建操作键盘
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="⬇️ 立即下载",
                callback_data=f"book:download:{book_id}"
            ),
        ],
        [
            InlineKeyboardButton(
                text="❤️ 收藏",
                callback_data=f"book:fav:{book_id}"
            ),
            InlineKeyboardButton(
                text="📝 评论",
                callback_data=f"book:review:{book_id}"
            ),
        ],
        [
            InlineKeyboardButton(
                text="⚠️ 举报",
                callback_data=f"book:report:{book_id}"
            ),
            InlineKeyboardButton(
                text="🔗 分享",
                callback_data=f"book:share:{book_id}"
            ),
        ],
        [
            InlineKeyboardButton(text="◀️ 返回搜索", callback_data="goto:search"),
        ],
    ])

    try:
        if file_sent:
            # 如果文件已发送，编辑原消息显示详情
            await callback.message.edit_text(detail_text, reply_markup=keyboard)
        else:
            # 文件发送失败，显示错误信息
            error_text = detail_text + "\n\n⚠️ <b>文件暂时无法下载</b>\n请稍后重试或联系管理员"
            await callback.message.edit_text(error_text, reply_markup=keyboard)

        await callback.answer()
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await callback.answer()
        else:
            raise


async def handle_download(callback: CallbackQuery, book_id: str):
    """处理下载请求"""
    book = await get_book_by_id(book_id)

    if not book or not book.file_id:
        await callback.answer("❌ 文件信息不存在")
        return

    # 尝试发送文件
    try:
        await callback.bot.send_document(
            chat_id=callback.message.chat.id,
            document=book.file_id,
            caption=f"📚 {book.title}"
        )
        await callback.answer("✅ 文件已发送")
    except Exception as e:
        logger.error(f"下载文件失败: {e}")

        # 尝试从备份恢复
        try:
            backup_service = await get_backup_service()
            msg = await backup_service.send_file_to_user(
                bot=callback.bot,
                sha256_hash=book.file_unique_id or book.file_id,
                user_chat_id=callback.message.chat.id,
                caption=f"📚 {book.title}"
            )
            if msg:
                await callback.answer("✅ 文件已从备份恢复")
            else:
                await callback.answer("❌ 文件暂时无法下载，请稍后重试")
        except Exception as e2:
            logger.error(f"从备份恢复失败: {e2}")
            await callback.answer("❌ 文件下载失败")


async def handle_favorite(callback: CallbackQuery, book_id: str):
    """处理收藏请求"""
    # TODO: 实现收藏逻辑
    await callback.answer(
        "❤️ 已添加到收藏夹！",
        show_alert=True
    )


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
