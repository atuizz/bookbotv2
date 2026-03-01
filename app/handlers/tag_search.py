# -*- coding: utf-8 -*-
"""
搜书神器 V2 - 标签/主角搜索处理器
处理 /ss 标签搜索命令
"""

from typing import Optional, Dict, Any

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from app.core.config import get_settings
from app.core.logger import logger
from app.core.text import escape_html
from app.handlers.search import (
    _search_cache,
    SearchCache,
    build_search_result_text,
    build_search_keyboard,
    perform_search as base_perform_search,
)
from app.services.search import get_search_service, SearchFilters

tag_search_router = Router(name="tag_search")


@tag_search_router.message(Command("ss"))
async def cmd_tag_search(message: Message):
    """
    处理 /ss 标签/主角搜索命令

    用法: /ss <标签/主角名>
    示例: /ss 修真
    """
    # 提取关键词
    command_parts = message.text.split(maxsplit=1)
    if len(command_parts) < 2:
        await message.answer(
            "⚠️ 请提供搜索关键词\n\n"
            "用法: <code>/ss 标签/主角</code>\n"
            "示例: <code>/ss 修真</code>\n\n"
            "💡 提示: /ss 用于搜索标签、主角、作者等元数据"
        )
        return

    query = command_parts[1].strip()
    if len(query) < 2:
        await message.answer("⚠️ 搜索关键词至少需要2个字符")
        return

    # 执行标签搜索
    await perform_tag_search(message, query, user_id=message.from_user.id)


async def perform_tag_search(
    message: Message,
    query: str,
    user_id: int,
    page: int = 1,
    filters: Optional[Dict] = None,
):
    """
    执行标签搜索

    与普通搜索的区别:
    1. 交互语义: 明确告诉用户这是“标签/主角”搜索入口
    2. 展示文案: 结果前缀会标注“标签/主角搜索”
    3. 搜索执行: 仍复用统一搜索服务（由 Meilisearch 索引配置决定实际可检索字段）
    """
    filters = filters or {}
    prefix_text = "🏷️ <b>标签/主角搜索</b>"

    # 发送"搜索中"提示
    status_message = await message.answer(f"🔍 正在搜索标签/主角: <b>{escape_html(query)}</b>...")

    try:
        # 获取搜索服务
        search_service = await get_search_service()

        # 构建筛选条件
        search_filters = SearchFilters()
        if filters.get("format"):
            search_filters.format = filters["format"]
        if filters.get("is_18plus") is not None:
            search_filters.is_18plus = filters["is_18plus"]

        # 构建排序
        sort_mapping = {
            "popular": ["download_count:desc", "rating_score:desc"],
            "newest": ["created_at:desc"],
            "largest": ["size:desc"],
        }
        sort = sort_mapping.get(filters.get("sort", "popular"))

        # 执行搜索 (使用标签搜索模式)
        # 注意: 这里我们使用相同的搜索API，但在显示时标注为标签搜索
        response = await search_service.search(
            query=query,
            page=page,
            per_page=10,
            filters=search_filters,
            sort=sort,
        )

        # 删除"搜索中"消息
        await status_message.delete()

        keyboard = build_search_keyboard(response, user_id, filters)
        if response.total == 0:
            result_text = (
                f"{prefix_text}\n"
                f"😔 未找到与 <b>{escape_html(query)}</b> 相关的书籍\n\n"
                f"💡 建议:\n"
                f"• 检查关键词拼写\n"
                f"• 尝试使用更通用的关键词\n"
                f"• 使用 /s 命令搜索书名/作者"
            )
            result_message = await message.answer(
                result_text,
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )
        else:
            result_text = build_search_result_text(response, get_settings().bot_username, filters)
            result_text = f"{prefix_text}\n{result_text}"
            result_message = await message.answer(
                result_text,
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )

        _search_cache.set(user_id, result_message.message_id, {
            "query": query,
            "page": page,
            "filters": filters.copy(),
            "last_response": response,
            "prefix_text": prefix_text,
        })

    except Exception as e:
        logger.error(f"标签搜索失败: {e}", exc_info=True)
        await status_message.edit_text(
            f"❌ 搜索出错了\n\n"
            f"错误信息: <code>{str(e)[:100]}</code>\n\n"
            f"请稍后再试或联系管理员"
        )
