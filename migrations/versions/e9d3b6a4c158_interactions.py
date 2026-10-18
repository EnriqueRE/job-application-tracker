"""interactions

Revision ID: e9d3b6a4c158
Revises: c2a7e5b81d34
Create Date: 2026-10-17 22:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e9d3b6a4c158"
down_revision: str | Sequence[str] | None = "c2a7e5b81d34"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CHANNELS = ("email", "linkedin", "phone", "video", "in_person", "other")


def upgrade() -> None:
    op.create_table(
        "interactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "application_id",
            sa.Integer(),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "contact_id",
            sa.Integer(),
            sa.ForeignKey("contacts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column(
            "channel",
            sa.Enum(
                *CHANNELS,
                name="interaction_channel",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_interactions_application_id", "interactions", ["application_id"])
    op.create_index("ix_interactions_contact_id", "interactions", ["contact_id"])


def downgrade() -> None:
    op.drop_table("interactions")
