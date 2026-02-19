"""add solution_image_url to diag_questions

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2025-02-12

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import ProgrammingError

# revision identifiers, used by Alembic.
revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade():
    try:
        op.add_column('diag_questions', sa.Column('solution_image_url', sa.String(length=512), nullable=True))
    except ProgrammingError as e:
        if 'already exists' not in str(e).lower():
            raise


def downgrade():
    op.drop_column('diag_questions', 'solution_image_url')
