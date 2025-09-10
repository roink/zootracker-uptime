"""add indexes for user/zoo lookups"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20240702_add_user_zoo_indexes"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "idx_zoovisit_user_zoo", "zoo_visits", ["user_id", "zoo_id"], if_not_exists=True
    )
    op.create_index(
        "idx_animalsighting_user_zoo", "animal_sightings", ["user_id", "zoo_id"], if_not_exists=True
    )


def downgrade() -> None:
    op.drop_index("idx_animalsighting_user_zoo", table_name="animal_sightings")
    op.drop_index("idx_zoovisit_user_zoo", table_name="zoo_visits")
