"""diag guest students, placement exams, nullable attempt user

Revision ID: q0r1s2t3u4v5
Revises: p8q9r0s1t2
Create Date: 2026-04-23

"""
from alembic import op
import sqlalchemy as sa


revision = 'q0r1s2t3u4v5'
down_revision = 'p8q9r0s1t2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'diag_guest_students',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('grade', sa.String(length=8), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'diag_guest_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('guest_student_id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['guest_student_id'], ['diag_guest_students.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token'),
    )
    op.create_index('ix_diag_guest_sessions_token', 'diag_guest_sessions', ['token'], unique=False)

    op.add_column('diag_exams', sa.Column('diag_placement_level', sa.Integer(), nullable=True))

    with op.batch_alter_table('diag_attempts', schema=None) as batch_op:
        batch_op.alter_column('user_id', existing_type=sa.Integer(), nullable=True)
        batch_op.add_column(sa.Column('guest_student_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('placement_level', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('guest_grade', sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column('share_token', sa.String(length=64), nullable=True))
        batch_op.create_foreign_key('fk_diag_attempts_guest_student', 'diag_guest_students', ['guest_student_id'], ['id'], ondelete='SET NULL')
    op.create_index('ix_diag_attempts_share_token', 'diag_attempts', ['share_token'], unique=True)

    with op.batch_alter_table('diag_practice_sets', schema=None) as batch_op:
        batch_op.alter_column('user_id', existing_type=sa.Integer(), nullable=True)
        batch_op.add_column(sa.Column('guest_student_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_diag_practice_sets_guest_student', 'diag_guest_students', ['guest_student_id'], ['id'], ondelete='SET NULL')

    with op.batch_alter_table('diag_practice_attempts', schema=None) as batch_op:
        batch_op.alter_column('user_id', existing_type=sa.Integer(), nullable=True)
        batch_op.add_column(sa.Column('guest_student_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_diag_practice_attempts_guest_student', 'diag_guest_students', ['guest_student_id'], ['id'], ondelete='SET NULL')


def downgrade():
    op.drop_index('ix_diag_attempts_share_token', table_name='diag_attempts')
    with op.batch_alter_table('diag_practice_attempts', schema=None) as batch_op:
        batch_op.drop_constraint('fk_diag_practice_attempts_guest_student', type_='foreignkey')
        batch_op.drop_column('guest_student_id')
        batch_op.alter_column('user_id', existing_type=sa.Integer(), nullable=False)

    with op.batch_alter_table('diag_practice_sets', schema=None) as batch_op:
        batch_op.drop_constraint('fk_diag_practice_sets_guest_student', type_='foreignkey')
        batch_op.drop_column('guest_student_id')
        batch_op.alter_column('user_id', existing_type=sa.Integer(), nullable=False)

    with op.batch_alter_table('diag_attempts', schema=None) as batch_op:
        batch_op.drop_constraint('fk_diag_attempts_guest_student', type_='foreignkey')
        batch_op.drop_column('share_token')
        batch_op.drop_column('guest_grade')
        batch_op.drop_column('placement_level')
        batch_op.drop_column('guest_student_id')
        batch_op.alter_column('user_id', existing_type=sa.Integer(), nullable=False)

    op.drop_column('diag_exams', 'diag_placement_level')
    op.drop_index('ix_diag_guest_sessions_token', table_name='diag_guest_sessions')
    op.drop_table('diag_guest_sessions')
    op.drop_table('diag_guest_students')
