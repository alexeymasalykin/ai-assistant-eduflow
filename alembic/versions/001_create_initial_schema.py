"""Create initial schema for EduFlow AI Assistant.

Revision ID: 001_create_initial_schema
Revises:
Create Date: 2026-04-02 12:00:00.000000

This migration creates the initial database schema with three tables:
- user_mappings: Maps Wappi chat IDs to Bitrix deals and contacts
- dialog_logs: Logs all messages with role and agent type
- analytics: Per-request analytics with response time and success
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "001_create_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create initial schema tables."""
    # user_mappings table
    op.create_table(
        "user_mappings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("wappi_chat_id", sa.String(255), unique=True, nullable=False),
        sa.Column("bitrix_deal_id", sa.Integer, nullable=False),
        sa.Column("bitrix_contact_id", sa.Integer, nullable=True),
        sa.Column("channel", sa.String(50), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Index on bitrix_deal_id for filtering by deal
    op.create_index("ix_user_mappings_deal_id", "user_mappings", ["bitrix_deal_id"])

    # dialog_logs table (no FK to user_mappings, uses wappi_chat_id directly)
    op.create_table(
        "dialog_logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("wappi_chat_id", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("agent_type", sa.String(50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Index on wappi_chat_id for filtering logs by chat
    op.create_index("ix_dialog_logs_wappi_chat_id", "dialog_logs", ["wappi_chat_id"])

    # analytics table — per-request tracking
    op.create_table(
        "analytics",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("agent_type", sa.String(50), nullable=False),
        sa.Column("response_time_ms", sa.Integer, nullable=True),
        sa.Column("success", sa.Boolean, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Index on created_at for time-range queries
    op.create_index("ix_analytics_created_at", "analytics", ["created_at"])


def downgrade() -> None:
    """Drop all tables created in upgrade."""
    op.drop_table("analytics")
    op.drop_table("dialog_logs")
    op.drop_table("user_mappings")
