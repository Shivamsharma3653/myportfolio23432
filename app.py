from __future__ import annotations

import json
import base64
from datetime import date, timedelta

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


st.set_page_config(page_title="JALDRISHTI | Rapid Flood Mapping", page_icon="🌊", layout="wide", initial_sidebar_state="expanded")

REGIONS = {
    "Nepal Terai · Koshi Basin": {"district": "Sunsari · Saptari", "area": 12.4, "settlements": 7, "roads": 18.6, "people": 4820, "confidence": 82},
    "Assam · Brahmaputra Valley": {"district": "Dibrugarh · Dhemaji", "area": 18.7, "settlements": 12, "roads": 31.2, "people": 9130, "confidence": 76},
    "Bangladesh · Jamuna Basin": {"district": "Sirajganj · Gaibandha", "area": 22.1, "settlements": 16, "roads": 26.4, "people": 12400, "confidence": 69},
}

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@400;500;600;700;800&display=swap');
:root { --bg:#0a1420; --panel:#111f2e; --panel2:#162638; --line:#26394b; --muted:#94a8ba; --text:#e8f1f7; --cyan:#25d4e5; --blue:#328cff; }
html, body, [class*="css"] { font-family:'DM Sans',sans-serif; }
.stApp { background:radial-gradient(ellipse at 77% 0%, #142b3d 0, var(--bg) 48%); color:var(--text); }
header[data-testid="stHeader"] { background:transparent; }
section[data-testid="stSidebar"] { background:linear-gradient(180deg,#101e2c,#0c1722); border-right:1px solid var(--line); }
section[data-testid="stSidebar"] > div { padding-top:1.2rem; }
.block-container { padding:1.6rem 2rem 3rem; max-width:1600px; }
h1,h2,h3 { font-family:'Manrope',sans-serif; letter-spacing:-.035em; color:#f1f7fb; }
.brand { display:flex; align-items:center; gap:11px; margin:0 0 26px; }
.brand-mark { width:42px;height:42px;border-radius:13px;background:linear-gradient(140deg,#26d5e5,#167acb);display:grid;place-items:center;color:#061520;font-size:24px;font-weight:800;box-shadow:0 8px 30px #16bcd333; }
.brand-name { font:800 19px Manrope,sans-serif; letter-spacing:.08em; color:#f4f8fb; }
.brand-sub { color:#55cfdd;font-size:9px;letter-spacing:.2em;font-weight:700;margin-top:1px; }
.side-caption { font-size:10px;letter-spacing:.14em;text-transform:uppercase;color:#73899b;font-weight:700;margin:23px 0 8px; }
.page-title { display:flex; justify-content:space-between; align-items:flex-start; gap:20px; margin:2px 0 21px; }
.eyebrow { color:#55cddb; text-transform:uppercase; letter-spacing:.15em; font-size:10px; font-weight:700; }
.title { font:800 clamp(25px,3vw,36px) Manrope,sans-serif; letter-spacing:-.045em; margin:5px 0 5px; }
.sub { color:#a2b4c3;font-size:13px;line-height:1.55;max-width:740px; }
.status-pill { border:1px solid #397b6c;background:#14352f;color:#8be0c4;padding:8px 12px;border-radius:22px;font-size:11px;font-weight:600;white-space:nowrap; }
.card { background:linear-gradient(145deg,rgba(23,39,55,.96),rgba(16,30,44,.96));border:1px solid var(--line);border-radius:14px;padding:17px 18px;box-shadow:0 12px 32px #00000018; }
.metric-label { color:#96aabd;font-size:11px;font-weight:600;letter-spacing:.02em; }
.metric-value { color:#f1f7fb;font:700 25px Manrope,sans-serif;letter-spacing:-.04em;margin:8px 0 3px; }
.metric-note { color:#7f95a8;font-size:10px; }
.metric-icon { float:right;color:#3bd2df;font-size:19px; }
.section-head { display:flex;justify-content:space-between;align-items:end;gap:15px;margin:26px 0 12px; }
.section-head h3 { font-size:17px;margin:0; }
.section-head p { color:#879caf;font-size:11px;margin:4px 0 0; }
.scene-label { display:flex;justify-content:space-between;color:#c6d4df;font-size:11px;font-weight:600;padding:0 1px 8px; }
.scene { border:1px solid #2b4357;border-radius:11px;overflow:hidden;background:#121d27; }
.scene svg,.map-frame svg { display:block;width:100%;height:auto; }
.map-frame { border:1px solid #2b4357;border-radius:12px;overflow:hidden;background:#12202b; }
.confidence-track { height:6px;border-radius:8px;background:#283849;margin:12px 0 6px;overflow:hidden; }
.confidence-fill {height:100%;border-radius:8px;background:linear-gradient(90deg,#2daaff,#26d4dc);}
.note { border:1px solid #4b4931;background:#29291e;border-radius:11px;padding:12px 14px;color:#d6d2ab;font-size:11px;line-height:1.5; }
.workflow { display:grid;grid-template-columns:repeat(6,1fr);gap:8px; }
.step { background:#142333;border:1px solid #283d50;border-radius:10px;padding:12px;min-height:88px; }
.step-n { color:#35cfdf;font-size:10px;font-weight:700;letter-spacing:.1em; }
.step-title { color:#dce7ef;font-size:11px;font-weight:700;margin:5px 0 3px; }
.step-copy { color:#8298aa;font-size:9px;line-height:1.35; }
div[data-testid="stDataFrame"] { border:1px solid var(--line);border-radius:11px;overflow:hidden; }
.stButton>button,.stDownloadButton>button { border-radius:9px;border:1px solid #2c5068;background:#142c3d;color:#dff7fa;font-weight:600; }
.stButton>button[kind="primary"] { background:linear-gradient(90deg,#1685e9,#14b9d1);border:0;color:#fff; }
.stButton>button:hover,.stDownloadButton>button:hover { border-color:#32c7d9;color:#fff; }
div[data-baseweb="select"]>div,div[data-baseweb="input"]>div { background:#152638;border-color:#2b4053;border-radius:8px; }
label,div[data-testid="stWidgetLabel"] p { color:#d0dce5!important;font-size:12px!important; }
.stCaption,small { color:#8499ab!important; }
@media(max-width:850px){ .block-container{padding:1.1rem .85rem 2rem}.workflow{grid-template-columns:repeat(2,1fr)}.page-title{display:block}.status-pill{display:inline-block;margin-top:12px}.metric-value{font-size:21px} }
</style>
""", unsafe_allow_html=True)


def river_svg(after: bool, region: str) -> str:
    patches = """
    <g fill="#27d6e3" opacity=".88">
      <path d="M92 79l20-8 12 11-8 13-25 2z"/><path d="M157 122l17-8 19 9-7 18-24 2z"/>
      <path d="M250 70l16-11 21 7 3 15-22 10-19-7z"/><path d="M309 145l21-12 20 8-4 17-25 8z"/>
      <path d="M387 91l20-8 12 12-5 16-22 5z"/><path d="M213 183l17-7 20 7 4 15-21 12-19-9z"/>
      <path d="M64 170l13-8 16 6-2 16-20 5z"/><path d="M354 197l20-10 16 9-8 16-24-2z"/>
      <path d="M115 208l22-7 12 10-6 13-23 2z"/>
    </g>""" if after else ""
    extra = "" if after else '<text x="18" y="25" fill="#b4c1cb" font-size="10">PRE-FLOOD BASELINE</text>'
    return f'''<svg viewBox="0 0 500 270" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{'Post' if after else 'Pre'} flood satellite mock image">
    <defs><linearGradient id="ground" x2="0" y2="1"><stop stop-color="#53606a"/><stop offset="1" stop-color="#333e47"/></linearGradient><pattern id="grain" width="32" height="28" patternUnits="userSpaceOnUse"><path d="M2 6l9-3 6 5-10 4zm18 17l9-5 4 5-8 4zM8 21l5-3 3 3-7 3z" fill="#9ea5a5" opacity=".3"/><path d="M0 14h32M15 0v28" stroke="#bec1b9" stroke-width=".6" opacity=".13"/></pattern></defs>
    <rect width="500" height="270" fill="url(#ground)"/><rect width="500" height="270" fill="url(#grain)"/>
    <g fill="none" stroke="#20292e" stroke-width="20" stroke-linecap="round"><path d="M257 -20 C230 23 285 38 250 74S267 116 241 148s29 45 3 79 5 35-7 63"/></g>
    <g fill="none" stroke="#10191e" stroke-width="8" stroke-linecap="round"><path d="M257 -20 C230 23 285 38 250 74S267 116 241 148s29 45 3 79 5 35-7 63"/></g>
    <g fill="none" stroke="#d0cdbf" stroke-width="1" opacity=".26"><path d="M0 88l156 30 160-15 184 30M10 224l132-51 185 34 173-50M95 0l32 270M416 0l-35 270"/></g>
    {patches}{extra}<rect x="12" y="235" width="68" height="23" rx="5" fill="#08131c" opacity=".78"/><text x="20" y="250" fill="#dce8ef" font-size="9">SAR · 10 m</text>
    <text x="428" y="253" fill="#e6eef4" font-size="9">N ↑</text></svg>'''


def flood_map(region: str, settlements: bool, roads: bool) -> str:
    road = '<g fill="none" stroke="#f1bc69" stroke-width="2" stroke-dasharray="6 5"><path d="M28 247Q150 214 235 156T478 42"/><path d="M77 30Q143 87 217 103t194 89"/></g>' if roads else ''
    homes = '<g fill="#f4cb76" stroke="#172330" stroke-width="2"><circle cx="102" cy="110" r="7"/><circle cx="145" cy="146" r="7"/><circle cx="330" cy="77" r="7"/><circle cx="370" cy="177" r="7"/><circle cx="250" cy="215" r="7"/><circle cx="416" cy="124" r="7"/></g>' if settlements else ''
    return f'''<svg viewBox="0 0 600 315" xmlns="http://www.w3.org/2000/svg" aria-label="Illustrative flood extent map for {region}">
    <defs><pattern id="grid" width="30" height="30" patternUnits="userSpaceOnUse"><path d="M30 0H0V30" fill="none" stroke="#385062" stroke-width=".7" opacity=".45"/></pattern></defs>
    <rect width="600" height="315" fill="#182b36"/><rect width="600" height="315" fill="url(#grid)"/>
    <path d="M-20 62Q78 30 151 74T277 109 397 83 620 117M-14 257Q95 208 186 226t190 16 243-63" fill="none" stroke="#32494f" stroke-width="26" opacity=".48"/>
    <path d="M-20 60Q78 28 151 72T277 107 397 81 620 115M-14 255Q95 206 186 224t190 16 243-63" fill="none" stroke="#253b40" stroke-width="12"/>
    <path d="M90 87l56-20 48 14 17 45-32 33-64-4-39-31zM293 48l60-8 40 23-4 42-53 19-49-25zM342 183l55-27 46 17 16 47-52 25-63-18zM158 210l44-18 31 24-12 39-52 11-26-24z" fill="#1cc4dd" fill-opacity=".57" stroke="#49e5ed" stroke-width="2"/>
    {road}{homes}<g fill="#e5eef3" font-family="sans-serif" font-size="10"><text x="20" y="24">{region.upper()}</text><text x="448" y="291">Illustrative extent · 10 km</text></g>
    <g transform="translate(18 276)"><rect width="10" height="10" rx="2" fill="#25d4e5"/><text x="16" y="9" fill="#d9e6ee" font-size="9">Detected inundation</text><rect x="137" width="10" height="10" rx="2" fill="#f4cb76"/><text x="153" y="9" fill="#d9e6ee" font-size="9">Settlement</text><path d="M240 5h18" stroke="#f1bc69" stroke-width="2" stroke-dasharray="4 3"/><text x="264" y="9" fill="#d9e6ee" font-size="9">Road network</text></g></svg>'''



def render_svg(svg: str, height: int, background: str = "#121d27") -> None:
    """Render the illustration as an image instead of exposing SVG source text."""
    svg_data = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    components.html(
        f"""<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1">
        <style>html,body{{margin:0;padding:0;background:{background};overflow:hidden}}
        img{{display:block;width:100%;height:auto}}</style></head>
        <body><img alt="Illustrative flood mapping panel" src="data:image/svg+xml;base64,{svg_data}"></body></html>""",
        height=height,
        scrolling=False,
    )

with st.sidebar:
    st.markdown('<div class="brand"><div class="brand-mark">✳</div><div><div class="brand-name">JALDRISHTI</div><div class="brand-sub">RAPID FLOOD MAPPING</div></div></div>', unsafe_allow_html=True)
    st.markdown('<div class="side-caption">Workspace</div>', unsafe_allow_html=True)
    page = st.radio("Navigate", ["Overview", "Impact & priorities", "Methodology"], label_visibility="collapsed")
    st.markdown('<div class="side-caption">Analysis settings</div>', unsafe_allow_html=True)
    region = st.selectbox("Region of interest", list(REGIONS))
    sensor = st.selectbox("Detection sensor", ["Sentinel-1 SAR", "Sentinel-1 + Sentinel-2", "Sentinel-1 + Landsat 8/9"])
    st.caption("SAR leads detection. Optical imagery is optional validation when cloud conditions allow.")
    today = date(2026, 10, 17)
    before_range = st.date_input("Pre-flood baseline", value=(today-timedelta(days=46), today-timedelta(days=27)), max_value=today)
    after_range = st.date_input("Post-flood event", value=(today-timedelta(days=19), today-timedelta(days=7)), max_value=today)
    threshold = st.slider("Change threshold", 0.05, 0.50, 0.20, 0.01, help="Display setting for this prototype; no live classification is run.")
    st.markdown('<div class="side-caption">Map layers</div>', unsafe_allow_html=True)
    show_settlements = st.checkbox("Settlements", value=True)
    show_roads = st.checkbox("Road network", value=True)
    run = st.button("⚡  Analyze flood event", type="primary", use_container_width=True)
    if run:
        st.session_state.analysis_run = True
        st.toast("Demo analysis refreshed for the selected region.", icon="🌊")
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    st.caption("DEMO MODE · No Earth Engine or satellite connection configured")

d = REGIONS[region]
if run:
    st.session_state.analysis_run = True

if page == "Overview":
    st.markdown(f'''<div class="page-title"><div><div class="eyebrow">Flood intelligence · {d['district']}</div><div class="title">Event overview</div><div class="sub">Rapid, confidence-aware flood mapping for operational planning. Compare radar observations, review potential exposure, and prioritize locations for field verification.</div></div><div class="status-pill">● &nbsp; DEMO SCENARIO</div></div>''', unsafe_allow_html=True)
    cols = st.columns(4, gap="medium")
    metrics = [("Newly detected inundation", f"{d['area']:.1f} km²", "Estimated event extent · mock data", "◈"), ("Potentially affected settlements", str(d["settlements"]), "Locations intersecting estimated extent", "⌂"), ("Road segments exposed", f"{d['roads']:.1f} km", "Potentially intersecting roads", "⌁"), ("Population exposure", f"{d['people']:,}", "Modelled estimate · not a verified count", "♙")]
    for col, (label, value, note, icon) in zip(cols, metrics):
        with col: st.markdown(f'<div class="card"><span class="metric-icon">{icon}</span><div class="metric-label">{label}</div><div class="metric-value">{value}</div><div class="metric-note">{note}</div></div>', unsafe_allow_html=True)

    st.markdown('<div class="section-head"><div><h3>Before / after satellite view</h3><p>Illustrative SAR scenes · cyan marks the estimated newly inundated areas</p></div><span class="metric-label">{}</span></div>'.format(sensor), unsafe_allow_html=True)
    a,b=st.columns(2,gap="medium")
    with a:
        st.markdown('<div class="scene-label"><span>PRE-FLOOD · BASELINE</span><span>Sentinel-1 SAR</span></div>',unsafe_allow_html=True)
        render_svg(river_svg(False,region), height=270)
    with b:
        st.markdown('<div class="scene-label"><span>POST-FLOOD · EVENT</span><span>Sentinel-1 SAR + extent</span></div>',unsafe_allow_html=True)
        render_svg(river_svg(True,region), height=270)
    st.caption("Satellite panels are generated mock illustrations, not Sentinel downloads. Selected date windows: baseline {} – {}; event {} – {}.".format(*(before_range if isinstance(before_range,tuple) else [before_range,before_range]), *(after_range if isinstance(after_range,tuple) else [after_range,after_range])))

    st.markdown('<div class="section-head"><div><h3>Estimated flood extent & exposure</h3><p>Illustrative impact layers · toggle settlements and roads in analysis settings</p></div><span class="metric-label">{}</span></div>'.format(region),unsafe_allow_html=True)
    m1,m2=st.columns([1.7,1],gap="medium")
    with m1: render_svg(flood_map(region,show_settlements,show_roads), height=315, background="#12202b")
    with m2:
        st.markdown('<div class="card"><div style="display:flex;justify-content:space-between"><div><div class="metric-label">Detection confidence</div><div class="metric-value" style="color:#47d8ce">{}%</div></div><div style="font-size:26px;color:#45d5ce">◈</div></div><div class="confidence-track"><div class="confidence-fill" style="width:{}%"></div></div><div class="metric-note">Moderate · verify against field reports and available optical imagery</div><hr style="border-color:#2a4052;margin:17px 0"><div class="metric-label">Sensor & processing</div><p style="font-size:11px;color:#c6d3dd;line-height:1.6;margin-bottom:0">Sentinel-1 SAR change detection<br>Permanent-water and artifact filtering<br>{} validation path</p></div>'.format(d['confidence'],d['confidence'], 'Sentinel-2' if 'Sentinel-2' in sensor else ('Landsat 8/9' if 'Landsat' in sensor else 'Optical validation not selected')),unsafe_allow_html=True)
        st.markdown('<div style="height:10px"></div>',unsafe_allow_html=True)
        st.markdown('<div class="note"><b>Confidence-aware result</b><br>Wet soil, vegetation, built-up areas, revisit timing, and incomplete reference layers can affect mapped extent. Treat exposure as a planning estimate, not a verified impact count.</div>',unsafe_allow_html=True)

    st.markdown('<div class="section-head"><div><h3>Processing workflow</h3><p>Proposal workflow · cloud-resilient radar-led detection</p></div></div>',unsafe_allow_html=True)
    st.markdown('<div class="workflow">'+''.join(f'<div class="step"><div class="step-n">0{i+1} / 06</div><div class="step-title">{title}</div><div class="step-copy">{copy}</div></div>' for i,(title,copy) in enumerate([("Acquire","Sentinel-1 event and baseline"),("Preprocess","Align scenes and check quality"),("Detect change","Compare SAR backscatter"),("Filter artifacts","Remove permanent water and likely false detections"),("Assess impact","Overlay settlements, roads, population"),("Export","Map layers and impact report")]))+'</div>',unsafe_allow_html=True)

    st.markdown('<div class="section-head"><div><h3>Priority areas</h3><p>Ranked for review using estimated inundation and potential exposure</p></div></div>',unsafe_allow_html=True)
    pri = pd.DataFrame([{ "Priority": "High", "Municipality / ward": "Ward 4 · Sunsari", "Flood area (km²)": round(d['area']*.31,1), "Settlements": 3, "People exposed*": round(d['people']*.37)}, {"Priority":"High","Municipality / ward":"Ward 2 · Saptari","Flood area (km²)":round(d['area']*.24,1),"Settlements":2,"People exposed*":round(d['people']*.26)}, {"Priority":"Medium","Municipality / ward":"Ward 7 · Koshi corridor","Flood area (km²)":round(d['area']*.18,1),"Settlements":1,"People exposed*":round(d['people']*.18)}, {"Priority":"Monitor","Municipality / ward":"Ward 1 · Riverside","Flood area (km²)":round(d['area']*.12,1),"Settlements":1,"People exposed*":round(d['people']*.11)}])
    if region != list(REGIONS)[0]: pri["Municipality / ward"] = [f"Zone {i} · {d['district'].split(' · ')[i%2]}" for i in range(1,5)]
    st.dataframe(pri,use_container_width=True,hide_index=True)
    st.caption("*Population exposure is a mock estimate for demonstration and may differ from actual impacts.")

    geojson={"type":"FeatureCollection","name":"jaldrishti_demo_extent","features":[{"type":"Feature","properties":{"region":region,"sensor":sensor,"area_km2":d['area'],"confidence_percent":d['confidence'],"data_status":"mock demo"},"geometry":{"type":"Polygon","coordinates":[[[87.10,26.55],[87.20,26.55],[87.20,26.63],[87.10,26.63],[87.10,26.55]]]}}]}
    csv=pri.to_csv(index=False).encode("utf-8")
    report=f"# JALDRISHTI Flood Impact Brief\n\n**Region:** {region}\n\n**Status:** DEMONSTRATION / MOCK DATA\n\n**Sensor:** {sensor}\n\n**Estimated inundation:** {d['area']} km²\n\n**Potentially affected settlements:** {d['settlements']}\n\n**Potential road exposure:** {d['roads']} km\n\n**Population exposure estimate:** {d['people']:,}\n\n**Confidence indicator:** {d['confidence']}% (moderate; requires validation)\n\nThis prototype contains illustrative imagery and estimates. No satellite data or live Earth Engine analysis is connected. Confirm with ground reports before operational use.\n"
    st.markdown('<div class="section-head"><div><h3>Export & report</h3><p>Download current demo summary and sample layers</p></div></div>',unsafe_allow_html=True)
    ec=st.columns(3)
    ec[0].download_button("↓  Priority areas · CSV",csv,"jaldrishti-priority-areas-demo.csv","text/csv",use_container_width=True)
    ec[1].download_button("↓  Flood extent · GeoJSON",json.dumps(geojson,indent=2),"jaldrishti-flood-extent-demo.geojson","application/geo+json",use_container_width=True)
    ec[2].download_button("↓  Impact brief · Markdown",report,"jaldrishti-impact-brief-demo.md","text/markdown",use_container_width=True)

elif page == "Impact & priorities":
    st.markdown(f'<div class="eyebrow">{region}</div><div class="title">Impact & priorities</div><div class="sub">Review indicative exposure estimates, map intersections, and the locations suggested for field verification.</div><br>',unsafe_allow_html=True)
    render_svg(flood_map(region,show_settlements,show_roads), height=315, background="#12202b")
    st.markdown('<div class="section-head"><div><h3>Priority areas</h3><p>Demo values · prioritize field validation</p></div></div>',unsafe_allow_html=True)
    st.dataframe(pd.DataFrame([{"Priority":"High","Location":f"Ward 4 · {d['district'].split(' · ')[0]}","Estimated flood area":f"{d['area']*.31:.1f} km²","Settlements":3,"Potential exposure":f"{round(d['people']*.37):,}"},{"Priority":"High","Location":f"Ward 2 · {d['district'].split(' · ')[1]}","Estimated flood area":f"{d['area']*.24:.1f} km²","Settlements":2,"Potential exposure":f"{round(d['people']*.26):,}"},{"Priority":"Medium","Location":"River corridor · Zone 3","Estimated flood area":f"{d['area']*.18:.1f} km²","Settlements":1,"Potential exposure":f"{round(d['people']*.18):,}"}]),use_container_width=True,hide_index=True)
    st.markdown('<div class="note">These are simulated estimates without connected population, road, or settlement datasets. Use this prototype to review the layout and workflow only.</div>',unsafe_allow_html=True)

else:
    st.markdown('<div class="eyebrow">How the result is produced</div><div class="title">Methodology & limitations</div><div class="sub">The proposed workflow combines radar-based flood detection with optional validation and settlement-level impact reporting.</div><br>',unsafe_allow_html=True)
    st.markdown('<div class="workflow">'+''.join(f'<div class="step"><div class="step-n">STAGE 0{i+1}</div><div class="step-title">{title}</div><div class="step-copy">{copy}</div></div>' for i,(title,copy) in enumerate([("Data acquisition","Collect Sentinel-1 observations for baseline and event windows."),("Preprocessing","Prepare, align, and quality-check selected scenes."),("Flood detection","Compare radar backscatter before and after the event."),("Artifact removal","Filter permanent water and likely false detections."),("Impact assessment","Overlay available settlements, road, and population layers."),("Reporting","Generate mapped outputs and an impact summary." )]))+'</div>',unsafe_allow_html=True)
    st.markdown('<div class="section-head"><div><h3>Sensor strategy</h3></div></div>',unsafe_allow_html=True)
    c1,c2=st.columns(2)
    with c1: st.markdown('<div class="card"><div class="metric-label">PRIMARY · SENTINEL-1 SAR</div><p style="font-size:12px;color:#bdccd8;line-height:1.6">Radar-led detection supports cloudy conditions and is the primary flood mapping input in the proposed workflow.</p><div class="metric-label">OPTIONAL VALIDATION · SENTINEL-2 / LANDSAT 8/9</div><p style="font-size:12px;color:#bdccd8;line-height:1.6;margin-bottom:0">Optical imagery can support cross-validation when clear scenes are available. It is not a required dependency.</p></div>',unsafe_allow_html=True)
    with c2: st.markdown('<div class="note"><b>Limitations to manage</b><br>Wet soil, vegetation, and urban structures can produce false detections. Satellite revisit timing may delay observations. Reference settlement and road layers may be incomplete. Population exposure estimates can differ from actual impacts. Ground-truth data may be limited.<br><br><b>Mitigation</b><br>Use quality checks, optional multi-sensor validation, field verification, and reference-based accuracy evaluation. Confidence indicators should highlight uncertainty rather than imply certainty.</div>',unsafe_allow_html=True)
    st.markdown('<div class="section-head"><div><h3>Prototype data status</h3></div></div>',unsafe_allow_html=True)
    st.info("This dashboard currently uses generated mock imagery, illustrative map geometry, and simulated exposure values. Google Earth Engine, satellite catalogs, and official impact datasets are not configured. Export files are labeled as demo samples.")

st.markdown('<div style="margin-top:32px;padding-top:14px;border-top:1px solid #223649;color:#70869a;font-size:10px;display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap"><span>JALDRISHTI · RAPID FLOOD MAPPING</span><span>Decision support prototype · verify all estimates before operational use</span></div>',unsafe_allow_html=True)
