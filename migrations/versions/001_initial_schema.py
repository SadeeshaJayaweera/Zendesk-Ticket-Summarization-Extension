"""Initial enterprise schema for Zendesk Support Intelligence Platform

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-11-19 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. organizations
    op.create_table(
        'organizations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('slug', sa.String(length=64), nullable=False),
        sa.Column('zendesk_subdomain', sa.String(length=64), nullable=False),
        sa.Column('zendesk_email', sa.String(length=255), nullable=True),
        sa.Column('zendesk_api_token_encrypted', sa.Text(), nullable=True),
        sa.Column('webhook_secret_encrypted', sa.Text(), nullable=True),
        sa.Column('primary_ai_provider', sa.String(length=32), nullable=False, server_default='gemini'),
        sa.Column('primary_model', sa.String(length=64), nullable=False, server_default='gemini-1.5-flash'),
        sa.Column('fallback_ai_provider', sa.String(length=32), nullable=False, server_default='groq'),
        sa.Column('fallback_model', sa.String(length=64), nullable=False, server_default='llama-3.3-70b-versatile'),
        sa.Column('default_summary_style', sa.String(length=32), nullable=False, server_default='standard'),
        sa.Column('allow_internal_notes_to_ai', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('allow_attachments_to_ai', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('data_retention_days', sa.Integer(), nullable=False, server_default='90'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_organizations_slug'), 'organizations', ['slug'], unique=True)
    op.create_index(op.f('ix_organizations_zendesk_subdomain'), 'organizations', ['zendesk_subdomain'], unique=True)

    # 2. users
    op.create_table(
        'users',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=128), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=32), nullable=False, server_default='support_agent'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_user_org_email', 'users', ['organization_id', 'email'], unique=True)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=False)
    op.create_index(op.f('ix_users_organization_id'), 'users', ['organization_id'], unique=False)

    # 3. summary_templates
    op.create_table(
        'summary_templates',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=True),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('style_key', sa.String(length=32), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('custom_system_prompt', sa.Text(), nullable=True),
        sa.Column('guidance_instructions', sa.Text(), nullable=True),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_summary_templates_organization_id'), 'summary_templates', ['organization_id'], unique=False)
    op.create_index(op.f('ix_summary_templates_style_key'), 'summary_templates', ['style_key'], unique=False)

    # 4. ticket_references
    op.create_table(
        'ticket_references',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('zendesk_ticket_id', sa.Integer(), nullable=False),
        sa.Column('subject', sa.String(length=255), nullable=False, server_default=''),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='open'),
        sa.Column('priority', sa.String(length=32), nullable=False, server_default='normal'),
        sa.Column('category', sa.String(length=64), nullable=True),
        sa.Column('detected_sentiment', sa.String(length=32), nullable=True),
        sa.Column('requester_name', sa.String(length=128), nullable=True),
        sa.Column('assignee_name', sa.String(length=128), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_ticket_org_tid', 'ticket_references', ['organization_id', 'zendesk_ticket_id'], unique=True)
    op.create_index(op.f('ix_ticket_references_organization_id'), 'ticket_references', ['organization_id'], unique=False)
    op.create_index(op.f('ix_ticket_references_zendesk_ticket_id'), 'ticket_references', ['zendesk_ticket_id'], unique=False)

    # 5. summary_records
    op.create_table(
        'summary_records',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('ticket_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('style', sa.String(length=32), nullable=False, server_default='standard'),
        sa.Column('provider_used', sa.String(length=32), nullable=False),
        sa.Column('model_used', sa.String(length=64), nullable=False),
        sa.Column('executive_summary', sa.Text(), nullable=False, server_default=''),
        sa.Column('customer_issue', sa.Text(), nullable=False),
        sa.Column('structured_json', sa.JSON(), nullable=False),
        sa.Column('markdown_content', sa.Text(), nullable=False),
        sa.Column('prompt_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('completion_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('estimated_cost_usd', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('latency_seconds', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('was_posted_to_zendesk', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('source', sa.String(length=32), nullable=False, server_default='agent_request'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_summary_records_created_at'), 'summary_records', ['created_at'], unique=False)
    op.create_index(op.f('ix_summary_records_organization_id'), 'summary_records', ['organization_id'], unique=False)
    op.create_index(op.f('ix_summary_records_ticket_id'), 'summary_records', ['ticket_id'], unique=False)

    # 6. pending_drafts
    op.create_table(
        'pending_drafts',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('ticket_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='pending_review'),
        sa.Column('summary_style', sa.String(length=32), nullable=False, server_default='standard'),
        sa.Column('structured_data', sa.JSON(), nullable=False),
        sa.Column('markdown_note', sa.Text(), nullable=False),
        sa.Column('source_trigger', sa.String(length=64), nullable=False, server_default='zendesk_webhook_solved'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_draft_org_ticket', 'pending_drafts', ['organization_id', 'ticket_id'], unique=False)
    op.create_index(op.f('ix_pending_drafts_organization_id'), 'pending_drafts', ['organization_id'], unique=False)
    op.create_index(op.f('ix_pending_drafts_ticket_id'), 'pending_drafts', ['ticket_id'], unique=False)

    # 7. webhook_events
    op.create_table(
        'webhook_events',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=True),
        sa.Column('event_id', sa.String(length=128), nullable=False),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('ticket_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='received'),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_webhook_events_created_at'), 'webhook_events', ['created_at'], unique=False)
    op.create_index(op.f('ix_webhook_events_event_id'), 'webhook_events', ['event_id'], unique=True)
    op.create_index(op.f('ix_webhook_events_ticket_id'), 'webhook_events', ['ticket_id'], unique=False)

    # 8. audit_logs
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=True),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('ticket_id', sa.Integer(), nullable=True),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('action', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='success'),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('model_used', sa.String(length=64), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_audit_logs_created_at'), 'audit_logs', ['created_at'], unique=False)
    op.create_index(op.f('ix_audit_logs_event_type'), 'audit_logs', ['event_type'], unique=False)
    op.create_index(op.f('ix_audit_logs_organization_id'), 'audit_logs', ['organization_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_ticket_id'), 'audit_logs', ['ticket_id'], unique=False)

    # 9. usage_records
    op.create_table(
        'usage_records',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('provider', sa.String(length=32), nullable=False),
        sa.Column('model', sa.String(length=64), nullable=False),
        sa.Column('operation', sa.String(length=32), nullable=False),
        sa.Column('prompt_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('completion_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('estimated_cost_usd', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_usage_records_created_at'), 'usage_records', ['created_at'], unique=False)
    op.create_index(op.f('ix_usage_records_organization_id'), 'usage_records', ['organization_id'], unique=False)


def downgrade() -> None:
    op.drop_table('usage_records')
    op.drop_table('audit_logs')
    op.drop_table('webhook_events')
    op.drop_table('pending_drafts')
    op.drop_table('summary_records')
    op.drop_table('ticket_references')
    op.drop_table('summary_templates')
    op.drop_table('users')
    op.drop_table('organizations')
