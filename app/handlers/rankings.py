# -*- coding: utf-8 -*-
"""
搜书神器 V2 - 排行榜处理器
处理 /top 排行榜命令
"""

from typing import Optional

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from app.core.logger import logger
from app.core.text import escape_html
from app.services.search import get_search_service

rankings_router = Router(name="rankings")


@rankings_router.message(Command(commands=["top", "topuser"]))
async def cmd_top(message: Message):
    """
    处理 /top 排行榜命令

    用法: /top [分类]
    示例: /top, /top hot, /top new, /top rating

    显示各类排行榜:
    - 热门下载榜
    - 最新上传榜
    - 高评分榜
    """
    # 解析参数
    args = message.text.split(maxsplit=1)
    category = args[1].strip().lower() if len(args) > 1 else "hot"

    # 发送加载提示
    status_msg = await message.answer("📊 正在获取排行榜数据...")

    try:
        # 根据分类获取排行榜
        if category in ("hot", "热门", "download", "下载"):
            await show_hot_ranking(status_msg, message.from_user.id)
        elif category in ("new", "最新", "newest", "upload"):
            await show_new_ranking(status_msg, message.from_user.id)
        elif category in ("rating", "评分", "高分", "toprated"):
            await show_rating_ranking(status_msg, message.from_user.id)
        else:
            await show_help(status_msg)

    except Exception as e:
        logger.error(f"获取排行榜失败: {e}", exc_info=True)
        await status_msg.edit_text(
            "❌ <b>获取排行榜失败</b>\n\n"
            f"错误信息: <code>{str(e)[:100]}</code>\n\n"
            "请稍后再试"
        )


async def show_hot_ranking(message, user_id: int):
    """显示热门下载榜"""
    search_service = await get_search_service()

    response = await search_service.search(
        query="",
        page=1,
        per_page=10,
        sort=["download_count:desc"],
    )

    # 构建排行榜文本
    text = "🔥 <b>热门下载榜 Top 10</b>\n\n"

    if response.hits:
        for i, book in enumerate(response.hits[:10], 1):
            emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            text += f"{emoji} <b>{escape_html(book.title)}</b>\n"
            text += f"   ⬇️ {book.download_count or 0} 次下载"
            if book.rating_score:
                text += f" | ⭐ {book.rating_score:.1f}"
            text += "\n\n"
    else:
        text += "暂无数据\n"

    # 构建导航键盘
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔥 热门榜", callback_data="ranking:hot"),
            InlineKeyboardButton(text="🆕 最新榜", callback_data="ranking:new"),
            InlineKeyboardButton(text="⭐ 评分榜", callback_data="ranking:rating"),
        ],
        [
            InlineKeyboardButton(text="🔍 去搜索", callback_data="goto:search"),
        ],
    ])

    await message.edit_text(text, reply_markup=keyboard)


async def show_new_ranking(message, user_id: int):
    """显示最新上传榜"""
    search_service = await get_search_service()

    response = await search_service.search(
        query="",
        page=1,
        per_page=10,
        sort=["created_at:desc"],
    )

    # 构建排行榜文本
    text = "🆕 <b>最新上传榜 Top 10</b>\n\n"

    if response.hits:
        from datetime import datetime
        for i, book in enumerate(response.hits[:10], 1):
            emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            text += f"{emoji} <b>{escape_html(book.title)}</b>\n"
            created = book.created_at
            if isinstance(created, int):
                text += f"   📅 {datetime.fromtimestamp(created).strftime('%Y-%m-%d')}"
            elif isinstance(created, str):
                text += f"   📅 {created[:10]}"
            else:
                text += "   📅 未知"
            text += "\n\n"
    else:
        text += "暂无数据\n"

    # 构建导航键盘
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔥 热门榜", callback_data="ranking:hot"),
            InlineKeyboardButton(text="🆕 最新榜", callback_data="ranking:new"),
            InlineKeyboardButton(text="⭐ 评分榜", callback_data="ranking:rating"),
        ],
        [
            InlineKeyboardButton(text="🔍 去搜索", callback_data="goto:search"),
        ],
    ])

    await message.edit_text(text, reply_markup=keyboard)


async def show_rating_ranking(message, user_id: int):
    """显示高评分榜"""
    search_service = await get_search_service()

    response = await search_service.search(
        query="",
        page=1,
        per_page=10,
        sort=["rating_score:desc"],
    )

    # 构建排行榜文本
    text = "⭐ <b>高分书籍榜 Top 10</b>\n\n"

    if response.hits:
        for i, book in enumerate(response.hits[:10], 1):
            emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            stars = "⭐" * int(book.rating_score or 0)
            text += f"{emoji} <b>{escape_html(book.title)}</b>\n"
            text += f"   {stars} {book.rating_score:.1f}/10"
            if book.rating_count:
                text += f" ({book.rating_count}人评分)"
            text += "\n\n"
    else:
        text += "暂无数据\n"

    # 构建导航键盘
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔥 热门榜", callback_data="ranking:hot"),
            InlineKeyboardButton(text="🆕 最新榜", callback_data="ranking:new"),
            InlineKeyboardButton(text="⭐ 评分榜", callback_data="ranking:rating"),
        ],
        [
            InlineKeyboardButton(text="🔍 去搜索", callback_data="goto:search"),
        ],
    ])

    await message.edit_text(text, reply_markup=keyboard)


async def show_help(message):
    """显示排行榜帮助"""
    text = (
        "📊 <b>排行榜使用帮助</b>\n\n"
        "<b>用法:</b> <code>/top [分类]</code>\n\n"
        "<b>支持的分类:</b>\n"
        "• <code>hot</code> / <code>热门</code> - 热门下载榜\n"
        "• <code>new</code> / <code>最新</code> - 最新上传榜\n"
        "• <code>rating</code> / <code>评分</code> - 高评分榜\n\n"
        "<b>示例:</b>\n"
        "• <code>/top</code> - 默认显示热门榜\n"
        "• <code>/top new</code> - 显示最新榜\n"
        "• <code>/top rating</code> - 显示评分榜"
    )

    await message.edit_text(text)


@rankings_router.callback_query(F.data.startswith("ranking:"))
async def on_ranking_callback(callback: CallbackQuery):
    """处理排行榜分类切换"""
    category = callback.data.replace("ranking:", "")
    user_id = callback.from_user.id

    try:
        if category == "hot":
            await show_hot_ranking(callback.message, user_id)
        elif category == "new":
            await show_new_ranking(callback.message, user_id)
        elif category == "rating":
            await show_rating_ranking(callback.message, user_id)
        else:
            await callback.answer("⚠️ 未知的排行榜分类")
            return

        await callback.answer()
    except Exception as e:
        logger.error(f"切换排行榜失败: {e}", exc_info=True)
        await callback.answer("❌ 切换失败，请重试")
