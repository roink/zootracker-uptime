"""Geometry utilities for distance calculations."""

from typing import Optional

from sqlalchemy import cast, func, or_
from sqlalchemy.orm import Query
from geoalchemy2 import Geography, Geometry

from .. import models


def query_zoos_with_distance(
    query: Query,
    latitude: Optional[float],
    longitude: Optional[float],
    radius_km: Optional[float] = None,
    include_no_coords: bool = False,
) -> list[tuple[models.Zoo, Optional[float]]]:
    """Return zoos paired with distance in kilometers ordered by proximity.

    The ``query`` should return :class:`~app.models.Zoo` rows. Distance is
    calculated using PostGIS when available and falls back to manual
    haversine calculations otherwise. If ``radius_km`` is provided, results
    beyond that radius are excluded. When ``include_no_coords`` is ``True``
    zoos lacking coordinates are included and sorted last.
    """

    if latitude is not None and longitude is not None:
        if query.session.bind.dialect.name != "postgresql":  # pragma: no cover - guardrail
            raise RuntimeError("PostgreSQL/PostGIS is required")
        # keep user point as geometry and cast zoo location when needed
        user_point = func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326)
        geom_loc = cast(models.Zoo.location, Geometry("POINT", 4326))
        q = query
        if not include_no_coords:
            q = q.filter(models.Zoo.location.is_not(None))
        if radius_km is not None:
            user_point_geo = cast(user_point, Geography)
            if include_no_coords:
                q = q.filter(
                    or_(
                        models.Zoo.location.is_(None),
                        func.ST_DWithin(
                            models.Zoo.location, user_point_geo, radius_km * 1000
                        ),
                    )
                )
            else:
                q = q.filter(
                    func.ST_DWithin(
                        models.Zoo.location, user_point_geo, radius_km * 1000
                    )
                )
        order_expr = geom_loc.op("<->")(user_point)
        precise_m = func.ST_DistanceSphere(geom_loc, user_point)
        rows = (
            q.with_entities(models.Zoo, precise_m.label("distance_m"))
            .order_by(order_expr.nulls_last(), models.Zoo.name)
            .all()
        )
        return [(z, d / 1000 if d is not None else None) for z, d in rows]

    # no coordinates supplied – return zoos without distance ordered by name
    return [(z, None) for z in query.order_by(models.Zoo.name).all()]
