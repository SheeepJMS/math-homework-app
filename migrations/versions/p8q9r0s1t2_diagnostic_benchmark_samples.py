"""add diagnostic_benchmark_samples (diagnostic only, 参考样本分布)

Revision ID: p8q9r0s1t2
Revises: n7o8p9q0r1s2
Create Date: 2026-03

"""
from alembic import op
import sqlalchemy as sa


revision = 'p8q9r0s1t2'
down_revision = 'n7o8p9q0r1s2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'diagnostic_benchmark_samples',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('contest_key', sa.String(64), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('max_score', sa.Float(), nullable=False),
        sa.Column('source_type', sa.String(20), nullable=False, server_default='seed'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_diagnostic_benchmark_samples_contest_key', 'diagnostic_benchmark_samples', ['contest_key'])


def downgrade():
    op.drop_index('ix_diagnostic_benchmark_samples_contest_key', table_name='diagnostic_benchmark_samples')
    op.drop_table('diagnostic_benchmark_samples')
