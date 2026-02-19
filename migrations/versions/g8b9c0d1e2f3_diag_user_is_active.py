"""add diag_users.is_active for suspend

Revision ID: g8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2025-02-14

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import ProgrammingError

revision = 'g8b9c0d1e2f3'
down_revision = 'f7a8b9c0d1e2'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    s = conn.begin_nested()
    try:
        op.add_column('diag_users', sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')))
        s.commit()
    except ProgrammingError as e:
        s.rollback()
        if 'already exists' not in str(e).lower():
            raise


def downgrade():
    op.drop_column('diag_users', 'is_active')
