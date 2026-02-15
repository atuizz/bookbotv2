#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
初始化 Meilisearch 索引
搜书神器 V2 - 搜索索引初始化脚本
"""

import asyncio
import sys
from pathlib import Path

from meilisearch import Client
from meilisearch.errors import MeilisearchApiError

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import get_settings
from app.core.logger import logger


# Meilisearch 索引设置
INDEX_SETTINGS = {
    # 可搜索字段
    "searchableAttributes": [
        "title",           # 书名 (最高优先级)
        "author",          # 作者
        "tags",            # 标签
        "description",     # 简介
        "series",          # 丛书
    ],
    # 可筛选字段
    "filterableAttributes": [
        "format",          # 格式
        "is_18plus",       # 是否成人内容
        "is_vip_only",     # 是否VIP专属
        "status",          # 状态
        "language",        # 语言
        "tags",            # 标签 (数组)
    ],
    # 可排序字段
    "sortableAttributes": [
        "created_at",      # 创建时间
        "rating_score",    # 评分
        "download_count",  # 下载数
        "view_count",      # 浏览数
        "word_count",      # 字数
        "size",            # 文件大小
    ],
    # 排名规则
    "rankingRules": [
        "words",           # 单词数量匹配
        "typo",            # 拼写容错
        "proximity",       # 接近度
        "attribute",       # 属性优先级
        "sort",            # 排序规则
        "exactness",       # 精确匹配
    ],
    # 同义词配置 (可扩展)
    "synonyms": {},
    # 停用词 (中文通常不需要太多停用词)
    "stopWords": [],
    # 分隔符
    "separatorTokens": [],
    # 非分隔符
    "nonSeparatorTokens": [],
}


async def init_meilisearch():
    """初始化 Meilisearch 索引"""
    logger.info("开始初始化 Meilisearch...")
    settings = get_settings()

    # 创建客户端 (注意：meilisearch-python 客户端是同步的)
    client = Client(
        settings.meili_host,
        settings.meili_api_key,
    )

    # 检查服务健康状态
    try:
        health = client.health()
        status = health.get('status', 'unknown')
        logger.info(f"Meilisearch 健康状态: {status}")
    except Exception as e:
        logger.error(f"Meilisearch 连接失败: {e}")
        return False

    # 获取或创建索引
    index_name = settings.meili_index_name

    try:
        # 尝试获取索引
        client.get_index(index_name)
        logger.info(f"索引 '{index_name}' 已存在")
    except MeilisearchApiError as e:
        # 检查错误代码
        if e.code == "index_not_found":
            # 创建新索引
            logger.info(f"创建新索引 '{index_name}'...")
            try:
                task = client.create_index(index_name, {"primaryKey": "id"})
                logger.info(f"索引创建任务已提交: {task.task_uid}")
                # 等待任务完成
                client.wait_for_task(task.task_uid)
                logger.info("索引创建成功")
            except Exception as create_error:
                logger.error(f"创建索引失败: {create_error}")
                return False
        else:
            logger.error(f"获取索引失败: {e}")
            raise

    # 获取索引对象
    index = client.index(index_name)

    # 更新索引设置
    logger.info("更新索引设置...")
    try:
        task = index.update_settings(INDEX_SETTINGS)
        logger.info(f"设置更新任务已提交: {task.task_uid}")
        client.wait_for_task(task.task_uid)
        logger.info("索引设置已更新")
    except Exception as e:
        logger.error(f"更新设置失败: {e}")
        return False

    # 获取最终设置确认
    try:
        final_settings = index.get_settings()
        # 兼容性处理
        searchable = getattr(final_settings, 'searchable_attributes', 
                     getattr(final_settings, 'searchableAttributes', []))
        logger.info(f"索引设置完成，可搜索字段: {searchable}")
    except Exception as e:
        logger.warning(f"无法获取最终设置 (可能是非致命错误): {e}")

    logger.info("Meilisearch 初始化完成！")
    return True


def init_meilisearch_sync():
    """同步初始化 Meilisearch 索引 (包装器)"""
    try:
        # 兼容 Python 3.7+
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 如果已有事件循环运行，则创建任务
            return loop.create_task(init_meilisearch())
        else:
            return loop.run_until_complete(init_meilisearch())
    except RuntimeError:
        return asyncio.run(init_meilisearch())

if __name__ == "__main__":
    init_meilisearch_sync()
