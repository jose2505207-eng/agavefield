"""add app_sessions table (server-side session revocation)

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-29 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'app_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('jti', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['app_users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_app_sessions_jti'), 'app_sessions', ['jti'], unique=True)
    op.create_index(op.f('ix_app_sessions_user_id'), 'app_sessions', ['user_id'], unique=False)
    op.create_index(op.f('ix_app_sessions_username'), 'app_sessions', ['username'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_app_sessions_username'), table_name='app_sessions')
    op.drop_index(op.f('ix_app_sessions_user_id'), table_name='app_sessions')
    op.drop_index(op.f('ix_app_sessions_jti'), table_name='app_sessions')
    op.drop_table('app_sessions')
