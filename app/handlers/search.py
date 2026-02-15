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
from app.core.config import get_settings
from app.services.search import (
    get_search_service,
    SearchFilters,
    SearchResponse,
)
from app.handlers.book_detail import send_book_card

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
        kb = round(size_bytes / 1024, 1)
        return f"{int(kb)}KB" if float(kb).is_integer() else f"{kb:.1f}KB"
    else:
        mb = round(size_bytes / (1024 * 1024), 1)
        return f"{int(mb)}MB" if float(mb).is_integer() else f"{mb:.1f}MB"


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
    bot_username: str = "",
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

    lines = [
        f"🔍 搜索作品/作者:<b>{query}</b> Results {start_idx}-{end_idx} of {total} (用时 {processing_time:.2f} 秒)"
    ]

    # 结果列表
    bot_username = (bot_username or "").lstrip("@")
    for idx, book in enumerate(hits, start=start_idx):
        # 书名和Flag
        flag = ""
        if book.is_18plus:
            flag = " 🔞"
        elif book.quality_score >= 9:
            flag = " ⭐"

        link = f"https://t.me/{bot_username}?start=book_{book.id}" if bot_username else ""
        title = f"<a href=\"{link}\">{book.title}</a>" if link else book.title
        prefix = "❓ " if (book.rating_score <= 0 and book.quality_score <= 0) else ""
        title_line = f"{idx:02d}. {prefix}{title}{flag}"
        lines.append(title_line)

        # 格式、大小、字数、评分
        emoji = FORMAT_EMOJI.get(book.format.lower(), "📄")
        size_str = format_size(book.size)
        word_str = format_word_count(book.word_count)
        rating_display = f"{book.rating_score:.2f}/{book.quality_score:.2f}"
        detail_line = f"{emoji}·{book.format.upper()}·{size_str}·{word_str}字·{rating_display}"
        lines.append(detail_line)

    lines.append("")
    lines.append("💎 捐赠会员：提升等级获得书币，享受权限增值，优先体验功能")

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

    keyboard: list[list[InlineKeyboardButton]] = []

    # 第1行：分页（选择页码）
    page_row: list[InlineKeyboardButton] = []
    if total_pages <= 1:
        page_row.append(InlineKeyboardButton(text="1∨", callback_data="search:noop"))
    else:
        visible = list(range(1, min(total_pages, 6) + 1))
        for p in visible:
            text = f"{p}∨" if p == page else str(p)
            page_row.append(InlineKeyboardButton(text=text, callback_data=f"search:page:{p}"))
        if total_pages > 6:
            page_row.append(InlineKeyboardButton(text=f"...{total_pages}", callback_data=f"search:page:{total_pages}"))
    keyboard.append(page_row)

    # 第2行：筛选
    is_18plus = filters.get("is_18plus")
    if is_18plus is True:
        rating_text = "分级:成人∨"
    elif is_18plus is False:
        rating_text = "分级:全年龄∨"
    else:
        rating_text = "分级∨"

    fmt = filters.get("format") or ""
    fmt_text = f"格式:{fmt.upper()}∨" if fmt else "格式∨"

    max_size = filters.get("max_size")
    if isinstance(max_size, int) and max_size > 0:
        size_text = f"体积≤{int(max_size / (1024 * 1024))}M∨"
    else:
        size_text = "体积∨"

    min_words = filters.get("min_word_count")
    if isinstance(min_words, int) and min_words > 0:
        words_text = f"字数≥{int(min_words / 10000)}万∨"
    else:
        words_text = "字数∨"

    keyboard.append([
        InlineKeyboardButton(text=rating_text, callback_data="search:filter:rating"),
        InlineKeyboardButton(text=fmt_text, callback_data="search:filter:format"),
        InlineKeyboardButton(text=size_text, callback_data="search:filter:size"),
        InlineKeyboardButton(text=words_text, callback_data="search:filter:words"),
    ])

    # 第3行：排序（点按选择）
    sort_key = filters.get("sort", "popular")
    keyboard.append([
        InlineKeyboardButton(
            text="最热↓" if sort_key == "popular" else "最热",
            callback_data="search:sort:popular",
        ),
        InlineKeyboardButton(
            text="最新↓" if sort_key == "newest" else "最新",
            callback_data="search:sort:newest",
        ),
        InlineKeyboardButton(
            text="最大↓" if sort_key == "largest" else "最大",
            callback_data="search:sort:largest",
        ),
    ])

    # 第4/5行：按序号下载（1-10）
    d1: list[InlineKeyboardButton] = []
    d2: list[InlineKeyboardButton] = []
    for i in range(1, 11):
        btn = InlineKeyboardButton(text=str(i), callback_data=f"search:dl:{i}")
        (d1 if i <= 5 else d2).append(btn)
    keyboard.append(d1)
    keyboard.append(d2)

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# ============================================================================
# 命令处理器
# ============================================================================

@search_router.message(Command(commands=["s", "book"]))
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


@search_router.message(F.text & ~F.text.startswith("/"))
async def text_search(message: Message):
    """
    处理直接发送的文本作为搜索关键词

    排除命令和太短的文本
    """
    text = message.text.strip()

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
        if filters.get("max_size") is not None:
            search_filters.max_size = filters["max_size"]
        if filters.get("min_word_count") is not None:
            search_filters.min_word_count = filters["min_word_count"]

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
        result_text = build_search_result_text(response, get_settings().bot_username, filters)

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

        elif action == "sort":
            sort_key = parts[2] if len(parts) > 2 else ""
            if sort_key not in {"popular", "newest", "largest"}:
                await callback.answer("⚠️ 无效的排序", show_alert=True)
                return
            filters["sort"] = sort_key
            cache_data = _search_cache.get(user_id)
            if cache_data:
                cache_data["filters"] = filters
                _search_cache.set(user_id, cache_data)
            await callback.message.edit_text("🔍 应用排序中...")
            await perform_search_edit(
                callback.message,
                query,
                user_id,
                page=1,
                filters=filters,
            )
            await callback.answer()

        elif action == "dl":
            idx = int(parts[2]) if len(parts) > 2 else 0
            last_response: SearchResponse = cache.get("last_response")
            if not last_response or idx < 1 or idx > len(last_response.hits):
                await callback.answer("⚠️ 序号无效或已过期", show_alert=True)
                return
            book_id = last_response.hits[idx - 1].id
            await send_book_card(
                bot=callback.bot,
                chat_id=callback.message.chat.id,
                book_id=book_id,
                from_user=callback.from_user,
            )
            await callback.answer("✅ 已发送", show_alert=False)

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

    elif filter_type in {"adult", "rating"}:
        # 循环切换成人内容筛选
        current = current_filters.get("is_18plus")
        if current is None:
            current_filters["is_18plus"] = False
        elif current is False:
            current_filters["is_18plus"] = True
        else:
            current_filters["is_18plus"] = None

    elif filter_type == "size":
        sizes = [None, 1, 5, 20, 50, 100]
        current = current_filters.get("max_size")
        current_mb = int(current / (1024 * 1024)) if isinstance(current, int) and current > 0 else None
        try:
            idx = sizes.index(current_mb)
            next_mb = sizes[(idx + 1) % len(sizes)]
        except ValueError:
            next_mb = sizes[1]
        current_filters["max_size"] = next_mb * 1024 * 1024 if next_mb else None

    elif filter_type == "words":
        words = [None, 1, 5, 10, 30, 50]
        current = current_filters.get("min_word_count")
        current_wan = int(current / 10000) if isinstance(current, int) and current > 0 else None
        try:
            idx = words.index(current_wan)
            next_wan = words[(idx + 1) % len(words)]
        except ValueError:
            next_wan = words[1]
        current_filters["min_word_count"] = next_wan * 10000 if next_wan else None

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
        if filters.get("max_size") is not None:
            search_filters.max_size = filters["max_size"]
        if filters.get("min_word_count") is not None:
            search_filters.min_word_count = filters["min_word_count"]

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
        result_text = build_search_result_text(response, get_settings().bot_username, filters)

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
