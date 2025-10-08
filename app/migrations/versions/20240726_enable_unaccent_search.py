"""Enable unaccent helper and optimized zoo search indexes"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20240726_enable_unaccent_search"
down_revision = "20240715_add_animal_popularity_index"
branch_labels = None
depends_on = None


_CREATE_F_UNACCENT = """
CREATE OR REPLACE FUNCTION f_unaccent(text)
RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS
$$ SELECT public.unaccent('public.unaccent', $1) $$
"""


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect != "postgresql":
        return

    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS unaccent"))
    op.execute(sa.text(_CREATE_F_UNACCENT))

    op.execute(sa.text("DROP INDEX IF EXISTS idx_zoos_name_trgm"))
    op.execute(sa.text("DROP INDEX IF EXISTS idx_zoos_city_trgm"))
    op.execute(
        sa.text(
            """
            CREATE INDEX IF NOT EXISTS idx_zoos_name_trgm
            ON zoos USING gin (f_unaccent(name) gin_trgm_ops)
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE INDEX IF NOT EXISTS idx_zoos_city_trgm
            ON zoos USING gin (f_unaccent(city) gin_trgm_ops)
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE INDEX IF NOT EXISTS idx_zoos_name_city_trgm
            ON zoos USING gin (
                f_unaccent(coalesce(name, '') || ' ' || coalesce(city, '')) gin_trgm_ops
            )
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect != "postgresql":
        return

    op.execute(sa.text("DROP INDEX IF EXISTS idx_zoos_name_city_trgm"))
    op.execute(sa.text("DROP INDEX IF EXISTS idx_zoos_city_trgm"))
    op.execute(sa.text("DROP INDEX IF EXISTS idx_zoos_name_trgm"))
    op.execute(
        sa.text(
            """
            CREATE INDEX IF NOT EXISTS idx_zoos_name_trgm
            ON zoos USING gin (name gin_trgm_ops)
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE INDEX IF NOT EXISTS idx_zoos_city_trgm
            ON zoos USING gin (city gin_trgm_ops)
            """
        )
    )

    op.execute(sa.text("DROP FUNCTION IF EXISTS f_unaccent(text)"))
