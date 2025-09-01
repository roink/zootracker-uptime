import os
import sqlite3
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from zootier_scraper_sqlite import (
    ensure_db_schema,
    get_or_create_animal,
    get_or_create_zoo,
    create_zoo_animal,
    update_counts,
    ZooLocation,
)


def test_update_counts_populates_columns():
    conn = sqlite3.connect(":memory:")
    ensure_db_schema(conn)

    with conn:
        a1 = get_or_create_animal(conn, 1, 1, 1, "a1", "Latin1")
        a2 = get_or_create_animal(conn, 1, 1, 1, "a2", "Latin2")
        a3 = get_or_create_animal(conn, 1, 1, 1, "a3", "Latin3")
        get_or_create_zoo(conn, ZooLocation(1, 0.0, 0.0))
        get_or_create_zoo(conn, ZooLocation(2, 0.0, 0.0))
        get_or_create_zoo(conn, ZooLocation(3, 0.0, 0.0))
        create_zoo_animal(conn, 1, a1)
        create_zoo_animal(conn, 2, a1)
        create_zoo_animal(conn, 1, a2)

    with conn:
        update_counts(conn)

    cur = conn.cursor()
    cur.execute("SELECT zoo_count FROM animal WHERE art=?", (a1,))
    assert cur.fetchone()[0] == 2
    cur.execute("SELECT zoo_count FROM animal WHERE art=?", (a2,))
    assert cur.fetchone()[0] == 1
    cur.execute("SELECT zoo_count FROM animal WHERE art=?", (a3,))
    assert cur.fetchone()[0] == 0
    cur.execute("SELECT species_count FROM zoo WHERE zoo_id=1")
    assert cur.fetchone()[0] == 2
    cur.execute("SELECT species_count FROM zoo WHERE zoo_id=2")
    assert cur.fetchone()[0] == 1
    cur.execute("SELECT species_count FROM zoo WHERE zoo_id=3")
    assert cur.fetchone()[0] == 0

    conn.close()
