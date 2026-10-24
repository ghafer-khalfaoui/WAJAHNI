"""Add plan groups, prerequisite notes, corequisite and alternative flags

Revision ID: f3a9c1d7e054
Revises: d9e1b3c5a728
Create Date: 2026-10-24

Study-plan details: which plan group a course belongs to, non-course conditions
(e.g. "Placement test"), whether a prerequisite is a corequisite, and "A or B" alternatives.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f3a9c1d7e054"
down_revision: Union[str, None] = "d9e1b3c5a728"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("courses", sa.Column("plan_groups", sa.JSON(), nullable=True))
    op.add_column("courses", sa.Column("prerequisite_note", sa.Text(), nullable=True))
    op.add_column("course_prerequisites", sa.Column("corequisite", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("course_prerequisites", sa.Column("alt_group", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("course_prerequisites", "alt_group")
    op.drop_column("course_prerequisites", "corequisite")
    op.drop_column("courses", "prerequisite_note")
    op.drop_column("courses", "plan_groups")
