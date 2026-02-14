# -*- coding: utf-8 -*-
"""
搜书神器 V2 - 邀请系统处理器
处理 /my 邀请链接命令
"""

import hashlib
from datetime import datetime
from typing import Dict, Optional

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from app.core.config import settings
from app.core.logger import logger

invite_router = Router(name="invite")

# 邀请统计缓存
_invite_stats: Dict[int, dict] = {}


def generate_invite_link(user_id: int) -> str:
    """
    生成用户专属邀请链接

    格式: https://t.me/{bot_username}?start={invite_code}
    邀请码: {user_id}_{hash}
    """
    # 生成邀请码
    hash_input = f"{user_id}:{settings.bot_token[:10]}:{datetime.now().strftime('%Y%m')}"
    hash_value = hashlib.md5(hash_input.encode()).hexdigest()[:8]
    invite_code = f"INV{user_id}{hash_value.upper()}"

    # 生成完整链接
    bot_username = settings.bot_name.replace(" ", "_").lower()
    return f"https://t.me/{bot_username}?start={invite_code}"


def get_invite_stats(user_id: int) -> dict:
    """获取用户邀请统计（模拟数据，实际应从数据库读取）"""
    if user_id not in _invite_stats:
        # 生成模拟数据
        # 实际项目中应该从数据库查询
        _invite_stats[user_id] = {
            "total_invited": 0,  # 累计邀请人数
            "active_users": 0,   # 活跃用户数
            "coins_earned": 0,   # 获得书币奖励
            "this_month": 0,     # 本月邀请
        }
    return _invite_stats[user_id]


@invite_router.message(Command("my"))
async def cmd_my(message: Message):
    """
    处理 /my 邀请链接命令

    功能:
    1. 显示用户专属邀请链接
    2. 显示邀请统计
    3. 提供分享按钮
    """
    user = message.from_user
    user_id = user.id

    # 生成邀请链接
    invite_link = generate_invite_link(user_id)

    # 获取邀请统计
    stats = get_invite_stats(user_id)

    # 构建消息文本
    text = f"""
🔗 <b>我的邀请链接</b>

👤 <b>用户信息</b>
├ 用户名: {user.username or '未设置'}
├ 用户ID: <code>{user_id}</code>
└ 昵称: {user.full_name}

📊 <b>邀请统计</b>
├ 累计邀请: {stats['total_invited']} 人
├ 活跃用户: {stats['active_users']} 人
├ 本月邀请: {stats['this_month']} 人
└ 获得奖励: {stats['coins_earned']} 书币

🔗 <b>您的专属邀请链接</b>
<code>{invite_link}</code>

💡 <b>邀请奖励说明:</b>
• 每成功邀请1位好友，获得 10 书币
• 好友首次上传书籍，额外获得 5 书币
• 无上限，多邀多得！

📱 点击按钮复制链接或立即分享
"""

    # 构建键盘
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📋 复制链接",
                url=f"https://t.me/share/url?url={invite_link}&text=快来加入搜书神器，海量小说免费下载！"
            ),
        ],
        [
            InlineKeyboardButton(text="📢 立即分享", switch_inline_query=""),
        ],
        [
            InlineKeyboardButton(text="📊 详细统计", callback_data="invite:stats"),
            InlineKeyboardButton(text="❓ 奖励说明", callback_data="invite:help"),
        ],
    ])

    await message.answer(text, reply_markup=keyboard)

    logger.info(f"用户 {user_id} 查看了邀请链接")


@invite_router.callback_query(F.data == "invite:stats")
async def on_invite_stats(callback: CallbackQuery):
    """显示详细邀请统计"""
    user_id = callback.from_user.id
    stats = get_invite_stats(user_id)

    text = f"""
📊 <b>详细邀请统计</b>

📈 <b>邀请趋势</b>
├ 累计邀请: {stats['total_invited']} 人
├ 本月新增: {stats['this_month']} 人
└ 活跃占比: {round(stats['active_users'] / stats['total_invited'] * 100) if stats['total_invited'] else 0}%

💰 <b>收益统计</b>
├ 邀请奖励: {stats['coins_earned']} 书币
├ 每用户收益: {round(stats['coins_earned'] / stats['total_invited'], 1) if stats['total_invited'] else 0} 书币
└ 预估月收益: {stats['this_month'] * 10} 书币

💡 更多功能开发中...
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
❓ <b>邀请奖励说明</b>

🎯 <b>如何获得奖励?</b>
1. 分享您的专属邀请链接给好友
2. 好友通过链接注册并加入Bot
3. 您将获得邀请奖励书币

💰 <b>奖励明细</b>
├ 基础邀请奖: 10 书币/人
├ 首次上传奖: 5 书币/人 (好友首次上传)
├ 活跃奖励: 2 书币/天 (好友每日使用)
└ 特别奖励: 100 书币 (邀请满10人)

⚠️ <b>注意事项</b>
• 禁止刷量，违规将封号
• 邀请奖励每日结算
• 书币可用于下载付费书籍
"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ 返回", callback_data="invite:back")],
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@invite_router.callback_query(F.data == "invite:back")
async def on_invite_back(callback: CallbackQuery):
    """返回邀请主页面"""
    # 重新触发 /my 命令
    from aiogram.types import Message

    # 模拟消息对象调用命令
    await cmd_my(callback.message)
    await callback.answer()