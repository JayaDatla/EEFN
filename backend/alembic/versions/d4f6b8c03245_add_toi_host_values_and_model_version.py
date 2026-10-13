"""add TOI-side host values and prediction model_version

Revision ID: d4f6b8c03245
Revises: c3e5a7b92134
Create Date: 2026-10-13 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4f6b8c03245'
down_revision: Union[str, Sequence[str], None] = 'c3e5a7b92134'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """TOI-vs-Gaia disagreement features need both sides at serving time; and a score must say
    which model produced it (scores in the DB silently outlived two retrains)."""
    with op.batch_alter_table('host_stars') as batch:
        for col in ('toi_teff', 'toi_rad', 'toi_dist', 'toi_logg'):
            batch.add_column(sa.Column(col, sa.Float(), nullable=True))
    with op.batch_alter_table('ml_predictions') as batch:
        batch.add_column(sa.Column('model_version', sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('ml_predictions') as batch:
        batch.drop_column('model_version')
    with op.batch_alter_table('host_stars') as batch:
        for col in ('toi_logg', 'toi_dist', 'toi_rad', 'toi_teff'):
            batch.drop_column(col)
