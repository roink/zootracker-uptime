"""Geometry utilities for distance calculations."""

from math import radians, cos, sin, asin, sqrt
from typing import Optional

from sqlalchemy import cast, func, or_
from sqlalchemy.orm import Query
from geoalchemy2 import Geography, Geometry

from .. import models

EARTH_RADIUS_KM = 6371.0


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance in kilometers between two points."""
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return EARTH_RADIUS_KM * c


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
        if query.session.bind.dialect.name == "postgresql":
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
        else:
            zoos = query.all()
            results: list[tuple[models.Zoo, Optional[float]]] = []
            for z in zoos:
                if z.latitude is None or z.longitude is None:
                    if include_no_coords:
                        results.append((z, None))
                    continue
                dist = distance_km(
                    float(latitude),
                    float(longitude),
                    float(z.latitude),
                    float(z.longitude),
                )
                if radius_km is None or dist <= radius_km:
                    results.append((z, dist))
            results.sort(
                key=lambda item: (
                    item[1] if item[1] is not None else float("inf"),
                    item[0].name,
                )
            )
            return results

    # no coordinates supplied – return zoos without distance ordered by name
    return [(z, None) for z in query.order_by(models.Zoo.name).all()]
