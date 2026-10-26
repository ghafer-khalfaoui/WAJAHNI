"""Add programs and program_courses; make plan_entries belong to a program

Revision ID: c5f1a7d3e826
Revises: b4e8d2a6c913
Create Date: 2026-10-26

A course code such as MATH101 is shared by many degree programs, so which requirement table a course
sits in must be stored per program, not on the course. Existing plan_entries are kept (program_id stays
empty until the plan is imported again with the new file format, which replaces them).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c5f1a7d3e826"
down_revision: Union[str, None] = "b4e8d2a6c913"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _audit_columns() -> list:
    return [
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "programs",
        sa.Column("university_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=60), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("school", sa.String(length=120), nullable=True),
        sa.Column("degree", sa.String(length=30), nullable=True),
        sa.Column("plan_version", sa.String(length=30), nullable=True),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=255), nullable=True),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["university_id"], ["universities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("university_id", "code", name="uq_programs_university_code"),
    )
    op.create_index(op.f("ix_programs_id"), "programs", ["id"], unique=False)
    op.create_index(op.f("ix_programs_university_id"), "programs", ["university_id"], unique=False)

    op.create_table(
        "program_courses",
        sa.Column("university_id", sa.Integer(), nullable=False),
        sa.Column("program_id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("group_title", sa.String(length=255), nullable=False),
        sa.Column("scope", sa.String(length=20), nullable=True),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("track", sa.String(length=80), nullable=True),
        sa.Column("source", sa.String(length=255), nullable=True),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["university_id"], ["universities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["program_id"], ["programs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("program_id", "course_id", "group_title", name="uq_program_courses_entry"),
    )
    op.create_index(op.f("ix_program_courses_id"), "program_courses", ["id"], unique=False)
    op.create_index(op.f("ix_program_courses_university_id"), "program_courses", ["university_id"], unique=False)
    op.create_index(op.f("ix_program_courses_program_id"), "program_courses", ["program_id"], unique=False)
    op.create_index(op.f("ix_program_courses_course_id"), "program_courses", ["course_id"], unique=False)

    op.add_column("plan_entries", sa.Column("program_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_plan_entries_program_id", "plan_entries", "programs", ["program_id"], ["id"],
                          ondelete="CASCADE")
    op.create_index(op.f("ix_plan_entries_program_id"), "plan_entries", ["program_id"], unique=False)
    op.alter_column("plan_entries", "track", existing_type=sa.String(length=30), type_=sa.String(length=80),
                    existing_nullable=False)
    op.drop_constraint("uq_plan_entries_slot", "plan_entries", type_="unique")
    op.create_unique_constraint("uq_plan_entries_slot", "plan_entries",
                                ["university_id", "program_id", "track", "year", "semester", "position"])


def downgrade() -> None:
    op.drop_constraint("uq_plan_entries_slot", "plan_entries", type_="unique")
    op.create_unique_constraint("uq_plan_entries_slot", "plan_entries",
                                ["university_id", "track", "year", "semester", "position"])
    op.alter_column("plan_entries", "track", existing_type=sa.String(length=80), type_=sa.String(length=30),
                    existing_nullable=False)
    op.drop_index(op.f("ix_plan_entries_program_id"), table_name="plan_entries")
    op.drop_constraint("fk_plan_entries_program_id", "plan_entries", type_="foreignkey")
    op.drop_column("plan_entries", "program_id")
    op.drop_table("program_courses")
    op.drop_table("programs")
