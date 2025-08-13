import sqlite3
from unittest.mock import patch
from bs4 import BeautifulSoup

from zootier_scraper_sqlite import (
    ensure_db_schema,
    get_or_create_zoo,
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


def test_get_or_create_zoo_upserts_coordinates():
    conn = sqlite3.connect(":memory:")
    ensure_db_schema(conn)
    soup = BeautifulSoup(SAMPLE_ZOO_INFO, "html.parser")

    with patch("zootier_scraper_sqlite.fetch_zoo_popup_soup", return_value=soup):
        with conn:
            zoo_id = get_or_create_zoo(conn, ZooLocation(123, 1.23, 4.56))
    assert zoo_id == 123

    cur = conn.cursor()
    cur.execute("SELECT latitude, longitude FROM zoo WHERE zoo_id=123")
    assert cur.fetchone() == (1.23, 4.56)

    # Second call updates coordinates
    with patch("zootier_scraper_sqlite.fetch_zoo_popup_soup", return_value=soup):
        with conn:
            zoo_id2 = get_or_create_zoo(conn, ZooLocation(123, 7.89, 0.12))
    assert zoo_id2 == 123
    cur.execute("SELECT latitude, longitude FROM zoo WHERE zoo_id=123")
    assert cur.fetchone() == (7.89, 0.12)
    conn.close()


def test_get_or_create_zoo_fills_missing_fields_and_refreshes():
    conn = sqlite3.connect(":memory:")
    ensure_db_schema(conn)

    # Insert initial row without website
    soup_no = BeautifulSoup(SAMPLE_ZOO_INFO_NO_WEBSITE, "html.parser")
    with patch("zootier_scraper_sqlite.fetch_zoo_popup_soup", return_value=soup_no):
        with conn:
            get_or_create_zoo(conn, ZooLocation(321, 1.0, 2.0))

    cur = conn.cursor()
    cur.execute("SELECT website, latitude, longitude FROM zoo WHERE zoo_id=321")
    assert cur.fetchone() == (None, 1.0, 2.0)

    # Second call provides website and new coordinates
    soup = BeautifulSoup(SAMPLE_ZOO_INFO, "html.parser")
    with patch("zootier_scraper_sqlite.fetch_zoo_popup_soup", return_value=soup):
        with conn:
            get_or_create_zoo(conn, ZooLocation(321, 3.0, 4.0))

    cur.execute("SELECT website, latitude, longitude FROM zoo WHERE zoo_id=321")
    assert cur.fetchone() == (
        "http://fr.zoo-infos.org/zoos-de/9998.html",
        3.0,
        4.0,
    )
    conn.close()
