"""add diag_users.is_active for suspend

Revision ID: g8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2025-02-14

"""
from alembic import op
import sqlalchemy as sa


revision = 'g8b9c0d1e2f3'
down_revision = 'f7a8b9c0d1e2'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('diag_users', sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')))


def downgrade():
    op.drop_column('diag_users', 'is_active')
