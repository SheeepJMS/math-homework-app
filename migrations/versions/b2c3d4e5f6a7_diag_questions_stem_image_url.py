"""add stem_image_url to diag_questions

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2025-02-12

"""
from alembic import op
import sqlalchemy as sa

revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('diag_questions', sa.Column('stem_image_url', sa.String(length=512), nullable=True))


def downgrade():
    op.drop_column('diag_questions', 'stem_image_url')
