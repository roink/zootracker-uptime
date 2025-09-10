import sqlite3
import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from fetch_taxon_names import ensure_name_tables, extract_names


def test_ensure_name_tables_creates_tables():
    conn = sqlite3.connect(":memory:")
    ensure_name_tables(conn)
    cur = conn.cursor()
    tables = {
        row[0] for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {"klasse_name", "ordnung_name", "familie_name"} <= tables


def test_extract_names_parses_html():
    html = """
    <div id="navigation">
        <a href="?klasse=1">Säugetiere</a>
        <a href="?klasse=2">Vögel</a>
        <a href="?klasse=1&ordnung=101">Kloakentiere</a>
        <a href="?klasse=1&ordnung=102">Beuteltiere</a>
        <a href="?klasse=1&ordnung=102&familie=10201">Testfamilie &amp; Co</a>
        <a href="?klasse=1&ordnung=102&familie=10202">Haustierrassen &nbsp;&amp; Zuchtformen</a>
        <a href="?klasse=1&ordnung=102&action=login">ignore</a>
    </div>
    """
    classes, orders, families = extract_names(html)
    assert classes == {1: "Säugetiere", 2: "Vögel"}
    assert orders == {101: "Kloakentiere", 102: "Beuteltiere"}
    assert families == {
        10201: "Testfamilie & Co",
        10202: "Haustierrassen & Zuchtformen",
    }
