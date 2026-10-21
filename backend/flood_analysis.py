
import ee
import math

PROJECT_ID = "project-43e60592-2ef1-4cf2-bb4"


def validate_analysis_result(
    before_count, after_count, area_km2, tile_url
):
    if before_count <= 0 or after_count <= 0:
        raise RuntimeError("Invalid satellite image count.")

    if not math.isfinite(area_km2) or area_km2 < 0:
        raise RuntimeError("Invalid flood area calculated.")

    if not isinstance(tile_url, str) or not tile_url.strip():
        raise RuntimeError("Flood map URL was not generated.")
# Initial test area near the Koshi River, Nepal.
# Replace with a verified event area after the first test.
def initialize_gee():
    ee.Initialize(project=PROJECT_ID)


def analyze_flood(before_start, before_end,
                  after_start, after_end):

    # Initialize before creating any Earth Engine objects.
    initialize_gee()

    aoi = ee.Geometry.Rectangle([
        86.8, 26.2, 87.2, 26.6
    ])

    collection = (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterBounds(aoi)
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(
            ee.Filter.listContains(
                "transmitterReceiverPolarisation", "VV"
            )
        )
        .select("VV")
    )

    before_collection = collection.filterDate(
        before_start, before_end
    )
    after_collection = collection.filterDate(
        after_start, after_end
    )

    before_count = before_collection.size().getInfo()
    after_count = after_collection.size().getInfo()

    print("Before images:", before_count)
    print("After images:", after_count)

    if before_count == 0 or after_count == 0:
        raise ValueError(
            "No Sentinel-1 images found. Try different dates."
        )

    before = before_collection.median().clip(aoi)
    after = after_collection.median().clip(aoi)

    change = before.subtract(after)

    flood_mask = (
        before.gt(-17)
        .And(after.lt(-22))
        .And(change.gt(3))
        .selfMask()
        .clip(aoi)
    )

    
    area_result = (
        ee.Image.pixelArea()
        .updateMask(flood_mask)
        .reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=aoi,
            scale=10,
            maxPixels=1e9
        )
        .getInfo()
    )

    area_m2 = area_result.get("area")

    if area_m2 is None:
        area_km2 = 0.0
    else:
        area_km2 = round(area_m2 / 1_000_000, 3)




    flood_visual = flood_mask.visualize(
            palette=["ff3030"],
            min=0,
            max=1
        )

    tile_url = flood_visual.getMapId()[
            "tile_fetcher"
        ].url_format

    validate_analysis_result(
    before_count,
    after_count,
    area_km2,
    tile_url
)

    return {
       "before_images": before_count,
        "after_images": after_count,
        "candidate_flood_area_km2": area_km2,
        "flood_detected": area_km2 > 0,
        "flood_tile_url": tile_url,
        "method": "Sentinel-1 VV backscatter change",
        "warning": (
            "Candidate flood extent only; "
            "not ground-validated."
            )
        }
