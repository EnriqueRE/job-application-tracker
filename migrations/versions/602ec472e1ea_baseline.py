"""baseline

Revision ID: 602ec472e1ea
Revises:
Create Date: 2026-10-17 18:56:04.122862

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "602ec472e1ea"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
