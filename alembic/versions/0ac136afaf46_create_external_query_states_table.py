"""create external_query_states table

Revision ID: 0ac136afaf46
Revises: 618c7ea43c41
Create Date: 2026-06-13 22:15:32.707102

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0ac136afaf46'
down_revision: Union[str, Sequence[str], None] = '618c7ea43c41'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "external_query_states",
        sa.Column("id", sa.Integer(), primary_key=True),

        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("query_hash", sa.String(length=255), nullable=False),

        sa.Column("last_fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_success_count", sa.Integer(), nullable=False, server_default="0"),

        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),

        sa.UniqueConstraint("source", "query_hash", name="uq_source_query_hash")
    )

    op.create_index(
        "ix_external_query_states_source_query",
        "external_query_states",
        ["source", "query_hash"]
    )


def downgrade() -> None:
    op.drop_index("ix_external_query_states_source_query", table_name="external_query_states")
    op.drop_table("external_query_states")
