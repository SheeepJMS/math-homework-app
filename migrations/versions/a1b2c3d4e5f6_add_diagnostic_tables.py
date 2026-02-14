"""add diagnostic tables (diag_* only, no ALTER on existing tables)

Revision ID: a1b2c3d4e5f6
Revises: b4fefe386c31
Create Date: 2025-02-11

"""
from alembic import op
import sqlalchemy as sa


revision = 'a1b2c3d4e5f6'
down_revision = 'b4fefe386c31'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('diag_competitions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('diag_users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=80), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username')
    )
    op.create_table('diag_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['diag_users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token')
    )
    op.create_table('diag_exams',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('competition_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('time_limit_sec', sa.Integer(), nullable=True),
        sa.Column('is_published', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['competition_id'], ['diag_competitions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('diag_knowledge_points',
        sa.Column('kp_id', sa.String(length=64), nullable=False),
        sa.Column('competition_id', sa.Integer(), nullable=False),
        sa.Column('name_en', sa.String(length=120), nullable=True),
        sa.Column('name_cn', sa.String(length=120), nullable=True),
        sa.Column('parent_kp_id', sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(['competition_id'], ['diag_competitions.id'], ),
        sa.PrimaryKeyConstraint('kp_id')
    )
    op.create_table('diag_questions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('competition_id', sa.Integer(), nullable=False),
        sa.Column('stem_text', sa.Text(), nullable=False),
        sa.Column('choices_json', sa.Text(), nullable=True),
        sa.Column('answer_key', sa.String(length=20), nullable=True),
        sa.Column('solution_text', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['competition_id'], ['diag_competitions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('diag_exam_questions',
        sa.Column('exam_id', sa.Integer(), nullable=False),
        sa.Column('question_id', sa.Integer(), nullable=False),
        sa.Column('q_index', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['exam_id'], ['diag_exams.id'], ),
        sa.ForeignKeyConstraint(['question_id'], ['diag_questions.id'], ),
        sa.PrimaryKeyConstraint('exam_id', 'question_id')
    )
    op.create_table('diag_question_tags',
        sa.Column('question_id', sa.Integer(), nullable=False),
        sa.Column('kp_id', sa.String(length=64), nullable=False),
        sa.Column('weight', sa.Float(), nullable=True),
        sa.Column('manual_override', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['question_id'], ['diag_questions.id'], ),
        sa.PrimaryKeyConstraint('question_id', 'kp_id')
    )
    op.create_table('diag_bank_questions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('competition_id', sa.Integer(), nullable=False),
        sa.Column('stem_text', sa.Text(), nullable=False),
        sa.Column('choices_json', sa.Text(), nullable=True),
        sa.Column('answer_key', sa.String(length=20), nullable=True),
        sa.Column('solution_text', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['competition_id'], ['diag_competitions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('diag_bank_question_tags',
        sa.Column('bank_question_id', sa.Integer(), nullable=False),
        sa.Column('kp_id', sa.String(length=64), nullable=False),
        sa.Column('weight', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['bank_question_id'], ['diag_bank_questions.id'], ),
        sa.PrimaryKeyConstraint('bank_question_id', 'kp_id')
    )
    op.create_table('diag_question_bank_links',
        sa.Column('question_id', sa.Integer(), nullable=False),
        sa.Column('bank_question_id', sa.Integer(), nullable=False),
        sa.Column('link_order', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['bank_question_id'], ['diag_bank_questions.id'], ),
        sa.ForeignKeyConstraint(['question_id'], ['diag_questions.id'], ),
        sa.PrimaryKeyConstraint('question_id', 'bank_question_id')
    )
    op.create_table('diag_question_practice_config',
        sa.Column('question_id', sa.Integer(), nullable=False),
        sa.Column('is_capstone', sa.Boolean(), nullable=True),
        sa.Column('practice_mode', sa.String(length=64), nullable=True),
        sa.Column('random_count', sa.Integer(), nullable=True),
        sa.Column('homework_assignment_id', sa.Integer(), nullable=True),
        sa.Column('curated_homework_question_ids', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['question_id'], ['diag_questions.id'], ),
        sa.PrimaryKeyConstraint('question_id')
    )
    op.create_table('diag_attempts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('exam_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('total_time_ms', sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(['exam_id'], ['diag_exams.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['diag_users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('diag_attempt_answers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('attempt_id', sa.Integer(), nullable=False),
        sa.Column('question_id', sa.Integer(), nullable=False),
        sa.Column('answer', sa.String(length=50), nullable=True),
        sa.Column('is_correct', sa.Boolean(), nullable=True),
        sa.Column('time_spent_ms', sa.BigInteger(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['attempt_id'], ['diag_attempts.id'], ),
        sa.ForeignKeyConstraint(['question_id'], ['diag_questions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('diag_practice_sets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('attempt_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['attempt_id'], ['diag_attempts.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['diag_users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('diag_practice_set_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('practice_set_id', sa.Integer(), nullable=False),
        sa.Column('source_type', sa.String(length=16), nullable=False),
        sa.Column('source_question_id', sa.Integer(), nullable=False),
        sa.Column('q_index', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['practice_set_id'], ['diag_practice_sets.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('diag_practice_set_items')
    op.drop_table('diag_practice_sets')
    op.drop_table('diag_attempt_answers')
    op.drop_table('diag_attempts')
    op.drop_table('diag_question_practice_config')
    op.drop_table('diag_question_bank_links')
    op.drop_table('diag_bank_question_tags')
    op.drop_table('diag_bank_questions')
    op.drop_table('diag_question_tags')
    op.drop_table('diag_exam_questions')
    op.drop_table('diag_questions')
    op.drop_table('diag_knowledge_points')
    op.drop_table('diag_exams')
    op.drop_table('diag_sessions')
    op.drop_table('diag_users')
    op.drop_table('diag_competitions')
