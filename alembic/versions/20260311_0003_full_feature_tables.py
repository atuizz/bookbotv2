"""add booklist review moderation and audit tables

Revision ID: 20260311_0003
Revises: 20260311_0002
Create Date: 2026-03-11 11:40:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260311_0003"
down_revision: Union[str, None] = "20260311_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "booklists",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("share_token", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("share_token"),
        sa.UniqueConstraint("user_id", "name", name="uq_booklists_user_name"),
    )
    op.create_index("ix_booklists_user_id", "booklists", ["user_id"], unique=False)
    op.create_index("ix_booklists_is_public", "booklists", ["is_public"], unique=False)

    op.create_table(
        "booklist_items",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("list_id", sa.BigInteger(), nullable=False),
        sa.Column("book_id", sa.BigInteger(), nullable=False),
        sa.Column("added_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["list_id"], ["booklists.id"]),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("list_id", "book_id", name="uq_booklist_items_unique"),
    )
    op.create_index("ix_booklist_items_list_id", "booklist_items", ["list_id"], unique=False)
    op.create_index("ix_booklist_items_book_id", "booklist_items", ["book_id"], unique=False)

    op.create_table(
        "book_reviews",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("book_id", sa.BigInteger(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("comment", sa.String(length=240), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "book_id", name="uq_book_reviews_user_book"),
    )
    op.create_index("ix_book_reviews_book_id", "book_reviews", ["book_id"], unique=False)
    op.create_index("ix_book_reviews_user_id", "book_reviews", ["user_id"], unique=False)
    op.create_index("ix_book_reviews_updated_at", "book_reviews", ["updated_at"], unique=False)

    op.create_table(
        "tag_applications",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("book_id", sa.BigInteger(), nullable=False),
        sa.Column("tag_name", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("reviewed_by", sa.BigInteger(), nullable=True),
        sa.Column("review_note", sa.String(length=240), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"]),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tag_applications_book_id", "tag_applications", ["book_id"], unique=False)
    op.create_index("ix_tag_applications_user_id", "tag_applications", ["user_id"], unique=False)
    op.create_index("ix_tag_applications_status", "tag_applications", ["status"], unique=False)
    op.create_index("ix_tag_applications_created_at", "tag_applications", ["created_at"], unique=False)

    op.create_table(
        "book_edit_history",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("book_id", sa.BigInteger(), nullable=False),
        sa.Column("editor_id", sa.BigInteger(), nullable=False),
        sa.Column("field_name", sa.String(length=40), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"]),
        sa.ForeignKeyConstraint(["editor_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_book_edit_history_book_id", "book_edit_history", ["book_id"], unique=False)
    op.create_index("ix_book_edit_history_editor_id", "book_edit_history", ["editor_id"], unique=False)
    op.create_index("ix_book_edit_history_created_at", "book_edit_history", ["created_at"], unique=False)

    op.create_table(
        "tag_audit_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("book_id", sa.BigInteger(), nullable=False),
        sa.Column("tag_id", sa.BigInteger(), nullable=True),
        sa.Column("actor_id", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("detail", sa.String(length=240), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"]),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"]),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tag_audit_logs_book_id", "tag_audit_logs", ["book_id"], unique=False)
    op.create_index("ix_tag_audit_logs_actor_id", "tag_audit_logs", ["actor_id"], unique=False)
    op.create_index("ix_tag_audit_logs_action", "tag_audit_logs", ["action"], unique=False)
    op.create_index("ix_tag_audit_logs_created_at", "tag_audit_logs", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_tag_audit_logs_created_at", table_name="tag_audit_logs")
    op.drop_index("ix_tag_audit_logs_action", table_name="tag_audit_logs")
    op.drop_index("ix_tag_audit_logs_actor_id", table_name="tag_audit_logs")
    op.drop_index("ix_tag_audit_logs_book_id", table_name="tag_audit_logs")
    op.drop_table("tag_audit_logs")

    op.drop_index("ix_book_edit_history_created_at", table_name="book_edit_history")
    op.drop_index("ix_book_edit_history_editor_id", table_name="book_edit_history")
    op.drop_index("ix_book_edit_history_book_id", table_name="book_edit_history")
    op.drop_table("book_edit_history")

    op.drop_index("ix_tag_applications_created_at", table_name="tag_applications")
    op.drop_index("ix_tag_applications_status", table_name="tag_applications")
    op.drop_index("ix_tag_applications_user_id", table_name="tag_applications")
    op.drop_index("ix_tag_applications_book_id", table_name="tag_applications")
    op.drop_table("tag_applications")

    op.drop_index("ix_book_reviews_updated_at", table_name="book_reviews")
    op.drop_index("ix_book_reviews_user_id", table_name="book_reviews")
    op.drop_index("ix_book_reviews_book_id", table_name="book_reviews")
    op.drop_table("book_reviews")

    op.drop_index("ix_booklist_items_book_id", table_name="booklist_items")
    op.drop_index("ix_booklist_items_list_id", table_name="booklist_items")
    op.drop_table("booklist_items")

    op.drop_index("ix_booklists_is_public", table_name="booklists")
    op.drop_index("ix_booklists_user_id", table_name="booklists")
    op.drop_table("booklists")
