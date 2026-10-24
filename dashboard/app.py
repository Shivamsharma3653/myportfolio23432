from __future__ import annotations

import csv
import io
import json
import os
from datetime import date, datetime, timedelta, timezone

import folium
import pandas as pd
import requests
import streamlit as st
from streamlit_folium import st_folium


st.set_page_config(
    page_title="JALDRISHTI | Rapid Flood Mapping",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_URL = os.getenv("JALDRISHTI_API_URL", "http://127.0.0.1:5000").rstrip("/")
ANALYZE_URL = f"{API_URL}/analyze"
DEFAULT_BOUNDS = {"west": 86.8, "south": 26.2, "east": 87.2, "north": 26.6}
REGION_PRESETS = {
    "koshi": {
        "label": "Koshi Basin · Eastern Terai",
        "bounds": DEFAULT_BOUNDS,
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


st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
:root{--bg:#0a1420;--panel:#111f2e;--line:#26394b;--text:#e8f1f7;--muted:#94a8ba;--cyan:#25d4e5}
html,body,[class*="css"]{font-family:'DM Sans',sans-serif}
.stApp{background:radial-gradient(ellipse at 78% 0%,#142b3d 0,var(--bg) 48%);color:var(--text)}
header[data-testid="stHeader"]{background:transparent}
section[data-testid="stSidebar"]{background:linear-gradient(180deg,#101e2c,#0c1722);border-right:1px solid var(--line)}
section[data-testid="stSidebar"]>div{padding-top:1.2rem}
.block-container{padding:1.6rem 2rem 3rem;max-width:1600px}
.brand{display:flex;align-items:center;gap:11px;margin:0 0 26px}
.brand-mark{width:42px;height:42px;border-radius:13px;background:linear-gradient(140deg,#26d5e5,#167acb);display:grid;place-items:center;color:#061520;font-size:24px;font-weight:800}
.brand-name{font:800 19px Manrope,sans-serif;letter-spacing:.08em;color:#f4f8fb}
.brand-sub{color:#55cfdd;font-size:9px;letter-spacing:.2em;font-weight:700}
.eyebrow{color:#55cddb;text-transform:uppercase;letter-spacing:.15em;font-size:10px;font-weight:700}
.title{font:800 clamp(25px,3vw,36px) Manrope,sans-serif;letter-spacing:-.045em;margin:5px 0}
.sub{color:#a2b4c3;font-size:13px;line-height:1.55;max-width:800px}
.section-head{margin:25px 0 11px}
.section-head h3{font:700 17px Manrope,sans-serif;margin:0;color:#f1f7fb}
.section-head p{color:#879caf;font-size:11px;margin:4px 0 0}
.metric-card{background:linear-gradient(145deg,rgba(23,39,55,.96),rgba(16,30,44,.96));border:1px solid var(--line);border-radius:14px;padding:17px 18px;min-height:115px}
.metric-label{color:#96aabd;font-size:11px;font-weight:600}
.metric-value{color:#f1f7fb;font:700 24px Manrope,sans-serif;letter-spacing:-.04em;margin:9px 0 4px}
.metric-note{color:#7f95a8;font-size:10px;line-height:1.4}
.status{display:inline-block;border:1px solid #3f614f;background:#173329;color:#98e0bd;padding:7px 11px;border-radius:20px;font-size:10px;font-weight:700;letter-spacing:.04em}
.note{border:1px solid #4b4931;background:#29291e;border-radius:11px;padding:12px 14px;color:#d6d2ab;font-size:11px;line-height:1.55}
.muted-box{border:1px solid #2a4052;background:#111f2e;border-radius:12px;padding:16px;color:#a8bac8;font-size:12px;line-height:1.6}
.stButton>button,.stDownloadButton>button{border-radius:9px;border:1px solid #2c5068;background:#142c3d;color:#dff7fa;font-weight:600}
.stButton>button[kind="primary"]{background:linear-gradient(90deg,#1685e9,#14b9d1);border:0;color:white}
div[data-baseweb="select"]>div,div[data-baseweb="input"]>div{background:#152638;border-color:#2b4053;border-radius:8px}
label,div[data-testid="stWidgetLabel"] p{color:#d0dce5!important;font-size:12px!important}
@media(max-width:850px){.block-container{padding:1.1rem .85rem 2rem}.title{font-size:27px}}
</style>
""",
    unsafe_allow_html=True,
)


def make_payload(
    before_range,
    after_range,
    bounds: dict[str, float],
    region_name: str,
    optical_sensor: str,
    ground_truth_geojson: dict | None,
    region_key: str,
) -> dict:
    if (
        not isinstance(before_range, (tuple, list))
        or not isinstance(after_range, (tuple, list))
        or len(before_range) != 2
        or len(after_range) != 2
    ):
        raise ValueError("Select a start and end date for each period.")
    if before_range[0] >= before_range[1] or after_range[0] >= after_range[1]:
        raise ValueError("Each date range must have a start date before its end date.")
    if before_range[1] >= after_range[0]:
        raise ValueError("The baseline period must finish before the event period begins.")
    west, south, east, north = (
        bounds["west"], bounds["south"], bounds["east"], bounds["north"]
    )
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError("Region coordinates must be valid west/south/east/north bounds.")
    if east - west > 2 or north - south > 2:
        raise ValueError("Each custom region dimension must be at most 2 degrees.")
    payload = {
        "before_start": before_range[0].isoformat(),
        "before_end": (before_range[1] + timedelta(days=1)).isoformat(),
        "after_start": after_range[0].isoformat(),
        "after_end": (after_range[1] + timedelta(days=1)).isoformat(),
        "region_name": region_name.strip() or "Custom analysis region",
        "region": region_key,
        "bounds": bounds,
        "optical_sensor": optical_sensor,
    }
    if ground_truth_geojson is not None:
        payload["ground_truth_geojson"] = ground_truth_geojson
    return payload


def validate_field_points(document: dict) -> tuple[dict | None, str | None]:
    if not isinstance(document, dict) or document.get("type") != "FeatureCollection":
        return None, "File must be a GeoJSON FeatureCollection."
    features = document.get("features")
    if not isinstance(features, list) or not features or len(features) > 5000:
        return None, "Provide between 1 and 5,000 field-observation points."
    observed = set()
    for feature in features:
        geometry = (feature or {}).get("geometry") or {}
        properties = (feature or {}).get("properties") or {}
        coordinates = geometry.get("coordinates") or []
        if geometry.get("type") != "Point" or len(coordinates) < 2:
            return None, "Each observation must be a GeoJSON Point."
        try:
            lon, lat = float(coordinates[0]), float(coordinates[1])
        except (TypeError, ValueError):
            return None, "Point coordinates must be numeric WGS84 longitude/latitude."
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            return None, "Point coordinates are outside WGS84 longitude/latitude bounds."
        label = properties.get("flooded")
        if isinstance(label, str):
            label = label.strip().lower()
            label = 1 if label in {"1", "true", "yes", "flood"} else 0 if label in {"0", "false", "no", "dry"} else label
        if label not in (0, 1, False, True):
            return None, "Every point needs a 'flooded' property with value 1 or 0."
        observed.add(int(label))
    if observed != {0, 1}:
        return None, "Include both flooded=1 and dry=0 field observations to calculate validation scores."
    return document, None


def _center(bounds: dict[str, float]) -> list[float]:
    return [(bounds["south"] + bounds["north"]) / 2, (bounds["west"] + bounds["east"]) / 2]


def build_flood_map(
    tile_url: str,
    bounds: dict[str, float],
    roads_geojson: dict | None = None,
    settlements_geojson: dict | None = None,
) -> folium.Map:
    map_view = folium.Map(location=_center(bounds), zoom_start=9, tiles=None, control_scale=True)
    folium.TileLayer(
        tiles="OpenStreetMap",
        name="OpenStreetMap",
        overlay=False,
        control=True,
    ).add_to(map_view)
    folium.TileLayer(
        tiles=tile_url,
        name="Sentinel-1 candidate flood extent · GEE",
        attr="Google Earth Engine",
        overlay=True,
        control=True,
        opacity=0.78,
        show=True,
    ).add_to(map_view)
    if roads_geojson:
        folium.GeoJson(
            roads_geojson,
            name="Exposed OSM roads",
            style_function=lambda _feature: {"color": "#36d8e8", "weight": 3},
            tooltip=folium.GeoJsonTooltip(fields=["name", "highway"]),
        ).add_to(map_view)
    if settlements_geojson:
        folium.GeoJson(
            settlements_geojson,
            name="Affected OSM settlements",
            style_function=lambda _feature: {
                "color": "#ffc857",
                "weight": 2,
                "fillColor": "#ffc857",
                "fillOpacity": 0.25,
            },
            marker=folium.CircleMarker(radius=5, color="#ffc857", fill=True, fill_opacity=0.9),
            tooltip=folium.GeoJsonTooltip(fields=["name", "place"]),
        ).add_to(map_view)
    folium.Rectangle(
        bounds=[[bounds["south"], bounds["west"]], [bounds["north"], bounds["east"]]],
        color="#f5bd61",
        weight=2,
        fill=False,
        tooltip="Analysis boundary",
        name="Analysis boundary",
    ).add_to(map_view)
    folium.LayerControl(collapsed=False, position="topright").add_to(map_view)
    legend = """<div style="position:fixed;bottom:28px;left:18px;z-index:9999;background:#101f2dde;
    color:#e7f0f6;padding:9px 12px;border:1px solid #496176;border-radius:8px;font:12px sans-serif">
    <span style="color:#ff4b4b;font-size:18px">■</span> Candidate flood pixels &nbsp;
    <span style="color:#36d8e8;font-size:18px">━</span> Exposed roads &nbsp;
    <span style="color:#ffc857;font-size:18px">●</span> Affected settlements</div>"""
    map_view.get_root().html.add_child(folium.Element(legend))
    map_view.fit_bounds(
        [[bounds["south"], bounds["west"]], [bounds["north"], bounds["east"]]]
    )
    return map_view


def build_sar_preview(tile_url: str, bounds: dict[str, float], layer_name: str) -> folium.Map:
    map_view = folium.Map(location=_center(bounds), zoom_start=9, tiles="OpenStreetMap", control_scale=True)
    folium.TileLayer(
        tiles=tile_url,
        name=layer_name,
        attr="Google Earth Engine",
        overlay=True,
        control=True,
        opacity=0.85,
        show=True,
    ).add_to(map_view)
    folium.LayerControl(collapsed=True).add_to(map_view)
    map_view.fit_bounds(
        [[bounds["south"], bounds["west"]], [bounds["north"], bounds["east"]]]
    )
    return map_view


def scalar_csv(parameters: dict, result: dict) -> bytes:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["field", "value"])
    writer.writeheader()
    for section, values in (("request", parameters), ("backend_result", result)):
        for key, value in values.items():
            if not isinstance(value, (dict, list)):
                writer.writerow({"field": f"{section}.{key}", "value": value})
    return output.getvalue().encode("utf-8")


today = date.today()
with st.sidebar:
    st.markdown(
        '<div class="brand"><div class="brand-mark">✳</div><div><div class="brand-name">JALDRISHTI</div><div class="brand-sub">RAPID FLOOD MAPPING</div></div></div>',
        unsafe_allow_html=True,
    )
    st.markdown("**ANALYSIS SETTINGS**")
    selected_region = st.selectbox(
        "Region preset",
        options=["koshi", "karnali", "rautahat", "custom"],
        format_func=lambda key: REGION_PRESETS[key]["label"] if key in REGION_PRESETS else "Custom bounds",
    )
    selected_bounds = REGION_PRESETS.get(selected_region, {}).get("bounds", DEFAULT_BOUNDS)
    region_default_name = REGION_PRESETS.get(selected_region, {}).get("label", "Custom analysis region")
    region_name = st.text_input("Analysis region name", region_default_name, key=f"region-name-{selected_region}")
    st.caption("Sentinel-1 SAR is the primary detector. Choose an optional optical cross-check.")
    with st.expander("Region bounds"):
        west = st.number_input("West longitude", value=selected_bounds["west"], min_value=-180.0, max_value=180.0, step=0.01, format="%.4f", key=f"west-{selected_region}")
        south = st.number_input("South latitude", value=selected_bounds["south"], min_value=-90.0, max_value=90.0, step=0.01, format="%.4f", key=f"south-{selected_region}")
        east = st.number_input("East longitude", value=selected_bounds["east"], min_value=-180.0, max_value=180.0, step=0.01, format="%.4f", key=f"east-{selected_region}")
        north = st.number_input("North latitude", value=selected_bounds["north"], min_value=-90.0, max_value=90.0, step=0.01, format="%.4f", key=f"north-{selected_region}")
        st.caption("You can edit any preset bounds. Prototype limit: each region dimension must be 2° or smaller.")
    bounds = {"west": west, "south": south, "east": east, "north": north}

    today = date.today()
    before_range = st.date_input(
        "Pre-flood baseline",
        value=(today - timedelta(days=46), today - timedelta(days=27)),
        max_value=today,
    )
    after_range = st.date_input(
        "Post-flood event",
        value=(today - timedelta(days=19), today - timedelta(days=7)),
        max_value=today,
    )
    optical_label = st.selectbox(
        "Optional optical validation",
        ["None", "Sentinel-2", "Landsat 8/9"],
        help="Optical agreement can corroborate water change, but it is not field ground truth.",
    )
    optical_sensor = {
        "None": "none",
        "Sentinel-2": "sentinel2",
        "Landsat 8/9": "landsat89",
    }[optical_label]

    with st.expander("Field reference validation"):
        st.caption(
            "Upload a GeoJSON FeatureCollection of GPS field points for the same event. "
            "Each point needs flooded=1 (observed flooded) or flooded=0 (observed dry)."
        )
        ground_truth_file = st.file_uploader(
            "Field observations (.geojson)",
            type=["geojson", "json"],
            max_upload_size=5,
        )
        ground_truth_geojson = None
        field_file_error = None
        if ground_truth_file is not None:
            try:
                document = json.loads(ground_truth_file.getvalue().decode("utf-8"))
                ground_truth_geojson, field_file_error = validate_field_points(document)
            except (UnicodeDecodeError, json.JSONDecodeError):
                field_file_error = "The uploaded file is not valid UTF-8 GeoJSON."
            if field_file_error:
                st.error(field_file_error)
            else:
                st.caption(f"{len(ground_truth_geojson['features'])} labeled points ready.")
                confirm_field_data = st.checkbox(
                    "These are real field observations for this event.",
                    key="confirm_field_observations",
                )
                if not confirm_field_data:
                    ground_truth_geojson = None
                    st.info("No field metrics will be calculated until you confirm the source.")
        st.caption("Scores apply only to submitted points; sparse samples do not validate the full map.")

    run_analysis = st.button("⚡  Run flood mapping", type="primary", width="stretch")
    st.markdown("---")
    st.caption("Sentinel-1 SAR · Earth Engine · WorldPop · OpenStreetMap")


if run_analysis:
    try:
        payload = make_payload(
            before_range,
            after_range,
            bounds,
            region_name,
            optical_sensor,
            ground_truth_geojson,
            selected_region,
        )
        if ground_truth_file is not None and field_file_error:
            raise ValueError(field_file_error)
    except ValueError as exc:
        st.error(str(exc))
    else:
        try:
            with st.spinner("Running Sentinel-1 analysis and impact overlays…"):
                response = requests.post(ANALYZE_URL, json=payload, timeout=300)
                response.raise_for_status()
                result = response.json()
            if not isinstance(result, dict):
                raise ValueError("Backend response must be a JSON object.")
            st.session_state["analysis"] = {
                "parameters": payload,
                "result": result,
                "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            st.toast("Flood analysis completed.", icon="🌊")
        except requests.HTTPError as exc:
            try:
                detail = exc.response.json().get("error", str(exc))
            except (AttributeError, ValueError):
                detail = str(exc)
            st.error(f"Backend returned an error: {detail}")
        except requests.RequestException as exc:
            st.error(f"Could not connect to {API_URL}. Start the Flask backend and try again. Details: {exc}")
        except ValueError as exc:
            st.error(f"Backend returned an invalid response: {exc}")

analysis = st.session_state.get("analysis")
current_params = None
try:
    current_params = make_payload(
        before_range,
        after_range,
        bounds,
        region_name,
        optical_sensor,
        ground_truth_geojson,
        selected_region,
    )
except ValueError:
    pass
is_stale = bool(analysis and current_params != analysis["parameters"])

st.markdown(f'<div class="eyebrow">FLOOD INTELLIGENCE · {region_name.upper()}</div>', unsafe_allow_html=True)
st.markdown('<div class="title">Rapid flood analysis</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub">Sentinel-1 change detection with optional optical corroboration, population exposure, mapped settlement/road overlays, and field-point validation.</div>',
    unsafe_allow_html=True,
)
st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

if analysis:
    result = analysis["result"]
    params = analysis["parameters"]
    if is_stale:
        st.warning("The selected dates, region, sensors, or field reference differ from the last completed analysis. Run flood mapping again to refresh the result.")
    validation = result.get("field_validation")
    badge = (
        f"● FIELD-POINT CHECK · {validation.get('sample_points')} SAMPLES"
        if validation
        else "● CANDIDATE RESULT · NOT GROUND-VALIDATED"
    )
    st.markdown(f'<span class="status">{badge}</span>', unsafe_allow_html=True)
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    def display(value, suffix="", digits=3):
        if value is None:
            return "Unavailable"
        if isinstance(value, (int, float)):
            return f"{value:,.{digits}f}{suffix}"
        return str(value)

    area = result.get("candidate_flood_area_km2")
    population = result.get("population_exposed_estimate")
    settlements = result.get("affected_settlements")
    roads = result.get("affected_roads_km")
    metrics = [
        ("Candidate flood area", display(area, " km²"), "Sentinel-1 estimate"),
        ("Pre-event Sentinel-1 images", display(result.get("before_images"), digits=0), "Acquisitions"),
        ("Post-event Sentinel-1 images", display(result.get("after_images"), digits=0), "Acquisitions"),
        ("Affected settlements", display(settlements, digits=0), "OpenStreetMap place features"),
        ("Road length exposed", display(roads, " km"), "Mapped OpenStreetMap roads"),
        ("Population exposed", display(population, digits=0), f"WorldPop {result.get('population_dataset_year') or 'year unavailable'} estimate"),
    ]
    for start in (0, 3):
        metric_cols = st.columns(3, gap="small")
        for col, (label, value, note) in zip(metric_cols, metrics[start:start + 3]):
            with col:
                st.markdown(
                    f'<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-value">{value}</div><div class="metric-note">{note}</div></div>',
                    unsafe_allow_html=True,
                )

    warning = result.get("warning") or "Candidate flood extent only; field ground validation is not available."
    st.warning(warning)
    st.caption(
        f"Region: {params.get('region_name', 'Analysis AOI')} · "
        f"Method: {result.get('method', 'Not supplied by backend')} · "
        f"Analysis completed {analysis['fetched_at']} UTC"
    )

    if validation:
        st.markdown('<div class="section-head"><h3>Field observation check</h3><p>Scores compare the SAR classification only at the field points you provided.</p></div>', unsafe_allow_html=True)
        validation_cols = st.columns(4)
        validation_metrics = [
            ("Accuracy", validation.get("accuracy_percent")),
            ("Precision", validation.get("precision_percent")),
            ("Recall", validation.get("recall_percent")),
            ("F1 score", validation.get("f1_percent")),
        ]
        for col, (label, value) in zip(validation_cols, validation_metrics):
            with col:
                st.metric(label, f"{value:.1f}%" if value is not None else "Unavailable")
        st.caption(
            f"{validation.get('sample_points', 0)} points: "
            f"{validation.get('flooded_observations', 0)} flooded and "
            f"{validation.get('dry_observations', 0)} dry. "
            f"Kappa: {validation.get('kappa', 'unavailable')}. "
            f"{validation.get('warning', '')}"
        )
    else:
        st.info(
            "Ground verification is not available for this run. Upload labeled field-observation points "
            "in the sidebar to calculate accuracy, precision, recall, and F1 at those locations."
        )

    optical = result.get("optical_validation")
    if optical:
        st.markdown('<div class="section-head"><h3>Optical cross-check</h3><p>Independent optical water-change comparison; this does not replace ground observations.</p></div>', unsafe_allow_html=True)
        if optical.get("available"):
            optical_cols = st.columns(3)
            optical_metrics = [
                (f"{optical['sensor']} images before", optical.get("before_images")),
                (f"{optical['sensor']} images after", optical.get("after_images")),
                ("SAR candidate overlap", optical.get("sar_candidate_overlap_percent")),
            ]
            for col, (label, value) in zip(optical_cols, optical_metrics):
                with col:
                    st.metric(label, f"{value:.1f}%" if label == "SAR candidate overlap" and value is not None else display(value, digits=0))
            st.caption(
                f"New optical-water area: {display(optical.get('optical_new_water_km2'), ' km²')}; "
                f"overlap area: {display(optical.get('overlap_with_sar_km2'), ' km²')}. "
                f"{optical.get('warning', '')}"
            )
        else:
            st.info(optical.get("warning", "Optical imagery was not available in both date windows."))

    st.markdown('<div class="section-head"><h3>Pre/post Sentinel-1 comparison</h3><p>Median VV backscatter previews for the selected windows.</p></div>', unsafe_allow_html=True)
    preview_left, preview_right = st.columns(2)
    for col, key, label in (
        (preview_left, "before_tile_url", "Pre-flood baseline"),
        (preview_right, "after_tile_url", "Post-flood event"),
    ):
        with col:
            st.caption(label)
            preview_url = result.get(key)
            if preview_url:
                try:
                    st_folium(
                        build_sar_preview(preview_url, result.get("analysis_bounds", DEFAULT_BOUNDS), label),
                        height=300,
                        returned_objects=[],
                    )
                except Exception as exc:
                    st.error(f"Could not render {label.lower()} preview: {exc}")

    st.markdown('<div class="section-head"><h3>Interactive flood and impact map</h3><p>Toggle the candidate extent, affected OpenStreetMap features, and boundary.</p></div>', unsafe_allow_html=True)
    bounds_for_map = result.get("analysis_bounds", DEFAULT_BOUNDS)
    flood_tile = result.get("flood_tile_url")
    if flood_tile:
        try:
            st_folium(
                build_flood_map(
                    flood_tile,
                    bounds_for_map,
                    result.get("roads_geojson"),
                    result.get("settlements_geojson"),
                ),
                height=520,
                returned_objects=[],
            )
        except Exception as exc:
            st.error(f"Could not render the Earth Engine impact map: {exc}")
    else:
        st.info("The backend response did not include a flood tile URL.")

    st.markdown('<div class="section-head"><h3>Impact data and sources</h3><p>Exposure values use the datasets and dates returned by the backend.</p></div>', unsafe_allow_html=True)
    impact_cols = st.columns(3)
    impact_notes = [
        ("Settlements", "Counts mapped OpenStreetMap place features intersecting the candidate flood extent."),
        ("Roads", "Sums mapped OSM road length intersecting the candidate flood extent. OSM coverage may be incomplete."),
        ("Population", f"WorldPop {result.get('population_dataset_year') or 'latest available'} grid; the source is older than the selected event."),
    ]
    for col, (label, detail) in zip(impact_cols, impact_notes):
        with col:
            st.markdown(f'<div class="muted-box"><b>{label}</b><br>{detail}</div>', unsafe_allow_html=True)
    st.caption(
        f"{result.get('osm_attribution', 'OpenStreetMap attribution unavailable')}. "
        f"OSM snapshot checked {result.get('osm_data_timestamp', 'time unavailable')}."
    )
    if result.get("osm_warning"):
        st.warning(result["osm_warning"])

    settlement_features = (result.get("settlements_geojson") or {}).get("features", [])
    review_rows = [
        {
            "Settlement / area": feature.get("properties", {}).get("name", "Unnamed mapped area"),
            "OSM type": feature.get("properties", {}).get("place", "mapped area"),
            "Candidate overlap (km²)": feature.get("properties", {}).get("candidate_overlap_km2"),
        }
        for feature in settlement_features
    ]
    st.markdown('<div class="section-head"><h3>Settlement review areas</h3><p>Mapped OSM places/residential areas intersecting the candidate flood extent; use for response-team review.</p></div>', unsafe_allow_html=True)
    if review_rows:
        review_table = pd.DataFrame(review_rows).sort_values(
            "Candidate overlap (km²)", ascending=False, na_position="last"
        )
        st.dataframe(review_table.head(20), hide_index=True, width="stretch")
        st.caption("Listed intersections are screening candidates, not confirmed flooded settlements or response priorities.")
    else:
        st.info("No mapped settlement/residential features intersected this candidate extent. Check OpenStreetMap coverage and confirm locally.")

    export_payload = {
        "request": params,
        "result": result,
        "fetched_at": analysis["fetched_at"],
    }
    export_left, export_right = st.columns(2)
    with export_left:
        st.download_button(
            "↓  Download analysis JSON",
            data=json.dumps(export_payload, indent=2),
            file_name="jaldrishti-analysis.json",
            mime="application/json",
            width="stretch",
        )
    with export_right:
        st.download_button(
            "↓  Download analysis CSV",
            data=scalar_csv(params, result),
            file_name="jaldrishti-analysis.csv",
            mime="text/csv",
            width="stretch",
        )
else:
    st.markdown('<span class="status">● READY · AWAITING BACKEND ANALYSIS</span>', unsafe_allow_html=True)
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    metrics = [
        ("Candidate flood area", "Awaiting analysis"),
        ("Pre-event images", "Awaiting analysis"),
        ("Post-event images", "Awaiting analysis"),
        ("Affected settlements", "Awaiting analysis"),
        ("Road length exposed", "Awaiting analysis"),
        ("Population exposure", "Awaiting analysis"),
    ]
    for start in (0, 3):
        cols = st.columns(3, gap="small")
        for col, (label, note) in zip(cols, metrics[start:start + 3]):
            with col:
                st.markdown(
                    f'<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-value">—</div><div class="metric-note">{note}</div></div>',
                    unsafe_allow_html=True,
                )
    st.markdown('<div class="section-head"><h3>Analysis map</h3><p>The flood and impact overlays appear after a successful backend run.</p></div>', unsafe_allow_html=True)
    st.markdown('<div class="muted-box">Select non-overlapping baseline and event dates, set a region of at most 2° per side, then choose <b>Run flood mapping</b>. You can add optional optical comparison and field reference points in the sidebar.</div>', unsafe_allow_html=True)

st.markdown(
    '<div class="note" style="margin-top:20px"><b>Interpretation & limitations</b><br>Sentinel-1 returns candidate flood pixels after speckle smoothing, permanent-water removal, and a slope filter. WorldPop estimates exposure from its latest available gridded population year, not the event year. Settlements and roads come from OpenStreetMap coverage. Optical agreement is cross-sensor corroboration. Ground verification requires real field-reference points and scores only those submitted samples.</div>',
    unsafe_allow_html=True,
)
st.markdown('<div style="margin-top:30px;padding-top:14px;border-top:1px solid #223649;color:#70869a;font-size:10px">JALDRISHTI · RAPID FLOOD MAPPING · DECISION SUPPORT PROTOTYPE</div>', unsafe_allow_html=True)
