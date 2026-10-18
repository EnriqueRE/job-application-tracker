"""app links

Revision ID: 8c4e2d1f9a60
Revises: 3b1f0c9a7d21
Create Date: 2026-10-17 21:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8c4e2d1f9a60"
down_revision: str | Sequence[str] | None = "3b1f0c9a7d21"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "app_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "application_id",
            sa.Integer(),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("url", sa.String(2000), nullable=False),
    )
    op.create_index("ix_app_links_application_id", "app_links", ["application_id"])


def downgrade() -> None:
    op.drop_table("app_links")
