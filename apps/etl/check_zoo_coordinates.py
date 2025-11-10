#!/usr/bin/env python3
"""Check zoo coordinates for invalid ranges and outliers.

This script inspects the ``zoo`` table of the zootierliste database and
reports entries with latitude/longitude values outside the valid geographic
range or statistical outliers per country based on the interquartile range
(IQR) rule.

Usage:
    python check_zoo_coordinates.py [DB_FILE]

If ``DB_FILE`` is omitted, ``zootierliste.db`` in the current directory is
used.
"""

from __future__ import annotations

import argparse
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from statistics import quantiles
from typing import Dict, Iterable, List, Optional, Sequence

DB_FILE = "zootierliste.db"


@dataclass
class ZooRecord:
    """A single row from the ``zoo`` table."""

    zoo_id: int
    country: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    name: Optional[str]


@dataclass
class Suspicious:
    """A record flagged for some reason."""

    record: ZooRecord
    reasons: List[str]
    severity: float = 0.0  # IQR outlier severity in number of IQRs beyond the bound


def fetch_rows(conn: sqlite3.Connection) -> List[ZooRecord]:
    cur = conn.cursor()
    cur.execute(
        "SELECT zoo_id, country, latitude, longitude, name FROM zoo"
    )
    rows = [ZooRecord(*r) for r in cur.fetchall()]
    return rows


def _compute_bounds(values: Sequence[float]) -> Optional[tuple[float, float, float]]:
    if len(values) < 4:
        return None
    q1, _, q3 = quantiles(values, n=4, method="inclusive")
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    return lower, upper, iqr


def find_suspicious(rows: Iterable[ZooRecord]) -> Dict[int, Suspicious]:
    flagged: Dict[int, Suspicious] = {}
    groups: Dict[Optional[str], List[ZooRecord]] = defaultdict(list)

    for r in rows:
        reasons = []
        if r.latitude is None or r.longitude is None:
            reasons.append("missing")
        else:
            if not (-90 <= r.latitude <= 90):
                reasons.append("latitude range")
            if not (-180 <= r.longitude <= 180):
                reasons.append("longitude range")
        if reasons:
            flagged[r.zoo_id] = Suspicious(r, reasons)
        else:
            groups[r.country].append(r)

    for country, entries in groups.items():
        lat_bounds = _compute_bounds([e.latitude for e in entries])
        lon_bounds = _compute_bounds([e.longitude for e in entries])
        for e in entries:
            reasons = []
            severity_val = 0.0
            if lat_bounds:
                lo, hi, iqr = lat_bounds
                if not (lo <= e.latitude <= hi):
                    reasons.append("latitude iqr")
                    if iqr > 0:
                        if e.latitude < lo:
                            severity_val = max(severity_val, (lo - e.latitude) / iqr)
                        elif e.latitude > hi:
                            severity_val = max(severity_val, (e.latitude - hi) / iqr)
  
            if lon_bounds:
                lo, hi, iqr = lon_bounds
                if not (lo <= e.longitude <= hi):
                    reasons.append("longitude iqr")
                    if iqr > 0:
                        if e.longitude < lo:
                            severity_val = max(severity_val, (lo - e.longitude) / iqr)
                        elif e.longitude > hi:
                            severity_val = max(severity_val, (e.longitude - hi) / iqr)
                      
            if reasons:
                if e.zoo_id in flagged:
                    flagged[e.zoo_id].reasons.extend(reasons)
                    flagged[e.zoo_id].severity = max(flagged[e.zoo_id].severity, severity_val)                    
                else:
                    flagged[e.zoo_id] = Suspicious(e, reasons)
                    flagged[e.zoo_id] = Suspicious(e, reasons, severity_val)                    

    return flagged


def main(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        rows = fetch_rows(conn)
    finally:
        conn.close()

    flagged = find_suspicious(rows)
    # Sort by IQR severity (descending). Non-IQR issues have severity 0 and come last.
    for s in sorted(
        flagged.values(), key=lambda x: (-x.severity, x.record.zoo_id)
    ):
        r = s.record
        reason = ", ".join(sorted(set(s.reasons)))
        print(
            f"{r.zoo_id}\t{r.country}\t{r.name}\t{r.latitude}\t{r.longitude}\t{reason}\t{s.severity:.3f}"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "db",
        nargs="?",
        default=DB_FILE,
        help="Path to the SQLite database (default: zootierliste.db)",
    )
    main(parser.parse_args().db)
