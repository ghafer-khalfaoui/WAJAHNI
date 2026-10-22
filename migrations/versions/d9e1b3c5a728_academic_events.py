"""Add academic_events

Revision ID: d9e1b3c5a728
Revises: c7d2f4a8b516
Create Date: 2026-10-23

Official academic calendar entries (tenant-scoped, with source and verified flag).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d9e1b3c5a728"
down_revision: Union[str, None] = "c7d2f4a8b516"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "academic_events",
        sa.Column("university_id", sa.Integer(), nullable=False),
        sa.Column("semester", sa.String(length=20), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("source", sa.String(length=255), nullable=True),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["university_id"], ["universities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("university_id", "semester", "start_date", "title", name="uq_academic_events_entry"),
        sa.CheckConstraint("end_date >= start_date", name="ck_academic_event_dates"),
    )
    op.create_index(op.f("ix_academic_events_id"), "academic_events", ["id"], unique=False)
    op.create_index(op.f("ix_academic_events_university_id"), "academic_events", ["university_id"], unique=False)
    op.create_index(op.f("ix_academic_events_start_date"), "academic_events", ["start_date"], unique=False)


def downgrade() -> None:
    op.drop_table("academic_events")
