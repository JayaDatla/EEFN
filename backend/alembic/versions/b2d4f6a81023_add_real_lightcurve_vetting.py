"""add real light-curve vetting columns

Revision ID: b2d4f6a81023
Revises: a1c3e5f70912
Create Date: 2026-10-11 20:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b2d4f6a81023'
down_revision: Union[str, Sequence[str], None] = 'a1c3e5f70912'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('exoplanet_candidates') as batch:
        batch.add_column(sa.Column('lc_vetting_json', sa.JSON(), nullable=True))
        batch.add_column(sa.Column('lc_vetting_status', sa.String(), nullable=True))
        batch.add_column(sa.Column('lc_vetting_at', sa.DateTime(), nullable=True))
        batch.add_column(sa.Column('lc_vetting_attempted_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('exoplanet_candidates') as batch:
        batch.drop_column('lc_vetting_attempted_at')
        batch.drop_column('lc_vetting_at')
        batch.drop_column('lc_vetting_status')
        batch.drop_column('lc_vetting_json')
