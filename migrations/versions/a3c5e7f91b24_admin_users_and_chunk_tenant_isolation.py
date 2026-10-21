"""Add admin_users; make documentchunks.university_id mandatory

Revision ID: a3c5e7f91b24
Revises: 8770692a9cc5
Create Date: 2026-10-21

Fixes drift between the models and the database (issue WJ-007) and makes
tenant filtering on chunks possible (WJ-008). Existing data is kept: chunks
get their university_id copied from their parent document before the column
becomes NOT NULL.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a3c5e7f91b24"
down_revision: Union[str, None] = "8770692a9cc5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "admin_users",
        sa.Column("university_id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["university_id"], ["universities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index(op.f("ix_admin_users_id"), "admin_users", ["id"], unique=False)
    op.create_index(op.f("ix_admin_users_university_id"), "admin_users", ["university_id"], unique=False)
    op.create_index(op.f("ix_admin_users_username"), "admin_users", ["username"], unique=True)

    # Every chunk has a NOT NULL document_id, so this backfill covers all rows.
    op.execute(
        "UPDATE documentchunks c SET university_id = d.university_id "
        "FROM documents d WHERE c.document_id = d.id AND c.university_id IS NULL"
    )
    op.alter_column("documentchunks", "university_id", existing_type=sa.Integer(), nullable=False)
    op.create_foreign_key(
        "documentchunks_university_id_fkey",
        "documentchunks",
        "universities",
        ["university_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("documentchunks_university_id_fkey", "documentchunks", type_="foreignkey")
    op.alter_column("documentchunks", "university_id", existing_type=sa.Integer(), nullable=True)
    op.drop_index(op.f("ix_admin_users_username"), table_name="admin_users")
    op.drop_index(op.f("ix_admin_users_university_id"), table_name="admin_users")
    op.drop_index(op.f("ix_admin_users_id"), table_name="admin_users")
    op.drop_table("admin_users")
