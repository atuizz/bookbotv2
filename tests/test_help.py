# -*- coding: utf-8 -*-

from app.handlers.common import HELP_TEXT, HELP_KEYBOARD


def test_help_text_matches_newbie_guide_screenshot_key_lines():
    assert "搜书神器是一个免费的Telegram机器人" in HELP_TEXT
    assert "<blockquote>TG 最好用的智能搜书机器人</blockquote>" in HELP_TEXT
    assert "新手指南:" in HELP_TEXT
    assert "/s+关键词，搜索书名和作者" in HELP_TEXT
    assert "/ss+关键词，搜索书籍的标签" in HELP_TEXT
    assert "关注BOT频道获取更多信息,有问题找BokFather" in HELP_TEXT
    assert "常用命令 /help /my /book /booklist /info /topuser /review" in HELP_TEXT
    assert "请考虑捐赠以支持我们提供更安全、更稳定、更智能、更丰富的服务。" in HELP_TEXT


def test_help_keyboard_buttons():
    assert HELP_KEYBOARD.inline_keyboard[0][0].text == "邀请书友使用"
    assert HELP_KEYBOARD.inline_keyboard[0][1].text == "捐赠会员计划"

