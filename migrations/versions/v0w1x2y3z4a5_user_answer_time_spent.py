"""add user_answer.time_spent for per-question timing

Revision ID: v0w1x2y3z4a5
Revises: u9v0w1x2y3z4
Create Date: 2026-03-17

"""
from alembic import op
import sqlalchemy as sa

revision = 'v0w1x2y3z4a5'
down_revision = 'u9v0w1x2y3z4'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user_answer', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('time_spent', sa.Integer(), nullable=True, server_default='0')
        )


def downgrade():
    with op.batch_alter_table('user_answer', schema=None) as batch_op:
        batch_op.drop_column('time_spent')
