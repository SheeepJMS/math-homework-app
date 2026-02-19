"""diagnostic subscription scaffolding - email, reset tokens, subscriptions, support, audit

Revision ID: i0d1e2f3a4b5
Revises: h9c0d1e2f3a4
Create Date: 2025-02-14

All additions are diag_* only. No changes to homework tables.
Default values ensure existing users unaffected (allow_all mode).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import ProgrammingError

revision = 'i0d1e2f3a4b5'
down_revision = 'h9c0d1e2f3a4'
branch_labels = None
depends_on = None


def _run(fn):
    try:
        fn()
    except ProgrammingError as e:
        if 'already exists' not in str(e).lower():
            raise


def upgrade():
    # A) diag_users: email, email_verified (nullable, optional for future)
    _run(lambda: op.add_column('diag_users', sa.Column('email', sa.String(255), nullable=True)))
    _run(lambda: op.add_column('diag_users', sa.Column('email_verified', sa.Boolean(), nullable=False, server_default=sa.text('false'))))
    _run(lambda: op.create_index('ix_diag_users_email', 'diag_users', ['email'], unique=True))

    # A) diag_password_reset_tokens
    _run(lambda: op.create_table('diag_password_reset_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(64), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['diag_users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token')
    ))
    _run(lambda: op.create_index('ix_diag_password_reset_tokens_token', 'diag_password_reset_tokens', ['token'], unique=True))

    # B) diag_subscriptions
    _run(lambda: op.create_table('diag_subscriptions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('plan', sa.String(32), nullable=False, server_default=sa.text("'legacy_active'")),
        sa.Column('status', sa.String(32), nullable=False, server_default=sa.text("'active'")),
        sa.Column('current_period_end', sa.DateTime(), nullable=True),
        sa.Column('provider', sa.String(32), nullable=True),
        sa.Column('provider_customer_id', sa.String(255), nullable=True),
        sa.Column('provider_subscription_id', sa.String(255), nullable=True),
        sa.Column('entitlements_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['diag_users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    ))
    _run(lambda: op.create_index('ix_diag_subscriptions_user_id', 'diag_subscriptions', ['user_id'], unique=True))

    # D) diag_support_tickets
    _run(lambda: op.create_table('diag_support_tickets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('category', sa.String(64), nullable=True),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('attachment_url', sa.String(512), nullable=True),
        sa.Column('status', sa.String(32), nullable=False, server_default=sa.text("'open'")),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['diag_users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    ))

    # E) diag_auth_audit
    _run(lambda: op.create_table('diag_auth_audit',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('event', sa.String(32), nullable=False),
        sa.Column('ip', sa.String(64), nullable=True),
        sa.Column('user_agent', sa.String(512), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['diag_users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    ))
    _run(lambda: op.create_index('ix_diag_auth_audit_user_id', 'diag_auth_audit', ['user_id']))
    _run(lambda: op.create_index('ix_diag_auth_audit_created_at', 'diag_auth_audit', ['created_at']))


def downgrade():
    op.drop_index('ix_diag_auth_audit_created_at', table_name='diag_auth_audit')
    op.drop_index('ix_diag_auth_audit_user_id', table_name='diag_auth_audit')
    op.drop_table('diag_auth_audit')
    op.drop_table('diag_support_tickets')
    op.drop_index('ix_diag_subscriptions_user_id', table_name='diag_subscriptions')
    op.drop_table('diag_subscriptions')
    op.drop_index('ix_diag_password_reset_tokens_token', table_name='diag_password_reset_tokens')
    op.drop_table('diag_password_reset_tokens')
    op.drop_index('ix_diag_users_email', table_name='diag_users')
    op.drop_column('diag_users', 'email_verified')
    op.drop_column('diag_users', 'email')
