import sqlite3
import subprocess
import sys
from pathlib import Path


def _prepare_db(path: Path) -> Path:
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE zoo (zoo_id INTEGER PRIMARY KEY, country TEXT, latitude REAL, longitude REAL, name TEXT)"
    )
    data = [
        (1, 'X', 10.0, 20.0, 'a'),
        (2, 'X', 11.0, 21.0, 'b'),
        (3, 'X', 12.0, 22.0, 'c'),
        (4, 'X', 13.0, 23.0, 'd'),
        (5, 'X', 50.0, 24.0, 'e'),  # latitude outlier
        (6, 'Y', 95.0, 30.0, 'f'),  # invalid latitude
        (7, 'Y', 10.0, 190.0, 'g'),  # invalid longitude
        (8, 'Z', None, 40.0, 'h'),  # missing latitude
        (9, 'W', 40.0, -10.0, 'i'),
        (10, 'W', 40.0, -11.0, 'j'),
        (11, 'W', 40.0, -12.0, 'k'),
        (12, 'W', 40.0, -13.0, 'l'),
        (13, 'W', 40.0, -60.0, 'm'),  # longitude outlier
    ]
    conn.executemany("INSERT INTO zoo VALUES (?,?,?,?,?)", data)
    conn.commit()
    conn.close()
    return path


def test_check_zoo_coordinates(tmp_path):
    db_path = _prepare_db(tmp_path / 'test.db')
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parent.parent / 'check_zoo_coordinates.py'), str(db_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    out = result.stdout
    assert '5' in out and 'latitude iqr' in out
    assert '6' in out and 'latitude range' in out
    assert '7' in out and 'longitude range' in out
    assert '8' in out and 'missing' in out
    assert '13' in out and 'longitude iqr' in out
