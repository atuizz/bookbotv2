# -*- coding: utf-8 -*-
"""
搜书神器 V2 - 核心配置模块
使用 Pydantic Settings 管理环境变量
"""

from pathlib import Path
from typing import List, Optional

from pydantic import Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录
BASE_DIR = Path(__file__).parent.parent.parent.absolute()


class Settings(BaseSettings):
    """应用配置类"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ============================================
    # Bot 核心配置
    # ============================================
    bot_token: str = Field(..., description="Telegram Bot Token")
    bot_username: str = Field(..., description="Bot 用户名")

    # Webhook 配置 (生产环境)
    webhook_host: Optional[str] = Field(None, description="Webhook 域名")
    webhook_port: int = Field(8443, description="Webhook 端口")
    webhook_path: str = Field("/webhook", description="Webhook 路径")

    @property
    def webhook_url(self) -> Optional[str]:
        if self.webhook_host:
            return f"{self.webhook_host}:{self.webhook_port}{self.webhook_path}"
        return None

    @property
    def use_webhook(self) -> bool:
        return self.webhook_host is not None

    # ============================================
    # 数据库配置
    # ============================================
    db_host: str = Field("localhost", description="PostgreSQL 主机")
    db_port: int = Field(5432, description="PostgreSQL 端口")
    db_name: str = Field("bookbot", description="数据库名")
    db_user: str = Field("bookbot_user", description="数据库用户")
    db_password: str = Field(..., description="数据库密码")

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    # ============================================
    # Redis 配置
    # ============================================
    redis_host: str = Field("localhost", description="Redis 主机")
    redis_port: int = Field(6379, description="Redis 端口")
    redis_db: int = Field(0, description="Redis 数据库编号")
    redis_password: Optional[str] = Field(None, description="Redis 密码")

    @property
    def redis_url(self) -> str:
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # ============================================
    # Meilisearch 配置
    # ============================================
    meili_host: str = Field("http://localhost:7700", description="Meilisearch 地址")
    meili_api_key: str = Field(..., description="Meilisearch API Key")
    meili_index_name: str = Field("books", description="Meilisearch 索引名")

    # ============================================
    # 业务逻辑配置
    # ============================================
    backup_channel_id: Optional[int] = Field(None, description="备份频道 ID")

    # 上传配置
    max_upload_size_mb: int = Field(100, description="最大上传文件大小 (MB)")
    allowed_extensions: List[str] = Field(
        default=["txt", "pdf", "epub", "mobi", "azw3"],
        description="允许的文件扩展名"
    )

    # 搜索配置
    default_search_limit: int = Field(10, description="默认搜索返回数量")
    max_search_limit: int = Field(50, description="最大搜索返回数量")

    # ============================================
    # 日志配置
    # ============================================
    log_level: str = Field("INFO", description="日志级别")
    log_format: str = Field("json", description="日志格式 (json/text)")

    # ============================================
    # 路径配置
    # ============================================
    @property
    def log_dir(self) -> Path:
        return BASE_DIR / "logs"

    @property
    def data_dir(self) -> Path:
        return BASE_DIR / "data"

    @property
    def temp_dir(self) -> Path:
        return BASE_DIR / "temp"


# 配置实例缓存
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """获取配置单例 (延迟初始化)"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

