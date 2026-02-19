"""add solution_image_url to diag_questions

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2025-02-12

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    insp = inspect(conn)
    if not insp.has_table('diag_questions'):
        return
    cols = [c['name'] for c in insp.get_columns('diag_questions')]
    if 'solution_image_url' not in cols:
        op.add_column('diag_questions', sa.Column('solution_image_url', sa.String(length=512), nullable=True))


def downgrade():
    op.drop_column('diag_questions', 'solution_image_url')
