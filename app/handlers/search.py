# -*- coding: utf-8 -*-
"""
搜书神器 V2 - 搜索处理器
处理 /s 搜索命令和相关回调
"""

import time
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.exceptions import TelegramAPIError

from app.core.logger import logger
from app.services.search import (
    get_search_service,
    SearchFilters,
    SearchResponse,
)

search_router = Router(name="search")


# ============================================================================
# 搜索状态缓存 (带过期机制)
# ============================================================================

class SearchCache:
    """带过期时间的搜索缓存"""

    def __init__(self, ttl_seconds: int = 1800):
        self._cache: Dict[int, Dict[str, Any]] = {}
        self._ttl = ttl_seconds

    def get(self, user_id: int) -> Optional[Dict[str, Any]]:
        """获取缓存，如果过期则返回 None"""
        if user_id not in self._cache:
            return None

        entry = self._cache[user_id]
        if datetime.now() - entry['_timestamp'] > timedelta(seconds=self._ttl):
            # 已过期，删除
            del self._cache[user_id]
            return None

        return entry

    def set(self, user_id: int, data: Dict[str, Any]) -> None:
        """设置缓存"""
        data = data.copy()
        data['_timestamp'] = datetime.now()
        self._cache[user_id] = data

    def __setitem__(self, key: int, value: Dict[str, Any]) -> None:
        """支持 [] 赋值操作"""
        self.set(key, value)

    def clear(self, user_id: Optional[int] = None) -> None:
        """清除缓存"""
        if user_id is None:
            self._cache.clear()
        else:
            self._cache.pop(user_id, None)


# 全局搜索缓存实例
_search_cache = SearchCache(ttl_seconds=1800)

# 格式对应的Emoji
FORMAT_EMOJI = {
    "txt": "📄",
    "pdf": "📕",
    "epub": "📗",
    "mobi": "📘",
    "azw3": "📙",
    "doc": "📝",
    "docx": "📝",
}

# 分级Flag
RATING_FLAGS = {
    "general": "",
    "mature": "🔞",
    "adult": "🔞",
}


def format_size(size_bytes: int) -> str:
    """格式化文件大小"""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f}MB"


def format_word_count(count: int) -> str:
    """格式化字数"""
    if count < 10000:
        return f"{count}"
    elif count < 100000000:
        value = count / 10000
        value = int(value * 10) / 10
        return f"{value:.1f}万"
    else:
        return f"{count / 100000000:.1f}亿"


def get_rating_stars(score: float) -> str:
    """获取评分星星显示"""
    full_stars = int(score / 2)
    half_star = (score % 2) >= 1
    empty_stars = 5 - full_stars - (1 if half_star else 0)

    stars = "★" * full_stars
    if half_star:
        stars += "☆"
    stars += "☆" * empty_stars
    return stars


def build_search_result_text(
    response: SearchResponse,
    user_filters: Optional[Dict] = None,
) -> str:
    """
    构建搜索结果文本

    格式:
    🔍 关键词 > Results 1-10 of 总数 (用时 X秒)

    1. 书名 {Flag}
    [Emoji] • 格式 • 大小 • 字数 • 评分

    2. ...
    """
    query = response.query
    total = response.total
    page = response.page
    per_page = response.per_page
    hits = response.hits
    processing_time = response.processing_time_ms / 1000  # 转换为秒

    start_idx = (page - 1) * per_page + 1
    end_idx = min(start_idx + len(hits) - 1, total)

    # 头部
    lines = [
        f"🔍 <b>{query}</b> > Results {start_idx}-{end_idx} of {total} (in {processing_time:.2f}s)"
    ]

    # 当前筛选条件显示
    if user_filters:
        filter_texts = []
        if user_filters.get("format"):
            filter_texts.append(f"格式:{user_filters['format']}")
        if user_filters.get("is_18plus") is not None:
            filter_texts.append("成人内容" if user_filters["is_18plus"] else "全年龄")
        if user_filters.get("sort"):
            sort_map = {
                "popular": "热度",
                "newest": "最新",
                "largest": "最大",
            }
            filter_texts.append(f"排序:{sort_map.get(user_filters['sort'], user_filters['sort'])}")
        if filter_texts:
            lines.append(f"<i>[筛选: {' | '.join(filter_texts)}]</i>")

    lines.append("")  # 空行

    # 结果列表
    for idx, book in enumerate(hits, start=start_idx):
        # 书名和Flag
        flag = ""
        if book.is_18plus:
            flag = " 🔞"
        elif book.quality_score >= 90:
            flag = " ⭐"

        title_line = f"{idx}. {book.title}{flag}"
        lines.append(title_line)

        # 格式、大小、字数、评分
        emoji = FORMAT_EMOJI.get(book.format.lower(), "📄")
        size_str = format_size(book.size)
        word_str = format_word_count(book.word_count)

        # 评分显示 (1-10分转换为星星)
        stars = get_rating_stars(book.rating_score)
        rating_display = f"{stars} {book.rating_score:.1f}"

        detail_line = f"{emoji} • {book.format.upper()} • {size_str} • {word_str}字 • {rating_display}"
        lines.append(detail_line)
        lines.append("")  # 空行分隔

    return "\n".join(lines)


def build_search_keyboard(
    response: SearchResponse,
    user_id: int,
    filters: Optional[Dict] = None,
) -> InlineKeyboardMarkup:
    """
    构建搜索结果的内联键盘

    布局:
    [1][2][3][4][5]
    [6][7][8][9][10]
    [筛选][排序][清除筛选]
    """
    filters = filters or {}
    page = response.page
    per_page = response.per_page
    total = response.total
    total_pages = response.total_pages

    keyboard = []

    # 分页按钮 (最多10个)
    start_idx = (page - 1) * per_page + 1
    end_idx = min(start_idx + len(response.hits) - 1, total)

    # 为每个结果创建一个按钮
    BUTTONS_PER_ROW = 5  # 每行按钮数量
    row1 = []
    row2 = []
    for idx, i in enumerate(range(start_idx, end_idx + 1)):
        btn = InlineKeyboardButton(
            text=str(i),
            callback_data=f"book:view:{i}"
        )
        if idx < BUTTONS_PER_ROW:
            row1.append(btn)
        else:
            row2.append(btn)

    if row1:
        keyboard.append(row1)
    if row2:
        keyboard.append(row2)

    # 导航和筛选按钮
    nav_row = []

    # 上一页/下一页
    if page > 1:
        nav_row.append(InlineKeyboardButton(
            text="◀️ 上一页",
            callback_data=f"search:page:{page-1}"
        ))

    # 页码指示
    nav_row.append(InlineKeyboardButton(
        text=f"{page}/{total_pages or 1}",
        callback_data="search:noop"
    ))

    if page < total_pages:
        nav_row.append(InlineKeyboardButton(
            text="下一页 ▶️",
            callback_data=f"search:page:{page+1}"
        ))

    if nav_row:
        keyboard.append(nav_row)

    # 筛选和排序按钮
    filter_row = []

    # 格式筛选
    current_format = filters.get("format", "")
    format_text = f"格式:{current_format.upper()}" if current_format else "📋格式"
    filter_row.append(InlineKeyboardButton(
        text=format_text,
        callback_data="search:filter:format"
    ))

    # 排序
    sort_map = {
        "popular": "🔥热度",
        "newest": "🕐最新",
        "largest": "📦最大",
    }
    current_sort = filters.get("sort", "popular")
    sort_text = sort_map.get(current_sort, "🔥热度")
    filter_row.append(InlineKeyboardButton(
        text=sort_text,
        callback_data="search:filter:sort"
    ))

    # 成人内容筛选
    is_18plus = filters.get("is_18plus")
    if is_18plus is True:
        adult_text = "🔞成人"
    elif is_18plus is False:
        adult_text = "✅全年龄"
    else:
        adult_text = "🔞/✅"
    filter_row.append(InlineKeyboardButton(
        text=adult_text,
        callback_data="search:filter:adult"
    ))

    keyboard.append(filter_row)

    # 清除筛选按钮
    if filters:
        keyboard.append([InlineKeyboardButton(
            text="🗑️ 清除所有筛选",
            callback_data="search:filter:clear"
        )])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# ============================================================================
# 命令处理器
# ============================================================================

@search_router.message(Command("s"))
async def cmd_search(message: Message):
    """
    处理 /s 搜索命令

    用法: /s <关键词>
    示例: /s 剑来
    """
    # 提取关键词
    command_parts = message.text.split(maxsplit=1)
    if len(command_parts) < 2:
        await message.answer(
            "⚠️ 请提供搜索关键词\n\n"
            "用法: <code>/s 关键词</code>\n"
            "示例: <code>/s 剑来</code>"
        )
        return

    query = command_parts[1].strip()
    if len(query) < 2:
        await message.answer("⚠️ 搜索关键词至少需要2个字符")
        return

    # 执行搜索
    await perform_search(message, query, user_id=message.from_user.id)


@search_router.message(F.text)
async def text_search(message: Message):
    """
    处理直接发送的文本作为搜索关键词

    排除命令和太短的文本
    """
    text = message.text.strip()

    # 排除命令
    if text.startswith("/"):
        return

    # 排除太短的文本（可能是误触）
    if len(text) < 2:
        return

    # 排除纯数字（可能是回复其他消息）
    if text.isdigit():
        return

    # 执行搜索
    await perform_search(message, text, user_id=message.from_user.id)


# ============================================================================
# 搜索核心逻辑
# ============================================================================

async def perform_search(
    message: Message,
    query: str,
    user_id: int,
    page: int = 1,
    filters: Optional[Dict] = None,
):
    """
    执行搜索并显示结果

    Args:
        message: 消息对象（用于回复）
        query: 搜索关键词
        user_id: 用户ID（用于缓存状态）
        page: 页码
        filters: 筛选条件
    """
    filters = filters or {}

    # 发送"搜索中"提示
    status_message = await message.answer(f"🔍 正在搜索: <b>{query}</b>...")

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

        # 执行搜索
        response = await search_service.search(
            query=query,
            page=page,
            per_page=10,
            filters=search_filters,
            sort=sort,
        )

        # 保存用户搜索状态到缓存
        _search_cache.set(user_id, {
            "query": query,
            "page": page,
            "filters": filters.copy(),
            "last_response": response,
        })

        # 删除"搜索中"消息
        await status_message.delete()

        if response.total == 0:
            # 无结果
            await message.answer(
                f"😔 未找到与 <b>{query}</b> 相关的书籍\n\n"
                f"💡 建议:\n"
                f"• 检查关键词拼写\n"
                f"• 尝试使用更通用的关键词\n"
                f"• 使用 /ss 命令搜索标签/主角"
            )
            return

        # 构建结果文本
        result_text = build_search_result_text(response, filters)

        # 构建键盘
        keyboard = build_search_keyboard(response, user_id, filters)

        # 发送结果
        await message.answer(
            result_text,
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )

    except Exception as e:
        logger.error(f"搜索失败: {e}", exc_info=True)
        await status_message.edit_text(
            f"❌ 搜索出错了\n\n"
            f"错误信息: <code>{str(e)[:100]}</code>\n\n"
            f"请稍后再试或联系管理员"
        )


# ============================================================================
# 回调处理器
# ============================================================================

@search_router.callback_query(F.data.startswith("search:"))
async def on_search_callback(callback: CallbackQuery):
    """处理搜索相关的回调"""
    data = callback.data
    user_id = callback.from_user.id

    # 解析回调数据并验证
    parts = data.split(":")
    if len(parts) < 2:
        await callback.answer("⚠️ 无效的回调数据", show_alert=True)
        return

    action = parts[1]

    # 获取用户搜索状态
    cache = _search_cache.get(user_id)
    if not cache:
        await callback.answer("⚠️ 搜索会话已过期，请重新搜索", show_alert=True)
        return

    query = cache["query"]
    filters = cache["filters"]

    try:
        if action == "page":
            # 翻页
            new_page = int(parts[2])
            await callback.message.edit_text("🔍 加载中...")
            await perform_search_edit(
                callback.message,
                query,
                user_id,
                page=new_page,
                filters=filters,
            )
            await callback.answer()

        elif action == "filter":
            # 筛选操作
            filter_type = parts[2] if len(parts) > 2 else ""
            await handle_filter_callback(callback, filter_type, query, filters)

        elif action == "noop":
            # 无操作
            await callback.answer()

    except Exception as e:
        logger.error(f"处理回调失败: {e}", exc_info=True)
        await callback.answer(f"❌ 操作失败: {str(e)[:50]}", show_alert=True)


async def handle_filter_callback(
    callback: CallbackQuery,
    filter_type: str,
    query: str,
    current_filters: Dict,
):
    """处理筛选回调"""
    user_id = callback.from_user.id

    if filter_type == "format":
        # 循环切换格式筛选
        formats = ["", "txt", "pdf", "epub", "mobi"]
        current = current_filters.get("format", "")
        try:
            idx = formats.index(current)
            next_format = formats[(idx + 1) % len(formats)]
        except ValueError:
            next_format = formats[1] if formats else ""

        current_filters["format"] = next_format

    elif filter_type == "sort":
        # 循环切换排序
        sorts = ["popular", "newest", "largest"]
        current = current_filters.get("sort", "popular")
        try:
            idx = sorts.index(current)
            next_sort = sorts[(idx + 1) % len(sorts)]
        except ValueError:
            next_sort = sorts[0]

        current_filters["sort"] = next_sort

    elif filter_type == "adult":
        # 循环切换成人内容筛选
        current = current_filters.get("is_18plus")
        if current is None:
            current_filters["is_18plus"] = False
        elif current is False:
            current_filters["is_18plus"] = True
        else:
            current_filters["is_18plus"] = None

    elif filter_type == "clear":
        # 清除所有筛选
        current_filters.clear()
        await callback.answer("✅ 已清除所有筛选", show_alert=True)

    else:
        await callback.answer(f"未知的筛选类型: {filter_type}")
        return

    # 更新缓存
    # _search_cache[user_id]["filters"] = current_filters
    # 使用 get 获取并更新
    cache_data = _search_cache.get(user_id)
    if cache_data:
        cache_data["filters"] = current_filters
        _search_cache.set(user_id, cache_data)

    # 重新搜索 (回到第1页)
    await callback.message.edit_text("🔍 应用筛选中...")
    await perform_search_edit(
        callback.message,
        query,
        user_id,
        page=1,
        filters=current_filters,
    )
    await callback.answer()


async def perform_search_edit(
    message,
    query: str,
    user_id: int,
    page: int = 1,
    filters: Optional[Dict] = None,
):
    """
    执行搜索并编辑消息 (用于回调更新)
    与 perform_search 类似，但编辑现有消息
    """
    filters = filters or {}

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

        # 执行搜索
        response = await search_service.search(
            query=query,
            page=page,
            per_page=10,
            filters=search_filters,
            sort=sort,
        )

        # 更新缓存
        _search_cache.set(user_id, {
            "query": query,
            "page": page,
            "filters": filters.copy(),
            "last_response": response,
        })

        if response.total == 0:
            await message.edit_text(
                f"😔 未找到与 <b>{query}</b> 相关的书籍\n\n"
                f"💡 建议:\n"
                f"• 检查关键词拼写\n"
                f"• 尝试使用更通用的关键词\n"
                f"• 使用 /ss 命令搜索标签/主角"
            )
            return

        # 构建结果文本
        result_text = build_search_result_text(response, filters)

        # 构建键盘
        keyboard = build_search_keyboard(response, user_id, filters)

        # 编辑消息
        await message.edit_text(
            result_text,
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )

    except Exception as e:
        logger.error(f"搜索失败: {e}", exc_info=True)
        await message.edit_text(
            f"❌ 搜索出错了\n\n"
            f"错误信息: <code>{str(e)[:100]}</code>\n\n"
            f"请稍后再试或联系管理员"
        )


# ============================================================================
# 书籍详情回调 (预留，后续实现)
# ============================================================================

@search_router.callback_query(F.data.startswith("book:"))
async def on_book_callback(callback: CallbackQuery):
    """处理书籍相关的回调"""
    data = callback.data
    parts = data.split(":")

    if len(parts) < 2:
        await callback.answer("无效的回调数据")
        return

    action = parts[1]

    if action == "view":
        # 查看书籍详情 - 预留接口
        book_idx = parts[2] if len(parts) > 2 else "?"
        await callback.answer(f"正在查看第 {book_idx} 本书的详情...")
        # TODO: 实现书籍详情显示
    else:
        await callback.answer(f"未知操作: {action}")
