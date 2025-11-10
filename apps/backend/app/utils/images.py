"""Utilities for working with image variants."""

from __future__ import annotations

from collections.abc import Iterable

from .. import models, schemas


def build_unique_variants(
    variants: Iterable[models.ImageVariant],
) -> list[schemas.ImageVariant]:
    """Return deduplicated schema variants sorted by width."""
    unique: dict[int, schemas.ImageVariant] = {}
    for variant in sorted(variants, key=lambda v: v.width):
        width = variant.width
        if width in unique:
            continue
        unique[width] = schemas.ImageVariant(
            width=variant.width,
            height=variant.height,
            thumb_url=variant.thumb_url,
        )
    return list(unique.values())
