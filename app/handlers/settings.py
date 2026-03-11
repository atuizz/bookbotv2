# -*- coding: utf-8 -*-
"""
搜书神器 V2 - 设置面板处理器
处理 /settings 设置命令（数据库持久化）
"""

from dataclasses import dataclass

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select

from app.core.database import get_session_factory
from app.core.models import User, UserSetting

settings_router = Router(name="settings")


@dataclass
class UserSettings:
    content_rating: str = "all"
    search_button_mode: str = "preview"
    hide_personal_info: bool = False
    hide_upload_list: bool = False
    close_upload_feedback: bool = False
    close_invite_feedback: bool = False
    close_download_feedback: bool = False
    close_book_update_notice: bool = False


async def get_user_settings(user_id: int) -> UserSettings:
    session_factory = get_session_factory()
    async with session_factory() as session:
        row = await session.scalar(select(UserSetting).where(UserSetting.user_id == user_id))
        if not row:
            return UserSettings()
        return UserSettings(
            content_rating=row.content_rating,
            search_button_mode=row.search_button_mode,
            hide_personal_info=bool(row.hide_personal_info),
            hide_upload_list=bool(row.hide_upload_list),
            close_upload_feedback=bool(row.close_upload_feedback),
            close_invite_feedback=bool(row.close_invite_feedback),
            close_download_feedback=bool(row.close_download_feedback),
            close_book_update_notice=bool(row.close_book_update_notice),
        )


async def save_user_settings(user_id: int, settings: UserSettings):
    session_factory = get_session_factory()
    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.id == user_id))
        if not user:
            user = User(
                id=user_id,
                username=None,
                first_name="Unknown",
                last_name=None,
                coins=0,
                upload_count=0,
                download_count=0,
                search_count=0,
            )
            session.add(user)
            await session.flush()

        row = await session.scalar(select(UserSetting).where(UserSetting.user_id == user_id))
        if not row:
            row = UserSetting(user_id=user_id)
            session.add(row)
            await session.flush()

        row.content_rating = settings.content_rating
        row.search_button_mode = settings.search_button_mode
        row.hide_personal_info = settings.hide_personal_info
        row.hide_upload_list = settings.hide_upload_list
        row.close_upload_feedback = settings.close_upload_feedback
        row.close_invite_feedback = settings.close_invite_feedback
        row.close_download_feedback = settings.close_download_feedback
        row.close_book_update_notice = settings.close_book_update_notice
        await session.commit()


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
        f"关闭下载反馈消息:{yn(settings.close_download_feedback)}",
        f"关闭书籍动态消息:{yn(settings.close_book_update_notice)}",
    ]
    return "\n".join(lines)


def build_settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="设置内容分级", callback_data="settings:content_rating"),
                InlineKeyboardButton(text="搜索按钮模式", callback_data="settings:search_mode"),
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
                InlineKeyboardButton(text="关闭下载反馈消息", callback_data="settings:toggle:close_download"),
            ],
            [
                InlineKeyboardButton(text="关闭书籍动态消息", callback_data="settings:toggle:close_book_update"),
            ],
        ]
    )


@settings_router.message(Command("settings"))
async def cmd_settings(message: Message):
    user_id = message.from_user.id
    settings = await get_user_settings(user_id)
    await message.answer(render_settings_text(settings), reply_markup=build_settings_keyboard())


def get_content_rating_name(rating: str) -> str:
    names = {
        "all": "全部",
        "general": "全年龄",
        "mature": "青少年",
        "adult": "成人",
    }
    return names.get(rating, "全部")


def get_search_mode_name(mode: str) -> str:
    names = {
        "preview": "预览模式",
        "download": "下载模式",
    }
    return names.get(mode, "预览模式")


@settings_router.callback_query(F.data.startswith("settings:"))
async def on_settings_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    settings = await get_user_settings(user_id)
    action = callback.data.replace("settings:", "")

    if action == "content_rating":
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
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
            ]
        )
        await callback.message.edit_text("请选择内容分级：", reply_markup=keyboard)
        await callback.answer()
        return

    if action.startswith("rating:"):
        settings.content_rating = action.replace("rating:", "")
        await save_user_settings(user_id, settings)
        await callback.message.edit_text(render_settings_text(settings), reply_markup=build_settings_keyboard())
        await callback.answer()
        return

    if action == "search_mode":
        settings.search_button_mode = "download" if settings.search_button_mode == "preview" else "preview"
        await save_user_settings(user_id, settings)
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
        elif key == "close_download":
            settings.close_download_feedback = not settings.close_download_feedback
        elif key == "close_book_update":
            settings.close_book_update_notice = not settings.close_book_update_notice
        await save_user_settings(user_id, settings)
        await callback.message.edit_text(render_settings_text(settings), reply_markup=build_settings_keyboard())
        await callback.answer()
        return

    if action == "back":
        await callback.message.edit_text(render_settings_text(settings), reply_markup=build_settings_keyboard())
        await callback.answer()
        return

    await callback.answer("未知操作", show_alert=True)
