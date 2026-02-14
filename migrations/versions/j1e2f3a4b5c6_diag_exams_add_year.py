"""add year column to diag_exams

Revision ID: j1e2f3a4b5c6
Revises: i0d1e2f3a4b5
Create Date: 2025-02-14

"""
from alembic import op
import sqlalchemy as sa


revision = 'j1e2f3a4b5c6'
down_revision = 'i0d1e2f3a4b5'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('diag_exams', sa.Column('year', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('diag_exams', 'year')
