"""stock obligatorio

Revision ID: fdd811483a1b
Revises: 307681d48bc2
Create Date: 2026-09-03 22:21:38.652009

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fdd811483a1b"
down_revision: str | Sequence[str] | None = "307681d48bc2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(sa.text("UPDATE products SET stock = 0 WHERE stock IS NULL"))
    with op.batch_alter_table("products") as batch_op:
        batch_op.drop_constraint("ck_products_stock_non_negative", type_="check")
        batch_op.alter_column("stock", existing_type=sa.INTEGER(), nullable=False)
        batch_op.create_check_constraint("ck_products_stock_non_negative", "stock >= 0")


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("products") as batch_op:
        batch_op.drop_constraint("ck_products_stock_non_negative", type_="check")
        batch_op.alter_column("stock", existing_type=sa.INTEGER(), nullable=True)
        batch_op.create_check_constraint(
            "ck_products_stock_non_negative", "stock IS NULL OR stock >= 0"
        )
