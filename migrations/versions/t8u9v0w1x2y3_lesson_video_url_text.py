"""widen lesson.video_url to Text to avoid long URL truncation

Revision ID: t8u9v0w1x2y3
Revises: s7t8u9v0w1x2
Create Date: 2026-09-17

"""
from alembic import op
import sqlalchemy as sa

revision = 't8u9v0w1x2y3'
down_revision = 's7t8u9v0w1x2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('lesson', schema=None) as batch_op:
        batch_op.alter_column(
            'video_url',
            existing_type=sa.String(length=500),
            type_=sa.Text(),
            existing_nullable=True,
        )


def downgrade():
    with op.batch_alter_table('lesson', schema=None) as batch_op:
        batch_op.alter_column(
            'video_url',
            existing_type=sa.Text(),
            type_=sa.String(length=500),
            existing_nullable=True,
        )
