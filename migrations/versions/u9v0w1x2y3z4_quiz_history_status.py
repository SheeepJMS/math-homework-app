"""add quiz_history.status for homework draft progress

Revision ID: u9v0w1x2y3z4
Revises: t8u9v0w1x2y3
Create Date: 2026-03-17

"""
from alembic import op
import sqlalchemy as sa

revision = 'u9v0w1x2y3z4'
down_revision = 't8u9v0w1x2y3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('quiz_history', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'status',
                sa.String(length=20),
                nullable=False,
                server_default='completed',
            )
        )


def downgrade():
    with op.batch_alter_table('quiz_history', schema=None) as batch_op:
        batch_op.drop_column('status')
