# -*- coding: utf-8 -*-
"""
书籍扩展能力服务
封装书单、评价、标签审核、相似推荐与索引同步逻辑
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.models import (
    Book,
    BookEditHistory,
    BookList,
    BookListItem,
    BookReview,
    BookTag,
    Favorite,
    File,
    Tag,
    TagApplication,
    TagAuditLog,
    User,
)
from app.services.search import get_search_service


DEFAULT_BOOKLIST_NAME = "我喜欢的书籍"


@dataclass
class SimilarBooksResult:
    items: list[Book]
    total: int
    tag_names: list[str]


async def ensure_user_record(
    session: AsyncSession,
    *,
    user_id: int,
    username: Optional[str],
    first_name: str,
    last_name: Optional[str],
) -> User:
    user = await session.scalar(select(User).where(User.id == user_id))
    if user:
        if username is not None:
            user.username = username
        if first_name:
            user.first_name = first_name
        user.last_name = last_name
        return user

    user = User(
        id=user_id,
        username=username,
        first_name=first_name or "Unknown",
        last_name=last_name,
        coins=0,
        upload_count=0,
        download_count=0,
        search_count=0,
    )
    session.add(user)
    await session.flush()
    return user


def generate_booklist_share_token() -> str:
    return secrets.token_urlsafe(12).replace("-", "A").replace("_", "B")[:20]


async def get_or_create_default_booklist(session: AsyncSession, user_id: int) -> BookList:
    row = await session.scalar(
        select(BookList).where(BookList.user_id == user_id, BookList.is_default.is_(True))
    )
    if row:
        return row

    row = BookList(
        user_id=user_id,
        name=DEFAULT_BOOKLIST_NAME,
        is_default=True,
        is_public=False,
        share_token=None,
    )
    session.add(row)
    await session.flush()
    return row


async def list_user_booklists(session: AsyncSession, user_id: int) -> list[BookList]:
    await get_or_create_default_booklist(session, user_id)
    result = await session.execute(
        select(BookList)
        .where(BookList.user_id == user_id)
        .options(selectinload(BookList.items))
        .order_by(BookList.is_default.desc(), BookList.created_at.asc())
    )
    return list(result.scalars().all())


async def create_booklist(session: AsyncSession, user_id: int, name: str) -> BookList:
    clean_name = (name or "").strip()
    if not clean_name:
        raise ValueError("书单名称不能为空")
    if len(clean_name) > 80:
        raise ValueError("书单名称不能超过80个字符")
    row = BookList(user_id=user_id, name=clean_name, is_default=False, is_public=False)
    session.add(row)
    await session.flush()
    return row


async def rename_booklist(session: AsyncSession, *, user_id: int, list_id: int, new_name: str) -> BookList:
    booklist = await session.scalar(select(BookList).where(BookList.id == list_id, BookList.user_id == user_id))
    if not booklist:
        raise ValueError("书单不存在")
    if booklist.is_default:
        raise ValueError("默认书单不支持重命名")
    clean_name = (new_name or "").strip()
    if not clean_name:
        raise ValueError("书单名称不能为空")
    if len(clean_name) > 80:
        raise ValueError("书单名称不能超过80个字符")
    booklist.name = clean_name
    await session.flush()
    return booklist


async def delete_booklist(session: AsyncSession, *, user_id: int, list_id: int) -> None:
    booklist = await session.scalar(
        select(BookList)
        .where(BookList.id == list_id, BookList.user_id == user_id)
        .options(selectinload(BookList.items))
    )
    if not booklist:
        raise ValueError("书单不存在")
    if booklist.is_default:
        raise ValueError("默认书单不可删除")
    for item in list(booklist.items):
        await session.delete(item)
    await session.delete(booklist)
    await session.flush()


async def toggle_booklist_public(
    session: AsyncSession,
    *,
    user_id: int,
    list_id: int,
) -> BookList:
    booklist = await session.scalar(select(BookList).where(BookList.id == list_id, BookList.user_id == user_id))
    if not booklist:
        raise ValueError("书单不存在")
    booklist.is_public = not bool(booklist.is_public)
    if booklist.is_public and not booklist.share_token:
        booklist.share_token = generate_booklist_share_token()
    await session.flush()
    return booklist


async def add_book_to_booklist(
    session: AsyncSession,
    *,
    list_id: int,
    book_id: int,
    added_by: int,
) -> bool:
    exists = await session.scalar(
        select(BookListItem).where(BookListItem.list_id == list_id, BookListItem.book_id == book_id)
    )
    if exists:
        return False
    session.add(BookListItem(list_id=list_id, book_id=book_id, added_by=added_by))
    await session.flush()
    return True


async def remove_book_from_booklist(session: AsyncSession, *, list_id: int, book_id: int) -> bool:
    row = await session.scalar(
        select(BookListItem).where(BookListItem.list_id == list_id, BookListItem.book_id == book_id)
    )
    if not row:
        return False
    await session.delete(row)
    await session.flush()
    return True


async def get_public_booklist(session: AsyncSession, share_token: str) -> Optional[BookList]:
    return await session.scalar(
        select(BookList)
        .where(BookList.share_token == share_token, BookList.is_public.is_(True))
        .options(selectinload(BookList.items).selectinload(BookListItem.book))
    )


async def upsert_review(
    session: AsyncSession,
    *,
    user_id: int,
    book_id: int,
    rating: int,
    comment: Optional[str],
) -> BookReview:
    if rating < 1 or rating > 5:
        raise ValueError("评分范围必须在1-5之间")
    clean_comment = (comment or "").strip()
    if len(clean_comment) > 240:
        raise ValueError("短评不能超过240个字符")

    review = await session.scalar(
        select(BookReview).where(BookReview.user_id == user_id, BookReview.book_id == book_id)
    )
    if not review:
        review = BookReview(user_id=user_id, book_id=book_id, rating=rating, comment=clean_comment or None)
        session.add(review)
    else:
        review.rating = rating
        review.comment = clean_comment or None
    await session.flush()
    await recompute_book_rating(session, book_id=book_id)
    return review


async def recompute_book_rating(session: AsyncSession, *, book_id: int) -> None:
    row = (
        await session.execute(
            select(
                func.count(BookReview.id),
                func.coalesce(func.avg(BookReview.rating), 0.0),
                func.count(case((BookReview.comment.is_not(None), 1))),
            ).where(BookReview.book_id == book_id)
        )
    ).one()
    count, avg_rating, comment_count = row
    book = await session.scalar(select(Book).where(Book.id == book_id))
    if not book:
        raise ValueError("书籍不存在")
    book.rating_count = int(count or 0)
    book.rating_score = float(avg_rating or 0.0) * 2
    book.comment_count = int(comment_count or 0)
    await session.flush()


async def get_recent_reviews(
    session: AsyncSession,
    *,
    book_id: int,
    page: int = 1,
    per_page: int = 5,
) -> tuple[list[BookReview], int]:
    offset = max(page - 1, 0) * per_page
    total = await session.scalar(select(func.count()).select_from(BookReview).where(BookReview.book_id == book_id)) or 0
    result = await session.execute(
        select(BookReview)
        .where(BookReview.book_id == book_id, BookReview.comment.is_not(None))
        .order_by(BookReview.updated_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    return list(result.scalars().all()), int(total)


async def submit_tag_application(
    session: AsyncSession,
    *,
    user_id: int,
    book_id: int,
    tag_name: str,
) -> TagApplication:
    clean_name = (tag_name or "").strip().lstrip("#")
    if not clean_name:
        raise ValueError("标签不能为空")
    if len(clean_name) > 50:
        raise ValueError("标签长度不能超过50个字符")

    existing_tag = await session.scalar(select(Tag).where(Tag.name == clean_name))
    if existing_tag:
        linked = await session.scalar(
            select(BookTag).where(BookTag.book_id == book_id, BookTag.tag_id == existing_tag.id)
        )
        if linked:
            raise ValueError("该标签已存在")

    pending = await session.scalar(
        select(TagApplication).where(
            TagApplication.user_id == user_id,
            TagApplication.book_id == book_id,
            TagApplication.tag_name == clean_name,
            TagApplication.status == "pending",
        )
    )
    if pending:
        raise ValueError("相同标签申请已在审核中")

    row = TagApplication(user_id=user_id, book_id=book_id, tag_name=clean_name, status="pending")
    session.add(row)
    await session.flush()
    return row


async def review_tag_application(
    session: AsyncSession,
    *,
    application_id: int,
    admin_id: int,
    approve: bool,
    review_note: Optional[str] = None,
) -> TagApplication:
    application = await session.scalar(select(TagApplication).where(TagApplication.id == application_id))
    if not application:
        raise ValueError("标签申请不存在")
    if application.status != "pending":
        raise ValueError("该申请已处理")

    application.reviewed_by = admin_id
    application.reviewed_at = datetime.utcnow()
    application.review_note = (review_note or "").strip() or None
    application.status = "approved" if approve else "rejected"

    if approve:
        tag = await session.scalar(select(Tag).where(Tag.name == application.tag_name))
        if not tag:
            tag = Tag(name=application.tag_name, usage_count=0)
            session.add(tag)
            await session.flush()

        linked = await session.scalar(
            select(BookTag).where(BookTag.book_id == application.book_id, BookTag.tag_id == tag.id)
        )
        if not linked:
            session.add(BookTag(book_id=application.book_id, tag_id=tag.id, added_by=application.user_id))
            tag.usage_count = int(tag.usage_count or 0) + 1

        session.add(
            TagAuditLog(
                book_id=application.book_id,
                tag_id=tag.id,
                actor_id=admin_id,
                action="review",
                detail=f"approved:{application.tag_name}",
            )
        )
    else:
        session.add(
            TagAuditLog(
                book_id=application.book_id,
                tag_id=None,
                actor_id=admin_id,
                action="review",
                detail=f"rejected:{application.tag_name}",
            )
        )

    await session.flush()
    return application


async def remove_tag_from_book(
    session: AsyncSession,
    *,
    book_id: int,
    tag_id: int,
    admin_id: int,
    detail: str = "manual_remove",
) -> None:
    link = await session.scalar(select(BookTag).where(BookTag.book_id == book_id, BookTag.tag_id == tag_id))
    if not link:
        raise ValueError("标签关联不存在")
    tag = await session.scalar(select(Tag).where(Tag.id == tag_id))
    if tag and int(tag.usage_count or 0) > 0:
        tag.usage_count -= 1
    await session.delete(link)
    session.add(TagAuditLog(book_id=book_id, tag_id=tag_id, actor_id=admin_id, action="remove", detail=detail))
    await session.flush()


async def edit_book_field(
    session: AsyncSession,
    *,
    book_id: int,
    editor_id: int,
    field_name: str,
    raw_value: str,
) -> Book:
    book = await session.scalar(select(Book).where(Book.id == book_id))
    if not book:
        raise ValueError("书籍不存在")

    value = (raw_value or "").strip()
    allowed_fields = {
        "title": "title",
        "author": "author",
        "description": "description",
        "is_18plus": "is_18plus",
        "is_vip_only": "is_vip_only",
    }
    attr = allowed_fields.get(field_name)
    if not attr:
        raise ValueError("不支持的字段")

    old_value = getattr(book, attr)
    if field_name in {"is_18plus", "is_vip_only"}:
        normalized = value.lower()
        if normalized in {"1", "true", "yes", "是", "开启", "开"}:
            new_value = True
        elif normalized in {"0", "false", "no", "否", "关闭", "关"}:
            new_value = False
        else:
            raise ValueError("布尔字段请输入 是/否")
    else:
        if not value:
            raise ValueError("字段内容不能为空")
        new_value = value

    setattr(book, attr, new_value)
    session.add(
        BookEditHistory(
            book_id=book_id,
            editor_id=editor_id,
            field_name=field_name,
            old_value="" if old_value is None else str(old_value),
            new_value="" if new_value is None else str(new_value),
        )
    )
    await session.flush()
    return book


async def get_book_edit_history(
    session: AsyncSession,
    *,
    book_id: int,
    limit: int = 10,
) -> list[BookEditHistory]:
    result = await session.execute(
        select(BookEditHistory)
        .where(BookEditHistory.book_id == book_id)
        .order_by(BookEditHistory.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def sync_book_to_search(session: AsyncSession, *, book_id: int) -> None:
    book = await session.scalar(
        select(Book)
        .where(Book.id == book_id)
        .options(selectinload(Book.file), selectinload(Book.book_tags).selectinload(BookTag.tag))
    )
    if not book or not book.file:
        return
    search_service = await get_search_service()
    await search_service.update_document(
        {
            "id": book.id,
            "title": book.title,
            "author": book.author,
            "format": book.file.extension,
            "size": int(book.file.size or 0),
            "word_count": int(book.file.word_count or 0),
            "rating_score": float(book.rating_score or 0.0),
            "quality_score": float(book.quality_score or 0.0),
            "rating_count": int(book.rating_count or 0),
            "download_count": int(book.download_count or 0),
            "view_count": int(book.view_count or 0),
            "is_18plus": bool(book.is_18plus),
            "is_vip_only": bool(book.is_vip_only),
            "tags": [bt.tag.name for bt in (book.book_tags or []) if bt.tag and bt.tag.name],
            "created_at": int(book.created_at.timestamp()) if book.created_at else 0,
        },
        wait=True,
        timeout_ms=8000,
    )


async def get_similar_books(
    session: AsyncSession,
    *,
    book_id: int,
    page: int = 1,
    per_page: int = 5,
) -> SimilarBooksResult:
    book = await session.scalar(
        select(Book)
        .where(Book.id == book_id)
        .options(selectinload(Book.book_tags).selectinload(BookTag.tag))
    )
    if not book:
        raise ValueError("书籍不存在")

    tag_names = [bt.tag.name for bt in (book.book_tags or []) if bt.tag and bt.tag.name]
    result_map: dict[int, Book] = {}

    if tag_names:
        tag_query = (
            select(Book)
            .join(BookTag, Book.id == BookTag.book_id)
            .join(Tag, Tag.id == BookTag.tag_id)
            .where(Book.id != book_id, Tag.name.in_(tag_names))
            .order_by(Book.download_count.desc(), Book.favorite_count.desc(), Book.created_at.desc())
            .limit(per_page * 4)
        )
        for item in (await session.execute(tag_query)).scalars().unique().all():
            result_map[item.id] = item

    if len(result_map) < per_page * page and book.author:
        author_query = (
            select(Book)
            .where(Book.id != book_id, Book.author == book.author)
            .order_by(Book.download_count.desc(), Book.favorite_count.desc(), Book.created_at.desc())
            .limit(per_page * 4)
        )
        for item in (await session.execute(author_query)).scalars().all():
            result_map.setdefault(item.id, item)

    if len(result_map) < per_page * page:
        hot_query = (
            select(Book)
            .where(Book.id != book_id)
            .order_by(Book.download_count.desc(), Book.favorite_count.desc(), Book.created_at.desc())
            .limit(per_page * 4)
        )
        for item in (await session.execute(hot_query)).scalars().all():
            result_map.setdefault(item.id, item)

    items = list(result_map.values())
    total = len(items)
    offset = max(page - 1, 0) * per_page
    return SimilarBooksResult(items=items[offset:offset + per_page], total=total, tag_names=tag_names)
