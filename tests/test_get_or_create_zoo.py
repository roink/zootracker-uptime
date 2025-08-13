import os
import sqlite3
import sys
from bs4 import BeautifulSoup

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from zootier_scraper_sqlite import (
    ensure_db_schema,
    get_or_create_zoo,
    parse_zoo_popup,
    ZooLocation,
)

SAMPLE_ZOO_INFO = (
    '<div class="datum">Lyon (Zoo)</div>'
    '<div class="inhalt">Land: Frankreich<br>Website: '
    '<a target="_blank" href="http://fr.zoo-infos.org/zoos-de/9998.html">'
    'http://fr.zoo-infos.org/zoos-de/9998.html</a><br></div>'
)

SAMPLE_ZOO_INFO_NO_WEBSITE = (
    '<div class="datum">Lyon (Zoo)</div>'
    '<div class="inhalt">Land: Frankreich<br></div>'
)


def test_get_or_create_zoo_insert_and_updates_coords():
    conn = sqlite3.connect(":memory:")
    ensure_db_schema(conn)
    soup = BeautifulSoup(SAMPLE_ZOO_INFO, "html.parser")
    info = parse_zoo_popup(soup)

    with conn:
        zoo_id = get_or_create_zoo(conn, ZooLocation(123, 1.23, 4.56), info)
    with conn:
        zoo_id2 = get_or_create_zoo(conn, ZooLocation(123, 7.89, 0.12))

    assert zoo_id == zoo_id2 == 123
    cur = conn.cursor()
    cur.execute("SELECT latitude, longitude, website FROM zoo WHERE zoo_id=123")
    assert cur.fetchone() == (
        7.89,
        0.12,
        "http://fr.zoo-infos.org/zoos-de/9998.html",
    )
    conn.close()


def test_get_or_create_zoo_handles_existing_without_refetch():
    conn = sqlite3.connect(":memory:")
    ensure_db_schema(conn)

    soup_no = BeautifulSoup(SAMPLE_ZOO_INFO_NO_WEBSITE, "html.parser")
    info = parse_zoo_popup(soup_no)
    with conn:
        get_or_create_zoo(conn, ZooLocation(321, 1.0, 2.0), info)
    with conn:
        get_or_create_zoo(conn, ZooLocation(321, 3.0, 4.0))

    cur = conn.cursor()
    cur.execute("SELECT website, latitude, longitude FROM zoo WHERE zoo_id=321")
    assert cur.fetchone() == (None, 3.0, 4.0)
    conn.close()
