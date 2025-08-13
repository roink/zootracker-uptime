import os
import sys
from unittest.mock import patch, Mock

from bs4 import BeautifulSoup

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from zootier_scraper_sqlite import (
    fetch_zoo_map_soup,
    parse_zoo_map,
    ZooLocation,
    fetch_zoo_popup_soup,
    parse_zoo_popup,
    ZooInfo,
    fetch_zoo_details,
)

SAMPLE_RESPONSE = (
    "point\ttitle\tdescription\ticon\n"
    "51.1285,5.14594\t10000950\t\timages/marker.png\n"
    "56.4566,10.0338\t10000345\t\timages/marker.png"
)


def test_fetch_zoo_map_soup(real_request):
    if real_request:
        soup = fetch_zoo_map_soup(1060101)
        assert "point" in soup.get_text()
    else:
        mock_resp = Mock(status_code=200, text=SAMPLE_RESPONSE)
        with (
            patch('zootier_scraper_sqlite.SESSION.get', return_value=mock_resp) as mock_get,
            patch('zootier_scraper_sqlite.time.sleep')
        ):
            soup = fetch_zoo_map_soup(1060101)
            mock_get.assert_called_once_with(
                "https://www.zootierliste.de/map_zoos.php",
                params={"art": "1060101", "tab": "tab_zootier"},
                timeout=(5, 20),
            )
        assert "point" in soup.get_text()


def test_parse_zoo_map_returns_known_zoo():
    soup = BeautifulSoup(SAMPLE_RESPONSE, 'html.parser')
    data = parse_zoo_map(soup)
    assert any(
        z.zoo_id == 10000950
        and abs(z.latitude - 51.1285) < 1e-4
        and abs(z.longitude - 5.14594) < 1e-4
        for z in data
    )
    for z in data:
        assert isinstance(z, ZooLocation)
        assert isinstance(z.zoo_id, int)
        assert isinstance(z.latitude, float)
        assert isinstance(z.longitude, float)


def test_parse_zoo_map_blank_lines_and_malformed_skipped():
    sample = (
        "point\ttitle\tdescription\ticon\n"
        "\n"
        "51.1285,5.14594\t10000950\t\timages/marker.png\n"
        "\n"
        "bad_latlon\t10009999\t\timages/marker.png\n"
        "56.4566,10.0338\t10000345\t\timages/marker.png\n"
    )
    soup = BeautifulSoup(sample, 'html.parser')
    data = parse_zoo_map(soup)
    assert [z.zoo_id for z in data] == [10000950, 10000345]


def test_parse_zoo_map_header_only():
    soup = BeautifulSoup("point\ttitle\tdescription\ticon\n", 'html.parser')
    assert parse_zoo_map(soup) == []


SAMPLE_ZOO_INFO = (
    '<div class="datum">Lyon (Zoo)</div>'
    '<div class="inhalt">Land: Frankreich<br>Website: '
    '<a target="_blank" href="http://fr.zoo-infos.org/zoos-de/9998.html">'
    'http://fr.zoo-infos.org/zoos-de/9998.html</a><br></div>'
)

SAMPLE_NO_WEBSITE = (
    '<div class="datum">Vienna Zoo</div>'
    '<div class="inhalt">Land: Österreich<br></div>'
)

SAMPLE_NBSP = (
    '<div class="datum">  Lyon&nbsp; ( Zoo ) </div>'
    '<div class="inhalt">Land:&nbsp;Frankreich</a><br></div>'
)


def test_fetch_zoo_popup_soup_makes_request():
    mock_resp = Mock(status_code=200, text=SAMPLE_ZOO_INFO)
    with (
        patch('zootier_scraper_sqlite.SESSION.get', return_value=mock_resp) as mock_get,
        patch('zootier_scraper_sqlite.time.sleep')
    ):
        soup = fetch_zoo_popup_soup(10000829)
        mock_get.assert_called_once_with(
            "https://www.zootierliste.de/map_zoos.php",
            params={"showzoo": "10000829", "popup": "true"},
            headers={"X-Requested-With": "XMLHttpRequest"},
            timeout=(5, 20),
        )
    assert soup.find("div", class_="datum") is not None


def test_parse_zoo_popup_basic():
    soup = BeautifulSoup(SAMPLE_ZOO_INFO, 'html.parser')
    info = parse_zoo_popup(soup)
    assert info == ZooInfo(
        country="Frankreich",
        website="http://fr.zoo-infos.org/zoos-de/9998.html",
        city="Lyon",
        name="Zoo",
    )


def test_parse_zoo_popup_missing_website():
    soup = BeautifulSoup(SAMPLE_NO_WEBSITE, 'html.parser')
    info = parse_zoo_popup(soup)
    assert info.country == "Österreich"
    assert info.website is None
    assert info.city == "Vienna Zoo"
    assert info.name is None


def test_parse_zoo_popup_nbsp_and_spacing():
    soup = BeautifulSoup(SAMPLE_NBSP, 'html.parser')
    info = parse_zoo_popup(soup)
    assert info.country == "Frankreich"
    assert info.city == "Lyon"
    assert info.name == "Zoo"


def test_parse_zoo_popup_city_only():
    html = '<div class="datum">Zoo Berlin</div><div class="inhalt">Land: Deutschland<br></div>'
    soup = BeautifulSoup(html, 'html.parser')
    info = parse_zoo_popup(soup)
    assert info.country == "Deutschland"
    assert info.city == "Zoo Berlin"
    assert info.name is None


def test_fetch_zoo_details_wrapper():
    soup = BeautifulSoup(SAMPLE_ZOO_INFO, 'html.parser')
    with patch('zootier_scraper_sqlite.fetch_zoo_popup_soup', return_value=soup):
        info = fetch_zoo_details(10000829)
    assert info == {
        "country": "Frankreich",
        "website": "http://fr.zoo-infos.org/zoos-de/9998.html",
        "city": "Lyon",
        "name": "Zoo",
    }
