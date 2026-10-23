from __future__ import annotations

import csv
import io
import json
import os
from datetime import date, datetime, timedelta, timezone

import folium
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
# backend/flood_analysis.py currently uses this fixed rectangle.
ROI_BOUNDS = [[26.2, 86.8], [26.6, 87.2]]
ROI_CENTER = [26.4, 87.0]

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


def make_payload(before_range, after_range) -> dict[str, str]:
    """Convert Streamlit date ranges into the Flask API's ISO date contract."""
    if (
        not isinstance(before_range, (tuple, list))
        or not isinstance(after_range, (tuple, list))
        or len(before_range) != 2
        or len(after_range) != 2
    ):
        raise ValueError("Select both a start and end date for each period.")
    if before_range[0] >= before_range[1] or after_range[0] >= after_range[1]:
        raise ValueError("Each date range must have a start date before its end date.")
    if before_range[1] > after_range[0]:
        raise ValueError("The baseline period must finish before the event period begins.")
    return {
        "before_start": before_range[0].isoformat(),
        "before_end": before_range[1].isoformat(),
        "after_start": after_range[0].isoformat(),
        "after_end": after_range[1].isoformat(),
    }


def build_flood_map(tile_url: str) -> folium.Map:
    """Create the Leaflet map with backend GEE tiles and the backend's fixed AOI."""
    map_view = folium.Map(location=ROI_CENTER, zoom_start=9, tiles=None, control_scale=True)
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
    folium.Rectangle(
        bounds=ROI_BOUNDS,
        color="#f5bd61",
        weight=2,
        fill=False,
        tooltip="Backend AOI · Koshi Basin test rectangle",
        name="Analysis region",
    ).add_to(map_view)
    folium.LayerControl(collapsed=False, position="topright").add_to(map_view)
    legend = """<div style="position:fixed;bottom:28px;left:18px;z-index:9999;background:#101f2dde;
    color:#e7f0f6;padding:9px 12px;border:1px solid #496176;border-radius:8px;font:12px sans-serif">
    <span style="color:#ff4b4b;font-size:18px">■</span> Candidate flood pixels &nbsp;
    <span style="color:#f5bd61;font-size:18px">▱</span> Analysis boundary</div>"""
    map_view.get_root().html.add_child(folium.Element(legend))
    return map_view


def scalar_csv(parameters: dict, result: dict) -> bytes:
    output = io.StringIO()
    fields = ["field", "value"]
    writer = csv.DictWriter(output, fieldnames=fields)
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
    st.caption("Current backend supports a fixed test area near the Koshi River, Nepal.")
    st.text_input("Analysis region", "Koshi Basin · Nepal", disabled=True)
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
    run_analysis = st.button("⚡  Run flood mapping", type="primary", use_container_width=True)
    st.markdown("---")
    st.caption("SENTINEL-1 SAR · Earth Engine backend")

if run_analysis:
    try:
        payload = make_payload(before_range, after_range)
    except ValueError as exc:
        st.error(str(exc))
    else:
        try:
            with st.spinner("Requesting Sentinel-1 analysis from the Flask backend…"):
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
            st.toast("Backend analysis completed.", icon="🌊")
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
    current_params = make_payload(before_range, after_range)
except ValueError:
    pass
is_stale = bool(analysis and current_params != analysis["parameters"])

st.markdown('<div class="eyebrow">FLOOD INTELLIGENCE · KOSHI BASIN, NEPAL</div>', unsafe_allow_html=True)
st.markdown('<div class="title">Rapid flood analysis</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub">Sentinel-1 change detection from the Flask + Google Earth Engine backend. Review the candidate extent, acquisition counts, and validation status.</div>',
    unsafe_allow_html=True,
)
st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

if analysis:
    result = analysis["result"]
    params = analysis["parameters"]
    if is_stale:
        st.warning("The selected dates differ from the last completed analysis. Run flood mapping again to refresh the displayed result.")
    st.markdown('<span class="status">● BACKEND RESULT · Earth Engine</span>', unsafe_allow_html=True)
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    area = result.get("candidate_flood_area_km2")
    area_label = f"{area:g} km²" if isinstance(area, (int, float)) else "Not returned"
    before_count = result.get("before_images")
    after_count = result.get("after_images")
    metrics = [
        ("Candidate flood area", area_label, "Backend estimate · not ground-validated"),
        ("Pre-event Sentinel-1 images", before_count if before_count is not None else "Not returned", "Count returned by backend"),
        ("Post-event Sentinel-1 images", after_count if after_count is not None else "Not returned", "Count returned by backend"),
        ("Affected settlements", "Not available", "Backend GIS integration required"),
        ("Population exposure", "Not available", "Backend population analysis required"),
    ]
    metric_cols = st.columns(5, gap="small")
    for col, (label, value, note) in zip(metric_cols, metrics):
        with col:
            st.markdown(
                f'<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-value">{value}</div><div class="metric-note">{note}</div></div>',
                unsafe_allow_html=True,
            )
    warning = result.get("warning") or "Candidate flood extent only; ground validation is not available."
    st.warning(warning)
    st.caption(f"Method: {result.get('method', 'Not supplied by backend')} · Analysis completed {analysis['fetched_at']} UTC")

    st.markdown('<div class="section-head"><h3>Interactive flood extent map</h3><p>Earth Engine tile overlay with basemap switcher and the backend’s fixed Koshi test-area boundary.</p></div>', unsafe_allow_html=True)
    tile_url = result.get("flood_tile_url")
    if tile_url:
        try:
            flood_map = build_flood_map(tile_url)
            st_folium(flood_map, use_container_width=True, height=520, returned_objects=[])
        except Exception as exc:
            st.error(f"Could not render the Earth Engine tile map: {exc}")
            st.code(tile_url, language=None)
    else:
        st.info("The backend response did not include a flood tile URL, so the map is unavailable for this result.")

    st.markdown('<div class="section-head"><h3>Impact data availability</h3><p>Only fields returned by the backend are reported as calculated.</p></div>', unsafe_allow_html=True)
    impact_cols = st.columns(3)
    for col, label, source in zip(
        impact_cols,
        ("Settlements intersected", "Road length exposed", "Population exposed"),
        ("No settlement layer or count in API response", "No road network analysis in API response", "No population dataset or exposure result in API response"),
    ):
        with col:
            st.markdown(f'<div class="muted-box"><b>{label}: Not available</b><br>{source}</div>', unsafe_allow_html=True)

    export_payload = {"request": params, "result": result, "fetched_at": analysis["fetched_at"]}
    ec1, ec2 = st.columns(2)
    with ec1:
        st.download_button(
            "↓  Download analysis JSON",
            data=json.dumps(export_payload, indent=2),
            file_name="jaldrishti-analysis.json",
            mime="application/json",
            use_container_width=True,
        )
    with ec2:
        st.download_button(
            "↓  Download analysis CSV",
            data=scalar_csv(params, result),
            file_name="jaldrishti-analysis.csv",
            mime="text/csv",
            use_container_width=True,
        )
else:
    st.markdown('<span class="status">● READY · AWAITING BACKEND ANALYSIS</span>', unsafe_allow_html=True)
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    cols = st.columns(5, gap="small")
    for col, label, note in zip(
        cols,
        ("Candidate flood area", "Pre-event images", "Post-event images", "Affected settlements", "Population exposure"),
        ("Awaiting analysis", "Awaiting analysis", "Awaiting analysis", "Not available from backend", "Not available from backend"),
    ):
        with col:
            st.markdown(f'<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-value">—</div><div class="metric-note">{note}</div></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-head"><h3>Analysis map</h3><p>The map will appear after the backend returns its Earth Engine flood tile URL.</p></div>', unsafe_allow_html=True)
    st.markdown('<div class="muted-box">No analysis has been run yet. Select non-overlapping baseline and event dates, then choose <b>Run flood mapping</b>. The backend currently analyzes a fixed test rectangle near the Koshi River.</div>', unsafe_allow_html=True)

st.markdown(
    '<div class="note" style="margin-top:20px"><b>Interpretation & limitations</b><br>The backend reports a candidate Sentinel-1 flood extent and acquisition counts. Its warning says the extent is not ground-validated. Population exposure, affected settlements, and roads are not calculated by the current backend. Pre/post satellite image previews are also not part of its API response.</div>',
    unsafe_allow_html=True,
)
st.markdown('<div style="margin-top:30px;padding-top:14px;border-top:1px solid #223649;color:#70869a;font-size:10px">JALDRISHTI · RAPID FLOOD MAPPING · DECISION SUPPORT PROTOTYPE</div>', unsafe_allow_html=True)
