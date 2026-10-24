"""Add plan_entries

Revision ID: b4e8d2a6c913
Revises: f3a9c1d7e054
Create Date: 2026-10-25

Study-plan guide slots: which course (or elective placeholder) sits in which year and semester of a track.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b4e8d2a6c913"
down_revision: Union[str, None] = "f3a9c1d7e054"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "plan_entries",
        sa.Column("university_id", sa.Integer(), nullable=False),
        sa.Column("track", sa.String(length=30), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("semester", sa.String(length=20), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=True),
        sa.Column("label", sa.String(length=100), nullable=True),
        sa.Column("credit_hours", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=255), nullable=True),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["university_id"], ["universities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("university_id", "track", "year", "semester", "position", name="uq_plan_entries_slot"),
        sa.CheckConstraint("course_id IS NOT NULL OR label IS NOT NULL", name="ck_plan_entry_has_content"),
    )
    op.create_index(op.f("ix_plan_entries_id"), "plan_entries", ["id"], unique=False)
    op.create_index(op.f("ix_plan_entries_university_id"), "plan_entries", ["university_id"], unique=False)


def downgrade() -> None:
    op.drop_table("plan_entries")
