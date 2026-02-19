"""add diag CSV import enhanced tables (answers, kp, practice_items, practice_config)

仅新增 diag_* 表，不修改作业网或现有 diag 表结构。
Revision ID: k2f3a4b5c6d7
Revises: j1e2f3a4b5c6
Create Date: 2025-02-18

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import ProgrammingError

revision = 'k2f3a4b5c6d7'
down_revision = 'j1e2f3a4b5c6'
branch_labels = None
depends_on = None


def _create(name, fn):
    try:
        fn()
    except ProgrammingError as e:
        if 'already exists' not in str(e).lower():
            raise


def upgrade():
    # 1) 每题答案与解析（CSV 导入后覆盖/补充）
    _create('diag_question_answers', lambda: op.create_table('diag_question_answers',
        sa.Column('exam_id', sa.Integer(), nullable=False),
        sa.Column('q_index', sa.Integer(), nullable=False),
        sa.Column('correct_answer', sa.String(length=50), nullable=True),
        sa.Column('solution_explain', sa.Text(), nullable=True),
        sa.Column('answer_format', sa.String(length=20), nullable=True),
        sa.Column('reserved_1', sa.String(length=255), nullable=True),
        sa.Column('reserved_2', sa.String(length=255), nullable=True),
        sa.Column('reserved_3', sa.String(length=255), nullable=True),
        sa.Column('extra_json', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['exam_id'], ['diag_exams.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('exam_id', 'q_index')
    ))

    # 2) 每题知识点（一级/二级，CSV 自由文本）
    _create('diag_question_kp', lambda: op.create_table('diag_question_kp',
        sa.Column('exam_id', sa.Integer(), nullable=False),
        sa.Column('q_index', sa.Integer(), nullable=False),
        sa.Column('kp_primary', sa.String(length=120), nullable=True),
        sa.Column('kp_secondary', sa.Text(), nullable=True),
        sa.Column('reserved_1', sa.String(length=255), nullable=True),
        sa.Column('reserved_2', sa.String(length=255), nullable=True),
        sa.Column('reserved_3', sa.String(length=255), nullable=True),
        sa.Column('extra_json', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['exam_id'], ['diag_exams.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('exam_id', 'q_index')
    ))

    # 3) 错题练习集（每题 5-8 道，CSV 导入）
    _create('diag_question_practice_items', lambda: op.create_table('diag_question_practice_items',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('exam_id', sa.Integer(), nullable=False),
        sa.Column('q_index', sa.Integer(), nullable=False),
        sa.Column('item_index', sa.Integer(), nullable=False),
        sa.Column('stem', sa.Text(), nullable=False),
        sa.Column('choices', sa.Text(), nullable=True),
        sa.Column('answer', sa.String(length=50), nullable=True),
        sa.Column('explain', sa.Text(), nullable=True),
        sa.Column('source', sa.String(length=32), nullable=True),
        sa.Column('reserved_1', sa.String(length=255), nullable=True),
        sa.Column('reserved_2', sa.String(length=255), nullable=True),
        sa.Column('reserved_3', sa.String(length=255), nullable=True),
        sa.Column('extra_json', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['exam_id'], ['diag_exams.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    ))
    _create('ix', lambda: op.create_index('ix_diag_question_practice_items_exam_q', 'diag_question_practice_items', ['exam_id', 'q_index']))

    # 4) 每题默认练习数量（CSV 可覆盖）
    _create('diag_exam_question_practice_config', lambda: op.create_table('diag_exam_question_practice_config',
        sa.Column('exam_id', sa.Integer(), nullable=False),
        sa.Column('q_index', sa.Integer(), nullable=False),
        sa.Column('practice_count_default', sa.Integer(), nullable=False, server_default=sa.text('3')),
        sa.Column('reserved_1', sa.String(length=255), nullable=True),
        sa.Column('reserved_2', sa.String(length=255), nullable=True),
        sa.Column('reserved_3', sa.String(length=255), nullable=True),
        sa.Column('extra_json', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['exam_id'], ['diag_exams.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('exam_id', 'q_index')
    ))


def downgrade():
    op.drop_table('diag_exam_question_practice_config')
    op.drop_index('ix_diag_question_practice_items_exam_q', table_name='diag_question_practice_items')
    op.drop_table('diag_question_practice_items')
    op.drop_table('diag_question_kp')
    op.drop_table('diag_question_answers')
