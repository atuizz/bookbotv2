# -*- coding: utf-8 -*-
"""
搜书神器 V2 - 设置面板处理器
处理 /settings 设置命令
"""

from typing import Dict
from dataclasses import dataclass

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

settings_router = Router(name="settings")


@dataclass
class UserSettings:
    """用户设置数据类"""
    content_rating: str = "all"  # all, general, mature, adult
    search_button_mode: str = "minimal"  # minimal, classic
    hide_personal_info: bool = False
    hide_upload_list: bool = False
    close_upload_feedback: bool = False
    close_invite_feedback: bool = False
    close_book_update_notice: bool = False


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


def render_settings_text(settings: UserSettings) -> str:
    yn = lambda v: "是" if v else "否"
    lines = [
        f"全局内容分级:{get_content_rating_name(settings.content_rating)}",
        f"搜索按钮模式:{get_search_mode_name(settings.search_button_mode)}",
        f"隐藏个人信息:{yn(settings.hide_personal_info)}",
        f"隐藏上传列表:{yn(settings.hide_upload_list)}",
        "",
        f"关闭上传反馈消息:{yn(settings.close_upload_feedback)}",
        f"关闭邀请反馈消息:{yn(settings.close_invite_feedback)}",
        f"关闭书籍动态消息:{yn(settings.close_book_update_notice)}",
    ]
    return "\n".join(lines)


def build_settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="设置内容分级", callback_data="settings:content_rating"),
            InlineKeyboardButton(text="搜索按钮模式", callback_data="settings:search_mode"),
        ],
        [
            InlineKeyboardButton(text="添加屏蔽标签", callback_data="settings:block_add"),
            InlineKeyboardButton(text="删除屏蔽标签", callback_data="settings:block_del"),
        ],
        [
            InlineKeyboardButton(text="隐藏个人信息", callback_data="settings:toggle:hide_personal"),
            InlineKeyboardButton(text="隐藏上传列表", callback_data="settings:toggle:hide_upload_list"),
        ],
        [
            InlineKeyboardButton(text="关闭上传反馈消息", callback_data="settings:toggle:close_upload"),
            InlineKeyboardButton(text="关闭邀请反馈消息", callback_data="settings:toggle:close_invite"),
        ],
        [
            InlineKeyboardButton(text="关闭书籍动态消息", callback_data="settings:toggle:close_book_update"),
        ],
    ])


@settings_router.message(Command("settings"))
async def cmd_settings(message: Message):
    """
    处理 /settings 设置命令

    显示用户设置面板主菜单
    """
    user_id = message.from_user.id
    settings = get_user_settings(user_id)
    await message.answer(render_settings_text(settings), reply_markup=build_settings_keyboard())


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
        "minimal": "极简模式",
        "classic": "传统模式",
    }
    return names.get(mode, "极简模式")


# 回调处理器
@settings_router.callback_query(F.data.startswith("settings:"))
async def on_settings_callback(callback: CallbackQuery):
    """处理设置面板的回调"""
    user_id = callback.from_user.id
    settings = get_user_settings(user_id)
    action = callback.data.replace("settings:", "")

    if action == "content_rating":
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="全部", callback_data="settings:rating:all"),
                InlineKeyboardButton(text="全年龄", callback_data="settings:rating:general"),
            ],
            [
                InlineKeyboardButton(text="青少年", callback_data="settings:rating:mature"),
                InlineKeyboardButton(text="成人", callback_data="settings:rating:adult"),
            ],
            [
                InlineKeyboardButton(text="◀️ 返回", callback_data="settings:back"),
            ],
        ])
        await callback.message.edit_text("请选择内容分级：", reply_markup=keyboard)
        await callback.answer()
        return

    if action.startswith("rating:"):
        settings.content_rating = action.replace("rating:", "")
        save_user_settings(user_id, settings)
        await callback.message.edit_text(render_settings_text(settings), reply_markup=build_settings_keyboard())
        await callback.answer()
        return

    if action == "search_mode":
        settings.search_button_mode = "classic" if settings.search_button_mode == "minimal" else "minimal"
        save_user_settings(user_id, settings)
        await callback.message.edit_text(render_settings_text(settings), reply_markup=build_settings_keyboard())
        await callback.answer()
        return

    if action.startswith("toggle:"):
        key = action.replace("toggle:", "")
        if key == "hide_personal":
            settings.hide_personal_info = not settings.hide_personal_info
        elif key == "hide_upload_list":
            settings.hide_upload_list = not settings.hide_upload_list
        elif key == "close_upload":
            settings.close_upload_feedback = not settings.close_upload_feedback
        elif key == "close_invite":
            settings.close_invite_feedback = not settings.close_invite_feedback
        elif key == "close_book_update":
            settings.close_book_update_notice = not settings.close_book_update_notice
        save_user_settings(user_id, settings)
        await callback.message.edit_text(render_settings_text(settings), reply_markup=build_settings_keyboard())
        await callback.answer()
        return

    if action in {"block_add", "block_del"}:
        await callback.answer("功能开发中...", show_alert=True)
        return

    if action == "back":
        await callback.message.edit_text(render_settings_text(settings), reply_markup=build_settings_keyboard())
        await callback.answer()
        return

    await callback.answer("⚠️ 未知操作", show_alert=True)
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
