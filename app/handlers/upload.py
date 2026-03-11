# -*- coding: utf-8 -*-
"""
搜书神器 V2 - 上传处理器
处理文件上传、校验、奖励计算
"""

import hashlib
from io import BytesIO
from pathlib import Path
from typing import Optional

from aiogram import Router, F
from aiogram.types import Message, Document, CallbackQuery
from aiogram.filters import Command
from aiogram.enums import ParseMode
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logger import logger
from app.core.database import get_session_factory
from app.core.models import Book, File, User, FileRef, BookStatus, FileFormat, Tag, BookTag
from app.core.text import escape_html
from app.services.metadata import extract_upload_metadata
from app.services.search import get_search_service
from app.worker import task_queue

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
    safe_file_name = escape_html(file_name)
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

    status_msg = await message.reply(
        f"文件：{safe_file_name}\n"
        f"大小：{format_file_size(file_size)}\n"
        f"状态：加入队列，等待收录\n\n"
        f"排队(1) 成功(0) 失败(0)\n"
        f"发送 /info 查看书库统计和上传进度"
    )

    try:
        await status_msg.edit_text(
            f"文件：{safe_file_name}\n"
            f"大小：{format_file_size(file_size)}\n"
            f"状态：正在收录，请稍候...\n\n"
            f"排队(1) 成功(0) 失败(0)\n"
            f"发送 /info 查看书库统计和上传进度"
        )

        buffer = BytesIO()
        await message.bot.download(document, destination=buffer)
        file_bytes = buffer.getvalue()
        file_hash = calculate_sha256(file_bytes)
        metadata = extract_upload_metadata(file_name=file_name, file_ext=file_ext, file_bytes=file_bytes)
        try:
            tags_preview = ",".join((metadata.tags or [])[:10])
            logger.info(
                f"上传元数据解析: ext={file_ext} title={metadata.title} author={metadata.author} "
                f"tags={len(metadata.tags or [])} [{tags_preview}]"
            )
        except Exception:
            pass

        settings = get_settings()
        if settings.upload_async_enabled:
            settings.temp_dir.mkdir(parents=True, exist_ok=True)
            temp_path = settings.temp_dir / f"upload_{user.id}_{message.message_id}_{file_hash[:8]}.{file_ext}"
            temp_path.write_bytes(file_bytes)

            if not task_queue.pool:
                await task_queue.connect()

            job_id = await task_queue.enqueue_upload(
                file_id=document.file_id,
                file_name=file_name,
                file_size=file_size,
                file_path=str(temp_path),
                user_id=user.id,
                chat_id=message.chat.id,
                message_id=message.message_id,
            )
            await status_msg.edit_text(
                f"文件：{safe_file_name}\n"
                f"大小：{format_file_size(file_size)}\n"
                f"状态：已进入后台队列，等待处理\n\n"
                f"任务ID：<code>{job_id}</code>\n"
                f"队列(1) 成功(0) 失败(0)\n"
                f"发送 /info 查看书库统计和上传进度"
            )
            return

        # 更新状态
        await status_msg.edit_text(
            f"⏳ <b>正在处理上传...</b>\n\n"
            f"📁 文件: <code>{safe_file_name}</code>\n"
            f"📏 大小: {format_file_size(file_size)}\n\n"
            f"💾 正在保存文件..."
        )

        # 4. 保存文件/转发到备份频道
        # 获取数据库会话
        session_factory = get_session_factory()
        async with session_factory() as session:
            # 4.1 检查/创建用户
            stmt = select(User).where(User.id == user.id)
            result = await session.execute(stmt)
            db_user = result.scalar_one_or_none()
            
            if not db_user:
                db_user = User(
                    id=user.id,
                    username=user.username,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    coins=0,
                    upload_count=0
                )
                session.add(db_user)
            
            # 4.2 检查/创建文件
            stmt = select(File).where(File.sha256_hash == file_hash)
            result = await session.execute(stmt)
            db_file = result.scalar_one_or_none()
            
            if not db_file:
                # 尝试匹配格式枚举
                try:
                    fmt = FileFormat(file_ext)
                except ValueError:
                    fmt = FileFormat.TXT
                
                db_file = File(
                    sha256_hash=file_hash,
                    size=file_size,
                    extension=file_ext,
                    format=fmt,
                    word_count=metadata.word_count or 0
                )
                session.add(db_file)
            else:
                if (db_file.word_count or 0) <= 0 and (metadata.word_count or 0) > 0:
                    db_file.word_count = metadata.word_count
            
            # 4.3 创建文件引用
            # 检查是否已存在引用
            stmt = select(FileRef).where(
                FileRef.file_hash == file_hash,
                FileRef.tg_file_id == document.file_id
            )
            result = await session.execute(stmt)
            if not result.scalar_one_or_none():
                file_ref = FileRef(
                    file_hash=file_hash,
                    tg_file_id=document.file_id,
                    is_primary=True,
                    is_active=True
                )
                session.add(file_ref)

            if settings.backup_channel_id:
                try:
                    forwarded = await message.bot.forward_message(
                        chat_id=settings.backup_channel_id,
                        from_chat_id=message.chat.id,
                        message_id=message.message_id,
                    )
                    if forwarded.document:
                        stmt = select(FileRef).where(
                            FileRef.file_hash == file_hash,
                            FileRef.channel_id == settings.backup_channel_id,
                        )
                        result = await session.execute(stmt)
                        if not result.scalar_one_or_none():
                            backup_ref = FileRef(
                                file_hash=file_hash,
                                tg_file_id=forwarded.document.file_id,
                                channel_id=settings.backup_channel_id,
                                message_id=forwarded.message_id,
                                is_primary=False,
                                is_backup=True,
                                is_active=True,
                            )
                            session.add(backup_ref)
                except Exception as e:
                    logger.warning(f"备份转发失败: {e}")

            stmt = select(Book).where(
                Book.file_hash == file_hash,
                Book.status == BookStatus.ACTIVE,
            )
            result = await session.execute(stmt)
            existing_book = result.scalars().first()
            
            # 5. 计算奖励
            reward_coins = 0
            new_book = None
            if existing_book:
                new_book = existing_book
            else:
                reward_coins = calculate_upload_reward(file_size, file_ext)
                new_book = Book(
                    title=metadata.title,
                    author=metadata.author,
                    file_hash=file_hash,
                    uploader_id=user.id,
                    status=BookStatus.ACTIVE,
                    is_original=False,
                    is_18plus=False,
                    is_vip_only=False,
                    description=metadata.description,
                    rating_score=0.0,
                    quality_score=0.0,
                    rating_count=0,
                    download_count=0,
                )
                session.add(new_book)
                await session.flush()

                db_user.coins += reward_coins
                db_user.upload_count += 1

            if metadata.tags:
                existing_linked_names = set(
                    (
                        await session.execute(
                            select(Tag.name)
                            .select_from(Tag)
                            .join(BookTag, Tag.id == BookTag.tag_id)
                            .where(
                                BookTag.book_id == new_book.id,
                                Tag.name.in_(metadata.tags),
                            )
                        )
                    ).scalars().all()
                )
                existing_tags = (
                    await session.execute(select(Tag).where(Tag.name.in_(metadata.tags)))
                ).scalars().all()
                tag_by_name = {t.name: t for t in existing_tags}
                for name in metadata.tags:
                    tag = tag_by_name.get(name)
                    if not tag:
                        tag = Tag(name=name, usage_count=0)
                        session.add(tag)
                        await session.flush()
                        tag_by_name[name] = tag
                    if name in existing_linked_names:
                        continue
                    tag.usage_count = int(tag.usage_count or 0) + 1
                    session.add(BookTag(book_id=new_book.id, tag_id=tag.id, added_by=user.id))
            
            # 提交事务
            await session.commit()
            await session.refresh(new_book)
            
            # 7. 添加到搜索索引
            search_service = await get_search_service()
            index_ok = await search_service.add_document(
                {
                    "id": new_book.id,
                    "title": new_book.title,
                    "author": new_book.author,
                    "format": file_ext,
                    "size": file_size,
                    "word_count": db_file.word_count if db_file else 0,
                    "rating_score": float(new_book.rating_score or 0.0),
                    "quality_score": float(new_book.quality_score or 0.0),
                    "rating_count": int(new_book.rating_count or 0),
                    "download_count": int(new_book.download_count or 0),
                    "is_18plus": bool(new_book.is_18plus),
                    "is_vip_only": bool(new_book.is_vip_only),
                    "tags": list(metadata.tags or []),
                    "created_at": int(new_book.created_at.timestamp()) if new_book.created_at else 0,
                },
                wait=True,
                timeout_ms=8000,
            )

        # 发送成功消息
        emoji = SUPPORTED_FORMATS[file_ext]["emoji"]

        if reward_coins == 0 and existing_book:
            await status_msg.edit_text(
                f"文件：{safe_file_name}\n"
                f"大小：{format_file_size(file_size)}\n"
                f"状态：文件已存在，已跳过收录\n\n"
                f"排队(0) 成功(1) 失败(0)\n"
                f"发送 /info 查看书库统计和上传进度"
            )
        else:
            status = "收录成功" if index_ok else "已入库，索引稍后补建后即可搜索"
            await status_msg.edit_text(
                f"文件：{safe_file_name}\n"
                f"大小：{format_file_size(file_size)}\n"
                f"状态：{status}\n\n"
                f"排队(0) 成功(1) 失败(0)\n"
                f"发送 /info 查看书库统计和上传进度"
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
            f"📁 文件: <code>{safe_file_name}</code>\n"
            f"❗ 错误: <code>{str(e)[:100]}</code>\n\n"
            f"💡 请重试或联系管理员"
        )
