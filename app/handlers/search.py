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
from app.core.text import escape_html
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
        self._cache: Dict[Tuple[int, int], Dict[str, Any]] = {}
        self._ttl = ttl_seconds

    def get(self, user_id: int, message_id: int) -> Optional[Dict[str, Any]]:
        """获取缓存，如果过期则返回 None"""
        key = (user_id, message_id)
        entry = self._cache.get(key)
        if not entry:
            return None
        if datetime.now() - entry["_timestamp"] > timedelta(seconds=self._ttl):
            self._cache.pop(key, None)
            return None
        return entry

    def set(self, user_id: int, message_id: int, data: Dict[str, Any]) -> None:
        """设置缓存"""
        data = data.copy()
        data["_timestamp"] = datetime.now()
        self._cache[(user_id, message_id)] = data

    def __setitem__(self, key: Tuple[int, int], value: Dict[str, Any]) -> None:
        """支持 [] 赋值操作"""
        user_id, message_id = key
        self.set(user_id, message_id, value)

    def clear(self, user_id: Optional[int] = None, message_id: Optional[int] = None) -> None:
        """清除缓存"""
        if user_id is None and message_id is None:
            self._cache.clear()
            return
        if user_id is not None and message_id is not None:
            self._cache.pop((user_id, message_id), None)
            return
        if user_id is not None:
            for k in list(self._cache.keys()):
                if k[0] == user_id:
                    self._cache.pop(k, None)
            return
        if message_id is not None:
            for k in list(self._cache.keys()):
                if k[1] == message_id:
                    self._cache.pop(k, None)
            return


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

    safe_query = escape_html(query)
    lines = [f"🔍 搜索作品/作者:<b>{safe_query}</b> Results {start_idx}-{end_idx} of {total} (用时 {processing_time:.2f} 秒)"]

    # 结果列表
    bot_username = (bot_username or "").lstrip("@")
    for idx, book in enumerate(hits, start=1):
        # 书名和Flag
        flag = ""
        if book.is_18plus:
            flag = " 🔞"
        elif book.quality_score >= 9:
            flag = " ⭐"

        link = f"https://t.me/{bot_username}?start=book_{book.id}" if bot_username else ""
        safe_title = escape_html(book.title)
        title = f"<a href=\"{escape_html(link)}\">{safe_title}</a>" if link else safe_title
        prefix = "❓ " if (book.rating_score <= 0 and book.quality_score <= 0) else ""
        title_line = f"<code>{idx:02d}.</code> {prefix}{title}{flag}"
        lines.append(title_line)

        # 格式、大小、字数、评分
        emoji = FORMAT_EMOJI.get(book.format.lower(), "📄")
        size_str = format_size(book.size)
        word_str = format_word_count(book.word_count)
        rating_display = f"{book.rating_score:.2f}/{book.quality_score:.2f}"
        detail_line = f"<code>{emoji}·{book.format.upper()}·{size_str}·{word_str}字·{rating_display}</code>"
        lines.append(detail_line)

    lines.append("")
    lines.append("💎 捐赠会员：提升等级获得书币，享受权限增值，优先体验功能")

    return "\n".join(lines)


def get_content_rating_label(filters: Optional[Dict]) -> str:
    filters = filters or {}
    value = filters.get("content_rating")
    if value == "safe":
        return "安全"
    if value == "teen":
        return "少年"
    if value == "unknown":
        return "未知"
    return "全部"


def build_no_result_text(filters: Optional[Dict] = None) -> str:
    return (
        "没有检索到结果，请尝试其他关键词或调整筛选条件\n"
        f"内容分级:{get_content_rating_label(filters)}"
    )


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
    if total > 0:
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

    menu = (filters.get("_menu") or "").strip()

    def arrow(name: str) -> str:
        return "▲" if menu == name else "▼"

    rating_label = get_content_rating_label(filters)
    rating_text = f"分级:{rating_label}{arrow('rating')}" if rating_label != "全部" else f"分级{arrow('rating')}"

    fmt_value = (filters.get("format") or "").strip().upper()
    fmt_text = f"格式:{fmt_value}{arrow('format')}" if fmt_value else f"格式{arrow('format')}"

    size_range = (filters.get("size_range") or "").strip()
    size_text = f"体积{arrow('size')}" if not size_range or size_range == "all" else f"体积:{size_range}{arrow('size')}"

    words_range = (filters.get("words_range") or "").strip()
    words_text = f"字数{arrow('words')}" if not words_range or words_range == "all" else f"字数:{words_range}{arrow('words')}"

    keyboard.append(
        [
            InlineKeyboardButton(text=rating_text, callback_data="search:filter:rating"),
            InlineKeyboardButton(text=fmt_text, callback_data="search:filter:format"),
            InlineKeyboardButton(text=size_text, callback_data="search:filter:size"),
            InlineKeyboardButton(text=words_text, callback_data="search:filter:words"),
        ]
    )

    def selected_text(is_selected: bool, text: str) -> str:
        return f"✅{text}" if is_selected else text

    if menu == "rating":
        current = (filters.get("content_rating") or "all").strip()
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=selected_text(current == "all", "全部"),
                    callback_data="search:filter:rating:all",
                ),
                InlineKeyboardButton(
                    text=selected_text(current == "safe", "安全🛟"),
                    callback_data="search:filter:rating:safe",
                ),
                InlineKeyboardButton(
                    text=selected_text(current == "adult", "成人🔞"),
                    callback_data="search:filter:rating:adult",
                ),
                InlineKeyboardButton(
                    text=selected_text(current == "unknown", "未知❓"),
                    callback_data="search:filter:rating:unknown",
                ),
            ]
        )

    if menu == "format":
        current = (filters.get("format") or "").strip().lower()
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=selected_text(current == "", "全部"),
                    callback_data="search:filter:format:all",
                ),
                InlineKeyboardButton(
                    text=selected_text(current == "txt", "TXT"),
                    callback_data="search:filter:format:txt",
                ),
                InlineKeyboardButton(
                    text=selected_text(current == "pdf", "PDF"),
                    callback_data="search:filter:format:pdf",
                ),
                InlineKeyboardButton(
                    text=selected_text(current == "epub", "EPUB"),
                    callback_data="search:filter:format:epub",
                ),
            ]
        )
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=selected_text(current == "azw3", "AZW3"),
                    callback_data="search:filter:format:azw3",
                ),
                InlineKeyboardButton(
                    text=selected_text(current == "mobi", "MOBI"),
                    callback_data="search:filter:format:mobi",
                ),
                InlineKeyboardButton(
                    text=selected_text(current == "docx", "DOCX"),
                    callback_data="search:filter:format:docx",
                ),
                InlineKeyboardButton(
                    text=selected_text(current == "rtf", "RTF"),
                    callback_data="search:filter:format:rtf",
                ),
            ]
        )

    if menu == "size":
        current = (filters.get("size_key") or "all").strip()
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=selected_text(current == "all", "全部"),
                    callback_data="search:filter:size:all",
                ),
                InlineKeyboardButton(
                    text=selected_text(current == "lt300k", "300KB以下"),
                    callback_data="search:filter:size:lt300k",
                ),
                InlineKeyboardButton(
                    text=selected_text(current == "300k_1m", "300KB-1MB"),
                    callback_data="search:filter:size:300k_1m",
                ),
            ]
        )
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=selected_text(current == "1m_3m", "1MB-3MB"),
                    callback_data="search:filter:size:1m_3m",
                ),
                InlineKeyboardButton(
                    text=selected_text(current == "3m_8m", "3MB-8MB"),
                    callback_data="search:filter:size:3m_8m",
                ),
                InlineKeyboardButton(
                    text=selected_text(current == "8m_20m", "8MB-20MB"),
                    callback_data="search:filter:size:8m_20m",
                ),
                InlineKeyboardButton(
                    text=selected_text(current == "20m_plus", "20MB以上"),
                    callback_data="search:filter:size:20m_plus",
                ),
            ]
        )

    if menu == "words":
        current = (filters.get("words_key") or "all").strip()
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=selected_text(current == "all", "全部"),
                    callback_data="search:filter:words:all",
                ),
                InlineKeyboardButton(
                    text=selected_text(current == "lt30w", "30万字以下"),
                    callback_data="search:filter:words:lt30w",
                ),
                InlineKeyboardButton(
                    text=selected_text(current == "30w_50w", "30-50万字"),
                    callback_data="search:filter:words:30w_50w",
                ),
            ]
        )
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=selected_text(current == "50w_100w", "50-100万字"),
                    callback_data="search:filter:words:50w_100w",
                ),
                InlineKeyboardButton(
                    text=selected_text(current == "100w_200w", "100-200万字"),
                    callback_data="search:filter:words:100w_200w",
                ),
                InlineKeyboardButton(
                    text=selected_text(current == "200w_plus", "200万字以上"),
                    callback_data="search:filter:words:200w_plus",
                ),
            ]
        )

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

    # 第4/5行：按序号下载（按当前页实际条数生成）
    hits_len = len(response.hits)
    if hits_len > 0:
        row: list[InlineKeyboardButton] = []
        for i in range(1, hits_len + 1):
            row.append(InlineKeyboardButton(text=str(i), callback_data=f"search:dl:{i}"))
            if len(row) == 5:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)

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

    # 排除纯数字（可能是回复其他消息）
    if text.isdigit():
        return

    # 排除太短的文本（可能是误触）
    if len(text) < 2:
        await message.answer("⚠️ 搜索关键词至少需要2个字符")
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
    status_message = await message.answer(f"🔍 正在搜索: <b>{escape_html(query)}</b>...")

    try:
        # 获取搜索服务
        search_service = await get_search_service()

        # 构建筛选条件
        search_filters = SearchFilters()
        if filters.get("format"):
            search_filters.format = filters["format"]
        if filters.get("is_18plus") is not None:
            search_filters.is_18plus = filters["is_18plus"]
        if filters.get("min_size") is not None:
            search_filters.min_size = filters["min_size"]
        if filters.get("max_size") is not None:
            search_filters.max_size = filters["max_size"]
        if filters.get("min_word_count") is not None:
            search_filters.min_word_count = filters["min_word_count"]
        if filters.get("max_word_count") is not None:
            search_filters.max_word_count = filters["max_word_count"]

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

        # 删除"搜索中"消息
        await status_message.delete()

        keyboard = build_search_keyboard(response, user_id, filters)
        if response.total == 0:
            result_message = await message.answer(
                build_no_result_text(filters),
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )
        else:
            result_text = build_search_result_text(response, get_settings().bot_username, filters)
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
        })

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
    message_id = callback.message.message_id
    cache = _search_cache.get(user_id, message_id)
    if not cache:
        await callback.answer("⚠️ 搜索会话已过期，请重新搜索", show_alert=True)
        return

    query = cache["query"]
    filters = cache["filters"]
    prefix_text = cache.get("prefix_text") or ""

    try:
        if action == "page":
            # 翻页
            new_page = int(parts[2])
            await perform_search_edit(
                callback.message,
                query,
                user_id,
                page=new_page,
                filters=filters,
                prefix_text=prefix_text,
            )
            await callback.answer()

        elif action == "filter":
            filter_type = parts[2] if len(parts) > 2 else ""
            option = parts[3] if len(parts) > 3 else None
            await handle_filter_callback(callback, filter_type, option, query, filters, prefix_text)

        elif action == "sort":
            sort_key = parts[2] if len(parts) > 2 else ""
            if sort_key not in {"popular", "newest", "largest"}:
                await callback.answer("⚠️ 无效的排序", show_alert=True)
                return
            filters["sort"] = sort_key
            cache_data = _search_cache.get(user_id, message_id)
            if cache_data:
                cache_data["filters"] = filters
                _search_cache.set(user_id, message_id, cache_data)
            await perform_search_edit(
                callback.message,
                query,
                user_id,
                page=1,
                filters=filters,
                prefix_text=prefix_text,
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
    option: Optional[str],
    query: str,
    current_filters: Dict,
    prefix_text: str = "",
):
    """处理筛选回调"""
    user_id = callback.from_user.id

    menu_key = "_menu"
    if option is None:
        current_menu = (current_filters.get(menu_key) or "").strip()
        current_filters[menu_key] = "" if current_menu == filter_type else filter_type
        message_id = callback.message.message_id
        cache_data = _search_cache.get(user_id, message_id)
        if not cache_data or not cache_data.get("last_response"):
            await callback.answer()
            return
        cache_data["filters"] = current_filters
        _search_cache.set(user_id, message_id, cache_data)
        keyboard = build_search_keyboard(cache_data["last_response"], user_id, current_filters)
        await callback.message.edit_reply_markup(reply_markup=keyboard)
        await callback.answer()
        return

    if filter_type == "rating":
        if option == "safe":
            current_filters["content_rating"] = "safe"
            current_filters["is_18plus"] = False
        elif option == "adult":
            current_filters["content_rating"] = "adult"
            current_filters["is_18plus"] = True
        elif option == "unknown":
            current_filters["content_rating"] = "unknown"
            current_filters["is_18plus"] = None
        else:
            current_filters["content_rating"] = "all"
            current_filters["is_18plus"] = None

    if filter_type == "format":
        if option == "all":
            current_filters["format"] = ""
        else:
            current_filters["format"] = option

    if filter_type == "size":
        kb = 1024
        mb = 1024 * 1024
        key = option
        current_filters["size_key"] = key
        current_filters.pop("min_size", None)
        current_filters.pop("max_size", None)
        if key == "lt300k":
            current_filters["max_size"] = 300 * kb
            current_filters["size_range"] = "300KB以下"
        elif key == "300k_1m":
            current_filters["min_size"] = 300 * kb
            current_filters["max_size"] = 1 * mb
            current_filters["size_range"] = "300KB-1MB"
        elif key == "1m_3m":
            current_filters["min_size"] = 1 * mb
            current_filters["max_size"] = 3 * mb
            current_filters["size_range"] = "1MB-3MB"
        elif key == "3m_8m":
            current_filters["min_size"] = 3 * mb
            current_filters["max_size"] = 8 * mb
            current_filters["size_range"] = "3MB-8MB"
        elif key == "8m_20m":
            current_filters["min_size"] = 8 * mb
            current_filters["max_size"] = 20 * mb
            current_filters["size_range"] = "8MB-20MB"
        elif key == "20m_plus":
            current_filters["min_size"] = 20 * mb
            current_filters["size_range"] = "20MB以上"
        else:
            current_filters["size_key"] = "all"
            current_filters["size_range"] = "all"

    if filter_type == "words":
        key = option
        current_filters["words_key"] = key
        current_filters.pop("min_word_count", None)
        current_filters.pop("max_word_count", None)
        if key == "lt30w":
            current_filters["max_word_count"] = 300_000
            current_filters["words_range"] = "30万字以下"
        elif key == "30w_50w":
            current_filters["min_word_count"] = 300_000
            current_filters["max_word_count"] = 500_000
            current_filters["words_range"] = "30-50万字"
        elif key == "50w_100w":
            current_filters["min_word_count"] = 500_000
            current_filters["max_word_count"] = 1_000_000
            current_filters["words_range"] = "50-100万字"
        elif key == "100w_200w":
            current_filters["min_word_count"] = 1_000_000
            current_filters["max_word_count"] = 2_000_000
            current_filters["words_range"] = "100-200万字"
        elif key == "200w_plus":
            current_filters["min_word_count"] = 2_000_000
            current_filters["words_range"] = "200万字以上"
        else:
            current_filters["words_key"] = "all"
            current_filters["words_range"] = "all"

    current_filters[menu_key] = ""

    # 更新缓存
    message_id = callback.message.message_id
    cache_data = _search_cache.get(user_id, message_id)
    if cache_data:
        cache_data["filters"] = current_filters
        _search_cache.set(user_id, message_id, cache_data)

    # 重新搜索 (回到第1页)
    await perform_search_edit(
        callback.message,
        query,
        user_id,
        page=1,
        filters=current_filters,
        prefix_text=prefix_text,
    )
    await callback.answer()


async def perform_search_edit(
    message,
    query: str,
    user_id: int,
    page: int = 1,
    filters: Optional[Dict] = None,
    prefix_text: str = "",
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
        if filters.get("min_size") is not None:
            search_filters.min_size = filters["min_size"]
        if filters.get("max_size") is not None:
            search_filters.max_size = filters["max_size"]
        if filters.get("min_word_count") is not None:
            search_filters.min_word_count = filters["min_word_count"]
        if filters.get("max_word_count") is not None:
            search_filters.max_word_count = filters["max_word_count"]

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
        message_id = message.message_id
        _search_cache.set(user_id, message_id, {
            "query": query,
            "page": page,
            "filters": filters.copy(),
            "last_response": response,
        })

        keyboard = build_search_keyboard(response, user_id, filters)
        if response.total == 0:
            text = build_no_result_text(filters)
            if prefix_text:
                text = f"{prefix_text}\n{text}"
            await message.edit_text(
                text,
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )
            return

        # 构建结果文本
        result_text = build_search_result_text(response, get_settings().bot_username, filters)
        if prefix_text:
            result_text = f"{prefix_text}\n{result_text}"

        # 构建键盘
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
