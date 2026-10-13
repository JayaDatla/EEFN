"""add cross-match quality columns

Revision ID: e5a7c9d14356
Revises: d4f6b8c03245
Create Date: 2026-10-13 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e5a7c9d14356'
down_revision: Union[str, Sequence[str], None] = 'd4f6b8c03245'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('host_stars') as batch:
        for col in ('toi_tmag', 'gaia_g_mag', 'gaia_bp_rp', 'gaia_match_sep_arcsec'):
            batch.add_column(sa.Column(col, sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('host_stars') as batch:
        for col in ('gaia_match_sep_arcsec', 'gaia_bp_rp', 'gaia_g_mag', 'toi_tmag'):
            batch.drop_column(col)
