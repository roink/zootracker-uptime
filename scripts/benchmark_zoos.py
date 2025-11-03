#!/usr/bin/env python
"""Simple load-testing helper for the /zoos endpoint.

This script is intended for local development benchmarking. It issues a mix
of requests against the `/zoos` endpoint that mirror queries captured in the
provided application logs, records latency metrics, and summarises
performance.

Example usage:

    python scripts/benchmark_zoos.py --base-url http://127.0.0.1:8000 --requests 1000

Use `--help` to see all available options.
"""

from __future__ import annotations

import argparse
import asyncio
import math
import random
import statistics
import time
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

import httpx

PAIRS_TSV = """
continent	country	n_zoos
1	4	1
1	19	4
1	23	1
1	29	3
1	32	1
1	37	1
1	47	2
1	49	2
1	67	1
1	70	9
1	83	6
1	87	4
1	88	5
1	94	1
1	103	20
1	117	1
1	118	1
1	121	8
1	125	2
1	127	1
1	128	7
1	132	1
1	136	4
1	139	52
1	143	2
1	145	4
1	148	12
1	150	5
1	172	10
1	173	2
2	1	1
2	6	5
2	7	2
2	11	6
2	12	9
2	16	1
2	21	4
2	25	118
2	26	4
2	27	1
2	54	60
2	55	51
2	56	3
2	57	2
2	60	68
2	63	287
2	64	2
2	65	8
2	66	3
2	69	13
2	71	1
2	76	4
2	77	1
2	79	1
2	84	63
2	85	2
2	93	3
2	95	5
2	104	2
2	107	6
2	108	1
2	114	12
2	122	8
2	129	12
2	134	7
2	138	1
2	140	19
2	141	1
2	142	22
2	144	35
2	149	23
2	155	9
2	158	20
2	168	13
3	8	114
3	9	1
3	39	1
3	43	1
3	46	2
3	96	43
3	109	3
3	111	2
3	156	3
3	161	1
4	2	6
4	3	1
4	13	22
4	14	45
4	18	6
4	22	26
4	30	1068
4	33	107
4	34	1
4	38	9
4	40	37
4	41	186
4	48	10
4	50	21
4	58	30
4	59	2
4	61	76
4	73	3
4	74	21
4	78	22
4	80	2
4	81	17
4	82	4
4	86	8
4	90	4
4	91	2
4	92	5
4	98	120
4	105	6
4	106	16
4	115	70
4	116	27
4	119	46
4	120	142
4	123	75
4	124	101
4	126	26
4	130	33
4	131	13
4	133	92
4	147	188
4	151	24
4	152	9
4	153	57
4	162	357
4	163	1
4	166	1
4	167	1
4	169	9
4	170	1
4	174	117
5	10	5
5	15	1
5	28	20
5	31	3
5	36	2
5	44	1
5	45	1
5	51	2
5	52	1
5	53	2
5	62	2
5	68	65
5	75	10
5	89	57
5	97	1
5	102	1
5	110	5
5	135	1
5	159	885
5	160	1
5	164	2
5	165	2
6	5	11
6	17	5
6	20	46
6	24	16
6	35	9
6	42	1
6	72	20
6	99	4
6	100	1
6	101	1
6	112	4
6	113	21
6	137	3
6	146	1
6	154	7
6	157	13
""".strip()

def _parse_pairs(ts: str) -> list[tuple[int, int, int]]:
    pairs: list[tuple[int, int, int]] = []
    for line in ts.splitlines():
        # skip header / empty lines
        if not line.strip() or line.lower().startswith("continent"):
            continue
        a, b, w = line.split()
        pairs.append((int(a), int(b), int(w)))
    return pairs

PAIR_TUPLES = _parse_pairs(PAIRS_TSV)  # [(continent, country, weight), ...]
PAIR_CHOICES = [(c, k) for c, k, _ in PAIR_TUPLES]
PAIR_WEIGHTS = [w for _, _, w in PAIR_TUPLES]

def sample_valid_pairs(k: int) -> list[dict[str, Any]]:
    picked = random.choices(PAIR_CHOICES, weights=PAIR_WEIGHTS, k=k)  # weighted by n_zoos
    return [
        {
            "latitude": "51.0",
            "longitude": "6.9",
            "continent_id": str(continent),
            "country_id": str(country),
        }
        for (continent, country) in picked
    ]


# Queries reproduced from the supplied log snippet. The categories ensure we
# exercise latitude/longitude lookups, text filtering, and continent/country
# filters.
LAT_LON_VARIANTS: List[Dict[str, Any]] = [
    {"latitude": "51.0", "longitude": "6.9"},
]

SEARCH_VARIANTS: List[Dict[str, Any]] = [
    {"latitude": "51.0", "longitude": "6.9", "q": "zoo"},
    {"latitude": "51.0", "longitude": "6.9", "q": "zoo", "continent_id": "6"},
    {"latitude": "51.0", "longitude": "6.9", "q": "zoo", "continent_id": "3"},
    {
        "latitude": "51.0",
        "longitude": "6.9",
        "q": "zoo",
        "continent_id": "3",
        "country_id": "109",
    },
    {"latitude": "51.0", "longitude": "6.9", "q": "K\u00f6ln"},
    {"latitude": "51.0", "longitude": "6.9", "q": "Berlin"},
    {"latitude": "51.0", "longitude": "6.9", "q": "Berl"},
    {"latitude": "51.0", "longitude": "6.9", "q": "Ber"},
]

CONTINENT_VARIANTS: List[Dict[str, Any]] = [
    {"latitude": "51.0", "longitude": "6.9", "continent_id": "1"},
    {"latitude": "51.0", "longitude": "6.9", "continent_id": "2"},
    {"latitude": "51.0", "longitude": "6.9", "continent_id": "3"},
    {"latitude": "51.0", "longitude": "6.9", "continent_id": "4"},
    {"latitude": "51.0", "longitude": "6.9", "continent_id": "5"},
    {"latitude": "51.0", "longitude": "6.9", "continent_id": "6"},
]

CONTINENT_COUNTRY_VARIANTS: List[Dict[str, Any]] = [
    {"latitude": "51.0", "longitude": "6.9", "continent_id": "2", "country_id": "16"},
    {"latitude": "51.0", "longitude": "6.9", "continent_id": "2", "country_id": "60"},
    {"latitude": "51.0", "longitude": "6.9", "continent_id": "2", "country_id": "144"},
    {"latitude": "51.0", "longitude": "6.9", "continent_id": "2", "country_id": "158"},
    {"latitude": "51.0", "longitude": "6.9", "continent_id": "3", "country_id": "39"},
    {"latitude": "51.0", "longitude": "6.9", "continent_id": "3", "country_id": "109"},
]

ALL_VARIANTS: List[Dict[str, Any]] = (
    LAT_LON_VARIANTS
    + SEARCH_VARIANTS
    + CONTINENT_VARIANTS
    + CONTINENT_COUNTRY_VARIANTS
)


@dataclass
class RequestResult:
    """Holds information about a single request outcome."""

    duration_ms: float
    status_code: Optional[int]
    params: Dict[str, Any]
    error: Optional[BaseException] = None


def build_request_plan(total: int) -> list[dict[str, Any]]:
    if total <= 0:
        raise ValueError("Total number of requests must be positive")

    plan: list[dict[str, Any]] = []
    # Keep your 25/25/25/25 mix (adjust if you like)
    n_latlon   = max(1, int(total * 0.25))
    n_search   = max(1, int(total * 0.25))
    n_continent= max(1, int(total * 0.25))
    n_pairs    = max(1, int(total * 0.25))

    # 1) plain lat/lon
    plan.extend(dict(random.choice(LAT_LON_VARIANTS)) for _ in range(n_latlon))

    # 2) search queries (leave as-is)
    plan.extend(dict(random.choice(SEARCH_VARIANTS)) for _ in range(n_search))

    # 3) continent-only filters (still valid)
    plan.extend(dict(random.choice(CONTINENT_VARIANTS)) for _ in range(n_continent))

    # 4) continent+country (weighted, *always* valid)
    plan.extend(sample_valid_pairs(n_pairs))

    # Top-up if rounding left us short
    while len(plan) < total:
        plan.append(random.choice(plan))

    random.shuffle(plan)
    return plan[:total]



async def send_request(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    params: Dict[str, Any],
) -> RequestResult:
    """Send a single request and capture its latency."""

    async with semaphore:
        start = time.perf_counter()
        try:
            response = await client.get("/zoos", params=params)
            duration_ms = (time.perf_counter() - start) * 1000
            return RequestResult(duration_ms, response.status_code, params)
        except BaseException as exc:  # include asyncio cancellation errors
            duration_ms = (time.perf_counter() - start) * 1000
            return RequestResult(duration_ms, None, params, exc)


def percentile(values: Iterable[float], percentile_value: float) -> Optional[float]:
    """Compute an interpolated percentile from a collection of values."""

    values = list(values)
    if not values:
        return None
    if not 0 <= percentile_value <= 1:
        raise ValueError("percentile must be between 0 and 1 inclusive")

    sorted_values = sorted(values)
    position = (len(sorted_values) - 1) * percentile_value
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[int(position)]
    lower_value = sorted_values[lower]
    upper_value = sorted_values[upper]
    return lower_value + (upper_value - lower_value) * (position - lower)


async def run_benchmark(
    base_url: str,
    total_requests: int,
    concurrency: int,
    timeout: float,
    seed: Optional[int],
) -> None:
    if seed is not None:
        random.seed(seed)

    if concurrency <= 0:
        raise ValueError("Concurrency must be a positive integer")

    semaphore = asyncio.Semaphore(concurrency)
    request_plan = build_request_plan(total_requests)

    limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency)
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout, limits=limits) as client:
        tasks = [
            asyncio.create_task(send_request(client, semaphore, dict(params)))
            for params in request_plan
        ]

        responses: List[RequestResult] = []
        for idx, task in enumerate(asyncio.as_completed(tasks), start=1):
            result = await task
            responses.append(result)
            if idx % max(1, total_requests // 10) == 0 or idx == total_requests:
                print(f"Completed {idx}/{total_requests} requests")

    durations = [r.duration_ms for r in responses if r.status_code is not None]
    status_counts = Counter(
        r.status_code if r.status_code is not None else "error" for r in responses
    )
    errors = [r for r in responses if r.error is not None]

    if not durations:
        print("No successful responses recorded; nothing to report.")
        return

    stats = {
        "min": min(durations),
        "max": max(durations),
        "mean": statistics.mean(durations),
        "std": statistics.pstdev(durations) if len(durations) > 1 else 0.0,
        "p5": percentile(durations, 0.05),
        "p50": percentile(durations, 0.50),
        "p95": percentile(durations, 0.95),
        "p99": percentile(durations, 0.99),
    }

    print("\nStatus codes:")
    for status, count in sorted(status_counts.items(), key=lambda item: str(item[0])):
        print(f"  {status}: {count}")

    if errors:
        print("\nErrors:")
        for err in errors:
            print(f"  params={err.params} -> {err.error}")

    print("\nLatency metrics (ms):")
    for key in ["min", "p5", "p50", "mean", "p95", "p99", "max", "std"]:
        value = stats[key]
        formatted = f"{value:.2f}" if value is not None else "n/a"
        print(f"  {key:>4}: {formatted}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark the /zoos endpoint")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="Base URL of the running API server (default: %(default)s)",
    )
    parser.add_argument(
        "--requests",
        type=int,
        default=1000,
        help="Total number of requests to issue (default: %(default)s)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=20,
        help="Maximum number of in-flight requests (default: %(default)s)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Per-request timeout in seconds (default: %(default)s)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Seed for the random generator to produce repeatable plans",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    asyncio.run(
        run_benchmark(
            base_url=args.base_url,
            total_requests=args.requests,
            concurrency=args.concurrency,
            timeout=args.timeout,
            seed=args.seed,
        )
    )


if __name__ == "__main__":
    main()
