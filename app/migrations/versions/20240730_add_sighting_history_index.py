from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20240730_add_sighting_history_index"
down_revision = "20240715_add_animal_popularity_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "postgresql":
        op.execute(
            sa.text(
                """
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sighting_user_zoo_datetime
                ON animal_sightings (user_id, zoo_id, sighting_datetime DESC, created_at DESC)
                """
            ).execution_options(autocommit=True)
        )
    else:
        op.execute(
            sa.text(
                """
                CREATE INDEX IF NOT EXISTS idx_sighting_user_zoo_datetime
                ON animal_sightings (user_id, zoo_id, sighting_datetime DESC, created_at DESC)
                """
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "postgresql":
        op.execute(
            sa.text(
                "DROP INDEX CONCURRENTLY IF EXISTS idx_sighting_user_zoo_datetime"
            ).execution_options(autocommit=True)
        )
    else:
        op.execute(
            sa.text("DROP INDEX IF EXISTS idx_sighting_user_zoo_datetime")
        )
