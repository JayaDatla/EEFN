"""add real centroid provenance fields

Revision ID: 36aa89409a3f
Revises: 24b706d5c38a
Create Date: 2026-08-12 12:05:06.842732

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '36aa89409a3f'
down_revision: Union[str, Sequence[str], None] = '24b706d5c38a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # UPGRADE_PLAN.md F.6. The autogenerate diff also proposed a batch of Uuid-column
    # "alter_column" ops and an extra index -- both are SQLite storage-class noise from
    # the same NUMERIC/Uuid autogenerate false-positive noted in prior migrations, not
    # real schema changes; trimmed to only the columns this revision actually adds.
    op.add_column('exoplanet_candidates', sa.Column('centroid_is_real', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('exoplanet_candidates', sa.Column('centroid_significance_sigma', sa.Float(), nullable=True))
    op.add_column('exoplanet_candidates', sa.Column('centroid_sector', sa.Integer(), nullable=True))
    op.add_column('exoplanet_candidates', sa.Column('centroid_computed_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('exoplanet_candidates', 'centroid_computed_at')
    op.drop_column('exoplanet_candidates', 'centroid_sector')
    op.drop_column('exoplanet_candidates', 'centroid_significance_sigma')
    op.drop_column('exoplanet_candidates', 'centroid_is_real')
