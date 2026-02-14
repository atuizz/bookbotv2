# -*- coding: utf-8 -*-
"""
搜书神器 V2 - 入群验证处理器
处理 /yanzheng 入群验证码命令
"""

import random
import string
from datetime import datetime, timedelta
from typing import Dict, Optional

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, ChatJoinRequest

from app.core.config import settings
from app.core.logger import logger

group_verify_router = Router(name="group_verify")

# 验证码缓存 (用户ID -> 验证码信息)
_verification_codes: Dict[int, dict] = {}


class VerificationCode:
    """验证码类"""

    def __init__(self, code: str, group_id: int, expires_at: datetime):
        self.code = code
        self.group_id = group_id
        self.expires_at = expires_at
        self.is_used = False

    def is_expired(self) -> bool:
        """检查是否过期"""
        return datetime.now() > self.expires_at


def generate_verification_code(length: int = 6) -> str:
    """生成随机验证码"""
    # 使用数字和大写字母，排除易混淆的字符
    characters = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return ''.join(random.choices(characters, k=length))


@group_verify_router.message(Command("yanzheng"))
async def cmd_yanzheng(message: Message):
    """
    处理 /yanzheng 入群验证码命令

    用法:
    1. /yanzheng - 获取新的验证码
    2. /yanzheng <验证码> - 验证验证码
    """
    user_id = message.from_user.id
    args = message.text.split(maxsplit=1)

    # 如果没有参数，生成新验证码
    if len(args) < 2:
        await generate_new_code(message, user_id)
        return

    # 验证用户输入的验证码
    input_code = args[1].strip().upper()
    await verify_code(message, user_id, input_code)


async def generate_new_code(message: Message, user_id: int):
    """生成新的验证码"""
    # 清理过期的验证码
    cleanup_expired_codes()

    # 生成新验证码
    code = generate_verification_code(6)

    # 设置过期时间（5分钟）
    expires_at = datetime.now() + timedelta(minutes=5)

    # 存储验证码
    _verification_codes[user_id] = {
        "code": code,
        "expires_at": expires_at,
        "is_used": False
    }

    # 发送验证码给用户
    await message.answer(
        f"🔐 <b>入群验证码</b>\n\n"
        f"您的验证码: <code>{code}</code>\n\n"
        f"⏰ 有效期: 5 分钟\n"
        f"💡 使用方法: 将验证码发送给群验证机器人\n\n"
        f"如需重新获取验证码，请再次发送 /yanzheng",
        protect_content=True  # 保护内容，防止转发
    )

    logger.info(f"用户 {user_id} 获取了新的入群验证码: {code}")


async def verify_code(message: Message, user_id: int, input_code: str):
    """验证用户输入的验证码"""
    # 检查是否有验证码记录
    if user_id not in _verification_codes:
        await message.answer(
            "❌ <b>验证失败</b>\n\n"
            "您还没有获取验证码，或者验证码已过期。\n"
            "请发送 /yanzheng 获取新的验证码。"
        )
        return

    user_code_info = _verification_codes[user_id]

    # 检查验证码是否已过期
    if datetime.now() > user_code_info["expires_at"]:
        await message.answer(
            "❌ <b>验证码已过期</b>\n\n"
            "验证码有效期为5分钟。\n"
            "请发送 /yanzheng 获取新的验证码。"
        )
        # 删除过期的验证码
        del _verification_codes[user_id]
        return

    # 检查验证码是否已使用
    if user_code_info["is_used"]:
        await message.answer(
            "❌ <b>验证码已使用</b>\n\n"
            "每个验证码只能使用一次。\n"
            "请发送 /yanzheng 获取新的验证码。"
        )
        return

    # 验证验证码是否正确
    if input_code == user_code_info["code"]:
        # 验证成功
        user_code_info["is_used"] = True

        await message.answer(
            "✅ <b>验证成功！</b>\n\n"
            "您的验证码已通过验证。\n"
            "现在您可以加入群组了。\n\n"
            "💡 提示: 每个验证码只能使用一次，请尽快加入群组。"
        )

        logger.info(f"用户 {user_id} 成功验证了验证码")
    else:
        await message.answer(
            "❌ <b>验证码错误</b>\n\n"
            "您输入的验证码不正确。\n"
            f"输入: <code>{input_code}</code>\n\n"
            "请检查验证码是否正确，或发送 /yanzheng 获取新的验证码。"
        )


def cleanup_expired_codes():
    """清理过期的验证码"""
    global _verification_codes
    current_time = datetime.now()
    expired_users = [
        user_id for user_id, code_info in _verification_codes.items()
        if current_time > code_info["expires_at"]
    ]
    for user_id in expired_users:
        del _verification_codes[user_id]
    if expired_users:
        logger.info(f"清理了 {len(expired_users)} 个过期的验证码")


@group_verify_router.message(Command("code_status"))
async def cmd_code_status(message: Message):
    """
    查看验证码系统状态（管理员命令）
    """
    user_id = message.from_user.id

    # TODO: 添加管理员权限检查
    # if not is_admin(user_id):
    #     await message.answer("❌ 您没有权限执行此命令")
    #     return

    total_codes = len(_verification_codes)
    used_codes = sum(1 for info in _verification_codes.values() if info["is_used"])
    expired_codes = sum(
        1 for info in _verification_codes.values()
        if datetime.now() > info["expires_at"]
    )

    await message.answer(
        f"📊 <b>验证码系统状态</b>\n\n"
        f"总验证码数: {total_codes}\n"
        f"已使用: {used_codes}\n"
        f"未使用: {total_codes - used_codes}\n"
        f"已过期: {expired_codes}\n\n"
        f"验证码有效期: 5 分钟\n"
        f"验证码长度: 6 位（数字+大写字母）"
    )
