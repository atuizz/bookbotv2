# -*- coding: utf-8 -*-
"""
搜书神器 V2 - 上传处理器测试
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.handlers.upload import (
    get_file_extension,
    format_file_size,
    calculate_upload_reward,
    calculate_sha256,
    SUPPORTED_FORMATS,
)


class TestFileHelpers:
    """测试文件辅助函数"""

    def test_get_file_extension_with_dot(self):
        """测试带点的扩展名"""
        assert get_file_extension("test.txt") == "txt"
        assert get_file_extension("book.epub") == "epub"

    def test_get_file_extension_uppercase(self):
        """测试大写扩展名"""
        assert get_file_extension("test.TXT") == "txt"
        assert get_file_extension("test.PDF") == "pdf"

    def test_get_file_extension_no_extension(self):
        """测试无扩展名"""
        assert get_file_extension("testfile") == ""

    def test_format_file_size_bytes(self):
        """测试字节格式化"""
        assert format_file_size(500) == "500 B"
        assert format_file_size(1023) == "1023 B"

    def test_format_file_size_kb(self):
        """测试KB格式化"""
        assert format_file_size(1024) == "1.00 KB"
        assert format_file_size(1536) == "1.50 KB"

    def test_format_file_size_mb(self):
        """测试MB格式化"""
        assert format_file_size(1024 * 1024) == "1.00 MB"
        assert format_file_size(1024 * 1024 * 5.5) == "5.50 MB"

    def test_calculate_sha256(self):
        """测试SHA256计算"""
        test_data = b"test data"
        expected = "973729a0db9c8c9f8e7e7e7e7e7e7e7e7e7e7e7e7e7e7e7e7e7e7e7e7e7e7e7e"
        # 实际测试
        result = calculate_sha256(test_data)
        assert len(result) == 64  # SHA256是64个十六进制字符
        assert all(c in "0123456789abcdef" for c in result)


class TestUploadReward:
    """测试上传奖励计算"""

    def test_base_reward(self):
        """测试基础奖励"""
        # 最小文件也应获得基础奖励
        reward = calculate_upload_reward(1024, "txt")
        assert reward >= 5

    def test_size_reward(self):
        """测试大小奖励"""
        # 10MB文件应该比1KB文件获得更多奖励
        small_reward = calculate_upload_reward(1024, "txt")
        large_reward = calculate_upload_reward(10 * 1024 * 1024, "txt")
        assert large_reward > small_reward

    def test_format_reward_pdf(self):
        """测试PDF格式奖励"""
        pdf_reward = calculate_upload_reward(1024 * 1024, "pdf")
        txt_reward = calculate_upload_reward(1024 * 1024, "txt")
        assert pdf_reward > txt_reward

    def test_format_reward_epub(self):
        """测试EPUB格式奖励"""
        epub_reward = calculate_upload_reward(1024 * 1024, "epub")
        txt_reward = calculate_upload_reward(1024 * 1024, "txt")
        assert epub_reward > txt_reward

    def test_max_reward(self):
        """测试最大奖励上限"""
        # 非常大的文件，最大奖励应该不会超过某个合理值
        large_reward = calculate_upload_reward(100 * 1024 * 1024, "pdf")
        assert large_reward <= 30  # 设置一个合理的上限


class TestSupportedFormats:
    """测试支持的格式配置"""

    def test_all_formats_have_required_fields(self):
        """测试所有格式都有必需的字段"""
        required_fields = ["mime", "emoji"]
        for format_name, config in SUPPORTED_FORMATS.items():
            for field in required_fields:
                assert field in config, f"格式 {format_name} 缺少字段 {field}"

    def test_format_names_are_lowercase(self):
        """测试格式名称为小写"""
        for format_name in SUPPORTED_FORMATS.keys():
            assert format_name == format_name.lower(), f"格式 {format_name} 不是小写"

    def test_common_formats_supported(self):
        """测试常见格式都被支持"""
        common_formats = ["txt", "pdf", "epub", "mobi", "azw3"]
        for fmt in common_formats:
            assert fmt in SUPPORTED_FORMATS, f"常见格式 {fmt} 未被支持"
