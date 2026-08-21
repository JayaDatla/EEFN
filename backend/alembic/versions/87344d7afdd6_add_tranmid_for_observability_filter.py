"""add tranmid for observability filter

Revision ID: 87344d7afdd6
Revises: edd10fb24ee9
Create Date: 2026-08-13 10:07:18.560433

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '87344d7afdd6'
down_revision: Union[str, Sequence[str], None] = 'edd10fb24ee9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # H.3.1 observability-tonight filter needs a real transit epoch to compute a
    # transit window; trimmed of the same SQLite NUMERIC/Uuid autogenerate noise
    # documented in the prior migrations.
    op.add_column('exoplanet_candidates', sa.Column('tranmid', sa.Float(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('exoplanet_candidates', 'tranmid')
