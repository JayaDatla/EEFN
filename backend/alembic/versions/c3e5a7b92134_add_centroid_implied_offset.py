"""add centroid implied source offset

Revision ID: c3e5a7b92134
Revises: b2d4f6a81023
Create Date: 2026-10-11 21:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3e5a7b92134'
down_revision: Union[str, Sequence[str], None] = 'b2d4f6a81023'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('exoplanet_candidates') as batch:
        batch.add_column(sa.Column('centroid_implied_offset_arcsec', sa.Float(), nullable=True))
        batch.add_column(sa.Column('centroid_implied_offset_err_arcsec', sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('exoplanet_candidates') as batch:
        batch.drop_column('centroid_implied_offset_err_arcsec')
        batch.drop_column('centroid_implied_offset_arcsec')
