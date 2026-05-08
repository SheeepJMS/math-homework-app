"""lesson knowledge point notes image url

Revision ID: r6s7t8u9v0w1
Revises: q0r1s2t3u4v5
Create Date: 2026-05-08

"""
from alembic import op
import sqlalchemy as sa

revision = 'r6s7t8u9v0w1'
down_revision = 'q0r1s2t3u4v5'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('lesson', schema=None) as batch_op:
        batch_op.add_column(sa.Column('kp_notes_image_url', sa.String(length=512), nullable=True))


def downgrade():
    with op.batch_alter_table('lesson', schema=None) as batch_op:
        batch_op.drop_column('kp_notes_image_url')
