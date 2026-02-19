"""add year column to diag_exams

Revision ID: j1e2f3a4b5c6
Revises: i0d1e2f3a4b5
Create Date: 2025-02-14

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import ProgrammingError

revision = 'j1e2f3a4b5c6'
down_revision = 'i0d1e2f3a4b5'
branch_labels = None
depends_on = None


def upgrade():
    try:
        op.add_column('diag_exams', sa.Column('year', sa.Integer(), nullable=True))
    except ProgrammingError as e:
        if 'already exists' not in str(e).lower():
            raise


def downgrade():
    op.drop_column('diag_exams', 'year')
