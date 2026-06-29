"""add app_users table (admin/staff login accounts)

Revision ID: a1b2c3d4e5f6
Revises: 6e1219fdb59c
Create Date: 2026-06-29 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'a1b2c3d4e5f6'
down_revision = '6e1219fdb59c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'app_users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=64), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=True),
        sa.Column('role', sa.String(length=24), nullable=False),
        sa.Column('is_demo', sa.Boolean(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('last_login_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_app_users_username'), 'app_users', ['username'], unique=True)
    op.create_index(op.f('ix_app_users_is_demo'), 'app_users', ['is_demo'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_app_users_is_demo'), table_name='app_users')
    op.drop_index(op.f('ix_app_users_username'), table_name='app_users')
    op.drop_table('app_users')
