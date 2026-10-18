"""applications and status history

Revision ID: 3b1f0c9a7d21
Revises: 602ec472e1ea
Create Date: 2026-10-17 20:00:00

Written by hand: autogenerate doesn't detect the expression indexes.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "3b1f0c9a7d21"
down_revision: str | Sequence[str] | None = "602ec472e1ea"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copy of the statuses at the time of this migration.
STATUSES = (
    "applied",
    "screening",
    "interviewing",
    "offer",
    "accepted",
    "rejected",
    "withdrawn",
    "no_response",
)


def status_column(name: str, constraint: str, *, nullable: bool) -> sa.Column[str]:
    return sa.Column(
        name,
        sa.Enum(*STATUSES, name=constraint, native_enum=False, create_constraint=True, length=20),
        nullable=nullable,
    )


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("website", sa.String(2000), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("uq_companies_name", "companies", [sa.text("lower(name)")], unique=True)

    op.create_table(
        "applications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("job_url", sa.String(2000), nullable=True),
        sa.Column("job_description", sa.Text(), nullable=False),
        sa.Column("location", sa.String(200), nullable=False),
        sa.Column("source", sa.String(200), nullable=False),
        sa.Column("applied_on", sa.Date(), nullable=False),
        status_column("status", "application_status", nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "uq_applications_company_title_applied_on",
        "applications",
        ["company_id", sa.text("lower(trim(title))"), "applied_on"],
        unique=True,
    )

    op.create_table(
        "status_changes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "application_id",
            sa.Integer(),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        status_column("from_status", "status_change_from", nullable=True),
        status_column("to_status", "status_change_to", nullable=False),
        sa.Column("changed_on", sa.Date(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_status_changes_application_id", "status_changes", ["application_id"])


def downgrade() -> None:
    op.drop_table("status_changes")
    op.drop_table("applications")
    op.drop_table("companies")
