"""add needs_image to diag_question_answers

Revision ID: l2g3h4i5j6k7
Revises: k2f3a4b5c6d7
Create Date: 2025-02-18

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


def upgrade():
    conn = op.get_bind()
    if not inspect(conn).has_table('diag_question_answers'):
        return
    cols = [c['name'] for c in inspect(conn).get_columns('diag_question_answers')]
    if 'needs_image' not in cols:
        op.add_column('diag_question_answers', sa.Column('needs_image', sa.Boolean(), nullable=True, server_default=sa.text('0')))


def downgrade():
    op.drop_column('diag_question_answers', 'needs_image')
