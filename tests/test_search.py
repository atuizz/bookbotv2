# -*- coding: utf-8 -*-
"""
搜书神器 V2 - 搜索处理器测试
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.handlers.search import (
    build_search_result_text,
    build_search_keyboard,
    build_no_result_text,
    format_size,
    format_word_count,
    get_rating_stars,
    FORMAT_EMOJI,
)
from app.services.search import SearchResponse, SearchResult


class TestFormatHelpers:
    """测试格式化辅助函数"""

    def test_format_size_bytes(self):
        """测试字节格式化"""
        assert format_size(500) == "500B"
        assert format_size(1023) == "1023B"

    def test_format_size_kb(self):
        """测试KB格式化"""
        assert format_size(1024) == "1KB"
        assert format_size(1536) == "1.5KB"
        assert format_size(1024 * 512) == "512KB"

    def test_format_size_mb(self):
        """测试MB格式化"""
        assert format_size(1024 * 1024) == "1MB"
        assert format_size(1024 * 1024 * 5.5) == "5.5MB"

    def test_format_word_count_small(self):
        """测试小字数格式化"""
        assert format_word_count(9999) == "9999"
        assert format_word_count(500) == "500"

    def test_format_word_count_wan(self):
        """测试万字格式化"""
        assert format_word_count(10000) == "1.0万"
        assert format_word_count(15000) == "1.5万"
        assert format_word_count(99999999) == "9999.9万"

    def test_format_word_count_yi(self):
        """测试亿字格式化"""
        assert format_word_count(100000000) == "1.0亿"
        assert format_word_count(150000000) == "1.5亿"

    def test_get_rating_stars(self):
        """测试评分星星显示"""
        assert "★" in get_rating_stars(10)
        assert "☆" in get_rating_stars(0)
        # 8分应该显示4个满星
        stars_8 = get_rating_stars(8)
        assert stars_8.count("★") == 4


class TestBuildSearchResultText:
    """测试结果文本构建"""

    @pytest.fixture
    def mock_search_result(self):
        """创建模拟搜索结果"""
        return SearchResult(
            id=1,
            title="测试书名",
            author="测试作者",
            format="txt",
            size=1024 * 500,  # 500KB
            word_count=50000,  # 5万字
            rating_score=8.5,
            quality_score=85.0,
            rating_count=100,
            download_count=1000,
            is_18plus=False,
            tags=["tag1", "tag2"],
        )

    @pytest.fixture
    def mock_response(self, mock_search_result):
        """创建模拟搜索响应"""
        return SearchResponse(
            hits=[mock_search_result],
            total=1,
            page=1,
            per_page=10,
            total_pages=1,
            query="测试",
            processing_time_ms=50,
        )

    def test_result_contains_header(self, mock_response):
        """测试结果包含头部信息"""
        text = build_search_result_text(mock_response)
        assert "🔍" in text
        assert "测试" in text
        assert "Results" in text
        assert "1-1 of 1" in text

    def test_result_contains_book_info(self, mock_response):
        """测试结果包含书籍信息"""
        text = build_search_result_text(mock_response)
        assert "<code>01.</code>" in text
        assert "测试书名" in text
        assert "📄" in text  # TXT格式Emoji
        assert "TXT" in text  # 格式大写
        assert "500KB" in text  # 大小

    def test_result_with_18plus_flag(self, mock_response):
        """测试成人内容标记"""
        mock_response.hits[0].is_18plus = True
        mock_response.hits[0].title = "成人书名"
        text = build_search_result_text(mock_response)
        assert "🔞" in text

    def test_result_escapes_html(self, mock_response):
        mock_response.query = "<b>Q</b>"
        mock_response.hits[0].title = "<i>T</i>"
        text = build_search_result_text(mock_response)
        assert "<b>Q</b>" not in text
        assert "&lt;b&gt;Q&lt;/b&gt;" in text
        assert "<i>T</i>" not in text
        assert "&lt;i&gt;T&lt;/i&gt;" in text


class TestBuildSearchKeyboard:
    """测试搜索键盘构建"""

    @pytest.fixture
    def mock_response(self):
        """创建模拟搜索响应"""
        from app.services.search import SearchResponse, SearchResult

        hits = []
        for i in range(5):
            hits.append(SearchResult(
                id=i+1,
                title=f"书名{i+1}",
                author=f"作者{i+1}",
                format="txt",
                size=1024,
                word_count=10000,
                rating_score=8.0,
                quality_score=80.0,
                rating_count=10,
                download_count=100,
                is_18plus=False,
                tags=[],
            ))

        return SearchResponse(
            hits=hits,
            total=50,
            page=1,
            per_page=10,
            total_pages=5,
            query="测试",
            processing_time_ms=50,
        )

    def test_keyboard_has_pagination(self, mock_response):
        """测试键盘有分页按钮"""
        keyboard = build_search_keyboard(mock_response, user_id=123)

        # 检查是否有分页数字按钮
        has_number_buttons = False
        for row in keyboard.inline_keyboard:
            for btn in row:
                if btn.text.isdigit():
                    has_number_buttons = True
                    break
        assert has_number_buttons, "键盘应该有数字分页按钮"

    def test_keyboard_has_navigation(self, mock_response):
        """测试键盘有导航按钮"""
        keyboard = build_search_keyboard(mock_response, user_id=123)

        # 检查是否有上一页/下一页按钮
        all_texts = []
        for row in keyboard.inline_keyboard:
            for btn in row:
                all_texts.append(btn.text)

        # 应该包含页码选择按钮
        assert any(("∨" in text) or text.isdigit() or text.startswith("...") for text in all_texts), "键盘应该显示页码"

    def test_keyboard_has_filters(self, mock_response):
        """测试键盘有筛选按钮"""
        keyboard = build_search_keyboard(mock_response, user_id=123)

        # 检查筛选相关按钮
        all_texts = []
        for row in keyboard.inline_keyboard:
            for btn in row:
                all_texts.append(btn.text)

        # 应该包含筛选相关按钮
        filter_keywords = ["分级", "格式", "体积", "字数", "最热", "最新", "最大"]
        has_filter = any(
            any(kw in text for kw in filter_keywords)
            for text in all_texts
        )
        assert has_filter, "键盘应该有筛选按钮"

    def test_keyboard_download_buttons_match_hits(self, mock_response):
        keyboard = build_search_keyboard(mock_response, user_id=123)
        dl_buttons = [
            btn
            for row in keyboard.inline_keyboard
            for btn in row
            if (btn.callback_data or "").startswith("search:dl:")
        ]
        assert [b.text for b in dl_buttons] == ["1", "2", "3", "4", "5"]

    def test_no_result_keyboard_has_no_download_buttons(self):
        response = SearchResponse(
            hits=[],
            total=0,
            page=1,
            per_page=10,
            total_pages=0,
            query="测试",
            processing_time_ms=1,
        )
        keyboard = build_search_keyboard(response, user_id=123, filters={})
        digit_buttons = [btn for row in keyboard.inline_keyboard for btn in row if btn.text.isdigit()]
        assert digit_buttons == []

    def test_keyboard_format_menu(self, mock_response):
        keyboard = build_search_keyboard(
            mock_response,
            user_id=123,
            filters={"_menu": "format", "format": "pdf"},
        )
        texts = [btn.text for row in keyboard.inline_keyboard for btn in row]
        assert "✅PDF" in texts
        assert "TXT" in texts

    def test_keyboard_size_menu(self, mock_response):
        keyboard = build_search_keyboard(
            mock_response,
            user_id=123,
            filters={"_menu": "size", "size_key": "1m_3m", "size_range": "1MB-3MB"},
        )
        texts = [btn.text for row in keyboard.inline_keyboard for btn in row]
        assert "✅1MB-3MB" in texts
        assert "300KB以下" in texts

    def test_no_result_text_contains_rating(self):
        assert "内容分级:全部" in build_no_result_text({})

    def test_no_result_text_contains_adult_rating(self):
        assert "内容分级:成人" in build_no_result_text({"content_rating": "adult"})

    def test_no_result_text_compat_with_legacy_teen_value(self):
        assert "内容分级:成人" in build_no_result_text({"content_rating": "teen"})


# ============================================================================
# 集成测试 (需要外部服务)
# ============================================================================

@pytest.mark.skip(reason="需要Meilisearch服务")
class TestSearchIntegration:
    """搜索集成测试"""

    @pytest.mark.asyncio
    async def test_real_search(self):
        """测试真实搜索"""
        from app.services.search import get_search_service

        service = await get_search_service()
        response = await service.search("测试", page=1, per_page=5)

        assert response is not None
        assert isinstance(response.total, int)
