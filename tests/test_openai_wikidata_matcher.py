import importlib
import os
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import openai_wikidata_matcher as matcher
from zootier_scraper_sqlite import ensure_db_schema


class DummyResponses:
    def __init__(self, outputs):
        self._outputs = outputs
        self.calls: list[dict] = []

    def parse(self, **kwargs):  # pragma: no cover - executed via lookup_qid
        self.calls.append(kwargs)
        qid = self._outputs.pop(0)
        return SimpleNamespace(output_parsed=SimpleNamespace(wikidata_qid=qid))


class DummyClient:
    def __init__(self, outputs):
        self.responses = DummyResponses(outputs)
        self.with_options_kwargs = None

    def with_options(self, **kwargs):  # pragma: no cover - executed via lookup_qid
        self.with_options_kwargs = kwargs
        return self


def test_process_animals_resolves_collision(tmp_path, capsys):
    db_path = tmp_path / "t.db"
    conn = sqlite3.connect(db_path)
    ensure_db_schema(conn)
    conn.execute(
        "INSERT INTO animal (art, klasse, latin_name, name_de, name_en) VALUES (?,?,?,?,?)",
        ("1", 1, "Panthera leo", "Löwe", "Lion"),
    )
    conn.execute(
        "INSERT INTO animal (art, klasse, latin_name, name_de, name_en) VALUES (?,?,?,?,?)",
        ("2", 1, "Panthera tigris", "Tiger", "Tiger"),
    )
    conn.commit()
    conn.close()

    outputs = iter(["Q1", "Q1"])
    calls: list[str] = []

    def stub_lookup(client, latin, name_de, name_en):
        return next(outputs)

    def stub_resolve(client, existing, new, collided_qid):
        assert collided_qid == "Q1"
        return ("Q1", "Q2")

    def stub_fetch(qid: str) -> dict[str, str]:
        calls.append(qid)
        return {
            "wikipedia_en": f"en{qid}",
            "wikipedia_de": f"de{qid}",
            "taxon_rank": f"rank{qid}",
            "parent_taxon": f"parent{qid}",
            "iucn_conservation_status": f"status{qid}",
        }

    original_update = matcher.update_enrichment

    def stub_update(cur, art, qid):
        original_update(cur, art, qid, fetch=stub_fetch)

    matcher.update_enrichment = stub_update  # type: ignore
    try:
        matcher.process_animals(
            db_path=str(db_path), client=object(), lookup=stub_lookup, resolve=stub_resolve
        )
        out = capsys.readouterr().out
        assert "resolver returned: existing=Q1, new=Q2" in out
        assert "resolver made no changes" not in out
        assert calls == ["Q1", "Q2"]

        conn = sqlite3.connect(db_path)
        rows = conn.execute(
            """
            SELECT art, wikidata_qid, wikipedia_en, wikipedia_de, taxon_rank,
                   parent_taxon, iucn_conservation_status
              FROM animal ORDER BY art
            """,
        ).fetchall()
        conn.close()

        assert rows == [
            ("1", "Q1", "enQ1", "deQ1", "rankQ1", "parentQ1", "statusQ1"),
            ("2", "Q2", "enQ2", "deQ2", "rankQ2", "parentQ2", "statusQ2"),
        ]
    finally:
        matcher.update_enrichment = original_update


def test_collision_updates_existing_row(tmp_path, capsys):
    db_path = tmp_path / "t.db"
    conn = sqlite3.connect(db_path)
    ensure_db_schema(conn)
    conn.executescript(
        """
        ALTER TABLE animal ADD COLUMN wikidata_id TEXT;
        ALTER TABLE animal ADD COLUMN taxon_rank TEXT;
        ALTER TABLE animal ADD COLUMN parent_taxon TEXT;
        ALTER TABLE animal ADD COLUMN wikipedia_en TEXT;
        ALTER TABLE animal ADD COLUMN wikipedia_de TEXT;
        ALTER TABLE animal ADD COLUMN iucn_conservation_status TEXT;
        """
    )
    conn.execute(
        """
        INSERT INTO animal (
            art, klasse, latin_name, name_de, name_en, wikidata_qid,
            wikidata_match_status, wikidata_match_method, wikidata_match_score,
            wikidata_review_json, wikidata_id, taxon_rank, parent_taxon,
            wikipedia_en, wikipedia_de, iucn_conservation_status
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "1",
            1,
            "Panthera leo",
            "Löwe",
            "Lion",
            "Q1",
            "manual",
            "sparql",
            99.0,
            "{}",
            "ID1",
            "rank",
            "parent",
            "enwiki",
            "dewiki",
            "status",
        ),
    )
    conn.execute(
        "INSERT INTO animal (art, klasse, latin_name, name_de, name_en) VALUES (?,?,?,?,?)",
        ("2", 1, "Panthera tigris", "Tiger", "Tiger"),
    )
    conn.commit()
    conn.close()

    def stub_lookup(client, latin, name_de, name_en):
        return "Q1"

    def stub_resolve(client, existing, new, collided_qid):
        assert collided_qid == "Q1"
        return ("Q3", "Q2")

    def stub_fetch(qid: str) -> dict[str, str]:
        return {
            "wikipedia_en": f"en{qid}",
            "wikipedia_de": f"de{qid}",
            "taxon_rank": f"rank{qid}",
            "parent_taxon": f"parent{qid}",
            "iucn_conservation_status": f"status{qid}",
        }

    original_update = matcher.update_enrichment

    def stub_update(cur, art, qid):
        original_update(cur, art, qid, fetch=stub_fetch)

    matcher.update_enrichment = stub_update  # type: ignore
    try:
        matcher.process_animals(
            db_path=str(db_path), client=object(), lookup=stub_lookup, resolve=stub_resolve
        )
        out = capsys.readouterr().out
        assert "resolver returned: existing=Q3, new=Q2" in out
        assert "resolver made no changes" not in out

        conn = sqlite3.connect(db_path)
        rows = conn.execute(
            """
            SELECT art, wikidata_qid, wikipedia_en, wikipedia_de, taxon_rank,
                   parent_taxon, iucn_conservation_status
              FROM animal ORDER BY art
            """,
        ).fetchall()
        conn.close()

        assert rows == [
            ("1", "Q3", "enQ3", "deQ3", "rankQ3", "parentQ3", "statusQ3"),
            ("2", "Q2", "enQ2", "deQ2", "rankQ2", "parentQ2", "statusQ2"),
        ]
    finally:
        matcher.update_enrichment = original_update


def test_lookup_qid_request_and_validation():
    dummy = DummyClient(["Q123"])
    qid = matcher.lookup_qid(dummy, "Panthera leo", "Löwe", "Lion")

    assert qid == "Q123"
    assert dummy.with_options_kwargs == {"timeout": 900.0}

    call = dummy.responses.calls[0]
    assert call["model"] == "gpt-5-mini"
    assert call["tools"] == [{"type": "web_search"}]
    assert call["service_tier"] == "flex"
    assert call["text_format"] is matcher.WikidataLookup
    assert any(m["role"] == "user" and "Panthera leo" in m["content"] for m in call["input"])


def test_lookup_qid_rejects_invalid_ids():
    dummy = DummyClient(["not-a-qid"])
    qid = matcher.lookup_qid(dummy, "Panthera leo", None, None)
    assert qid is None


def test_load_env_file(monkeypatch):
    env_path = Path(matcher.__file__).resolve().parent / ".env"
    env_path.write_text("OPENAI_API_KEY=test123\n")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    try:
        importlib.reload(matcher)
        assert os.environ["OPENAI_API_KEY"] == "test123"
    finally:
        env_path.unlink()

