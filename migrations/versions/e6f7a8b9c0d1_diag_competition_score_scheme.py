"""add score_scheme to diag_competitions

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2025-02-12

"""
from alembic import op
import sqlalchemy as sa


revision = 'e6f7a8b9c0d1'
down_revision = 'd5e6f7a8b9c0'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('diag_competitions', sa.Column('score_scheme', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('diag_competitions', 'score_scheme')
