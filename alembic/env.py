# -*- coding: utf-8 -*-
"""
Alembic 环境配置
搜书神器 V2 - 数据库迁移脚本
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# 加载应用配置
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.core.models import Base

# Alembic 配置对象
config = context.config

# 配置日志
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 设置元数据
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata

# 动态设置数据库 URL
config.set_main_option("sqlalchemy.url", settings.database_url)


def run_migrations_offline() -> None:
    """离线模式运行迁移 (生成 SQL 脚本)"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """实际执行迁移"""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """在线模式运行迁移"""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
