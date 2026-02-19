# -*- coding: utf-8 -*-
"""
搜书神器 V2 - Meilisearch 搜索服务
封装搜索功能，提供书籍搜索、索引管理等功能
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime

import asyncio
from meilisearch import Client
from meilisearch.errors import MeilisearchApiError

from app.core.config import get_settings
from app.core.logger import logger


@dataclass
class SearchFilters:
    """搜索筛选条件"""
    format: Optional[str] = None           # 格式: txt, pdf, epub...
    is_18plus: Optional[bool] = None       # 成人内容
    is_vip_only: Optional[bool] = None     # VIP专属
    min_rating: Optional[float] = None     # 最低评分
    min_size: Optional[int] = None         # 最小文件大小
    max_size: Optional[int] = None         # 最大文件大小
    min_word_count: Optional[int] = None   # 最小字数
    max_word_count: Optional[int] = None   # 最大字数
    tags: Optional[List[str]] = None       # 标签列表

    def to_meili_filter(self) -> List[str]:
        """转换为 Meilisearch 筛选语法"""
        filters = []

        if self.format:
            filters.append(f"format = '{self.format}'")

        if self.is_18plus is not None:
            filters.append(f"is_18plus = {str(self.is_18plus).lower()}")

        if self.is_vip_only is not None:
            filters.append(f"is_vip_only = {str(self.is_vip_only).lower()}")

        if self.min_rating is not None:
            filters.append(f"rating_score >= {self.min_rating}")

        if self.min_size is not None:
            filters.append(f"size >= {self.min_size}")

        if self.max_size is not None:
            filters.append(f"size <= {self.max_size}")

        if self.min_word_count is not None:
            filters.append(f"word_count >= {self.min_word_count}")

        if self.max_word_count is not None:
            filters.append(f"word_count <= {self.max_word_count}")

        if self.tags:
            # 标签使用 OR 匹配 (至少匹配一个)
            tag_filters = [f"tags = '{tag}'" for tag in self.tags]
            filters.append(f"({' OR '.join(tag_filters)})")

        return filters


@dataclass
class SearchResult:
    """搜索结果条目"""
    id: int
    title: str
    author: str
    format: str
    size: int
    word_count: int
    rating_score: float
    quality_score: float
    rating_count: int
    download_count: int
    is_18plus: bool
    tags: List[str]
    created_at: Optional[int] = None
    highlight: Optional[Dict[str, Any]] = None


@dataclass
class SearchResponse:
    """搜索响应"""
    hits: List[SearchResult]
    total: int
    page: int
    per_page: int
    total_pages: int
    query: str
    processing_time_ms: int


class SearchService:
    """搜索服务类"""

    def __init__(self):
        """初始化搜索服务"""
        settings = get_settings()
        self.client = Client(
            settings.meili_host,
            settings.meili_api_key,
        )
        self.index = self.client.index(settings.meili_index_name)
        self._ready = False
        logger.info(f"搜索服务初始化完成，索引: {settings.meili_index_name}")

    async def ensure_ready(self) -> None:
        if self._ready:
            return
        await asyncio.to_thread(self._ensure_ready_sync)
        self._ready = True

    def _ensure_ready_sync(self) -> None:
        settings = get_settings()
        index_name = settings.meili_index_name

        index_settings = {
            "searchableAttributes": [
                "title",
                "author",
                "tags",
                "description",
                "series",
            ],
            "filterableAttributes": [
                "format",
                "is_18plus",
                "is_vip_only",
                "status",
                "language",
                "tags",
                "size",
                "word_count",
            ],
            "sortableAttributes": [
                "created_at",
                "rating_score",
                "download_count",
                "view_count",
                "word_count",
                "size",
            ],
            "rankingRules": [
                "words",
                "typo",
                "proximity",
                "attribute",
                "sort",
                "exactness",
            ],
            "synonyms": {},
            "stopWords": [],
            "separatorTokens": [],
            "nonSeparatorTokens": [],
        }

        try:
            self.client.get_index(index_name)
        except MeilisearchApiError as e:
            if getattr(e, "code", None) == "index_not_found":
                task = self.client.create_index(index_name, {"primaryKey": "id"})
                task_uid = None
                if isinstance(task, dict):
                    task_uid = task.get("taskUid") or task.get("uid") or task.get("updateId")
                else:
                    task_uid = getattr(task, "task_uid", None) or getattr(task, "taskUid", None)
                if task_uid is not None:
                    self.client.wait_for_task(task_uid)
                self.index = self.client.index(index_name)
            else:
                raise

        task = self.index.update_settings(index_settings)
        task_uid = None
        if isinstance(task, dict):
            task_uid = task.get("taskUid") or task.get("uid") or task.get("updateId")
        else:
            task_uid = getattr(task, "task_uid", None) or getattr(task, "taskUid", None)
        if task_uid is not None:
            self.client.wait_for_task(task_uid)

    async def search(
        self,
        query: str,
        page: int = 1,
        per_page: int = 10,
        filters: Optional[SearchFilters] = None,
        sort: Optional[List[str]] = None,
        highlight: bool = True,
    ) -> SearchResponse:
        """
        执行书籍搜索

        Args:
            query: 搜索关键词
            page: 页码 (从1开始)
            per_page: 每页数量
            filters: 筛选条件
            sort: 排序规则
            highlight: 是否高亮匹配

        Returns:
            SearchResponse: 搜索结果
        """
        # 构建筛选条件
        meili_filters = filters.to_meili_filter() if filters else []
        filter_string = " AND ".join(meili_filters) if meili_filters else None

        # 构建高亮配置
        highlight_config = None
        if highlight:
            highlight_config = {
                "preTag": "<mark>",
                "postTag": "</mark>",
            }

        # 执行搜索
        offset = (page - 1) * per_page

        try:
            search_result = await asyncio.to_thread(
                self.index.search,
                query,
                {
                    "offset": offset,
                    "limit": per_page,
                    "filter": filter_string,
                    "sort": sort,
                    "highlightPreTag": "<mark>" if highlight else None,
                    "highlightPostTag": "</mark>" if highlight else None,
                    "attributesToHighlight": ["title", "author", "description"] if highlight else None,
                },
            )
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            raise

        # 解析结果
        hits = []
        for hit in search_result.get("hits", []):
            result = SearchResult(
                id=hit["id"],
                title=hit.get("title", ""),
                author=hit.get("author", ""),
                format=hit.get("format", ""),
                size=hit.get("size", 0),
                word_count=hit.get("word_count", 0),
                rating_score=hit.get("rating_score", 0.0),
                quality_score=hit.get("quality_score", 0.0),
                rating_count=hit.get("rating_count", 0),
                download_count=hit.get("download_count", 0),
                is_18plus=hit.get("is_18plus", False),
                tags=hit.get("tags", []),
                created_at=hit.get("created_at"),
                highlight=hit.get("_formatted"),
            )
            hits.append(result)

        # 构建响应
        total = search_result.get("estimatedTotalHits", 0)
        total_pages = (total + per_page - 1) // per_page if total > 0 else 0

        return SearchResponse(
            hits=hits,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
            query=query,
            processing_time_ms=search_result.get("processingTimeMs", 0),
        )

    async def add_document(
        self,
        document: Dict[str, Any],
        *,
        wait: bool = False,
        timeout_ms: int = 5000,
        raise_on_error: bool = False,
    ) -> bool:
        """
        添加文档到索引

        Args:
            document: 文档数据

        Returns:
            bool: 是否成功
        """
        try:
            task = await asyncio.to_thread(self.index.add_documents, [document])
            task_uid = None
            if isinstance(task, dict):
                task_uid = task.get("taskUid") or task.get("uid") or task.get("updateId")

            if wait and task_uid is not None:
                await asyncio.to_thread(
                    self.client.wait_for_task,
                    task_uid,
                    timeout_in_ms=timeout_ms,
                )

            logger.info(f"添加文档到索引: {document.get('id')}")
            return True
        except Exception as e:
            logger.error(f"添加文档失败: {e}")
            if raise_on_error:
                raise
            return False

    async def update_document(
        self,
        document: Dict[str, Any],
        *,
        wait: bool = False,
        timeout_ms: int = 5000,
        raise_on_error: bool = False,
    ) -> bool:
        """
        更新索引中的文档

        Args:
            document: 文档数据

        Returns:
            bool: 是否成功
        """
        try:
            task = await asyncio.to_thread(self.index.update_documents, [document])
            task_uid = None
            if isinstance(task, dict):
                task_uid = task.get("taskUid") or task.get("uid") or task.get("updateId")

            if wait and task_uid is not None:
                await asyncio.to_thread(
                    self.client.wait_for_task,
                    task_uid,
                    timeout_in_ms=timeout_ms,
                )

            logger.info(f"更新索引文档: {document.get('id')}")
            return True
        except Exception as e:
            logger.error(f"更新文档失败: {e}")
            if raise_on_error:
                raise
            return False

    async def delete_document(
        self,
        document_id: int,
        *,
        wait: bool = False,
        timeout_ms: int = 5000,
        raise_on_error: bool = False,
    ) -> bool:
        """
        从索引中删除文档

        Args:
            document_id: 文档ID

        Returns:
            bool: 是否成功
        """
        try:
            task = await asyncio.to_thread(self.index.delete_document, document_id)
            task_uid = None
            if isinstance(task, dict):
                task_uid = task.get("taskUid") or task.get("uid") or task.get("updateId")

            if wait and task_uid is not None:
                await asyncio.to_thread(
                    self.client.wait_for_task,
                    task_uid,
                    timeout_in_ms=timeout_ms,
                )

            logger.info(f"删除索引文档: {document_id}")
            return True
        except Exception as e:
            logger.error(f"删除文档失败: {e}")
            if raise_on_error:
                raise
            return False


# 全局搜索服务实例
_search_service: Optional[SearchService] = None


async def get_search_service() -> SearchService:
    """获取搜索服务单例"""
    global _search_service
    if _search_service is None:
        _search_service = SearchService()
        await _search_service.ensure_ready()
    return _search_service
