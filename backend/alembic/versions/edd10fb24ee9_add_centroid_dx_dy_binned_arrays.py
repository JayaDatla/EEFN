"""add centroid dx dy binned arrays

Revision ID: edd10fb24ee9
Revises: 485459105b7b
Create Date: 2026-08-12 12:30:38.762321

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'edd10fb24ee9'
down_revision: Union[str, Sequence[str], None] = '485459105b7b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # UPGRADE_PLAN.md F.6. Trimmed of the same SQLite NUMERIC/Uuid autogenerate
    # false-positive noise documented in the prior three migrations.
    op.add_column('exoplanet_candidates', sa.Column('centroid_dx_json', sa.JSON(), nullable=True))
    op.add_column('exoplanet_candidates', sa.Column('centroid_dy_json', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('exoplanet_candidates', 'centroid_dy_json')
    op.drop_column('exoplanet_candidates', 'centroid_dx_json')
