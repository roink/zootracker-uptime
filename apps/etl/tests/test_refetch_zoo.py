import sqlite3
from unittest.mock import Mock

from bs4 import BeautifulSoup

import refetch_zoo
from refetch_zoo import fetch_zoo_location
from zootier_scraper_sqlite import ZooLocation


def test_fetch_zoo_location_makes_request(monkeypatch):
    text = (
        "point\ttitle\tdescription\ticon\n"
        "51.1285,5.14594\t10000950\t\timages/marker.png\n"
    )
    mock_resp = Mock(status_code=200, text=text)
    get_mock = Mock(return_value=mock_resp)
    monkeypatch.setattr("refetch_zoo.SESSION.get", get_mock)
    monkeypatch.setattr("refetch_zoo.time.sleep", lambda _: None)
    loc = fetch_zoo_location(10000950)
    get_mock.assert_called_once_with(
        "https://www.zootierliste.de/map_zoos.php",
        params={"showzoo": "10000950"},
        timeout=(5, 20),
    )
    assert loc == ZooLocation(10000950, 51.1285, 5.14594)


def test_refetch_zoo_updates_database(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    location = ZooLocation(555, 1.23, 4.56)
    monkeypatch.setattr(refetch_zoo, "fetch_zoo_location", lambda _z: location)
    sample = '<div class="datum">City (Name)</div><div class="inhalt">Land: Country<br></div>'
    soup = BeautifulSoup(sample, "html.parser")
    monkeypatch.setattr(refetch_zoo, "fetch_zoo_popup_soup", lambda _z: soup)
    refetch_zoo.refetch_zoo(555, str(db_path))
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT zoo_id, country, city, name, latitude, longitude FROM zoo WHERE zoo_id=555"
    )
    assert cur.fetchone() == (555, "Country", "City", "Name", 1.23, 4.56)
    conn.close()
