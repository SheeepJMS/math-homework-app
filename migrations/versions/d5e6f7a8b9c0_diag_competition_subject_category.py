"""add subject and category to diag_competitions

Revision ID: d5e6f7a8b9c0
Revises: c3d4e5f6a7b8
Create Date: 2025-02-12

"""
from alembic import op
import sqlalchemy as sa


revision = 'd5e6f7a8b9c0'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('diag_competitions', sa.Column('subject', sa.String(length=80), nullable=True))
    op.add_column('diag_competitions', sa.Column('category', sa.String(length=80), nullable=True))


def downgrade():
    op.drop_column('diag_competitions', 'category')
    op.drop_column('diag_competitions', 'subject')
