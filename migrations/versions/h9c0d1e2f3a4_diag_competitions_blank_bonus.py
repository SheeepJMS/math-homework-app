"""add blank_bonus to diag_competitions

Revision ID: h9c0d1e2f3a4
Revises: g8b9c0d1e2f3
Create Date: 2025-02-14

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import ProgrammingError

revision = 'h9c0d1e2f3a4'
down_revision = 'g8b9c0d1e2f3'
branch_labels = None
depends_on = None


def upgrade():
    try:
        op.add_column('diag_competitions', sa.Column('blank_bonus', sa.Integer(), nullable=True, server_default=sa.text('0')))
    except ProgrammingError as e:
        if 'already exists' not in str(e).lower():
            raise


def downgrade():
    op.drop_column('diag_competitions', 'blank_bonus')
