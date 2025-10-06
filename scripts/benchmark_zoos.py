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


# Queries reproduced from the supplied log snippet. The categories ensure we
# exercise latitude/longitude lookups, text filtering, and continent/country
# filters.
@dataclass(frozen=True)
class VariantTemplate:
    """Template for a request variant with a descriptive label."""

    name: str
    params: Dict[str, Any]

    def build_params(self) -> Dict[str, Any]:
        """Return a shallow copy of the stored parameters for safe reuse."""

        return dict(self.params)


LAT_LON_VARIANTS: List[VariantTemplate] = [
    VariantTemplate("lat_lon", {"latitude": "51.0", "longitude": "6.9"}),
]

SEARCH_VARIANTS: List[VariantTemplate] = [
    VariantTemplate("search_zoo", {"latitude": "51.0", "longitude": "6.9", "q": "zoo"}),
    VariantTemplate(
        "search_zoo_continent6",
        {"latitude": "51.0", "longitude": "6.9", "q": "zoo", "continent_id": "6"},
    ),
    VariantTemplate(
        "search_zoo_continent3",
        {"latitude": "51.0", "longitude": "6.9", "q": "zoo", "continent_id": "3"},
    ),
    VariantTemplate(
        "search_zoo_continent3_country109",
        {
            "latitude": "51.0",
            "longitude": "6.9",
            "q": "zoo",
            "continent_id": "3",
            "country_id": "109",
        },
    ),
    VariantTemplate("search_koeln", {"latitude": "51.0", "longitude": "6.9", "q": "K\u00f6ln"}),
    VariantTemplate("search_berlin", {"latitude": "51.0", "longitude": "6.9", "q": "Berlin"}),
    VariantTemplate("search_berl", {"latitude": "51.0", "longitude": "6.9", "q": "Berl"}),
    VariantTemplate("search_ber", {"latitude": "51.0", "longitude": "6.9", "q": "Ber"}),
]

CONTINENT_VARIANTS: List[VariantTemplate] = [
    VariantTemplate("continent_1", {"latitude": "51.0", "longitude": "6.9", "continent_id": "1"}),
    VariantTemplate("continent_2", {"latitude": "51.0", "longitude": "6.9", "continent_id": "2"}),
    VariantTemplate("continent_3", {"latitude": "51.0", "longitude": "6.9", "continent_id": "3"}),
    VariantTemplate("continent_4", {"latitude": "51.0", "longitude": "6.9", "continent_id": "4"}),
    VariantTemplate("continent_5", {"latitude": "51.0", "longitude": "6.9", "continent_id": "5"}),
    VariantTemplate("continent_6", {"latitude": "51.0", "longitude": "6.9", "continent_id": "6"}),
]

CONTINENT_COUNTRY_VARIANTS: List[VariantTemplate] = [
    VariantTemplate(
        "continent2_country16",
        {"latitude": "51.0", "longitude": "6.9", "continent_id": "2", "country_id": "16"},
    ),
    VariantTemplate(
        "continent2_country60",
        {"latitude": "51.0", "longitude": "6.9", "continent_id": "2", "country_id": "60"},
    ),
    VariantTemplate(
        "continent2_country144",
        {"latitude": "51.0", "longitude": "6.9", "continent_id": "2", "country_id": "144"},
    ),
    VariantTemplate(
        "continent2_country158",
        {"latitude": "51.0", "longitude": "6.9", "continent_id": "2", "country_id": "158"},
    ),
    VariantTemplate(
        "continent3_country39",
        {"latitude": "51.0", "longitude": "6.9", "continent_id": "3", "country_id": "39"},
    ),
    VariantTemplate(
        "continent3_country109",
        {"latitude": "51.0", "longitude": "6.9", "continent_id": "3", "country_id": "109"},
    ),
]

ALL_VARIANTS: List[VariantTemplate] = (
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


def build_request_plan(total: int) -> List[VariantTemplate]:
    """Return a shuffled list of query parameter templates."""

    if total <= 0:
        raise ValueError("Total number of requests must be positive")

    plan: List[VariantTemplate] = []
    category_plan = [
        (LAT_LON_VARIANTS, 0.25),
        (SEARCH_VARIANTS, 0.25),
        (CONTINENT_VARIANTS, 0.25),
        (CONTINENT_COUNTRY_VARIANTS, 0.25),
    ]

    for variants, fraction in category_plan:
        count = max(1, int(total * fraction))
        plan.extend(random.choice(variants) for _ in range(count))

    while len(plan) < total:
        plan.append(random.choice(ALL_VARIANTS))

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

    mix_counter = Counter(template.name for template in request_plan)

    print("Request mix:")
    for name, count in sorted(mix_counter.items(), key=lambda item: item[1], reverse=True):
        share = (count / total_requests) * 100
        print(f"  {name}: {count} ({share:.1f}%)")

    limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency)
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout, limits=limits) as client:
        tasks = [
            asyncio.create_task(
                send_request(client, semaphore, template.build_params())
            )
            for template in request_plan
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
