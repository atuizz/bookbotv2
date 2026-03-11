# -*- coding: utf-8 -*-
"""
搜书神器 V2 - SQLAlchemy 数据模型
定义所有数据库表结构
"""

from datetime import datetime
from typing import List, Optional
from enum import Enum as PyEnum

from sqlalchemy import (
    String, Integer, BigInteger, Float, Boolean, DateTime, Text,
    ForeignKey, Index, UniqueConstraint, Enum, ARRAY
)
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, mapped_column, relationship
)
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """基础模型类"""

    # 默认添加创建时间和更新时间
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间"
    )


# ============================================
# 枚举类型定义
# ============================================

class UserLevel(PyEnum):
    """用户等级"""
    BLACK_IRON = "黑铁"
    BRONZE = "青铜"
    SILVER = "白银"
    GOLD = "黄金"
    DIAMOND = "钻石"


class FileFormat(PyEnum):
    """文件格式"""
    TXT = "txt"
    PDF = "pdf"
    EPUB = "epub"
    MOBI = "mobi"
    AZW3 = "azw3"


class BookStatus(PyEnum):
    """书籍状态"""
    ACTIVE = "active"        # 正常
    PENDING = "pending"      # 审核中
    HIDDEN = "hidden"        # 隐藏
    BANNED = "banned"        # 封禁


# ============================================
# 用户相关模型
# ============================================

class User(Base):
    """用户模型"""
    __tablename__ = "users"

    # Telegram 用户ID作为主键
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, comment="Telegram 用户ID")

    # 用户信息
    username: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, comment="用户名")
    first_name: Mapped[str] = mapped_column(String(64), comment="名字")
    last_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="姓氏")

    # 等级与积分系统
    level: Mapped[UserLevel] = mapped_column(
        Enum(UserLevel),
        default=UserLevel.BLACK_IRON,
        comment="用户等级"
    )
    coins: Mapped[int] = mapped_column(BigInteger, default=0, comment="书币数量")
    experience: Mapped[int] = mapped_column(BigInteger, default=0, comment="经验值")

    # VIP 与权限
    is_vip: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否VIP")
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否封禁")
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否管理员")

    # 统计
    upload_count: Mapped[int] = mapped_column(Integer, default=0, comment="上传次数")
    download_count: Mapped[int] = mapped_column(Integer, default=0, comment="下载次数")
    search_count: Mapped[int] = mapped_column(Integer, default=0, comment="搜索次数")

    # 关联
    favorites: Mapped[List["Favorite"]] = relationship("Favorite", back_populates="user", lazy="selectin")
    uploads: Mapped[List["Book"]] = relationship("Book", back_populates="uploader", foreign_keys="Book.uploader_id", lazy="selectin")

    # 索引
    __table_args__ = (
        Index('ix_users_username', 'username'),
        Index('ix_users_level', 'level'),
        Index('ix_users_is_vip', 'is_vip'),
    )


# ============================================
# 文件相关模型
# ============================================

class File(Base):
    """文件信息模型 (基于SHA256去重)"""
    __tablename__ = "files"

    # SHA256 作为主键
    sha256_hash: Mapped[str] = mapped_column(String(64), primary_key=True, comment="SHA256 哈希值")

    # 文件信息
    size: Mapped[int] = mapped_column(BigInteger, comment="文件大小(字节)")
    extension: Mapped[str] = mapped_column(String(10), comment="文件扩展名")
    format: Mapped[FileFormat] = mapped_column(Enum(FileFormat), comment="文件格式")
    word_count: Mapped[int] = mapped_column(Integer, default=0, comment="字数统计")

    # 内容分析 (可选)
    content_preview: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="内容预览")
    language: Mapped[Optional[str]] = mapped_column(String(10), nullable=True, comment="语言检测")

    # 关联
    book_refs: Mapped[List["Book"]] = relationship("Book", back_populates="file", lazy="selectin")
    file_refs: Mapped[List["FileRef"]] = relationship("FileRef", back_populates="file", lazy="selectin")

    # 索引
    __table_args__ = (
        Index('ix_files_size', 'size'),
        Index('ix_files_format', 'format'),
        Index('ix_files_extension', 'extension'),
    )


class FileRef(Base):
    """文件引用模型 (存储不同渠道的 File ID)"""
    __tablename__ = "file_refs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # 关联文件
    file_hash: Mapped[str] = mapped_column(ForeignKey("files.sha256_hash"), comment="文件哈希")

    # Telegram 存储信息
    tg_file_id: Mapped[str] = mapped_column(String(255), comment="Telegram File ID")
    channel_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, comment="存储频道ID")
    message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, comment="消息ID")

    # 元数据
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否主引用")
    is_backup: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否备份")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否可用")

    # 关联
    file: Mapped["File"] = relationship("File", back_populates="file_refs", lazy="selectin")

    # 索引
    __table_args__ = (
        Index('ix_file_refs_file_hash', 'file_hash'),
        Index('ix_file_refs_tg_file_id', 'tg_file_id'),
        Index('ix_file_refs_channel_id', 'channel_id'),
        UniqueConstraint('file_hash', 'channel_id', name='uq_file_channel'),
    )


# ============================================
# 书籍相关模型
# ============================================

class Book(Base):
    """书籍信息模型"""
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # 基础信息
    title: Mapped[str] = mapped_column(String(255), comment="书名")
    subtitle: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="副标题")
    original_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="原名")

    # 作者信息
    author: Mapped[str] = mapped_column(String(255), comment="作者")
    author_other: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="其他作者")

    # 文件关联
    file_hash: Mapped[str] = mapped_column(ForeignKey("files.sha256_hash"), comment="文件哈希")

    # 内容信息
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="简介")
    language: Mapped[Optional[str]] = mapped_column(String(10), nullable=True, comment="语言")
    isbn: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, comment="ISBN")
    publisher: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="出版社")
    publish_date: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="出版日期")
    series: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="丛书")

    # 评分系统 (双评分制)
    rating_score: Mapped[float] = mapped_column(Float, default=0.0, comment="内容评分(0-10)")
    quality_score: Mapped[float] = mapped_column(Float, default=0.0, comment="质量评分(0-10)")
    rating_count: Mapped[int] = mapped_column(Integer, default=0, comment="评分人数")

    # 统计数据
    view_count: Mapped[int] = mapped_column(BigInteger, default=0, comment="浏览次数")
    download_count: Mapped[int] = mapped_column(BigInteger, default=0, comment="下载次数")
    like_count: Mapped[int] = mapped_column(Integer, default=0, comment="点赞数")
    favorite_count: Mapped[int] = mapped_column(Integer, default=0, comment="收藏数")
    comment_count: Mapped[int] = mapped_column(Integer, default=0, comment="评论数")

    # 状态与标记
    status: Mapped[BookStatus] = mapped_column(Enum(BookStatus), default=BookStatus.ACTIVE, comment="状态")
    is_18plus: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否成人内容")
    is_vip_only: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否VIP专属")
    is_original: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否原创")

    # 上传者信息
    uploader_id: Mapped[int] = mapped_column(ForeignKey("users.id"), comment="上传者ID")

    # 关联
    file: Mapped["File"] = relationship("File", back_populates="book_refs", lazy="selectin")
    uploader: Mapped["User"] = relationship("User", back_populates="uploads", foreign_keys=[uploader_id], lazy="selectin")
    favorites: Mapped[List["Favorite"]] = relationship("Favorite", back_populates="book", lazy="selectin")
    book_tags: Mapped[List["BookTag"]] = relationship("BookTag", back_populates="book", lazy="selectin")
    reviews: Mapped[List["BookReview"]] = relationship("BookReview", back_populates="book", lazy="selectin")
    booklist_items: Mapped[List["BookListItem"]] = relationship("BookListItem", back_populates="book", lazy="selectin")

    # 索引
    __table_args__ = (
        Index('ix_books_title', 'title'),
        Index('ix_books_author', 'author'),
        Index('ix_books_file_hash', 'file_hash'),
        Index('ix_books_uploader_id', 'uploader_id'),
        Index('ix_books_status', 'status'),
        Index('ix_books_is_18plus', 'is_18plus'),
        Index('ix_books_rating_score', 'rating_score'),
        Index('ix_books_download_count', 'download_count'),
        Index('ix_books_created_at', 'created_at'),
    )


# ============================================
# 标签相关模型
# ============================================

class Tag(Base):
    """标签模型"""
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(String(50), unique=True, comment="标签名")
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="分类")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="描述")
    color: Mapped[Optional[str]] = mapped_column(String(7), nullable=True, comment="颜色")

    # 统计
    usage_count: Mapped[int] = mapped_column(Integer, default=0, comment="使用次数")

    # 关联
    book_tags: Mapped[List["BookTag"]] = relationship("BookTag", back_populates="tag", lazy="selectin")

    # 索引
    __table_args__ = (
        Index('ix_tags_name', 'name'),
        Index('ix_tags_category', 'category'),
    )


class BookTag(Base):
    """书籍-标签关联模型"""
    __tablename__ = "book_tags"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), comment="书籍ID")
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id"), comment="标签ID")

    # 谁添加的标签
    added_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, comment="添加者ID")

    # 关联
    book: Mapped["Book"] = relationship("Book", back_populates="book_tags", lazy="selectin")
    tag: Mapped["Tag"] = relationship("Tag", back_populates="book_tags", lazy="selectin")

    # 索引和唯一约束
    __table_args__ = (
        UniqueConstraint('book_id', 'tag_id', name='uq_book_tag'),
        Index('ix_book_tags_book_id', 'book_id'),
        Index('ix_book_tags_tag_id', 'tag_id'),
    )


# ============================================
# 收藏相关模型
# ============================================

class Favorite(Base):
    """用户收藏模型"""
    __tablename__ = "favorites"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), comment="用户ID")
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), comment="书籍ID")

    # 收藏列表分类
    collection_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="收藏列表名")

    # 关联
    user: Mapped["User"] = relationship("User", back_populates="favorites", lazy="selectin")
    book: Mapped["Book"] = relationship("Book", back_populates="favorites", lazy="selectin")

    # 索引和唯一约束
    __table_args__ = (
        UniqueConstraint('user_id', 'book_id', name='uq_user_favorite'),
        Index('ix_favorites_user_id', 'user_id'),
        Index('ix_favorites_book_id', 'book_id'),
    )


# ============================================
# 邀请相关模型
# ============================================

class InviteRelation(Base):
    """邀请关系（一个被邀请用户只允许绑定一个邀请人）"""
    __tablename__ = "invite_relations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    inviter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), comment="邀请人ID")
    invitee_id: Mapped[int] = mapped_column(ForeignKey("users.id"), comment="被邀请人ID")

    __table_args__ = (
        UniqueConstraint('invitee_id', name='uq_invitee_once'),
        Index('ix_invite_relations_inviter_id', 'inviter_id'),
        Index('ix_invite_relations_invitee_id', 'invitee_id'),
        Index('ix_invite_relations_created_at', 'created_at'),
    )


class InviteRewardLog(Base):
    """邀请奖励流水"""
    __tablename__ = "invite_reward_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    inviter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), comment="邀请人ID")
    invitee_id: Mapped[int] = mapped_column(ForeignKey("users.id"), comment="被邀请人ID")
    reward_type: Mapped[str] = mapped_column(String(30), default="invite_register", comment="奖励类型")
    coins: Mapped[int] = mapped_column(Integer, default=0, comment="奖励书币")

    __table_args__ = (
        Index('ix_invite_reward_logs_inviter_id', 'inviter_id'),
        Index('ix_invite_reward_logs_invitee_id', 'invitee_id'),
        Index('ix_invite_reward_logs_reward_type', 'reward_type'),
        Index('ix_invite_reward_logs_created_at', 'created_at'),
    )


class UserSetting(Base):
    """用户设置"""
    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, unique=True)

    content_rating: Mapped[str] = mapped_column(String(20), default="all")
    search_button_mode: Mapped[str] = mapped_column(String(20), default="preview")
    hide_personal_info: Mapped[bool] = mapped_column(Boolean, default=False)
    hide_upload_list: Mapped[bool] = mapped_column(Boolean, default=False)
    close_upload_feedback: Mapped[bool] = mapped_column(Boolean, default=False)
    close_invite_feedback: Mapped[bool] = mapped_column(Boolean, default=False)
    close_download_feedback: Mapped[bool] = mapped_column(Boolean, default=False)
    close_book_update_notice: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        Index("ix_user_settings_user_id", "user_id"),
    )


# ============================================
# 书单 / 评价 / 审核 / 审计
# ============================================

class BookList(Base):
    """用户书单"""
    __tablename__ = "booklists"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, comment="书单归属用户")
    name: Mapped[str] = mapped_column(String(80), nullable=False, comment="书单名称")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否默认书单")
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否公开分享")
    share_token: Mapped[Optional[str]] = mapped_column(String(40), nullable=True, unique=True, comment="分享令牌")

    items: Mapped[List["BookListItem"]] = relationship("BookListItem", back_populates="booklist", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_booklists_user_name"),
        Index("ix_booklists_user_id", "user_id"),
        Index("ix_booklists_is_public", "is_public"),
    )


class BookListItem(Base):
    """书单条目"""
    __tablename__ = "booklist_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    list_id: Mapped[int] = mapped_column(ForeignKey("booklists.id"), nullable=False, comment="书单ID")
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), nullable=False, comment="书籍ID")
    added_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, comment="添加人ID")

    booklist: Mapped["BookList"] = relationship("BookList", back_populates="items", lazy="selectin")
    book: Mapped["Book"] = relationship("Book", back_populates="booklist_items", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("list_id", "book_id", name="uq_booklist_items_unique"),
        Index("ix_booklist_items_list_id", "list_id"),
        Index("ix_booklist_items_book_id", "book_id"),
    )


class BookReview(Base):
    """用户书籍评分与短评（每用户每书唯一）"""
    __tablename__ = "book_reviews"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, comment="用户ID")
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), nullable=False, comment="书籍ID")
    rating: Mapped[int] = mapped_column(Integer, nullable=False, default=5, comment="评分(1-5)")
    comment: Mapped[Optional[str]] = mapped_column(String(240), nullable=True, comment="短评")

    book: Mapped["Book"] = relationship("Book", back_populates="reviews", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("user_id", "book_id", name="uq_book_reviews_user_book"),
        Index("ix_book_reviews_book_id", "book_id"),
        Index("ix_book_reviews_user_id", "user_id"),
        Index("ix_book_reviews_updated_at", "updated_at"),
    )


class TagApplication(Base):
    """用户标签申请，管理员审核后生效"""
    __tablename__ = "tag_applications"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, comment="申请用户")
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), nullable=False, comment="书籍ID")
    tag_name: Mapped[str] = mapped_column(String(50), nullable=False, comment="申请标签")
    status: Mapped[str] = mapped_column(String(20), default="pending", comment="状态: pending/approved/rejected")
    reviewed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, comment="审核人")
    review_note: Mapped[Optional[str]] = mapped_column(String(240), nullable=True, comment="审核备注")
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, comment="审核时间")

    __table_args__ = (
        Index("ix_tag_applications_book_id", "book_id"),
        Index("ix_tag_applications_user_id", "user_id"),
        Index("ix_tag_applications_status", "status"),
        Index("ix_tag_applications_created_at", "created_at"),
    )


class BookEditHistory(Base):
    """管理员编辑历史"""
    __tablename__ = "book_edit_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), nullable=False, comment="书籍ID")
    editor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, comment="编辑人")
    field_name: Mapped[str] = mapped_column(String(40), nullable=False, comment="字段")
    old_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="旧值")
    new_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="新值")

    __table_args__ = (
        Index("ix_book_edit_history_book_id", "book_id"),
        Index("ix_book_edit_history_editor_id", "editor_id"),
        Index("ix_book_edit_history_created_at", "created_at"),
    )


class TagAuditLog(Base):
    """标签变更审计日志（含管理员删除）"""
    __tablename__ = "tag_audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), nullable=False, comment="书籍ID")
    tag_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tags.id"), nullable=True, comment="标签ID")
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, comment="操作人")
    action: Mapped[str] = mapped_column(String(20), nullable=False, comment="动作:add/remove/review")
    detail: Mapped[Optional[str]] = mapped_column(String(240), nullable=True, comment="备注")

    __table_args__ = (
        Index("ix_tag_audit_logs_book_id", "book_id"),
        Index("ix_tag_audit_logs_actor_id", "actor_id"),
        Index("ix_tag_audit_logs_action", "action"),
        Index("ix_tag_audit_logs_created_at", "created_at"),
    )


# ============================================
# 日志相关模型
# ============================================

class DownloadLog(Base):
    """下载记录模型"""
    __tablename__ = "download_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(BigInteger, comment="用户ID")
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), comment="书籍ID")
    file_hash: Mapped[str] = mapped_column(String(64), comment="文件哈希")

    # 下载信息
    cost_coins: Mapped[int] = mapped_column(Integer, default=0, comment="消耗书币")
    is_free: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否免费")

    # 索引
    __table_args__ = (
        Index('ix_download_logs_user_id', 'user_id'),
        Index('ix_download_logs_book_id', 'book_id'),
        Index('ix_download_logs_created_at', 'created_at'),
    )


class SearchLog(Base):
    """搜索记录模型"""
    __tablename__ = "search_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    user_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, comment="用户ID")
    keyword: Mapped[str] = mapped_column(Text, comment="搜索关键词")

    # 搜索结果
    result_count: Mapped[int] = mapped_column(Integer, default=0, comment="结果数量")
    execution_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="执行时间(ms)")

    # 筛选条件
    filters: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="筛选条件(JSON)")

    # 索引
    __table_args__ = (
        Index('ix_search_logs_user_id', 'user_id'),
        Index('ix_search_logs_keyword', 'keyword'),
        Index('ix_search_logs_created_at', 'created_at'),
    )
