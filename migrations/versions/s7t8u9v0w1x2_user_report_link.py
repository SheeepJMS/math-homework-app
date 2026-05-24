"""add user report_link field

Revision ID: s7t8u9v0w1x2
Revises: r6s7t8u9v0w1
Create Date: 2026-05-23

"""
from alembic import op
import sqlalchemy as sa

revision = 's7t8u9v0w1x2'
down_revision = 'r6s7t8u9v0w1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('report_link', sa.String(length=500), nullable=True))


def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('report_link')
