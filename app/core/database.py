# -*- coding: utf-8 -*-
"""
搜书神器 V2 - 数据库连接管理
提供异步数据库会话管理
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from app.core.config import settings

# 创建异步引擎
engine = create_async_engine(
    settings.database_url,
    echo=settings.log_level == "DEBUG",
    future=True,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=10,
)

# 创建异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话 (用于依赖注入)"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """初始化数据库 (创建所有表)"""
    from app.core.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """关闭数据库连接"""
    await engine.dispose()
