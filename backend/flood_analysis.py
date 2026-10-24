from __future__ import annotations

from typing import Any
import math

import ee

from backend.impact_analysis import calculate_osm_impacts


PROJECT_ID = "annular-mercury-512512-v1"
DEFAULT_BOUNDS = {"west": 86.8, "south": 26.2, "east": 87.2, "north": 26.6}
REGIONS = {
    "koshi": {
        "label": "Koshi Basin · Eastern Terai",
        "bounds": DEFAULT_BOUNDS.copy(),
    },
    "karnali": {
        "label": "Karnali Floodplain · Western Terai",
        "bounds": {"west": 80.95, "south": 28.30, "east": 81.30, "north": 28.70},
    },
    "rautahat": {
        "label": "Rautahat · Central Terai",
        "bounds": {"west": 84.8, "south": 26.75, "east": 85.35, "north": 27.25},
    },
}
MAX_BOUNDS_SPAN_DEGREES = 2.0
WORLDPOP_DATASET = "WorldPop/GP/100m/pop"


def validate_bounds(bounds: Any = None) -> dict[str, float]:
    if bounds is None:
        return DEFAULT_BOUNDS.copy()
    if not isinstance(bounds, dict):
        raise ValueError("bounds must be an object with west, south, east, and north.")
    try:
        result = {key: float(bounds[key]) for key in ("west", "south", "east", "north")}
    except (KeyError, TypeError, ValueError):
        raise ValueError("Provide numeric west, south, east, and north coordinates.") from None
    west, south, east, north = (
        result["west"], result["south"], result["east"], result["north"]
    )
    if not (-180 <= west < east <= 180):
        raise ValueError("Longitude bounds must satisfy -180 ≤ west < east ≤ 180.")
    if not (-90 <= south < north <= 90):
        raise ValueError("Latitude bounds must satisfy -90 ≤ south < north ≤ 90.")
    if east - west > MAX_BOUNDS_SPAN_DEGREES or north - south > MAX_BOUNDS_SPAN_DEGREES:
        raise ValueError("For this prototype, each custom region dimension must be at most 2 degrees.")
    return result


def validate_analysis_result(before_count, after_count, area_km2, tile_url):
    if before_count <= 0 or after_count <= 0:
        raise RuntimeError("Invalid satellite image count.")
    if not math.isfinite(area_km2) or area_km2 < 0:
        raise RuntimeError("Invalid flood area calculated.")
    if not isinstance(tile_url, str) or not tile_url.strip():
        raise RuntimeError("Flood map URL was not generated.")


def _area_km2(mask, aoi, scale: int = 10) -> float:
    values = (
        ee.Image.pixelArea()
        .updateMask(mask)
        .reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=aoi,
            scale=scale,
            maxPixels=1e9,
            tileScale=4,
        )
        .getInfo()
    )
    return round(float(values.get("area") or 0) / 1_000_000, 3)


def _population_exposure(flood_mask, aoi) -> dict[str, Any]:
    collection = ee.ImageCollection(WORLDPOP_DATASET).filterBounds(aoi)
    years = collection.aggregate_array("year").distinct().sort().getInfo()
    years = [int(year) for year in years if year is not None]
    if not years:
        return {
            "population_exposed_estimate": None,
            "population_dataset_year": None,
            "population_warning": "No WorldPop population grid intersects this region.",
        }

    year = max(years)
    year_collection = collection.filter(ee.Filter.eq("year", year))
    population_projection = (
        ee.Image(year_collection.first()).select("population").projection()
    )
    population = (
        year_collection.mosaic()
        .select("population")
        .setDefaultProjection(population_projection)
    )
    flooded_fraction = (
        flood_mask.unmask(0)
        .rename("flood")
        .toFloat()
        .reduceResolution(reducer=ee.Reducer.mean(), maxPixels=1024)
        .reproject(crs=population_projection, scale=100)
    )
    estimate = (
        population.multiply(flooded_fraction)
        .rename("population")
        .reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=aoi,
            scale=100,
            crs=population_projection,
            maxPixels=1e9,
            tileScale=4,
        )
        .get("population")
        .getInfo()
    )
    return {
        "population_exposed_estimate": round(float(estimate or 0)),
        "population_dataset_year": year,
        "population_warning": (
            f"WorldPop {year} estimate. Flooded share of each ~100 m cell is "
            "assumed to contain population uniformly."
        ),
    }


def _optical_preprocess_s2(image):
    scl = image.select("SCL")
    clear = (
        scl.gt(1)
        .And(scl.neq(3))
        .And(scl.neq(8))
        .And(scl.neq(9))
        .And(scl.neq(10))
        .And(scl.neq(11))
    )
    return image.updateMask(clear)


def _optical_preprocess_landsat(image):
    qa = image.select("QA_PIXEL")
    clear = (
        qa.bitwiseAnd(1 << 1).eq(0)
        .And(qa.bitwiseAnd(1 << 2).eq(0))
        .And(qa.bitwiseAnd(1 << 3).eq(0))
        .And(qa.bitwiseAnd(1 << 4).eq(0))
        .And(qa.bitwiseAnd(1 << 5).eq(0))
    )
    scaled = image.select(["SR_B3", "SR_B6"]).multiply(0.0000275).add(-0.2)
    return scaled.updateMask(clear)


def _optical_cross_check(
    sensor: str,
    aoi,
    flood_mask,
    before_start: str,
    before_end: str,
    after_start: str,
    after_end: str,
) -> dict[str, Any] | None:
    if sensor == "none":
        return None
    if sensor == "sentinel2":
        collection = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(aoi)
            .filter(ee.Filter.lte("CLOUDY_PIXEL_PERCENTAGE", 80))
            .map(_optical_preprocess_s2)
        )
        sensor_name = "Sentinel-2"
        green_band, swir_band = "B3", "B11"
    elif sensor == "landsat89":
        collection = (
            ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
            .merge(ee.ImageCollection("LANDSAT/LC09/C02/T1_L2"))
            .filterBounds(aoi)
            .filter(ee.Filter.lte("CLOUD_COVER_LAND", 80))
            .map(_optical_preprocess_landsat)
        )
        sensor_name = "Landsat 8/9"
        green_band, swir_band = "SR_B3", "SR_B6"
    else:
        raise ValueError("optical_sensor must be none, sentinel2, or landsat89.")

    before_collection = collection.filterDate(before_start, before_end)
    after_collection = collection.filterDate(after_start, after_end)
    before_count = int(before_collection.size().getInfo())
    after_count = int(after_collection.size().getInfo())
    if before_count == 0 or after_count == 0:
        return {
            "sensor": sensor_name,
            "available": False,
            "before_images": before_count,
            "after_images": after_count,
            "warning": f"Not enough {sensor_name} imagery in both selected date windows.",
        }

    before = before_collection.median()
    after = after_collection.median()
    before_water = before.normalizedDifference([green_band, swir_band]).gt(0.25)
    after_water = after.normalizedDifference([green_band, swir_band]).gt(0.25)
    optical_new_water = after_water.And(before_water.Not()).selfMask()
    optical_projection = after.select(green_band).projection()
    sar_coarse = (
        flood_mask.unmask(0)
        .rename("candidate")
        .reduceResolution(reducer=ee.Reducer.max(), maxPixels=1024)
        .reproject(crs=optical_projection)
        .eq(1)
    )
    agreement_mask = optical_new_water.And(sar_coarse)
    agreement_km2 = _area_km2(agreement_mask, aoi, scale=20)
    optical_water_km2 = _area_km2(optical_new_water, aoi, scale=20)
    sar_area_on_optical_grid = _area_km2(sar_coarse, aoi, scale=20)
    agreement_pct = (
        round(100 * agreement_km2 / sar_area_on_optical_grid, 1)
        if sar_area_on_optical_grid
        else None
    )
    return {
        "sensor": sensor_name,
        "available": True,
        "before_images": before_count,
        "after_images": after_count,
        "optical_new_water_km2": optical_water_km2,
        "overlap_with_sar_km2": agreement_km2,
        "sar_candidate_overlap_percent": agreement_pct,
        "warning": (
            "Cross-sensor optical corroboration only; it is not field ground truth."
        ),
    }


def _ground_validation(geojson: Any, aoi, flood_mask, projection) -> dict[str, Any]:
    if not isinstance(geojson, dict) or geojson.get("type") != "FeatureCollection":
        raise ValueError("Ground reference must be a GeoJSON FeatureCollection of labeled points.")
    features = geojson.get("features")
    if not isinstance(features, list) or not features or len(features) > 5000:
        raise ValueError("Provide between 1 and 5,000 ground-observation points.")

    reference_features = []
    for feature in features:
        if not isinstance(feature, dict):
            raise ValueError("Each ground reference must be a GeoJSON point feature.")
        geometry = feature.get("geometry") or {}
        coordinates = geometry.get("coordinates") or []
        properties = feature.get("properties") or {}
        if geometry.get("type") != "Point" or len(coordinates) < 2:
            raise ValueError("Ground reference GeoJSON must contain Point geometries.")
        lon, lat = float(coordinates[0]), float(coordinates[1])
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise ValueError("Ground reference coordinates must use WGS84 longitude/latitude.")
        label = properties.get("flooded")
        if isinstance(label, str):
            label = label.strip().lower()
            if label in {"1", "true", "yes", "flood"}:
                label = 1
            elif label in {"0", "false", "no", "dry"}:
                label = 0
        if label not in (0, 1, False, True):
            raise ValueError("Every point needs a 'flooded' property with value 1 or 0.")
        reference_features.append(
            ee.Feature(ee.Geometry.Point([lon, lat]), {"flooded": int(label)})
        )

    references = ee.FeatureCollection(reference_features).filterBounds(aoi)
    sampled = (
        flood_mask.unmask(0)
        .rename("predicted")
        .sampleRegions(
            collection=references,
            properties=["flooded"],
            scale=10,
            projection=projection,
            geometries=False,
        )
    )
    matrix = sampled.errorMatrix("flooded", "predicted", [0, 1])
    raw_matrix = matrix.array().getInfo()
    total = sum(sum(int(value) for value in row) for row in raw_matrix)
    if not total:
        raise ValueError("No reference points fall inside this analysis region.")

    tn, fp = map(int, raw_matrix[0])
    fn, tp = map(int, raw_matrix[1])
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    kappa_value = float(matrix.kappa().getInfo())
    kappa = round(kappa_value, 3) if math.isfinite(kappa_value) else None
    return {
        "reference_source": "User-supplied field observation points",
        "sample_points": total,
        "flooded_observations": tp + fn,
        "dry_observations": tn + fp,
        "confusion_matrix": {"true_negative": tn, "false_positive": fp, "false_negative": fn, "true_positive": tp},
        "accuracy_percent": round(100 * (tn + tp) / total, 1),
        "precision_percent": round(100 * precision, 1),
        "recall_percent": round(100 * recall, 1),
        "f1_percent": round(100 * f1, 1),
        "kappa": kappa,
        "warning": "Validation applies only to submitted sample points and does not certify the full map.",
    }


def analyze_flood(
    before_start: str,
    before_end: str,
    after_start: str,
    after_end: str,
    bounds: Any = None,
    optical_sensor: str = "none",
    ground_truth_geojson: Any = None,
) -> dict[str, Any]:
    ee.Initialize(project=PROJECT_ID)
    bounds = validate_bounds(bounds)
    aoi = ee.Geometry.Rectangle(
        [bounds["west"], bounds["south"], bounds["east"], bounds["north"]],
        geodesic=False,
    )

    collection = (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterBounds(aoi)
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .select("VV")
    )
    before_collection = collection.filterDate(before_start, before_end)
    after_collection = collection.filterDate(after_start, after_end)
    before_count = int(before_collection.size().getInfo())
    after_count = int(after_collection.size().getInfo())
    if before_count == 0 or after_count == 0:
        raise ValueError("No Sentinel-1 images found in one of the selected date windows.")

    projection = ee.Image(before_collection.first()).select("VV").projection()
    before = before_collection.median().setDefaultProjection(projection).clip(aoi)
    after = after_collection.median().setDefaultProjection(projection).clip(aoi)
    before_filtered = before.focalMean(30, "circle", "meters")
    after_filtered = after.focalMean(30, "circle", "meters")
    change = before_filtered.subtract(after_filtered)

    permanent_water = (
        ee.Image("JRC/GSW1_4/GlobalSurfaceWater")
        .select("occurrence")
        .gte(90)
        .unmask(0)
    )
    low_slope = ee.Terrain.slope(ee.Image("USGS/SRTMGL1_003")).lt(5)
    flood_mask = (
        before_filtered.gt(-17)
        .And(after_filtered.lt(-22))
        .And(change.gt(3))
        .And(permanent_water.Not())
        .And(low_slope)
        .selfMask()
        .clip(aoi)
        .reproject(crs=projection)
    )
    area_km2 = _area_km2(flood_mask, aoi)
    flood_visual = flood_mask.visualize(palette=["ff3030"], min=0, max=1)
    before_visual = before.visualize(min=-25, max=0, palette=["101820", "f2f7fa"])
    after_visual = after.visualize(min=-25, max=0, palette=["101820", "f2f7fa"])
    tile_url = flood_visual.getMapId()["tile_fetcher"].url_format
    before_tile_url = before_visual.getMapId()["tile_fetcher"].url_format
    after_tile_url = after_visual.getMapId()["tile_fetcher"].url_format
    validate_analysis_result(before_count, after_count, area_km2, tile_url)

    population = _population_exposure(flood_mask, aoi)
    optical = _optical_cross_check(
        optical_sensor,
        aoi,
        flood_mask,
        before_start,
        before_end,
        after_start,
        after_end,
    )

    if area_km2:
        vectors = (
            flood_mask.rename("flood")
            .reduceToVectors(
                reducer=ee.Reducer.countEvery(),
                geometry=aoi,
                scale=30,
                geometryType="polygon",
                eightConnected=True,
                labelProperty="class",
                maxPixels=1e9,
                tileScale=4,
            )
        )
        flood_geometry = vectors.geometry().simplify(30).getInfo()
        osm = calculate_osm_impacts(bounds, flood_geometry)
    else:
        osm = calculate_osm_impacts(bounds, None)

    field_validation = (
        _ground_validation(ground_truth_geojson, aoi, flood_mask, projection)
        if ground_truth_geojson is not None
        else None
    )

    warning_parts = ["Candidate flood extent only; not ground-validated."]
    if population["population_warning"]:
        warning_parts.append(population["population_warning"])
    if osm["osm_warning"]:
        warning_parts.append(osm["osm_warning"])
    if optical and optical.get("warning"):
        warning_parts.append(optical["warning"])

    return {
        "before_images": before_count,
        "after_images": after_count,
        "candidate_flood_area_km2": area_km2,
        "flood_detected": area_km2 > 0,
        "flood_tile_url": tile_url,
        "before_tile_url": before_tile_url,
        "after_tile_url": after_tile_url,
        "method": "Sentinel-1 VV change with speckle smoothing, permanent-water and slope filters",
        "warning": " ".join(warning_parts),
        "analysis_bounds": bounds,
        **population,
        **osm,
        "optical_validation": optical,
        "field_validation": field_validation,
        "osm_attribution": "© OpenStreetMap contributors, ODbL 1.0",
    }
