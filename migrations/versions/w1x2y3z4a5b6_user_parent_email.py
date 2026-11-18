"""add user.parent_email for homework reminders

Revision ID: w1x2y3z4a5b6
Revises: v0w1x2y3z4a5
Create Date: 2026-03-17

"""
from alembic import op
import sqlalchemy as sa

revision = 'w1x2y3z4a5b6'
down_revision = 'v0w1x2y3z4a5'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('parent_email', sa.String(length=120), nullable=True))
        batch_op.create_index('ix_user_parent_email', ['parent_email'], unique=False)


def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_index('ix_user_parent_email')
        batch_op.drop_column('parent_email')
