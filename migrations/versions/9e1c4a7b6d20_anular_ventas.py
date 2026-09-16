"""anular ventas

Revision ID: 9e1c4a7b6d20
Revises: fdd811483a1b
Create Date: 2026-09-16 13:53:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9e1c4a7b6d20"
down_revision: str | Sequence[str] | None = "fdd811483a1b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("sales") as batch_op:
        batch_op.add_column(sa.Column("voided_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("sales") as batch_op:
        batch_op.drop_column("voided_at")
