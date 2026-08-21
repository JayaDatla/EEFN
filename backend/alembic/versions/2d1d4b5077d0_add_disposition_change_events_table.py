"""add disposition change events table

Revision ID: 2d1d4b5077d0
Revises: 87344d7afdd6
Create Date: 2026-08-13 13:19:51.976172

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2d1d4b5077d0'
down_revision: Union[str, Sequence[str], None] = '87344d7afdd6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # UPGRADE_PLAN.md H.3.5. Trimmed of the same SQLite NUMERIC/Uuid autogenerate
    # noise documented in the prior migrations.
    op.create_table(
        'disposition_change_events',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('candidate_id', sa.Uuid(), nullable=False),
        sa.Column('toi_id', sa.Float(), nullable=True),
        sa.Column('pl_name', sa.String(), nullable=False),
        sa.Column('field_name', sa.String(), nullable=False),
        sa.Column('old_value', sa.String(), nullable=True),
        sa.Column('new_value', sa.String(), nullable=True),
        sa.Column('changed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['candidate_id'], ['exoplanet_candidates.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_disposition_change_events_toi_id'), 'disposition_change_events', ['toi_id'], unique=False)
    op.create_index(op.f('ix_disposition_change_events_changed_at'), 'disposition_change_events', ['changed_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_disposition_change_events_changed_at'), table_name='disposition_change_events')
    op.drop_index(op.f('ix_disposition_change_events_toi_id'), table_name='disposition_change_events')
    op.drop_table('disposition_change_events')
