"""renombrar periodos a pagos

Revision ID: 307681d48bc2
Revises: f6b68cdb4271
Create Date: 2026-08-25 19:21:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "307681d48bc2"
down_revision: str | Sequence[str] | None = "f6b68cdb4271"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    SQLite puede renombrar la tabla sin recrearla. batch_alter_table fallaria
    al borrar `periods` si ya hay filas, porque memberships las referencian
    al reves: payments apunta a memberships, no al contrario, pero recrear
    igualmente es mas fragil que RENAME.
    """
    op.rename_table("periods", "payments")
    op.execute("DROP INDEX IF EXISTS ix_periods_membership_end")
    op.execute("CREATE INDEX ix_payments_membership_end ON payments (membership_id, end_date)")
    op.execute("DROP INDEX IF EXISTS ix_periods_start_date")
    op.execute("CREATE INDEX ix_payments_start_date ON payments (start_date)")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS ix_payments_membership_end")
    op.execute("CREATE INDEX ix_periods_membership_end ON payments (membership_id, end_date)")
    op.execute("DROP INDEX IF EXISTS ix_payments_start_date")
    op.execute("CREATE INDEX ix_periods_start_date ON payments (start_date)")
    op.rename_table("payments", "periods")
