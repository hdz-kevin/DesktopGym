"""quitar genero y fecha de nacimiento

Revision ID: c4f8b2a1d760
Revises: a8c4e2f91b30
Create Date: 2026-09-17 10:45:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4f8b2a1d760"
down_revision: str | Sequence[str] | None = "a8c4e2f91b30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("members") as batch_op:
        batch_op.drop_column("gender")
        batch_op.drop_column("birth_date")


def downgrade() -> None:
    with op.batch_alter_table("members") as batch_op:
        batch_op.add_column(sa.Column("gender", sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column("birth_date", sa.Date(), nullable=True))

    op.execute("UPDATE members SET gender = 'female' WHERE gender IS NULL")

    with op.batch_alter_table("members") as batch_op:
        batch_op.alter_column("gender", existing_type=sa.String(length=10), nullable=False)
