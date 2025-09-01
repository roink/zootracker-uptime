import sqlite3

import httpx
import pytest

from zootier_scraper_sqlite import ensure_db_schema
from wikidata_matcher import find_qid, process_animals


@pytest.mark.asyncio
async def test_find_qid_uses_sparql_first():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url)
        if request.url.host == "query.wikidata.org":
            return httpx.Response(
                200,
                json={
                    "results": {
                        "bindings": [
                            {
                                "item": {
                                    "type": "uri",
                                    "value": "http://www.wikidata.org/entity/Q1",
                                }
                            }
                        ]
                    }
                },
            )
        return httpx.Response(500)

    transport = httpx.MockTransport(handler)
    animal = {
        "normalized_latin_name": "Pavo cristatus",
        "alternative_latin_names": "[]",
        "name_en": None,
        "name_de": None,
    }
    async with httpx.AsyncClient(transport=transport) as client:
        qid = await find_qid(client, animal)
    assert qid == "Q1"
    assert all(url.host == "query.wikidata.org" for url in requests)


@pytest.mark.asyncio
async def test_find_qid_falls_back_to_api():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url)
        if request.url.host == "query.wikidata.org":
            params = httpx.QueryParams(request.content.decode())
            q = params.get("query", "")
            if q.strip().startswith("SELECT ?tn"):
                return httpx.Response(
                    200,
                    json={
                        "results": {
                            "bindings": [
                                {"tn": {"type": "literal", "value": "Pavo cristatus"}}
                            ]
                        }
                    },
                )
            return httpx.Response(200, json={"results": {"bindings": []}})
        if request.url.path == "/w/api.php":
            return httpx.Response(200, json={"search": [{"id": "Q1"}]})
        return httpx.Response(500)

    transport = httpx.MockTransport(handler)
    animal = {
        "normalized_latin_name": "Pavo cristatus",
        "alternative_latin_names": "[]",
        "name_en": None,
        "name_de": None,
    }
    async with httpx.AsyncClient(transport=transport) as client:
        qid = await find_qid(client, animal)
    assert qid == "Q1"
    assert any(url.path == "/w/api.php" for url in calls)


@pytest.mark.asyncio
async def test_process_animals_updates_db(tmp_path):
    db_path = tmp_path / "t.db"
    conn = sqlite3.connect(db_path)
    ensure_db_schema(conn)
    conn.execute(
        "INSERT INTO animal (art, klasse, normalized_latin_name, zoo_count) VALUES (?,?,?,?)",
        ("1", 1, "Pavo cristatus", 5),
    )
    conn.execute(
        "INSERT INTO animal (art, klasse, normalized_latin_name, zoo_count) VALUES (?,?,?,?)",
        ("2", 1, "Unknown", 4),
    )
    conn.commit()
    conn.close()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "query.wikidata.org":
            params = httpx.QueryParams(request.content.decode())
            q = params.get("query", "")
            if "Pavo cristatus" in q:
                return httpx.Response(
                    200,
                    json={
                        "results": {
                            "bindings": [
                                {
                                    "item": {
                                        "type": "uri",
                                        "value": "http://www.wikidata.org/entity/Q1",
                                    }
                                }
                            ]
                        }
                    },
                )
            return httpx.Response(200, json={"results": {"bindings": []}})
        if request.url.path == "/w/api.php":
            return httpx.Response(200, json={"search": []})
        return httpx.Response(500)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        await process_animals(db_path=str(db_path), client=client)

    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT art, wikidata_qid, wikidata_match_status FROM animal"
    ).fetchall()
    conn.close()
    data = {art: (qid, status) for art, qid, status in rows}
    assert data["1"] == ("Q1", "auto")
    assert data["2"] == (None, "none")
