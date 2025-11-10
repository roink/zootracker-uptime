import os
import sys
import sqlite3
from unittest.mock import Mock

import requests
from bs4 import BeautifulSoup

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from zootier_scraper_sqlite import (
    parse_species,
    build_locale_url,
    ensure_db_schema,
    get_or_create_animal,
    update_animal_enrichment,
)


def _mock_response(text: str, status: int = 200) -> Mock:
    resp = Mock(status_code=status, text=text)
    if status >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError()
    else:
        resp.raise_for_status = Mock()
    return resp


def test_parse_species_localized_names(monkeypatch):
    de_html = '<td class="pageName">Dachs (Meles)</td>'
    en_html = '<td class="pageName">Badger</td>'
    mock_get = Mock(side_effect=[
        _mock_response(de_html),
        _mock_response(en_html),
    ])
    monkeypatch.setattr('zootier_scraper_sqlite.SESSION.get', mock_get)
    monkeypatch.setattr('zootier_scraper_sqlite.fetch_zoo_map_soup', lambda *_: BeautifulSoup("", 'html.parser'))
    monkeypatch.setattr('zootier_scraper_sqlite.parse_zoo_map', lambda *_: [])
    monkeypatch.setattr('zootier_scraper_sqlite.time.sleep', lambda *_: None)

    _, _, name_de, name_en, _, ztl_link = parse_species(
        'https://www.zootierliste.de/index.php?klasse=1&ordnung=107&familie=10701&art=123',
        123,
    )

    assert name_de == 'Dachs'
    assert name_en == 'Badger'
    assert ztl_link is None
    called_url = mock_get.call_args_list[1][0][0]
    assert called_url == build_locale_url('https://www.zootierliste.de/index.php?klasse=1&ordnung=107&familie=10701&art=123', 'en')


def test_parse_species_en_404(monkeypatch):
    de_html = '<td class="pageName">Dachs</td>'
    mock_get = Mock(side_effect=[
        _mock_response(de_html),
        _mock_response("not found", status=404),
    ])
    monkeypatch.setattr('zootier_scraper_sqlite.SESSION.get', mock_get)
    monkeypatch.setattr('zootier_scraper_sqlite.fetch_zoo_map_soup', lambda *_: BeautifulSoup("", 'html.parser'))
    monkeypatch.setattr('zootier_scraper_sqlite.parse_zoo_map', lambda *_: [])
    monkeypatch.setattr('zootier_scraper_sqlite.time.sleep', lambda *_: None)

    _, _, _, name_en, _, ztl_link = parse_species(
        'https://www.zootierliste.de/index.php?klasse=1&ordnung=107&familie=10701&art=123',
        123,
    )

    assert name_en is None
    assert ztl_link is None


def test_build_locale_url_idempotent():
    base = 'https://www.zootierliste.de/index.php?a=1'
    localized = build_locale_url(base, 'en')
    assert localized == 'https://www.zootierliste.de/en/index.php?a=1'
    assert build_locale_url(localized, 'en') == localized


def test_parse_species_extracts_ztl_link(monkeypatch):
    html = '<td id="tagline"><i>Latinus</i></td><td class="pageName">Name</td>' \
           '<a href="https://ZOOTIER-LEXIKON.org/abc/">ZTL</a>'
    mock_get = Mock(side_effect=[_mock_response(html)])
    monkeypatch.setattr('zootier_scraper_sqlite.SESSION.get', mock_get)
    monkeypatch.setattr('zootier_scraper_sqlite.fetch_localized_name', lambda *_: None)
    monkeypatch.setattr('zootier_scraper_sqlite.fetch_zoo_map_soup', lambda *_: BeautifulSoup("", 'html.parser'))
    monkeypatch.setattr('zootier_scraper_sqlite.parse_zoo_map', lambda *_: [])
    monkeypatch.setattr('zootier_scraper_sqlite.time.sleep', lambda *_: None)

    latin, _, _, _, _, ztl_link = parse_species('url', 1)
    assert ztl_link == 'https://zootier-lexikon.org/abc'
    assert latin == 'Latinus'


def test_parse_species_extracts_ztl_link_fallback(monkeypatch):
    html = '<td id="tagline"><i>Latinus</i></td>' \
           '<td class="pageName">Name</td>' \
           '<td>Zusätzliche Artinfos <a href="https://zootier-lexikon.org/fallback">ZTL</a></td>'
    mock_get = Mock(side_effect=[_mock_response(html)])
    monkeypatch.setattr('zootier_scraper_sqlite.SESSION.get', mock_get)
    monkeypatch.setattr('zootier_scraper_sqlite.fetch_localized_name', lambda *_: None)
    monkeypatch.setattr('zootier_scraper_sqlite.fetch_zoo_map_soup', lambda *_: BeautifulSoup("", 'html.parser'))
    monkeypatch.setattr('zootier_scraper_sqlite.parse_zoo_map', lambda *_: [])
    monkeypatch.setattr('zootier_scraper_sqlite.time.sleep', lambda *_: None)

    latin, _, _, _, _, ztl_link = parse_species('url', 1)
    assert ztl_link == 'https://zootier-lexikon.org/fallback'
    assert latin == 'Latinus'


def test_update_animal_enrichment_stores_ztl_link(tmp_path):
    db = tmp_path / 'db.sqlite'
    conn = sqlite3.connect(db)
    ensure_db_schema(conn)
    art = get_or_create_animal(conn, 1, 2, 3, '99', 'Latinus')
    update_animal_enrichment(conn, art, 'DE', 'EN', {}, 'https://zootier-lexikon.org/abc')
    update_animal_enrichment(conn, art, 'DE2', 'EN2', {}, None)
    c = conn.cursor()
    c.execute('SELECT name_de, name_en, zootierlexikon_link FROM animal WHERE art=?', (art,))
    row = c.fetchone()
    assert row[0] == 'DE2'
    assert row[1] == 'EN2'
    assert row[2] == 'https://zootier-lexikon.org/abc'
    conn.close()

