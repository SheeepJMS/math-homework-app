"""add diag_users profile fields (birth_year, school, province)

Revision ID: n7o8p9q0r1s2
Revises: k2f3a4b5c6d7
Create Date: 2026-02-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import ProgrammingError


revision = 'n7o8p9q0r1s2'
down_revision = 'k2f3a4b5c6d7'
branch_labels = None
depends_on = None


def _add_column(table, col):
    conn = op.get_bind()
    s = conn.begin_nested()
    try:
        op.add_column(table, col)
        s.commit()
    except ProgrammingError as e:
        s.rollback()
        msg = str(e).lower()
        if 'duplicate column' in msg or 'already exists' in msg:
            return
        raise


def upgrade():
    _add_column('diag_users', sa.Column('birth_year', sa.Integer(), nullable=True))
    _add_column('diag_users', sa.Column('school', sa.String(length=255), nullable=True))
    # 旧账号默认为 BC（不强制非空，避免历史数据问题）
    _add_column('diag_users', sa.Column('province', sa.String(length=32), nullable=True, server_default='BC'))


def downgrade():
    # 非破坏原则：不提供降级删除列，避免误伤线上数据
    pass

