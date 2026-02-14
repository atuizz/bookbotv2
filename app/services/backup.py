# -*- coding: utf-8 -*-
"""
搜书神器 V2 - 备份服务 (重构版)

核心理解:
1. file_id 是与上下文绑定的，不同聊天、不同Bot的file_id都不同
2. 用户上传文件给Bot，获取file_id_A（Bot-用户私聊上下文）
3. 转发到备份频道，获取file_id_B（Bot-备份频道上下文）
4. 给用户发送文件时，只能用file_id_A或从备份频道转发

备份策略:
1. 用户上传 → 立即转发到备份频道
2. 保存两个file_id: original(用户私聊) 和 backup(备份频道)
3. 发送给用户时优先用original，失效则从备份转发
"""

import hashlib
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Union

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import Document, Message

from app.core.config import get_settings
from app.core.logger import logger


@dataclass
class FileLocation:
    """文件位置信息"""
    file_id: str
    chat_id: int
    message_id: Optional[int] = None
    file_unique_id: Optional[str] = None

    def is_valid(self) -> bool:
        """检查位置信息是否完整"""
        return bool(self.file_id and self.chat_id)


@dataclass
class BackupRecord:
    """备份记录数据类 (重构版)"""

    # 文件基本信息
    sha256_hash: str
    file_name: str
    file_size: int
    mime_type: Optional[str] = None

    # 文件位置信息
    original_location: Optional[FileLocation] = None  # 用户私聊位置
    backup_location: Optional[FileLocation] = None     # 备份频道位置

    # 状态
    is_active: bool = True
    fail_count: int = 0
    last_check: Optional[datetime] = None

    # 元数据
    created_at: datetime = None
    updated_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()

    def get_effective_location(self) -> Optional[FileLocation]:
        """获取有效的文件位置（优先original，其次backup）"""
        if self.original_location and self.original_location.is_valid():
            return self.original_location
        if self.backup_location and self.backup_location.is_valid():
            return self.backup_location
        return None

    def to_dict(self) -> dict:
        """转换为字典（用于JSON序列化）"""
        data = asdict(self)
        # 处理datetime
        for key in ['created_at', 'updated_at', 'last_check']:
            if data.get(key) and isinstance(data[key], datetime):
                data[key] = data[key].isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'BackupRecord':
        """从字典创建实例"""
        # 处理datetime
        for key in ['created_at', 'updated_at', 'last_check']:
            if data.get(key) and isinstance(data[key], str):
                data[key] = datetime.fromisoformat(data[key])

        # 处理嵌套dataclass
        if data.get('original_location'):
            data['original_location'] = FileLocation(**data['original_location'])
        if data.get('backup_location'):
            data['backup_location'] = FileLocation(**data['backup_location'])

        return cls(**data)


class BackupService:
    """
    备份服务 (重构版)

    核心改进:
    1. 明确区分 original_location 和 backup_location
    2. 正确的file_id使用逻辑
    3. 智能恢复策略
    """

    _instance: Optional['BackupService'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._cache: Dict[str, BackupRecord] = {}  # sha256 -> record
        self._backup_channels: List[int] = []
        self._initialized = True

    async def initialize(self):
        """初始化备份服务"""
        settings = get_settings()
        # 加载备份频道配置
        if settings.backup_channel_id:
            self._backup_channels.append(settings.backup_channel_id)

        # 支持多备份频道
        if hasattr(settings, 'backup_channel_ids') and settings.backup_channel_ids:
            for ch_id in settings.backup_channel_ids.split(','):
                ch_id = int(ch_id.strip())
                if ch_id not in self._backup_channels:
                    self._backup_channels.append(ch_id)

        # 加载缓存
        await self._load_cache()

        logger.info(f"备份服务初始化完成，备份频道: {self._backup_channels}")

    async def _load_cache(self):
        """从持久化存储加载缓存"""
        settings = get_settings()
        cache_file = Path(settings.data_dir) / "backup_cache.json"
        if not cache_file.exists():
            return

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            for item in data:
                record = BackupRecord.from_dict(item)
                self._cache[record.sha256_hash] = record

            logger.info(f"加载备份缓存: {len(self._cache)} 条记录")

        except Exception as e:
            logger.error(f"加载备份缓存失败: {e}")

    async def _save_cache(self):
        """保存缓存到持久化存储"""
        settings = get_settings()
        cache_file = Path(settings.data_dir) / "backup_cache.json"

        try:
            data = [record.to_dict() for record in self._cache.values()]

            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"保存备份缓存失败: {e}")

    async def create_backup(
        self,
        bot: Bot,
        message: Message,
        sha256_hash: str
    ) -> Optional[BackupRecord]:
        """
        创建文件备份 (重构版)

        流程:
        1. 用户上传文件到Bot私聊，获得original_location
        2. 转发到备份频道，获得backup_location
        3. 保存两个location到数据库
        """
        if not self._backup_channels:
            logger.warning("未配置备份频道，跳过备份")
            return None

        # 检查是否已存在
        if sha256_hash in self._cache:
            existing = self._cache[sha256_hash]
            if existing.backup_location and existing.backup_location.is_valid():
                logger.info(f"文件已存在有效备份: {sha256_hash[:16]}")
                return existing

        document = message.document if message.document else None
        if not document:
            logger.error("消息不包含文件")
            return None

        # 创建original_location
        original_location = FileLocation(
            file_id=document.file_id,
            chat_id=message.chat.id,
            message_id=message.message_id,
            file_unique_id=document.file_unique_id
        )

        # 尝试备份到备份频道
        backup_location = None
        for channel_id in self._backup_channels:
            try:
                # 转发到备份频道
                forwarded = await bot.forward_message(
                    chat_id=channel_id,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id
                )

                # 创建backup_location
                if forwarded.document:
                    backup_location = FileLocation(
                        file_id=forwarded.document.file_id,
                        chat_id=channel_id,
                        message_id=forwarded.message_id,
                        file_unique_id=forwarded.document.file_unique_id
                    )

                logger.info(f"文件备份成功: {sha256_hash[:16]} -> 频道 {channel_id}")
                break

            except Exception as e:
                logger.warning(f"备份到频道 {channel_id} 失败: {e}")
                continue

        # 创建记录
        record = BackupRecord(
            sha256_hash=sha256_hash,
            file_name=document.file_name or "unknown",
            file_size=document.file_size or 0,
            mime_type=document.mime_type,
            original_location=original_location,
            backup_location=backup_location,
            is_active=backup_location is not None
        )

        # 保存到缓存
        self._cache[sha256_hash] = record
        await self._save_cache()

        return record

    async def send_file_to_user(
        self,
        bot: Bot,
        sha256_hash: str,
        user_chat_id: int,
        caption: str = None
    ) -> Optional[Message]:
        """
        发送文件给用户 (重构版)

        策略:
        1. 优先尝试使用 original_file_id 直接发送 (最快)
        2. 如果失败，从备份频道转发
        3. 如果都失败，返回None
        """
        if sha256_hash not in self._cache:
            logger.error(f"文件不在备份记录中: {sha256_hash[:16]}")
            return None

        record = self._cache[sha256_hash]

        # 策略1: 尝试使用 original_file_id 直接发送
        if record.original_location:
            try:
                msg = await bot.send_document(
                    chat_id=user_chat_id,
                    document=record.original_location.file_id,
                    caption=caption
                )
                logger.info(f"使用 original_file_id 发送成功: {sha256_hash[:16]}")
                return msg
            except Exception as e:
                logger.warning(f"original_file_id 发送失败: {e}")

        # 策略2: 从备份频道转发
        if record.backup_location and record.backup_location.message_id:
            try:
                forwarded = await bot.forward_message(
                    chat_id=user_chat_id,
                    from_chat_id=record.backup_location.chat_id,
                    message_id=record.backup_location.message_id
                )
                logger.info(f"从备份频道转发成功: {sha256_hash[:16]}")
                return forwarded
            except Exception as e:
                logger.error(f"从备份频道转发失败: {e}")

        # 所有策略都失败
        logger.error(f"无法发送文件: {sha256_hash[:16]}")
        return None


# 全局备份服务实例
_backup_service: Optional[BackupService] = None


async def get_backup_service() -> BackupService:
    """获取备份服务实例 (单例模式)"""
    global _backup_service
    if _backup_service is None:
        _backup_service = BackupService()
        await _backup_service.initialize()
    return _backup_service
