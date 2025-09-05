"""Add taxon_rank column and IUCN check constraint"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20240515_add_taxon_rank"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("animals", sa.Column("taxon_rank", sa.Text(), nullable=True))
    op.create_check_constraint(
        "chk_animals_iucn",
        "animals",
        "conservation_state IS NULL OR conservation_state IN ('EX','EW','CR','EN','VU','NT','LC','DD','NE')",
    )


def downgrade() -> None:
    op.drop_constraint("chk_animals_iucn", "animals", type_="check")
    op.drop_column("animals", "taxon_rank")
