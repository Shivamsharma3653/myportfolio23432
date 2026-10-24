from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

import requests
from pyproj import Transformer
from shapely.geometry import LineString, Point, Polygon, mapping, shape
from shapely.ops import transform


OVERPASS_URL = "https://overpass-api.de/api/interpreter"
ROAD_CLASSES = {
    "motorway", "trunk", "primary", "secondary", "tertiary",
    "unclassified", "residential", "living_street", "service",
}
PLACE_CLASSES = {
    "city", "town", "village", "hamlet", "suburb",
    "neighbourhood", "isolated_dwelling",
}
MAX_OVERLAY_FEATURES = 1500


def _transformer(bounds: dict[str, float]) -> tuple[Transformer, Transformer]:
    lon0 = (bounds["west"] + bounds["east"]) / 2
    lat0 = (bounds["south"] + bounds["north"]) / 2
    local_crs = (
        f"+proj=aeqd +lat_0={lat0} +lon_0={lon0} "
        "+datum=WGS84 +units=m +no_defs"
    )
    return (
        Transformer.from_crs("EPSG:4326", local_crs, always_xy=True),
        Transformer.from_crs(local_crs, "EPSG:4326", always_xy=True),
    )


@lru_cache(maxsize=8)
def _fetch_osm(bounds_key: tuple[float, float, float, float]) -> dict[str, Any]:
    west, south, east, north = bounds_key
    bbox = f"{south},{west},{north},{east}"
    query = f"""[out:json][timeout:50];
(
  nwr["place"~"^(city|town|village|hamlet|suburb|neighbourhood|isolated_dwelling)$"]({bbox});
  way["landuse"~"^(residential|allotments)$"]({bbox});
  way["highway"~"^(motorway|trunk|primary|secondary|tertiary|unclassified|residential|living_street|service)$"]({bbox});
);
out center geom;"""
    response = requests.post(
        OVERPASS_URL,
        data={"data": query},
        headers={"User-Agent": "JaldrishtiFloodMapping/1.0 (local prototype)"},
        timeout=(10, 70),
    )
    response.raise_for_status()
    return response.json()


def _element_geometry(element: dict[str, Any]):
    element_type = element.get("type")
    if element_type == "node":
        if "lon" in element and "lat" in element:
            return Point(float(element["lon"]), float(element["lat"]))
        return None

    coordinates = [
        (float(point["lon"]), float(point["lat"]))
        for point in element.get("geometry", [])
        if "lon" in point and "lat" in point
    ]
    tags = element.get("tags") or {}
    if len(coordinates) >= 4 and coordinates[0] == coordinates[-1]:
        polygon = Polygon(coordinates)
        if polygon.is_valid and polygon.area > 0:
            return polygon
        return polygon.buffer(0)
    if len(coordinates) >= 2:
        return LineString(coordinates)

    center = element.get("center")
    if center and "lon" in center and "lat" in center:
        return Point(float(center["lon"]), float(center["lat"]))
    return None


def _geojson_feature(geometry, properties: dict[str, Any]) -> dict[str, Any]:
    return {"type": "Feature", "geometry": mapping(geometry), "properties": properties}


def calculate_osm_impacts(
    bounds: dict[str, float],
    flood_geometry_geojson: dict[str, Any] | None,
) -> dict[str, Any]:
    """Intersect OSM place and road features with the simplified candidate extent."""
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if not flood_geometry_geojson:
        return {
            "affected_settlements": 0,
            "affected_roads_km": 0.0,
            "settlements_geojson": {"type": "FeatureCollection", "features": []},
            "roads_geojson": {"type": "FeatureCollection", "features": []},
            "osm_data_timestamp": timestamp,
            "osm_warning": None,
        }

    try:
        flood_wgs84 = shape(flood_geometry_geojson)
        to_local, to_wgs84 = _transformer(bounds)
        flood_local = transform(to_local.transform, flood_wgs84)
        if not flood_local.is_valid:
            flood_local = flood_local.buffer(0)
        if flood_local.is_empty:
            raise ValueError("Flood geometry was empty after simplification.")

        bounds_key = tuple(
            round(bounds[key], 6) for key in ("west", "south", "east", "north")
        )
        elements = _fetch_osm(bounds_key).get("elements", [])
        seen: set[tuple[str, int]] = set()
        places: dict[str, dict[str, Any]] = {}
        road_features: list[dict[str, Any]] = []
        road_length_m = 0.0

        for element in elements:
            key = (str(element.get("type")), int(element.get("id", -1)))
            if key in seen:
                continue
            seen.add(key)
            tags = element.get("tags") or {}
            geometry = _element_geometry(element)
            if geometry is None:
                continue
            local_geometry = transform(to_local.transform, geometry)
            if not local_geometry.is_valid:
                local_geometry = local_geometry.buffer(0)
            if local_geometry.is_empty or not local_geometry.intersects(flood_local):
                continue

            place = tags.get("place")
            landuse = tags.get("landuse")
            highway = tags.get("highway")
            if place in PLACE_CLASSES or landuse in {"residential", "allotments"}:
                clipped = local_geometry.intersection(flood_local)
                if clipped.is_empty:
                    continue
                name = str(tags.get("name") or "").strip()
                place_key = name.casefold() if name else f"{key[0]}:{key[1]}"
                places.setdefault(
                    place_key,
                    {
                        "geometry": transform(to_wgs84.transform, clipped.simplify(5)),
                        "properties": {
                            "name": name or "Unnamed OSM settlement",
                            "place": place or landuse,
                            "candidate_overlap_km2": round(clipped.area / 1_000_000, 4) if clipped.area else None,
                            "osm_type": key[0],
                            "osm_id": key[1],
                        },
                    },
                )
            elif highway in ROAD_CLASSES and key[0] == "way":
                clipped = local_geometry.intersection(flood_local)
                length_m = clipped.length
                if length_m <= 0:
                    continue
                road_length_m += length_m
                if len(road_features) < MAX_OVERLAY_FEATURES:
                    road_wgs84 = transform(to_wgs84.transform, clipped.simplify(5))
                    road_features.append(
                        _geojson_feature(
                            road_wgs84,
                            {
                                "name": tags.get("name", "Unnamed OSM road"),
                                "highway": highway,
                                "osm_id": key[1],
                            },
                        )
                    )

        settlement_features = [
            _geojson_feature(item["geometry"], item["properties"])
            for item in places.values()
        ]
        warnings = []
        if len(road_features) >= MAX_OVERLAY_FEATURES:
            warnings.append("Overlay display is capped at 1,500 road features; reported counts and road length use all returned OSM features.")
        if not settlement_features:
            warnings.append("No mapped OSM settlement or residential-area features intersected this candidate extent; an empty map result does not mean the area has no residents.")
        return {
            "affected_settlements": len(settlement_features),
            "affected_roads_km": round(road_length_m / 1000, 3),
            "settlements_geojson": {
                "type": "FeatureCollection",
                "features": settlement_features[:MAX_OVERLAY_FEATURES],
            },
            "roads_geojson": {
                "type": "FeatureCollection",
                "features": road_features,
            },
            "osm_data_timestamp": timestamp,
            "osm_warning": " ".join(warnings) or None,
        }
    except Exception as exc:
        return {
            "affected_settlements": None,
            "affected_roads_km": None,
            "settlements_geojson": None,
            "roads_geojson": None,
            "osm_data_timestamp": timestamp,
            "osm_warning": (
                "OpenStreetMap impact layers could not be calculated: "
                f"{type(exc).__name__}: {exc}"
            ),
        }
