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

    def create(self, **kwargs):  # pragma: no cover - executed via lookup_qid
        self.calls.append(kwargs)
        qid = self._outputs.pop(0)
        content = SimpleNamespace(json={"wikidata_qid": qid})
        return SimpleNamespace(output=[SimpleNamespace(content=[content])])


class DummyClient:
    def __init__(self, outputs):
        self.responses = DummyResponses(outputs)
        self.with_options_kwargs = None

    def with_options(self, **kwargs):  # pragma: no cover - executed via lookup_qid
        self.with_options_kwargs = kwargs
        return self


def test_process_animals_inserts_unique_qids(tmp_path, capsys):
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

    def stub_lookup(client, latin, name_de, name_en):
        return next(outputs)

    matcher.process_animals(db_path=str(db_path), client=object(), lookup=stub_lookup)

    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT art, wikidata_qid, wikidata_match_status, wikidata_match_method FROM animal ORDER BY art",
    ).fetchall()
    conn.close()

    assert rows == [("1", "Q1", "llm", "gpt-5-mini"), ("2", None, None, None)]
    captured = capsys.readouterr().out
    assert "collision for 2: Q1" in captured


def test_lookup_qid_request_and_validation():
    dummy = DummyClient(["Q123"])
    qid = matcher.lookup_qid(dummy, "Panthera leo", "Löwe", "Lion")

    assert qid == "Q123"
    assert dummy.with_options_kwargs == {"timeout": 900.0}

    call = dummy.responses.calls[0]
    assert call["model"] == "gpt-5-mini"
    assert call["tools"] == [{"type": "web_search"}]
    assert call["service_tier"] == "flex"
    assert call["response_format"]["type"] == "json_schema"
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

