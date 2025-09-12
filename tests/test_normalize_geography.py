import sqlite3

from zootier_scraper_sqlite import ensure_db_schema
from normalize_geography import normalize_geography


def test_normalize_geography_creates_lookup_and_replaces_values():
    conn = sqlite3.connect(":memory:")
    ensure_db_schema(conn)
    with conn:
        conn.execute(
            "INSERT INTO zoo(zoo_id, continent, country, city, name) "
            "VALUES (1, 'Europa', 'Deutschland', 'Berlin', 'Zoo Berlin')"
        )
        conn.execute(
            "INSERT INTO zoo(zoo_id, continent, country, city, name) "
            "VALUES (2, 'Europa', 'Deutschland', 'Munich', 'Zoo Munich')"
        )
        conn.execute(
            "INSERT INTO zoo(zoo_id, continent, country, city, name) "
            "VALUES (3, 'Europa', 'Frankreich', 'Paris', 'Zoo Paris')"
        )
        conn.execute(
            "INSERT INTO zoo(zoo_id, continent, country, city, name) "
            "VALUES (4, 'Asien', 'Japan', 'Tokyo', 'Zoo Tokyo')"
        )

    normalize_geography(conn)

    cur = conn.cursor()
    cur.execute(
        "SELECT id, name_de, name_en FROM continent_name ORDER BY id"
    )
    assert cur.fetchall() == [(1, "Asien", None), (2, "Europa", None)]

    cur.execute(
        "SELECT id, name_de, name_en, continent_id FROM country_name ORDER BY id"
    )
    assert cur.fetchall() == [
        (1, "Deutschland", None, 2),
        (2, "Frankreich", None, 2),
        (3, "Japan", None, 1),
    ]

    cur.execute("SELECT continent, country FROM zoo ORDER BY zoo_id")
    assert cur.fetchall() == [(2, 1), (2, 1), (2, 2), (1, 3)]

    # Foreign keys are enforced
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1

    # Ensure name_en columns exist for future translations
    cur.execute("PRAGMA table_info(continent_name)")
    assert any(col[1] == "name_en" for col in cur.fetchall())
    cur.execute("PRAGMA table_info(country_name)")
    assert any(col[1] == "name_en" for col in cur.fetchall())

    conn.close()


def test_normalize_geography_drops_indexes_and_is_idempotent():
    conn = sqlite3.connect(":memory:")
    ensure_db_schema(conn)
    # extra index that should survive
    with conn:
        conn.execute("CREATE INDEX idx_name ON zoo(name)")
        conn.execute(
            "INSERT INTO zoo(zoo_id, continent, country, city, name) "
            "VALUES (1, 'Europa', 'Deutschland', 'Berlin', 'Zoo Berlin')"
        )
    normalize_geography(conn)

    # zoo_name_idx references country and should be gone; idx_name remains
    indexes = {
        row[1]: row[2]
        for row in conn.execute("PRAGMA index_list('zoo')").fetchall()
    }
    assert "idx_name" in indexes
    assert "zoo_name_idx" not in indexes

    # Run normalization again after recreating zoo table to ensure IDs stable
    continents_first = conn.execute(
        "SELECT id, name_de FROM continent_name ORDER BY id"
    ).fetchall()
    countries_first = conn.execute(
        "SELECT id, name_de FROM country_name ORDER BY id"
    ).fetchall()

    with conn:
        conn.execute("DROP TABLE zoo")
    ensure_db_schema(conn)
    with conn:
        conn.execute(
            "INSERT INTO zoo(zoo_id, continent, country, city, name) "
            "VALUES (1, 'Europa', 'Deutschland', 'Berlin', 'Zoo Berlin')"
        )
    normalize_geography(conn)

    assert continents_first == conn.execute(
        "SELECT id, name_de FROM continent_name ORDER BY id"
    ).fetchall()
    assert countries_first == conn.execute(
        "SELECT id, name_de FROM country_name ORDER BY id"
    ).fetchall()

    conn.close()
