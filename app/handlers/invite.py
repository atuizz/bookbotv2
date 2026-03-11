# -*- coding: utf-8 -*-
"""
搜书神器 V2 - 邀请系统处理器
处理 /my 邀请链接命令与邀请统计（数据库持久化）
"""

import hashlib
from datetime import datetime
from typing import Optional
from urllib.parse import quote

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.core.logger import logger
from app.core.text import escape_html
from app.core.database import get_session_factory
from app.core.models import User, InviteRelation, InviteRewardLog

invite_router = Router(name="invite")


def generate_invite_link(user_id: int) -> str:
    """生成用户专属邀请链接"""
    settings = get_settings()
    hash_input = f"{user_id}:{settings.bot_username}:{datetime.now().strftime('%Y%m')}"
    hash_value = hashlib.md5(hash_input.encode()).hexdigest()[:8]
    invite_code = f"INV{user_id}{hash_value.upper()}"
    bot_username = settings.bot_username.lstrip("@")
    return f"https://t.me/{bot_username}?start={invite_code}"


def parse_invite_code(invite_code: str) -> Optional[int]:
    """
    解析并校验邀请码，返回 inviter_id。
    邀请码格式：INV{inviter_id}{8位hash}
    """
    code = (invite_code or "").strip()
    if not code.startswith("INV") or len(code) <= 11:
        return None

    inviter_part = code[3:-8]
    hash_part = code[-8:].upper()
    if not inviter_part.isdigit():
        return None

    inviter_id = int(inviter_part)
    settings = get_settings()
    expect = hashlib.md5(
        f"{inviter_id}:{settings.bot_username}:{datetime.now().strftime('%Y%m')}".encode()
    ).hexdigest()[:8].upper()
    if expect != hash_part:
        return None
    return inviter_id


async def _ensure_user(
    *,
    user_id: int,
    username: Optional[str],
    first_name: str,
    last_name: Optional[str],
) -> User:
    session_factory = get_session_factory()
    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.id == user_id))
        if user:
            return user

        user = User(
            id=user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            coins=0,
            upload_count=0,
            download_count=0,
            search_count=0,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def bind_invite_relation(
    *,
    inviter_id: int,
    invitee_id: int,
) -> bool:
    """
    绑定邀请关系（只在首次注册/首次绑定时生效）
    返回：是否本次新绑定成功
    """
    if inviter_id <= 0 or invitee_id <= 0 or inviter_id == invitee_id:
        return False

    session_factory = get_session_factory()
    async with session_factory() as session:
        inviter = await session.scalar(select(User).where(User.id == inviter_id))
        invitee = await session.scalar(select(User).where(User.id == invitee_id))
        if not inviter or not invitee:
            return False

        existing = await session.scalar(
            select(InviteRelation).where(InviteRelation.invitee_id == invitee_id)
        )
        if existing:
            return False

        try:
            session.add(InviteRelation(inviter_id=inviter_id, invitee_id=invitee_id))
            inviter.coins += 10
            session.add(
                InviteRewardLog(
                    inviter_id=inviter_id,
                    invitee_id=invitee_id,
                    reward_type="invite_register",
                    coins=10,
                )
            )
            await session.commit()
            return True
        except IntegrityError:
            await session.rollback()
            return False


async def get_invite_stats(user_id: int) -> dict:
    """从数据库获取邀请统计"""
    now = datetime.now()
    month_start = datetime(now.year, now.month, 1)

    session_factory = get_session_factory()
    async with session_factory() as session:
        total_invited = await session.scalar(
            select(func.count()).select_from(InviteRelation).where(InviteRelation.inviter_id == user_id)
        ) or 0

        this_month = await session.scalar(
            select(func.count())
            .select_from(InviteRelation)
            .where(
                InviteRelation.inviter_id == user_id,
                InviteRelation.created_at >= month_start,
            )
        ) or 0

        coins_earned = await session.scalar(
            select(func.coalesce(func.sum(InviteRewardLog.coins), 0))
            .where(InviteRewardLog.inviter_id == user_id)
        ) or 0

        active_users = await session.scalar(
            select(func.count())
            .select_from(InviteRelation)
            .join(User, User.id == InviteRelation.invitee_id)
            .where(
                InviteRelation.inviter_id == user_id,
                (User.upload_count + User.download_count + User.search_count) > 0,
            )
        ) or 0

    return {
        "total_invited": int(total_invited),
        "active_users": int(active_users),
        "coins_earned": int(coins_earned),
        "this_month": int(this_month),
    }


def build_invite_main(user, stats: Optional[dict] = None) -> tuple[str, InlineKeyboardMarkup]:
    user_id = user.id
    invite_link = generate_invite_link(user_id)
    stats = stats or {
        "total_invited": 0,
        "active_users": 0,
        "coins_earned": 0,
        "this_month": 0,
    }

    username = escape_html(user.username or "未设置")
    full_name = escape_html(user.full_name or "")
    safe_invite_link = escape_html(invite_link)

    text = (
        "🔆 <b>我的邀请链接</b>\n\n"
        "👁 <b>用户信息</b>\n"
        f"• 用户名: {username}\n"
        f"• 用户ID: <code>{user_id}</code>\n"
        f"• 昵称: {full_name}\n\n"
        "📳 <b>邀请统计</b>\n"
        f"• 累计邀请: {stats['total_invited']} 人\n"
        f"• 活跃用户: {stats['active_users']} 人\n"
        f"• 本月邀请: {stats['this_month']} 人\n"
        f"• 获得奖励: {stats['coins_earned']} 书币\n\n"
        "🔆 <b>您的专属邀请链接</b>\n"
        f"<code>{safe_invite_link}</code>\n\n"
        "💡 <b>邀请奖励说明</b>\n"
        "• 每成功邀请 1 位好友，获得 10 书币\n"
        "• 奖励实时写入账户余额\n"
    )

    share_url = "https://t.me/share/url?url=" + quote(invite_link, safe="") + "&text=" + quote(
        "快来加入搜书神器，海量小说免费搜索下载！", safe=""
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📵 复制链接", url=share_url)],
            [InlineKeyboardButton(text="📙 立即分享", switch_inline_query="")],
            [
                InlineKeyboardButton(text="📳 详细统计", callback_data="invite:stats"),
                InlineKeyboardButton(text="❔ 奖励说明", callback_data="invite:help"),
            ],
        ]
    )
    return text, keyboard


async def build_invite_main_async(user) -> tuple[str, InlineKeyboardMarkup]:
    """异步版本：从数据库读取统计后构建邀请主页"""
    stats = await get_invite_stats(user.id)
    return build_invite_main(user, stats=stats)


@invite_router.message(Command("my"))
async def cmd_my(message: Message):
    """处理 /my 邀请链接命令"""
    await _ensure_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
    )
    text, keyboard = await build_invite_main_async(message.from_user)
    await message.answer(text, reply_markup=keyboard, disable_web_page_preview=True)
    logger.info(f"用户 {message.from_user.id} 查看了邀请链接")


@invite_router.callback_query(F.data == "invite:stats")
async def on_invite_stats(callback: CallbackQuery):
    """显示详细邀请统计"""
    user_id = callback.from_user.id
    stats = await get_invite_stats(user_id)

    text = f"""
📳 <b>详细邀请统计</b>

📱 <b>邀请趋势</b>
• 累计邀请: {stats['total_invited']} 人
• 本月新增: {stats['this_month']} 人
• 活跃占比: {round(stats['active_users'] / stats['total_invited'] * 100) if stats['total_invited'] else 0}%

💵 <b>收益统计</b>
• 邀请奖励: {stats['coins_earned']} 书币
• 每用户收益: {round(stats['coins_earned'] / stats['total_invited'], 1) if stats['total_invited'] else 0} 书币
• 预估月收益: {stats['this_month'] * 10} 书币
"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ 返回", callback_data="invite:back")],
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@invite_router.callback_query(F.data == "invite:help")
async def on_invite_help(callback: CallbackQuery):
    """显示奖励说明"""
    text = """
❔ <b>邀请奖励说明</b>

🎆 <b>如何获得奖励?</b>
1. 分享您的专属邀请链接给好友
2. 好友通过链接注册并加入Bot
3. 您将获得邀请奖励书币

💵 <b>奖励明细</b>
• 基础邀请奖: 10 书币/人
• 奖励实时结算并入账

⚠️ <b>注意事项</b>
• 禁止刷量，违规将封号
• 邀请奖励仅首次绑定有效
"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ 返回", callback_data="invite:back")],
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@invite_router.callback_query(F.data == "invite:back")
async def on_invite_back(callback: CallbackQuery):
    """返回邀请主页"""
    text, keyboard = await build_invite_main_async(callback.from_user)
    await callback.message.edit_text(text, reply_markup=keyboard, disable_web_page_preview=True)
    await callback.answer()
