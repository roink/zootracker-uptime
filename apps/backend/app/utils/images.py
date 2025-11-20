"""Utilities for working with image variants."""

from __future__ import annotations

from collections.abc import Iterable

from .. import models, schemas


def build_unique_variants(
    variants: Iterable[models.ImageVariant],
) -> list[models.ImageVariant]:
    """Return deduplicated variants sorted by width."""
    unique: dict[int, models.ImageVariant] = {}
    for variant in sorted(variants, key=lambda v: v.width):
        width = variant.width
        if width in unique:
            continue
        unique[width] = variant
    return list(unique.values())
