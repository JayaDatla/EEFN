"""add centroid/spectroscopy attempt tracking

Revision ID: a1c3e5f70912
Revises: 9c760528654a
Create Date: 2026-10-11 18:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1c3e5f70912'
down_revision: Union[str, Sequence[str], None] = '9c760528654a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Scheduled centroid/spectroscopy sync needs to know what it already tried, or it
    would re-download the same TPF-less targets every night forever."""
    with op.batch_alter_table('exoplanet_candidates') as batch:
        batch.add_column(sa.Column('centroid_attempted_at', sa.DateTime(), nullable=True))
        batch.add_column(sa.Column('centroid_status', sa.String(), nullable=True))
    with op.batch_alter_table('host_stars') as batch:
        batch.add_column(sa.Column('spectroscopy_attempted_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('host_stars') as batch:
        batch.drop_column('spectroscopy_attempted_at')
    with op.batch_alter_table('exoplanet_candidates') as batch:
        batch.drop_column('centroid_status')
        batch.drop_column('centroid_attempted_at')
