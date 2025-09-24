from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20240715_add_animal_popularity_index"
down_revision = "20240702_add_user_zoo_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "postgresql":
        op.execute(
            sa.text(
                """
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_animal_popularity
                ON animals (zoo_count DESC, name_en ASC, id ASC)
                """
            ).execution_options(autocommit=True)
        )
    else:
        op.execute(
            sa.text(
                """
                CREATE INDEX IF NOT EXISTS idx_animal_popularity
                ON animals (zoo_count DESC, name_en ASC, id ASC)
                """
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "postgresql":
        op.execute(
            sa.text(
                "DROP INDEX CONCURRENTLY IF EXISTS idx_animal_popularity"
            ).execution_options(autocommit=True)
        )
    else:
        op.execute(sa.text("DROP INDEX IF EXISTS idx_animal_popularity"))
