"""add diag_attempt_answers.error_type

Revision ID: m4n5o6p7q8r9
Revises: k2f3a4b5c6d7
Create Date: 2026-02-18

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import ProgrammingError


revision = 'm4n5o6p7q8r9'
down_revision = 'k2f3a4b5c6d7'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    s = conn.begin_nested()
    try:
        op.add_column('diag_attempt_answers', sa.Column('error_type', sa.String(length=64), nullable=True))
        s.commit()
    except ProgrammingError as e:
        s.rollback()
        msg = str(e).lower()
        if 'duplicate column' in msg or 'already exists' in msg:
            return
        raise


def downgrade():
    conn = op.get_bind()
    s = conn.begin_nested()
    try:
        op.drop_column('diag_attempt_answers', 'error_type')
        s.commit()
    except ProgrammingError as e:
        s.rollback()
        msg = str(e).lower()
        if 'does not exist' in msg or 'unknown column' in msg:
            return
        raise

