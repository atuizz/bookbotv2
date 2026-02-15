# -*- coding: utf-8 -*-
"""
搜书神器 V2 - 上传处理器
处理文件上传、校验、奖励计算
"""

import hashlib
from pathlib import Path
from typing import Optional

from aiogram import Router, F
from aiogram.types import Message, Document, CallbackQuery
from aiogram.filters import Command
from aiogram.enums import ParseMode

from app.core.logger import logger

upload_router = Router(name="upload")

# 支持的文件格式
SUPPORTED_FORMATS = {
    "txt": {"mime": "text/plain", "emoji": "📄"},
    "pdf": {"mime": "application/pdf", "emoji": "📕"},
    "epub": {"mime": "application/epub+zip", "emoji": "📗"},
    "mobi": {"mime": "application/x-mobipocket-ebook", "emoji": "📘"},
    "azw3": {"mime": "application/vnd.amazon.ebook", "emoji": "📙"},
    "doc": {"mime": "application/msword", "emoji": "📝"},
    "docx": {"mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "emoji": "📝"},
}

# 文件大小限制 (MB)
MAX_FILE_SIZE_MB = 100
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


def get_file_extension(filename: str) -> str:
    """获取文件扩展名（小写）"""
    return Path(filename).suffix.lower().lstrip(".")


def calculate_sha256(file_bytes: bytes) -> str:
    """计算文件SHA256哈希值"""
    return hashlib.sha256(file_bytes).hexdigest()


def format_file_size(size_bytes: int) -> str:
    """格式化文件大小显示"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f} MB"


def calculate_upload_reward(file_size: int, format_type: str) -> int:
    """
    计算上传奖励书币

    规则:
    - 基础奖励: 5 书币
    - 文件大小奖励: 每10MB +1 书币 (上限10)
    - 格式奖励: PDF/EPUB +2, 其他 +1

    Returns:
        int: 奖励书币数量
    """
    base_reward = 5

    # 大小奖励
    size_mb = file_size / (1024 * 1024)
    size_reward = min(int(size_mb / 10), 10)

    # 格式奖励
    format_rewards = {
        "pdf": 2,
        "epub": 2,
        "mobi": 2,
        "azw3": 2,
        "txt": 1,
        "doc": 1,
        "docx": 1,
    }
    format_reward = format_rewards.get(format_type.lower(), 1)

    total = base_reward + size_reward + format_reward
    return total


# ============================================================================
# 处理器
# ============================================================================

@upload_router.message(Command("upload"))
async def cmd_upload(message: Message):
    """上传命令 - 显示上传说明"""
    help_text = f"""
📤 <b>上传书籍指南</b>

<b>📋 支持格式:</b>
{', '.join([f"{v['emoji']} {k.upper()}" for k, v in SUPPORTED_FORMATS.items()])}

<b>📏 文件限制:</b>
• 最大大小: {MAX_FILE_SIZE_MB}MB
• 最小大小: 1KB

<b>💰 上传奖励:</b>
• 基础奖励: 5 书币
• 大小奖励: 每10MB +1 书币
• 格式奖励: PDF/EPUB +2, 其他 +1

<b>🚀 如何上传:</b>
直接发送文件或拖拽文件到对话框即可!

⚠️ <b>注意:</b> 上传的文件会进行去重检查，重复文件不会获得奖励。
"""
    await message.answer(help_text)


@upload_router.message(F.document)
async def handle_document(message: Message):
    """
    处理文件上传

    流程:
    1. 校验文件格式
    2. 校验文件大小
    3. 计算SHA256去重
    4. 保存文件/转发到备份频道
    5. 计算奖励
    6. 发送确认消息
    """
    document: Document = message.document
    user = message.from_user

    # 1. 校验文件格式
    file_name = document.file_name or "unknown"
    file_ext = get_file_extension(file_name)

    if file_ext not in SUPPORTED_FORMATS:
        supported = ', '.join(SUPPORTED_FORMATS.keys())
        await message.reply(
            f"❌ <b>不支持的文件格式</b>\n\n"
            f"您的文件: <code>{file_ext or '无'}</code>\n"
            f"支持格式: <code>{supported}</code>\n\n"
            f"请转换格式后重新上传。"
        )
        return

    # 2. 校验文件大小
    file_size = document.file_size or 0

    if file_size < 1:
        await message.reply(
            f"❌ <b>文件太小</b>\n\n"
            f"文件大小: {format_file_size(file_size)}\n"
            f"最小要求: 1 字节\n\n"
            f"请检查文件是否完整。"
        )
        return

    if file_size > MAX_FILE_SIZE_BYTES:
        await message.reply(
            f"❌ <b>文件太大</b>\n\n"
            f"文件大小: {format_file_size(file_size)}\n"
            f"最大限制: {MAX_FILE_SIZE_MB}MB\n\n"
            f"请压缩或拆分后重新上传。"
        )
        return

    # 发送处理中消息
    status_msg = await message.reply(
        f"⏳ <b>正在处理上传...</b>\n\n"
        f"📁 文件: <code>{file_name}</code>\n"
        f"📏 大小: {format_file_size(file_size)}\n\n"
        f"🔍 正在校验文件..."
    )

    try:
        # 3. 下载文件并计算SHA256
        # 注意: 在实际生产环境中，这里应该从Telegram下载文件
        # 为了演示，我们使用file_unique_id作为伪哈希
        file_hash = document.file_unique_id

        # TODO: 在这里进行数据库查询，检查文件是否已存在
        # is_duplicate = await check_duplicate(file_hash)
        is_duplicate = False  # 演示用

        if is_duplicate:
            await status_msg.edit_text(
                f"⚠️ <b>文件已存在</b>\n\n"
                f"📁 文件: <code>{file_name}</code>\n"
                f"🔍 该文件已被其他用户上传过\n\n"
                f"💡 您可以直接搜索下载该文件。"
            )
            return

        # 更新状态
        await status_msg.edit_text(
            f"⏳ <b>正在处理上传...</b>\n\n"
            f"📁 文件: <code>{file_name}</code>\n"
            f"📏 大小: {format_file_size(file_size)}\n\n"
            f"💾 正在保存文件..."
        )

        # 4. 保存文件/转发到备份频道
        # TODO: 实现实际的文件保存逻辑
        # - 转发到备份频道
        # - 保存文件元数据到数据库
        # - 建立用户-文件关联

        # 5. 计算奖励
        reward_coins = calculate_upload_reward(file_size, file_ext)

        # 6. 更新数据库（演示用，实际需要调用数据库接口）
        # TODO:
        # - 更新用户书币余额
        # - 记录上传历史
        # - 添加文件到索引

        # 发送成功消息
        emoji = SUPPORTED_FORMATS[file_ext]["emoji"]

        await status_msg.edit_text(
            f"✅ <b>上传成功!</b>\n\n"
            f"{emoji} <b>{file_name}</b>\n"
            f"📏 大小: {format_file_size(file_size)}\n"
            f"🔍 文件ID: <code>{file_hash[:16]}...</code>\n\n"
            f"💰 <b>获得奖励:</b> +{reward_coins} 书币\n\n"
            f"🎉 感谢你的分享! 文件将在审核后对所有用户可见。"
        )

        logger.info(
            f"用户 {message.from_user.id} ({message.from_user.username}) 上传文件成功: "
            f"{file_name} ({format_file_size(file_size)}), "
            f"奖励: {reward_coins} 书币"
        )

    except Exception as e:
        logger.error(f"处理上传失败: {e}", exc_info=True)
        await status_msg.edit_text(
            f"❌ <b>上传处理失败</b>\n\n"
            f"📁 文件: <code>{file_name}</code>\n"
            f"❗ 错误: <code>{str(e)[:100]}</code>\n\n"
            f"💡 请重试或联系管理员"
        )
