"""add invite email verification + AppUser email / password-reset columns

Revision ID: d73fc3ae1bd8
Revises: b4b8620239bc
Create Date: 2026-07-01 00:40:00.000000

Additive only (all nullable / defaulted), SQLite-safe. Adds:
- ``invitations.verification_code_hash`` — optional one-time invite code (hash).
- ``app_users.email`` / ``email_verified`` — contact + verification flag.
- ``app_users.password_reset_token_hash`` / ``password_reset_expires_at`` —
  hash-only password-reset token with expiry.
"""
from alembic import op
import sqlalchemy as sa


revision = "d73fc3ae1bd8"
down_revision = "b4b8620239bc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "invitations",
        sa.Column("verification_code_hash", sa.String(length=128), nullable=True),
    )
    op.add_column("app_users", sa.Column("email", sa.String(length=255), nullable=True))
    op.add_column(
        "app_users",
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "app_users",
        sa.Column("password_reset_token_hash", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "app_users", sa.Column("password_reset_expires_at", sa.DateTime(), nullable=True)
    )
    op.create_index(op.f("ix_app_users_email"), "app_users", ["email"], unique=False)
    op.create_index(
        op.f("ix_app_users_password_reset_token_hash"),
        "app_users",
        ["password_reset_token_hash"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_app_users_password_reset_token_hash"), table_name="app_users")
    op.drop_index(op.f("ix_app_users_email"), table_name="app_users")
    op.drop_column("app_users", "password_reset_expires_at")
    op.drop_column("app_users", "password_reset_token_hash")
    op.drop_column("app_users", "email_verified")
    op.drop_column("app_users", "email")
    op.drop_column("invitations", "verification_code_hash")
