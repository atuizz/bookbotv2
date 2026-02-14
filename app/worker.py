# -*- coding: utf-8 -*-
"""
搜书神器 V2 - arq Worker 入口
基于 arq 的异步任务队列实现
"""

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, Optional

from arq import create_pool
from arq.connections import RedisSettings
from arq.worker import Worker

from app.core.config import settings
from app.core.logger import logger


# ============================================
# arq 上下文
# ============================================

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


# ============================================
# 任务定义
# ============================================

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
    处理文件上传任务 (简化版)
    完整版将在后续实现
    """
    logger.info(f"开始处理文件上传: {file_name} (用户: {user_id})")

    result = {
        "success": True,
        "file_id": file_id,
        "message": "文件已加入队列，后台处理中...",
        "book_id": None,
        "is_duplicate": False,
    }

    # TODO: 实现完整的文件处理逻辑

    return result


# ============================================
# arq Worker 配置
# ============================================

class WorkerSettings:
    """arq Worker 配置类"""

    # Redis 连接配置
    redis_settings = RedisSettings(
        host=settings.redis_host,
        port=settings.redis_port,
        database=settings.redis_db,
        password=settings.redis_password or None,
    )

    # 任务函数列表
    functions = [
        process_file_upload,
    ]

    # Worker 配置
    max_jobs = 10  # 并发处理的最大任务数
    job_timeout = 300  # 任务超时时间 (秒)
    poll_delay = 1.0  # 轮询延迟 (秒)
    queue_read_limit = 100  # 每次读取的最大任务数

    # 启动和关闭函数
    on_startup = startup
    on_shutdown = shutdown


# 导出 WorkerSettings 供 arq 命令行使用
worker_settings = WorkerSettings()


# ============================================
# 任务队列操作
# ============================================

class TaskQueue:
    """任务队列管理类"""

    def __init__(self):
        self.redis = None
        self.pool = None

    async def connect(self):
        """连接到 Redis"""
        self.pool = await create_pool(worker_settings.redis_settings)
        logger.info("任务队列连接成功")

    async def disconnect(self):
        """断开 Redis 连接"""
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
        """
        将文件上传任务加入队列

        Returns:
            job_id: 任务ID
        """
        if not self.pool:
            raise RuntimeError("任务队列未连接")

        job = await self.pool.enqueue_job(
            'process_file_upload',
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


# 全局任务队列实例
task_queue = TaskQueue()


async def init_task_queue():
    """初始化任务队列"""
    await task_queue.connect()


async def close_task_queue():
    """关闭任务队列"""
    await task_queue.disconnect()
