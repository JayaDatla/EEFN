"""add spectroscopy provenance fields

Revision ID: 485459105b7b
Revises: 36aa89409a3f
Create Date: 2026-08-12 12:15:09.791091

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '485459105b7b'
down_revision: Union[str, Sequence[str], None] = '36aa89409a3f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # UPGRADE_PLAN.md F.7. Trimmed of the same SQLite NUMERIC/Uuid autogenerate
    # false-positive noise documented in the prior two migrations.
    op.add_column('host_stars', sa.Column('spectroscopy_is_real', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('host_stars', sa.Column('spectroscopy_source', sa.String(), nullable=True))
    op.add_column('host_stars', sa.Column('spectroscopy_computed_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('host_stars', 'spectroscopy_computed_at')
    op.drop_column('host_stars', 'spectroscopy_source')
    op.drop_column('host_stars', 'spectroscopy_is_real')
