"""renombrar catalogo a categorias y planes

Revision ID: f6b68cdb4271
Revises: e3c75012dc99
Create Date: 2026-08-25 17:28:19.080981

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6b68cdb4271"
down_revision: str | Sequence[str] | None = "e3c75012dc99"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    SQLite puede renombrar tablas y columnas sin recrearlas. batch_alter_table
    recrea la tabla y al borrar `durations` falla si ya hay periodos, porque
    conservan la llave foranea.
    """
    op.rename_table("membership_types", "plan_categories")
    op.execute("ALTER TABLE durations RENAME COLUMN membership_type_id TO plan_category_id")
    op.rename_table("durations", "plans")
    op.execute("ALTER TABLE memberships RENAME COLUMN membership_type_id TO plan_category_id")
    op.execute("ALTER TABLE periods RENAME COLUMN duration_id TO plan_id")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("ALTER TABLE periods RENAME COLUMN plan_id TO duration_id")
    op.execute("ALTER TABLE memberships RENAME COLUMN plan_category_id TO membership_type_id")
    op.rename_table("plans", "durations")
    op.execute("ALTER TABLE durations RENAME COLUMN plan_category_id TO membership_type_id")
    op.rename_table("plan_categories", "membership_types")
