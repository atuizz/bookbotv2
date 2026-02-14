# -*- coding: utf-8 -*-
"""
搜书神器 V2 - 设置面板处理器
处理 /settings 设置命令
"""

from typing import Dict, Any
from dataclasses import dataclass, asdict

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from app.core.logger import logger

settings_router = Router(name="settings")


@dataclass
class UserSettings:
    """用户设置数据类"""
    # 内容分级
    content_rating: str = "all"  # all, general, mature, adult

    # 搜索设置
    search_button_mode: str = "preview"  # preview, download
    hide_personal_info: bool = False
    hide_upload_list: bool = False

    # 消息通知
    close_upload_feedback: bool = False
    close_invite_feedback: bool = False
    close_download_feedback: bool = False
    close_book_update_notice: bool = False

    # 界面设置
    theme: str = "default"  # default, dark, light
    language: str = "zh"  # zh, en


# 用户设置缓存 (实际项目中应使用数据库)
_user_settings: Dict[int, UserSettings] = {}


def get_user_settings(user_id: int) -> UserSettings:
    """获取用户设置，如果不存在则创建默认设置"""
    if user_id not in _user_settings:
        _user_settings[user_id] = UserSettings()
    return _user_settings[user_id]


def save_user_settings(user_id: int, settings: UserSettings):
    """保存用户设置"""
    _user_settings[user_id] = settings


@settings_router.message(Command("settings"))
async def cmd_settings(message: Message):
    """
    处理 /settings 设置命令

    显示用户设置面板主菜单
    """
    user_id = message.from_user.id
    settings = get_user_settings(user_id)

    # 构建设置面板文本
    settings_text = f"""
⚙️ <b>全局设置面板</b>

┌─ <b>内容分级</b>
│ 当前: <code>{get_content_rating_name(settings.content_rating)}</code>
│
├─ <b>搜索设置</b>
│ 搜索按钮模式: <code>{get_search_mode_name(settings.search_button_mode)}</code>
│ 隐藏个人信息: <code>{'是' if settings.hide_personal_info else '否'}</code>
│ 隐藏上传列表: <code>{'是' if settings.hide_upload_list else '否'}</code>
│
├─ <b>消息通知</b>
│ 关闭上传反馈: <code>{'是' if settings.close_upload_feedback else '否'}</code>
│ 关闭邀请反馈: <code>{'是' if settings.close_invite_feedback else '否'}</code>
│ 关闭下载反馈: <code>{'是' if settings.close_download_feedback else '否'}</code>
│ 关闭书籍更新通知: <code>{'是' if settings.close_book_update_notice else '否'}</code>
│
└─ <b>界面设置</b>
   主题: <code>{get_theme_name(settings.theme)}</code>
   语言: <code>{get_language_name(settings.language)}</code>

💡 <b>提示:</b> 点击下方按钮快速修改设置
"""

    # 构建设置面板键盘
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔞 内容分级", callback_data="settings:content_rating"),
            InlineKeyboardButton(text="🔍 搜索设置", callback_data="settings:search"),
        ],
        [
            InlineKeyboardButton(text="🔔 消息通知", callback_data="settings:notifications"),
            InlineKeyboardButton(text="🎨 界面设置", callback_data="settings:ui"),
        ],
        [
            InlineKeyboardButton(text="💾 保存并关闭", callback_data="settings:save"),
        ],
    ])

    await message.answer(settings_text, reply_markup=keyboard)


# 辅助函数
def get_content_rating_name(rating: str) -> str:
    """获取内容分级名称"""
    names = {
        "all": "全部",
        "general": "全年龄",
        "mature": "青少年",
        "adult": "成人",
    }
    return names.get(rating, "全部")


def get_search_mode_name(mode: str) -> str:
    """获取搜索模式名称"""
    names = {
        "preview": "预览模式",
        "download": "下载模式",
    }
    return names.get(mode, "预览模式")


def get_theme_name(theme: str) -> str:
    """获取主题名称"""
    names = {
        "default": "默认",
        "dark": "深色",
        "light": "浅色",
    }
    return names.get(theme, "默认")


def get_language_name(lang: str) -> str:
    """获取语言名称"""
    names = {
        "zh": "中文",
        "en": "English",
    }
    return names.get(lang, "中文")


# 回调处理器
@settings_router.callback_query(F.data.startswith("settings:"))
async def on_settings_callback(callback: CallbackQuery):
    """处理设置面板的回调"""
    data = callback.data
    user_id = callback.from_user.id

    action = data.replace("settings:", "")

    if action == "content_rating":
        await show_content_rating_options(callback, user_id)
    elif action == "search":
        await show_search_settings(callback, user_id)
    elif action == "notifications":
        await show_notification_settings(callback, user_id)
    elif action == "ui":
        await show_ui_settings(callback, user_id)
    elif action == "save":
        await save_settings(callback, user_id)
    else:
        await callback.answer("⚠️ 未知的设置选项")


async def show_content_rating_options(callback: CallbackQuery, user_id: int):
    """显示内容分级选项"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="全部", callback_data="rating:all"),
            InlineKeyboardButton(text="全年龄", callback_data="rating:general"),
        ],
        [
            InlineKeyboardButton(text="青少年", callback_data="rating:mature"),
            InlineKeyboardButton(text="成人", callback_data="rating:adult"),
        ],
        [
            InlineKeyboardButton(text="◀️ 返回", callback_data="settings:back"),
        ],
    ])

    await callback.message.edit_text(
        "🔞 <b>内容分级设置</b>\n\n"
        "请选择您要显示的内容分级:\n\n"
        "• <b>全部</b> - 显示所有内容\n"
        "• <b>全年龄</b> - 仅显示适合所有年龄的内容\n"
        "• <b>青少年</b> - 显示适合13岁以上的内容\n"
        "• <b>成人</b> - 仅显示成人内容",
        reply_markup=keyboard
    )
    await callback.answer()


async def show_search_settings(callback: CallbackQuery, user_id: int):
    """显示搜索设置"""
    await callback.message.edit_text(
        "🔍 <b>搜索设置</b>\n\n"
        "搜索设置功能开发中...\n\n"
        "将包含:\n"
        "• 搜索按钮模式 (预览/下载)\n"
        "• 隐藏个人信息\n"
        "• 隐藏上传列表",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ 返回", callback_data="settings:back")]
        ])
    )
    await callback.answer()


async def show_notification_settings(callback: CallbackQuery, user_id: int):
    """显示通知设置"""
    await callback.message.edit_text(
        "🔔 <b>消息通知设置</b>\n\n"
        "通知设置功能开发中...\n\n"
        "将包含:\n"
        "• 关闭上传反馈消息\n"
        "• 关闭邀请反馈消息\n"
        "• 关闭下载反馈消息\n"
        "• 关闭书籍更新通知",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ 返回", callback_data="settings:back")]
        ])
    )
    await callback.answer()


async def show_ui_settings(callback: CallbackQuery, user_id: int):
    """显示界面设置"""
    await callback.message.edit_text(
        "🎨 <b>界面设置</b>\n\n"
        "界面设置功能开发中...\n\n"
        "将包含:\n"
        "• 主题选择 (默认/深色/浅色)\n"
        "• 语言选择 (中文/English)",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ 返回", callback_data="settings:back")]
        ])
    )
    await callback.answer()


async def save_settings(callback: CallbackQuery, user_id: int):
    """保存设置并关闭面板"""
    await callback.message.edit_text(
        "✅ <b>设置已保存</b>\n\n"
        "您的设置已保存并生效。\n"
        "如需再次修改设置，请发送 /settings"
    )
    await callback.answer("✅ 设置已保存")


# 注册回到设置主面板的回调
@settings_router.callback_query(F.data == "settings:back")
async def on_settings_back(callback: CallbackQuery):
    """返回设置主面板"""
    # 重新调用 /settings 命令的处理逻辑
    from app.handlers.settings import cmd_settings

    # 模拟一个消息对象来调用主函数
    # 或者直接重新显示主面板
    await callback.message.edit_text(
        "⚙️ <b>全局设置面板</b>\n\n"
        "⚠️ 设置功能正在开发中...\n\n"
        "可用设置:\n"
        "• 🔞 内容分级\n"
        "• 🔍 搜索设置\n"
        "• 🔔 消息通知\n"
        "• 🎨 界面设置\n\n"
        "💡 点击下方按钮快速修改设置",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🔞 内容分级", callback_data="settings:content_rating"),
                InlineKeyboardButton(text="🔍 搜索设置", callback_data="settings:search"),
            ],
            [
                InlineKeyboardButton(text="🔔 消息通知", callback_data="settings:notifications"),
                InlineKeyboardButton(text="🎨 界面设置", callback_data="settings:ui"),
            ],
            [
                InlineKeyboardButton(text="💾 保存并关闭", callback_data="settings:save"),
            ],
        ])
    )
    await callback.answer()
