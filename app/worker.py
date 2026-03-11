# -*- coding: utf-8 -*-
"""
搜书神器 V2 - arq Worker 入口
基于 arq 的异步任务队列实现
"""

import hashlib
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict

from arq import create_pool
from arq.connections import RedisSettings
from sqlalchemy import select

from app.core.logger import logger
from app.core.database import get_session_factory
from app.core.models import Book, File, User, FileRef, BookStatus, FileFormat, Tag, BookTag
from app.services.metadata import extract_upload_metadata
from app.services.search import get_search_service


@dataclass
class WorkerContext:
    """Worker 上下文"""
    redis: Any
    db: Any


async def startup(ctx: Dict[str, Any]) -> None:
    """Worker 启动时执行"""
    logger.info("Worker 启动中...")
    logger.info("Worker 启动完成")


async def shutdown(ctx: Dict[str, Any]) -> None:
    """Worker 关闭时执行"""
    logger.info("Worker 关闭中...")
    logger.info("Worker 关闭完成")


def _calculate_upload_reward(file_size: int, format_type: str) -> int:
    base_reward = 5
    size_mb = file_size / (1024 * 1024)
    size_reward = min(int(size_mb / 10), 10)
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
    return base_reward + size_reward + format_reward


async def process_file_upload(
    ctx: Dict[str, Any],
    *,
    file_id: str,
    file_name: str,
    file_size: int,
    file_path: str,
    user_id: int,
    chat_id: int,
    message_id: int,
) -> Dict[str, Any]:
    """
    处理文件上传任务（完整链路）
    """
    logger.info(f"开始处理上传任务: file={file_name}, user_id={user_id}")
    temp_file = Path(file_path)

    if not temp_file.exists():
        return {
            "success": False,
            "file_id": file_id,
            "message": "临时文件不存在",
            "book_id": None,
            "is_duplicate": False,
        }

    try:
        file_bytes = temp_file.read_bytes()
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        file_ext = temp_file.suffix.lower().lstrip(".") or "txt"
        metadata = extract_upload_metadata(file_name=file_name, file_ext=file_ext, file_bytes=file_bytes)

        session_factory = get_session_factory()
        async with session_factory() as session:
            db_user = await session.scalar(select(User).where(User.id == user_id))
            if not db_user:
                db_user = User(
                    id=user_id,
                    username=None,
                    first_name="Unknown",
                    last_name=None,
                    coins=0,
                    upload_count=0,
                    download_count=0,
                    search_count=0,
                )
                session.add(db_user)

            db_file = await session.scalar(select(File).where(File.sha256_hash == file_hash))
            if not db_file:
                try:
                    fmt = FileFormat(file_ext)
                except ValueError:
                    fmt = FileFormat.TXT
                db_file = File(
                    sha256_hash=file_hash,
                    size=file_size,
                    extension=file_ext,
                    format=fmt,
                    word_count=metadata.word_count or 0,
                )
                session.add(db_file)
            elif (db_file.word_count or 0) <= 0 and (metadata.word_count or 0) > 0:
                db_file.word_count = metadata.word_count

            existing_ref = await session.scalar(
                select(FileRef).where(FileRef.file_hash == file_hash, FileRef.tg_file_id == file_id)
            )
            if not existing_ref:
                session.add(
                    FileRef(
                        file_hash=file_hash,
                        tg_file_id=file_id,
                        channel_id=chat_id,
                        message_id=message_id,
                        is_primary=True,
                        is_active=True,
                    )
                )

            existing_book = await session.scalar(
                select(Book).where(Book.file_hash == file_hash, Book.status == BookStatus.ACTIVE)
            )

            reward_coins = 0
            is_duplicate = existing_book is not None
            if existing_book:
                target_book = existing_book
            else:
                reward_coins = _calculate_upload_reward(file_size, file_ext)
                target_book = Book(
                    title=metadata.title,
                    author=metadata.author,
                    file_hash=file_hash,
                    uploader_id=user_id,
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
                session.add(target_book)
                await session.flush()
                db_user.coins += reward_coins
                db_user.upload_count += 1

            if metadata.tags:
                existing_tags = (
                    await session.execute(select(Tag).where(Tag.name.in_(metadata.tags)))
                ).scalars().all()
                tag_by_name = {t.name: t for t in existing_tags}
                linked_names = set(
                    (
                        await session.execute(
                            select(Tag.name)
                            .select_from(Tag)
                            .join(BookTag, Tag.id == BookTag.tag_id)
                            .where(BookTag.book_id == target_book.id, Tag.name.in_(metadata.tags))
                        )
                    ).scalars().all()
                )

                for name in metadata.tags:
                    tag = tag_by_name.get(name)
                    if not tag:
                        tag = Tag(name=name, usage_count=0)
                        session.add(tag)
                        await session.flush()
                        tag_by_name[name] = tag
                    if name in linked_names:
                        continue
                    tag.usage_count = int(tag.usage_count or 0) + 1
                    session.add(BookTag(book_id=target_book.id, tag_id=tag.id, added_by=user_id))

            await session.commit()
            await session.refresh(target_book)

            search_service = await get_search_service()
            await search_service.add_document(
                {
                    "id": target_book.id,
                    "title": target_book.title,
                    "author": target_book.author,
                    "format": file_ext,
                    "size": file_size,
                    "word_count": int(db_file.word_count or 0),
                    "rating_score": float(target_book.rating_score or 0.0),
                    "quality_score": float(target_book.quality_score or 0.0),
                    "rating_count": int(target_book.rating_count or 0),
                    "download_count": int(target_book.download_count or 0),
                    "is_18plus": bool(target_book.is_18plus),
                    "is_vip_only": bool(target_book.is_vip_only),
                    "tags": list(metadata.tags or []),
                    "created_at": int(target_book.created_at.timestamp()) if target_book.created_at else 0,
                },
                wait=True,
                timeout_ms=8000,
            )

        logger.info(
            f"上传任务处理成功: file={file_name}, book_id={target_book.id}, duplicate={is_duplicate}, reward={reward_coins}"
        )
        return {
            "success": True,
            "file_id": file_id,
            "message": "处理完成",
            "book_id": target_book.id,
            "is_duplicate": is_duplicate,
        }
    except Exception as e:
        logger.error(f"上传任务处理失败: {e}", exc_info=True)
        return {
            "success": False,
            "file_id": file_id,
            "message": f"处理失败: {str(e)[:120]}",
            "book_id": None,
            "is_duplicate": False,
        }
    finally:
        try:
            temp_file.unlink(missing_ok=True)
        except Exception:
            pass


class WorkerSettings:
    """arq Worker 配置类"""

    redis_settings = RedisSettings(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        database=int(os.getenv("REDIS_DB", "0")),
        password=os.getenv("REDIS_PASSWORD") or None,
    )

    functions = [
        process_file_upload,
    ]

    max_jobs = 10
    job_timeout = 300
    poll_delay = 1.0
    queue_read_limit = 100
    on_startup = startup
    on_shutdown = shutdown


worker_settings = WorkerSettings()


class TaskQueue:
    """任务队列管理类"""

    def __init__(self):
        self.pool = None

    async def connect(self):
        self.pool = await create_pool(worker_settings.redis_settings)
        logger.info("任务队列连接成功")

    async def disconnect(self):
        if self.pool:
            await self.pool.close()
            logger.info("任务队列连接已关闭")

    async def enqueue_upload(
        self,
        file_id: str,
        file_name: str,
        file_size: int,
        file_path: str,
        user_id: int,
        chat_id: int,
        message_id: int,
    ) -> str:
        if not self.pool:
            raise RuntimeError("任务队列未连接")

        job = await self.pool.enqueue_job(
            "process_file_upload",
            file_id=file_id,
            file_name=file_name,
            file_size=file_size,
            file_path=file_path,
            user_id=user_id,
            chat_id=chat_id,
            message_id=message_id,
        )
        logger.info(f"上传任务已加入队列: job_id={job.job_id}, file={file_name}")
        return job.job_id


task_queue = TaskQueue()


async def init_task_queue():
    await task_queue.connect()


async def close_task_queue():
    await task_queue.disconnect()
