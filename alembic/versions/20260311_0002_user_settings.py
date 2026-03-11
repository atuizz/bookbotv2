"""add user settings table

Revision ID: 20260311_0002
Revises: 20260311_0001
Create Date: 2026-03-11 07:10:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260311_0002"
down_revision: Union[str, None] = "20260311_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_settings",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("content_rating", sa.String(length=20), nullable=False, server_default="all"),
        sa.Column("search_button_mode", sa.String(length=20), nullable=False, server_default="preview"),
        sa.Column("hide_personal_info", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("hide_upload_list", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("close_upload_feedback", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("close_invite_feedback", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("close_download_feedback", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("close_book_update_notice", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_user_settings_user_id", "user_settings", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_user_settings_user_id", table_name="user_settings")
    op.drop_table("user_settings")
