"""socios categorias y pagos

Revision ID: a8c4e2f91b30
Revises: 9e1c4a7b6d20
Create Date: 2026-09-17 02:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a8c4e2f91b30"
down_revision: str | Sequence[str] | None = "9e1c4a7b6d20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Mueve la categoria al socio y los pagos dejan de pasar por membresias."""
    with op.batch_alter_table("members") as batch_op:
        batch_op.add_column(sa.Column("plan_category_id", sa.Integer(), nullable=True))

    with op.batch_alter_table("payments") as batch_op:
        batch_op.add_column(sa.Column("member_id", sa.Integer(), nullable=True))

    op.execute(
        """
        UPDATE payments
        SET member_id = (
            SELECT member_id FROM memberships
            WHERE memberships.id = payments.membership_id
        )
        """
    )
    op.execute(
        """
        UPDATE members
        SET plan_category_id = (
            SELECT plan_category_id FROM memberships
            WHERE memberships.member_id = members.id
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
        )
        """
    )
    op.execute(
        """
        UPDATE members
        SET plan_category_id = (
            SELECT id FROM plan_categories ORDER BY id LIMIT 1
        )
        WHERE plan_category_id IS NULL
        """
    )

    with op.batch_alter_table("members") as batch_op:
        batch_op.alter_column("plan_category_id", existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key(
            "fk_members_plan_category_id_plan_categories",
            "plan_categories",
            ["plan_category_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    with op.batch_alter_table("payments") as batch_op:
        batch_op.drop_index("ix_payments_membership_end")
        batch_op.drop_column("membership_id")
        batch_op.alter_column("member_id", existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key(
            "fk_payments_member_id_members",
            "members",
            ["member_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_index("ix_payments_member_end", ["member_id", "end_date"], unique=False)

    op.drop_table("memberships")


def downgrade() -> None:
    """Vuelve a agrupar los pagos en una membresia por socio."""
    op.create_table(
        "memberships",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("plan_category_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_category_id"], ["plan_categories.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.execute(
        """
        INSERT INTO memberships (member_id, plan_category_id, created_at, updated_at)
        SELECT id, plan_category_id, created_at, updated_at FROM members
        """
    )

    with op.batch_alter_table("payments") as batch_op:
        batch_op.add_column(sa.Column("membership_id", sa.Integer(), nullable=True))

    op.execute(
        """
        UPDATE payments
        SET membership_id = (
            SELECT id FROM memberships
            WHERE memberships.member_id = payments.member_id
        )
        """
    )

    with op.batch_alter_table("payments") as batch_op:
        batch_op.drop_index("ix_payments_member_end")
        batch_op.drop_column("member_id")
        batch_op.alter_column("membership_id", existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key(
            "fk_payments_membership_id_memberships",
            "memberships",
            ["membership_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_index(
            "ix_payments_membership_end", ["membership_id", "end_date"], unique=False
        )

    with op.batch_alter_table("members") as batch_op:
        batch_op.drop_constraint("fk_members_plan_category_id_plan_categories", type_="foreignkey")
        batch_op.drop_column("plan_category_id")
