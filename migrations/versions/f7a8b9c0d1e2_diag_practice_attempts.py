"""add diag_practice_attempts table

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2025-02-12

"""
from alembic import op
import sqlalchemy as sa


revision = 'f7a8b9c0d1e2'
down_revision = 'e6f7a8b9c0d1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'diag_practice_attempts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('practice_set_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('answers_json', sa.Text(), nullable=True),
        sa.Column('submitted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['practice_set_id'], ['diag_practice_sets.id']),
        sa.ForeignKeyConstraint(['user_id'], ['diag_users.id']),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('diag_practice_attempts')
