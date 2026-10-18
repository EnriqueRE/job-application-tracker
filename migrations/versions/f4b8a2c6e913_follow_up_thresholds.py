"""follow-up thresholds

Revision ID: f4b8a2c6e913
Revises: e9d3b6a4c158
Create Date: 2026-10-17 22:30:00

"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "f4b8a2c6e913"
down_revision: str | Sequence[str] | None = "e9d3b6a4c158"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_DAYS = {"applied": 7, "screening": 5, "interviewing": 3}


def upgrade() -> None:
    table = op.create_table(
        "follow_up_thresholds",
        sa.Column("status", sa.String(20), primary_key=True),
        sa.Column("days", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("days BETWEEN 1 AND 365", name="ck_follow_up_thresholds_days"),
        sa.CheckConstraint(
            "status IN ('applied', 'screening', 'interviewing')",
            name="ck_follow_up_thresholds_open_status",
        ),
    )
    now = datetime.now(UTC)
    op.bulk_insert(
        table,
        [
            {"status": status, "days": days, "updated_at": now}
            for status, days in DEFAULT_DAYS.items()
        ],
    )


def downgrade() -> None:
    op.drop_table("follow_up_thresholds")
