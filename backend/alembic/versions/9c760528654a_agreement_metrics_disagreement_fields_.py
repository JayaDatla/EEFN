"""agreement metrics disagreement fields nullable

Revision ID: 9c760528654a
Revises: 2d1d4b5077d0
Create Date: 2026-08-20 11:57:48.385992

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9c760528654a'
down_revision: Union[str, Sequence[str], None] = '2d1d4b5077d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ingest.py used to write 0.0 into these columns whenever one side of a
    # catalog comparison was missing (e.g. no Gaia match), which made "never
    # measured" render identically to "measured, perfect agreement" on the
    # fusion/compare pages and the evidence card. NOT NULL forced that default;
    # None is now the honest value for "we don't have both measurements to
    # compare." Existing 0.0 rows are corrected by a real re-sync, not by this
    # migration (a migration can't tell a genuine 0.0 apart from a fabricated
    # one after the fact).
    with op.batch_alter_table('agreement_metrics') as batch_op:
        batch_op.alter_column('teff_disagreement', existing_type=sa.Float(), nullable=True)
        batch_op.alter_column('rad_disagreement', existing_type=sa.Float(), nullable=True)
        batch_op.alter_column('dist_disagreement', existing_type=sa.Float(), nullable=True)
        batch_op.alter_column('derived_rp_diff', existing_type=sa.Float(), nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('agreement_metrics') as batch_op:
        batch_op.alter_column('teff_disagreement', existing_type=sa.Float(), nullable=False)
        batch_op.alter_column('rad_disagreement', existing_type=sa.Float(), nullable=False)
        batch_op.alter_column('dist_disagreement', existing_type=sa.Float(), nullable=False)
        batch_op.alter_column('derived_rp_diff', existing_type=sa.Float(), nullable=False)
