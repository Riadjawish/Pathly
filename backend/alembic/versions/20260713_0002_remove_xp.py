"""Remove XP in favor of direct study progress.

Revision ID: 20260713_0002
Revises: 20260713_0001
Create Date: 2026-07-13
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260713_0002"
down_revision: str | None = "20260713_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _column_names(table_name: str) -> set[str]:
    return {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns(table_name)
    }


def _check_names(table_name: str) -> set[str]:
    return {
        constraint["name"]
        for constraint in sa.inspect(op.get_bind()).get_check_constraints(table_name)
        if constraint["name"]
    }


def upgrade() -> None:
    tables = _table_names()
    if "xp_transactions" in tables:
        op.drop_table("xp_transactions")

    removals = (
        ("users", "xp", None),
        ("learning_levels", "xp_reward", "xp_nonnegative"),
        ("quiz_attempts", "xp_earned", "xp_nonnegative"),
        ("progress_events", "xp_delta", None),
    )
    for table_name, column_name, check_name in removals:
        if table_name not in tables or column_name not in _column_names(table_name):
            continue
        if check_name and check_name in _check_names(table_name):
            op.drop_constraint(check_name, table_name, type_="check")
        op.drop_column(table_name, column_name)


def downgrade() -> None:
    tables = _table_names()
    additions = (
        ("users", sa.Column("xp", sa.Integer(), server_default="0", nullable=False)),
        (
            "learning_levels",
            sa.Column("xp_reward", sa.Integer(), server_default="20", nullable=False),
        ),
        (
            "quiz_attempts",
            sa.Column("xp_earned", sa.Integer(), server_default="0", nullable=False),
        ),
        (
            "progress_events",
            sa.Column("xp_delta", sa.Integer(), server_default="0", nullable=False),
        ),
    )
    for table_name, column in additions:
        if table_name in tables and column.name not in _column_names(table_name):
            op.add_column(table_name, column)

    if "learning_levels" in tables and "xp_nonnegative" not in _check_names(
        "learning_levels"
    ):
        op.create_check_constraint(
            "xp_nonnegative", "learning_levels", "xp_reward >= 0"
        )
    if "quiz_attempts" in tables and "xp_nonnegative" not in _check_names(
        "quiz_attempts"
    ):
        op.create_check_constraint(
            "xp_nonnegative", "quiz_attempts", "xp_earned >= 0"
        )

    if "xp_transactions" not in tables:
        op.create_table(
            "xp_transactions",
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("subject_id", sa.Uuid(), nullable=True),
            sa.Column("amount", sa.Integer(), nullable=False),
            sa.Column("balance_after", sa.Integer(), nullable=False),
            sa.Column("reason", sa.String(length=120), nullable=False),
            sa.Column("source_id", sa.Uuid(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.CheckConstraint("balance_after >= 0", name="balance_nonnegative"),
            sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_xp_transactions_subject_id"),
            "xp_transactions",
            ["subject_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_xp_transactions_user_id"),
            "xp_transactions",
            ["user_id"],
            unique=False,
        )
