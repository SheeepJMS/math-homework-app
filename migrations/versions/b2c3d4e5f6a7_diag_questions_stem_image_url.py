"""add stem_image_url to diag_questions

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2025-02-12

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


def upgrade():
    conn = op.get_bind()
    insp = inspect(conn)
    if not insp.has_table('diag_questions'):
        return
    cols = [c['name'] for c in insp.get_columns('diag_questions')]
    if 'stem_image_url' not in cols:
        op.add_column('diag_questions', sa.Column('stem_image_url', sa.String(length=512), nullable=True))


def downgrade():
    op.drop_column('diag_questions', 'stem_image_url')
