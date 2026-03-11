"""add invite persistence tables

Revision ID: 20260311_0001
Revises:
Create Date: 2026-03-11 06:20:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260311_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "invite_relations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("inviter_id", sa.BigInteger(), nullable=False),
        sa.Column("invitee_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["inviter_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["invitee_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invitee_id", name="uq_invitee_once"),
    )
    op.create_index("ix_invite_relations_inviter_id", "invite_relations", ["inviter_id"], unique=False)
    op.create_index("ix_invite_relations_invitee_id", "invite_relations", ["invitee_id"], unique=False)
    op.create_index("ix_invite_relations_created_at", "invite_relations", ["created_at"], unique=False)

    op.create_table(
        "invite_reward_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("inviter_id", sa.BigInteger(), nullable=False),
        sa.Column("invitee_id", sa.BigInteger(), nullable=False),
        sa.Column("reward_type", sa.String(length=30), nullable=False, server_default="invite_register"),
        sa.Column("coins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["inviter_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["invitee_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_invite_reward_logs_inviter_id", "invite_reward_logs", ["inviter_id"], unique=False)
    op.create_index("ix_invite_reward_logs_invitee_id", "invite_reward_logs", ["invitee_id"], unique=False)
    op.create_index("ix_invite_reward_logs_reward_type", "invite_reward_logs", ["reward_type"], unique=False)
    op.create_index("ix_invite_reward_logs_created_at", "invite_reward_logs", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_invite_reward_logs_created_at", table_name="invite_reward_logs")
    op.drop_index("ix_invite_reward_logs_reward_type", table_name="invite_reward_logs")
    op.drop_index("ix_invite_reward_logs_invitee_id", table_name="invite_reward_logs")
    op.drop_index("ix_invite_reward_logs_inviter_id", table_name="invite_reward_logs")
    op.drop_table("invite_reward_logs")

    op.drop_index("ix_invite_relations_created_at", table_name="invite_relations")
    op.drop_index("ix_invite_relations_invitee_id", table_name="invite_relations")
    op.drop_index("ix_invite_relations_inviter_id", table_name="invite_relations")
    op.drop_table("invite_relations")
