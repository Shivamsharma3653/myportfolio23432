from __future__ import annotations

import json
import base64
import os
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components

from backend.reporting import TIER_RULES, build_local_management_report, rank_settlements


API_URL = os.getenv("JALDRISHTI_API_URL", "http://127.0.0.1:5000").rstrip("/")
ANALYZE_URL = f"{API_URL}/analyze"


st.set_page_config(
    page_title="TERAI FLOODWATCH | Satellite Flood Intelligence",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Helper for loading base64 images reliably
@st.cache_data
def load_img_b64(path: str) -> str:
    if os.path.exists(path):
        with open(path, "rb") as f:
            return f"data:image/jpeg;base64,{base64.b64encode(f.read()).decode('ascii')}"
    return ""

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
IMG_HERO = load_img_b64(os.path.join(ASSETS_DIR, "hero_earth.jpg"))
IMG_SENTINEL1 = load_img_b64(os.path.join(ASSETS_DIR, "sentinel1_sar.jpg"))
IMG_SENTINEL2 = load_img_b64(os.path.join(ASSETS_DIR, "sentinel2_optical.jpg"))
IMG_PREFLOOD = load_img_b64(os.path.join(ASSETS_DIR, "terai_preflood.jpg"))
IMG_POSTFLOOD = load_img_b64(os.path.join(ASSETS_DIR, "terai_postflood.jpg"))

REGIONS = {
    "Nepal Terai · Koshi Basin": {"district": "Sunsari · Saptari · Morang", "coords": "26.65° N, 87.15° E", "bounds": {"west": 86.8, "south": 26.2, "east": 87.2, "north": 26.6}},
    "Nepal Terai · Bagmati Basin": {"district": "Rautahat · Sarlahi", "coords": "27.02° N, 85.38° E", "bounds": {"west": 84.8, "south": 26.75, "east": 85.35, "north": 27.25}},
    "Nepal Terai · Gandaki Basin": {"district": "Nawalpur · Chitwan", "coords": "27.53° N, 84.35° E", "bounds": {"west": 84.1, "south": 27.3, "east": 84.6, "north": 27.8}},
    "Nepal · Bhote Koshi–Trishuli (26 Aug 2026)": {"district": "Rasuwa · Nuwakot", "coords": "27.98° N, 84.89° E", "bounds": {"west": 84.405, "south": 27.682, "east": 85.381, "north": 28.280}, "event": True},
    "Assam · Brahmaputra Valley": {"district": "Dibrugarh · Dhemaji", "coords": "27.48° N, 94.92° E", "bounds": {"west": 94.5, "south": 27.1, "east": 95.3, "north": 27.8}},
    "Bangladesh · Jamuna Basin": {"district": "Sirajganj · Gaibandha", "coords": "24.45° N, 89.70° E", "bounds": {"west": 89.3, "south": 24.1, "east": 90.1, "north": 24.8}},
}


def render_leaflet_map(result: dict, bounds: dict, height: int = 420, *,
                       show_settlements: bool = True, show_roads: bool = True,
                       tile_url: str | None = None, label: str = "GEE flood layer") -> None:
    """Render GEE/OSM layers without Folium so the app works in the project venv."""
    payload = {
        "bounds": bounds,
        "flood": result.get("flood_tile_url") if tile_url is None else tile_url,
        "roads": result.get("roads_geojson") if show_roads else None,
        "settlements": result.get("settlements_geojson") if show_settlements else None,
        "label": label,
    }
    encoded = json.dumps(payload, ensure_ascii=True).replace("<", "\\u003c")
    map_id = f"map-{abs(hash((encoded, height))) % 10**12}"
    page = f'''<!doctype html><html><head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>html,body,#{map_id}{{height:100%;width:100%;margin:0}} .leaflet-container{{font:13px Inter,Arial,sans-serif}}</style>
</head><body><div id="{map_id}"></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const data={encoded};
const b=data.bounds, bounds=[[b.south,b.west],[b.north,b.east]];
const map=L.map({json.dumps(map_id)}).fitBounds(bounds);
const base=L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',{{maxZoom:19,attribution:'&copy; OpenStreetMap contributors'}}).addTo(map);
const overlays={{}};
if(data.flood) overlays[data.label]=L.tileLayer(data.flood,{{opacity:0.78,attribution:'Google Earth Engine'}}).addTo(map);
if(data.roads) overlays['Exposed roads']=L.geoJSON(data.roads,{{style:{{color:'#ea580c',weight:3}}}}).addTo(map);
if(data.settlements) overlays['Affected settlements']=L.geoJSON(data.settlements,{{style:{{color:'#2563eb',weight:2,fillColor:'#38bdf8',fillOpacity:0.28}},pointToLayer:(_f,ll)=>L.circleMarker(ll,{{radius:5,color:'#ea580c',fillOpacity:.9}}),onEachFeature:(f,l)=>{{const p=f.properties||{{}};const n=p.name||p.place;if(n)l.bindTooltip(String(n))}}}}).addTo(map);
L.rectangle(bounds,{{color:'#f59e0b',weight:2,fill:false}}).addTo(map);
if(Object.keys(overlays).length)L.control.layers({{'OpenStreetMap':base}},overlays,{{collapsed:false}}).addTo(map);
setTimeout(()=>map.invalidateSize(),100);
</script></body></html>'''
    components.html(page, height=height, scrolling=False)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&family=Space+Grotesk:wght@500;600;700;800&display=swap');

:root {
  --bg-page: #F8FAFC;
  --bg-card: #FFFFFF;
  --bg-card-hover: #F1F5F9;
  --bg-subtle: #F1F5F9;
  --border-card: #E2E8F0;
  --border-focus: #0284C7;
  --text-primary: #0F172A;
  --text-secondary: #475569;
  --text-muted: #64748B;
  --accent-cyan: #0284C7;
  --accent-blue: #2563EB;
  --flood-orange: #EA580C;
  --pill-bg: #E0F2FE;
  --pill-text: #0369A1;
}

html, body, [class*="css"] {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  color: var(--text-primary);
}

.stApp {
  background-color: var(--bg-page);
  background-image: 
    radial-gradient(circle at 92% 5%, rgba(2, 132, 199, 0.05) 0%, transparent 45%),
    radial-gradient(circle at 8% 25%, rgba(37, 99, 235, 0.04) 0%, transparent 50%),
    radial-gradient(circle at 50% 90%, rgba(226, 232, 240, 0.4) 0%, transparent 60%);
  color: var(--text-primary);
}

header[data-testid="stHeader"] { 
  background: transparent; 
}

section[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #FFFFFF 0%, #F8FAFC 100%) !important;
  border-right: 1px solid var(--border-card);
  box-shadow: 2px 0 12px rgba(15, 23, 42, 0.02);
}
section[data-testid="stSidebar"] > div {
  padding-top: 1.2rem;
}

.block-container {
  padding: 1.2rem 2.2rem 3.5rem;
  max-width: 1600px;
}

h1, h2, h3, h4, .space-heading {
  font-family: 'Space Grotesk', sans-serif !important;
  letter-spacing: -0.025em;
  color: var(--text-primary);
  font-weight: 700;
}

.telemetry-mono {
  font-family: 'JetBrains Mono', monospace;
  letter-spacing: 0.03em;
}

/* Bright Aerospace Top HUD Bar */
.aerospace-hud {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #FFFFFF;
  border: 1px solid var(--border-card);
  border-radius: 12px;
  padding: 11px 20px;
  margin-bottom: 22px;
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.04);
}
.hud-telemetry {
  display: flex;
  gap: 20px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11.5px;
  color: var(--text-secondary);
}
.hud-telemetry span {
  color: var(--accent-cyan);
  font-weight: 600;
}
.hud-tag {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  font-weight: 600;
  color: var(--pill-text);
  background: var(--pill-bg);
  border: 1px solid #BAE6FD;
  padding: 5px 12px;
  border-radius: 20px;
}
.pulse-dot {
  width: 7.5px;
  height: 7.5px;
  border-radius: 50%;
  background: #0284C7;
  box-shadow: 0 0 8px rgba(2, 132, 199, 0.7);
  animation: pulse-light 2s infinite;
}
@keyframes pulse-light {
  0% { transform: scale(0.95); opacity: 0.75; }
  50% { transform: scale(1.3); opacity: 1; }
  100% { transform: scale(0.95); opacity: 0.75; }
}

/* Brand in Sidebar */
.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 0 0 24px;
}
.brand-mark {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: linear-gradient(135deg, #0284C7 0%, #2563EB 100%);
  display: grid;
  place-items: center;
  color: #FFFFFF;
  box-shadow: 0 4px 16px rgba(2, 132, 199, 0.28);
}
.brand-name {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 18.5px;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: var(--text-primary);
  line-height: 1.15;
}
.brand-sub {
  color: var(--accent-cyan);
  font-size: 9.5px;
  letter-spacing: 0.14em;
  font-weight: 600;
  font-family: 'JetBrains Mono', monospace;
  margin-top: 2px;
}

.side-caption {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--text-muted);
  font-weight: 700;
  margin: 22px 0 8px;
}

/* Bright Hero Section */
.hero-card {
  position: relative;
  border-radius: 18px;
  overflow: hidden;
  border: 1px solid var(--border-card);
  background: #FFFFFF;
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.05);
  margin-bottom: 26px;
}
.hero-bg-img {
  width: 100%;
  height: 350px;
  object-fit: cover;
  object-position: center;
  display: block;
}
.hero-overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.15) 0%, rgba(15, 23, 42, 0.72) 55%, rgba(15, 23, 42, 0.94) 100%);
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  padding: 30px 36px;
}
.hero-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(255, 255, 255, 0.5);
  color: #0369A1;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  padding: 5px 13px;
  border-radius: 20px;
  width: fit-content;
  margin-bottom: 12px;
  font-weight: 600;
  box-shadow: 0 2px 8px rgba(0,0,0,0.15);
}
.hero-title {
  font-family: 'Space Grotesk', sans-serif;
  font-size: clamp(28px, 3.8vw, 44px);
  font-weight: 800;
  letter-spacing: -0.035em;
  color: #FFFFFF;
  margin: 0 0 10px;
  line-height: 1.14;
  text-shadow: 0 2px 14px rgba(0,0,0,0.5);
}
.hero-sub {
  color: #E2E8F0;
  font-size: clamp(14px, 1.2vw, 16px);
  line-height: 1.55;
  max-width: 860px;
  margin: 0 0 14px;
}
.hero-quote {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 14.5px;
  color: #38BDF8;
  font-weight: 600;
  letter-spacing: 0.03em;
  border-left: 2px solid #38BDF8;
  padding-left: 12px;
  margin-top: 4px;
}

/* Crisp White Cards */
.card {
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: 14px;
  padding: 18px 20px;
  box-shadow: 0 4px 18px rgba(15, 23, 42, 0.04);
  transition: all 0.22s ease;
  position: relative;
  overflow: hidden;
}
.card:hover {
  border-color: #BAE6FD;
  box-shadow: 0 10px 28px rgba(2, 132, 199, 0.08);
  transform: translateY(-1px);
}
.card::before {
  content: "";
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 2px;
  background: linear-gradient(90deg, transparent, rgba(2, 132, 199, 0.4), transparent);
}

.metric-label {
  color: var(--text-muted);
  font-size: 11.5px;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  font-family: 'JetBrains Mono', monospace;
}
.metric-value {
  color: var(--text-primary);
  font-family: 'Space Grotesk', sans-serif;
  font-weight: 700;
  font-size: 28px;
  letter-spacing: -0.03em;
  margin: 8px 0 4px;
}
.metric-note {
  color: var(--text-secondary);
  font-size: 11.5px;
}
.metric-icon-wrap {
  float: right;
  width: 38px;
  height: 38px;
  border-radius: 10px;
  background: #E0F2FE;
  color: #0284C7;
  display: grid;
  place-items: center;
  font-size: 19px;
}

.section-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 15px;
  margin: 28px 0 14px;
}
.section-head h3 {
  font-family: 'Space Grotesk', sans-serif !important;
  font-size: 19px;
  margin: 0;
  color: var(--text-primary);
}
.section-head p {
  color: var(--text-secondary);
  font-size: 12.5px;
  margin: 4px 0 0;
}

.confidence-track {
  height: 8px;
  border-radius: 8px;
  background: #E2E8F0;
  margin: 12px 0 6px;
  overflow: hidden;
}
.confidence-fill {
  height: 100%;
  border-radius: 8px;
  background: linear-gradient(90deg, #2563EB, #0284C7);
  box-shadow: 0 0 8px rgba(2, 132, 199, 0.4);
}

.note {
  border: 1px solid #FED7AA;
  background: #FFF7ED;
  border-radius: 12px;
  padding: 14px 16px;
  color: #9A3412;
  font-size: 12px;
  line-height: 1.55;
}

.workflow {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 10px;
}
.step {
  background: #FFFFFF;
  border: 1px solid var(--border-card);
  border-radius: 12px;
  padding: 14px;
  min-height: 102px;
  position: relative;
  box-shadow: 0 2px 10px rgba(15, 23, 42, 0.03);
  transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}
.step:hover {
  transform: translateY(-2px);
  border-color: #0284C7;
  box-shadow: 0 8px 20px rgba(2, 132, 199, 0.09);
}
.step-n {
  color: var(--accent-cyan);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.12em;
  font-family: 'JetBrains Mono', monospace;
}
.step-title {
  color: var(--text-primary);
  font-family: 'Space Grotesk', sans-serif;
  font-size: 12.5px;
  font-weight: 700;
  margin: 6px 0 4px;
}
.step-copy {
  color: var(--text-secondary);
  font-size: 10.5px;
  line-height: 1.4;
}

/* Streamlit component overrides for bright theme */
div[data-testid="stDataFrame"] {
  border: 1px solid var(--border-card);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.04);
}
.stButton>button, .stDownloadButton>button {
  border-radius: 10px;
  border: 1px solid var(--border-card);
  background: #FFFFFF;
  color: var(--text-primary);
  font-weight: 600;
  font-family: 'Inter', sans-serif;
  box-shadow: 0 2px 6px rgba(15, 23, 42, 0.04);
  transition: all 0.22s ease;
}
.stButton>button[kind="primary"] {
  background: linear-gradient(135deg, #0284C7 0%, #2563EB 100%) !important;
  border: 0 !important;
  color: #FFFFFF !important;
  font-weight: 700;
  box-shadow: 0 4px 16px rgba(2, 132, 199, 0.3) !important;
}
.stButton>button:hover, .stDownloadButton>button:hover {
  border-color: #0284C7;
  color: #0284C7;
  box-shadow: 0 4px 14px rgba(2, 132, 199, 0.15);
}
.stButton>button[kind="primary"]:hover {
  color: #FFFFFF !important;
  box-shadow: 0 6px 20px rgba(2, 132, 199, 0.4) !important;
}
div[data-baseweb="select"]>div, div[data-baseweb="input"]>div {
  background: #FFFFFF !important;
  border-color: #CBD5E1 !important;
  border-radius: 9px;
  color: var(--text-primary) !important;
}
div[data-baseweb="select"]>div:hover, div[data-baseweb="input"]>div:hover {
  border-color: #0284C7 !important;
}
label, div[data-testid="stWidgetLabel"] p {
  color: var(--text-primary) !important;
  font-size: 12.5px !important;
  font-weight: 600;
}
.stCaption, small {
  color: var(--text-secondary) !important;
}

/* Media Queries */
@media (max-width: 900px) {
  .workflow { grid-template-columns: repeat(2, 1fr); }
  .hero-overlay { padding: 20px; }
  .aerospace-hud { flex-direction: column; align-items: flex-start; gap: 8px; }
}
</style>
""", unsafe_allow_html=True)


def river_svg(after: bool, region: str) -> str:
    patches = """
    <g fill="#0284C7" opacity=".88" filter="drop-shadow(0 2px 4px rgba(2,132,199,0.3))">
      <path d="M92 79l20-8 12 11-8 13-25 2z"/><path d="M157 122l17-8 19 9-7 18-24 2z"/>
      <path d="M250 70l16-11 21 7 3 15-22 10-19-7z"/><path d="M309 145l21-12 20 8-4 17-25 8z"/>
      <path d="M387 91l20-8 12 12-5 16-22 5z"/><path d="M213 183l17-7 20 7 4 15-21 12-19-9z"/>
      <path d="M64 170l13-8 16 6-2 16-20 5z"/><path d="M354 197l20-10 16 9-8 16-24-2z"/>
      <path d="M115 208l22-7 12 10-6 13-23 2z"/>
    </g>
    <g fill="#EA580C" opacity=".95">
      <circle cx="152" cy="116" r="4"/><circle cx="258" cy="74" r="4"/><circle cx="315" cy="142" r="4"/>
    </g>""" if after else ""
    extra = "" if after else '<text x="18" y="25" fill="#475569" font-family="JetBrains Mono, monospace" font-size="10" font-weight="600" letter-spacing="1">PRE-FLOOD BASELINE (SAR C-BAND)</text>'
    after_tag = '<text x="18" y="25" fill="#0284C7" font-family="JetBrains Mono, monospace" font-size="10" font-weight="600" letter-spacing="1">EVENT DETECTION (INUNDATION DETECTED)</text>' if after else ""
    
    return f'''<svg viewBox="0 0 500 270" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{'Post' if after else 'Pre'} flood satellite radar image">
    <defs>
      <linearGradient id="groundLight" x2="0" y2="1">
        <stop stop-color="#F1F5F9"/>
        <stop offset="1" stop-color="#E2E8F0"/>
      </linearGradient>
      <pattern id="grainLight" width="28" height="28" patternUnits="userSpaceOnUse">
        <path d="M0 14h28M14 0v28" stroke="#CBD5E1" stroke-width=".5" opacity=".35"/>
        <circle cx="14" cy="14" r=".7" fill="#94A3B8" opacity=".4"/>
      </pattern>
    </defs>
    <rect width="500" height="270" fill="url(#groundLight)"/>
    <rect width="500" height="270" fill="url(#grainLight)"/>
    <!-- Topographic contour lines -->
    <path d="M-10 40Q120 20 240 60T510 30" fill="none" stroke="#CBD5E1" stroke-width="1.2" stroke-dasharray="4 4"/>
    <path d="M-10 120Q150 140 300 110T510 150" fill="none" stroke="#CBD5E1" stroke-width="1.2" stroke-dasharray="4 4"/>
    <path d="M-10 210Q180 180 320 230T510 190" fill="none" stroke="#CBD5E1" stroke-width="1.2" stroke-dasharray="4 4"/>
    <!-- River channel baseline -->
    <g fill="none" stroke="#94A3B8" stroke-width="24" stroke-linecap="round"><path d="M257 -20 C230 23 285 38 250 74S267 116 241 148s29 45 3 79 5 35-7 63"/></g>
    <g fill="none" stroke="#0284C7" stroke-width="11" stroke-linecap="round"><path d="M257 -20 C230 23 285 38 250 74S267 116 241 148s29 45 3 79 5 35-7 63"/></g>
    <!-- Radar coordinates overlay -->
    <g fill="none" stroke="#0284C7" stroke-width=".8" opacity=".22"><path d="M0 88l156 30 160-15 184 30M10 224l132-51 185 34 173-50M95 0l32 270M416 0l-35 270"/></g>
    {patches}{extra}{after_tag}
    <rect x="12" y="235" width="90" height="23" rx="5" fill="#FFFFFF" opacity=".95" stroke="#CBD5E1" stroke-width="1"/>
    <text x="18" y="250" fill="#0284C7" font-family="JetBrains Mono, monospace" font-size="9.5" font-weight="600">SENTINEL-1 · 10m</text>
    <text x="435" y="253" fill="#475569" font-family="JetBrains Mono, monospace" font-size="9.5" font-weight="600">GRID N ↑</text>
    </svg>'''


def flood_map(region: str, settlements: bool, roads: bool) -> str:
    road = '<g fill="none" stroke="#D97706" stroke-width="2" stroke-dasharray="5 4"><path d="M28 247Q150 214 235 156T478 42"/><path d="M77 30Q143 87 217 103t194 89"/></g>' if roads else ''
    homes = '<g fill="#EA580C" stroke="#FFFFFF" stroke-width="2"><circle cx="102" cy="110" r="6.5"/><circle cx="145" cy="146" r="6.5"/><circle cx="330" cy="77" r="6.5"/><circle cx="370" cy="177" r="6.5"/><circle cx="250" cy="215" r="6.5"/><circle cx="416" cy="124" r="6.5"/></g>' if settlements else ''
    
    return f'''<svg viewBox="0 0 600 315" xmlns="http://www.w3.org/2000/svg" aria-label="Illustrative flood extent map for {region}">
    <defs>
      <linearGradient id="mapBgLight" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stop-color="#F8FAFC"/>
        <stop offset="100%" stop-color="#EDF2F7"/>
      </linearGradient>
      <pattern id="geogridLight" width="40" height="40" patternUnits="userSpaceOnUse">
        <path d="M40 0H0V40" fill="none" stroke="#CBD5E1" stroke-width=".6" opacity=".4"/>
        <circle cx="20" cy="20" r=".8" fill="#94A3B8" opacity=".5"/>
      </pattern>
    </defs>
    <rect width="600" height="315" fill="url(#mapBgLight)"/>
    <rect width="600" height="315" fill="url(#geogridLight)"/>
    
    <!-- Elevation contours -->
    <path d="M0 45Q180 30 320 65T600 40" fill="none" stroke="#CBD5E1" stroke-width="1.2"/>
    <path d="M0 130Q160 160 340 125T600 150" fill="none" stroke="#CBD5E1" stroke-width="1.2"/>
    <path d="M0 240Q200 210 380 250T600 230" fill="none" stroke="#CBD5E1" stroke-width="1.2"/>
    
    <!-- River corridors -->
    <path d="M-20 62Q78 30 151 74T277 109 397 83 620 117M-14 257Q95 208 186 226t190 16 243-63" fill="none" stroke="#BAE6FD" stroke-width="26" opacity=".8"/>
    <path d="M-20 60Q78 28 151 72T277 107 397 81 620 115M-14 255Q95 206 186 224t190 16 243-63" fill="none" stroke="#0284C7" stroke-width="12"/>
    
    <!-- Detected Inundation Polygons (Vibrant Cyan-Sky Blue) -->
    <path d="M90 87l56-20 48 14 17 45-32 33-64-4-39-31zM293 48l60-8 40 23-4 42-53 19-49-25zM342 183l55-27 46 17 16 47-52 25-63-18zM158 210l44-18 31 24-12 39-52 11-26-24z" 
          fill="#38BDF8" fill-opacity=".55" stroke="#0284C7" stroke-width="2" filter="drop-shadow(0 2px 6px rgba(2,132,199,0.3))"/>
    
    {road}{homes}
    
    <!-- Map HUD Labels -->
    <g fill="#0F172A" font-family="Space Grotesk, sans-serif" font-weight="700">
      <text x="20" y="26" font-size="12" letter-spacing="1">{region.upper()}</text>
    </g>
    <g fill="#475569" font-family="JetBrains Mono, monospace" font-size="9.5" font-weight="500">
      <text x="20" y="42">SENTINEL-1 C-SAR · REVISIT CYCLE 6D</text>
      <text x="440" y="295">SCALE 1:50,000 · 10 km</text>
    </g>
    
    <!-- Symbology Legend -->
    <g transform="translate(18 282)">
      <rect width="11" height="11" rx="2" fill="#38BDF8" stroke="#0284C7" stroke-width="1"/>
      <text x="17" y="9.5" fill="#0F172A" font-size="9" font-family="Inter, sans-serif" font-weight="500">Detected inundation</text>
      <circle cx="140" cy="5.5" r="5" fill="#EA580C"/>
      <text x="152" y="9.5" fill="#0F172A" font-size="9" font-family="Inter, sans-serif" font-weight="500">Settlement</text>
      <path d="M230 5.5h16" stroke="#D97706" stroke-width="2" stroke-dasharray="4 3"/>
      <text x="252" y="9.5" fill="#0F172A" font-size="9" font-family="Inter, sans-serif" font-weight="500">Road network</text>
    </g>
    </svg>'''


def render_svg(svg: str, height: int, background: str = "#FFFFFF") -> None:
    svg_data = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    components.html(
        f"""<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1">
        <style>html,body{{margin:0;padding:0;background:{background};overflow:hidden;border-radius:12px;}}
        img{{display:block;width:100%;height:auto;border-radius:12px;border:1px solid #E2E8F0;}}</style></head>
        <body><img alt="Illustrative flood mapping panel" src="data:image/svg+xml;base64,{svg_data}"></body></html>""",
        height=height,
        scrolling=False,
    )


def render_swipe_slider(img_before: str, img_after: str) -> None:
    """Interactive swipe slider comparing pre-flood baseline and post-flood event satellite data."""
    slider_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ background: transparent; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
        .comparison-wrapper {{
          position: relative;
          width: 100%;
          height: 380px;
          border-radius: 14px;
          overflow: hidden;
          border: 1px solid #CBD5E1;
          box-shadow: 0 4px 20px rgba(15, 23, 42, 0.08);
          user-select: none;
        }}
        .img-layer {{
          position: absolute;
          top: 0; left: 0;
          width: 100%; height: 100%;
          object-fit: cover;
        }}
        .top-layer {{
          width: 50%;
          overflow: hidden;
          border-right: 3px solid #0284C7;
          box-shadow: 2px 0 14px rgba(2, 132, 199, 0.35);
          z-index: 2;
        }}
        .top-layer .img-layer {{
          width: 100vw;
          max-width: none;
        }}
        .slider-handle {{
          position: absolute;
          top: 0; bottom: 0;
          left: 50%;
          width: 4px;
          cursor: ew-resize;
          z-index: 10;
        }}
        .handle-knob {{
          position: absolute;
          top: 50%;
          left: 50%;
          transform: translate(-50%, -50%);
          width: 42px;
          height: 42px;
          border-radius: 50%;
          background: #FFFFFF;
          border: 2px solid #0284C7;
          box-shadow: 0 4px 14px rgba(15, 23, 42, 0.2);
          display: flex;
          align-items: center;
          justify-content: center;
          color: #0284C7;
          font-size: 13px;
          font-weight: bold;
        }}
        .hud-tag {{
          position: absolute;
          top: 14px;
          padding: 6px 14px;
          background: rgba(255, 255, 255, 0.94);
          border: 1px solid #CBD5E1;
          backdrop-filter: blur(8px);
          border-radius: 8px;
          font-size: 11px;
          font-family: monospace;
          font-weight: 600;
          z-index: 5;
          box-shadow: 0 2px 10px rgba(0,0,0,0.12);
        }}
        .tag-left {{ left: 14px; color: #475569; }}
        .tag-right {{ right: 14px; color: #0369A1; border-color: #BAE6FD; background: rgba(224, 242, 254, 0.95); }}
        .slider-input {{
          position: absolute;
          inset: 0;
          opacity: 0;
          width: 100%;
          height: 100%;
          cursor: ew-resize;
          z-index: 20;
        }}
      </style>
    </head>
    <body>
      <div class="comparison-wrapper" id="compContainer">
        <!-- Background: Post-flood event -->
        <img class="img-layer" src="{img_after}" alt="Post-flood event satellite data">
        <div class="hud-tag tag-right">POST-FLOOD EVENT · INUNDATION DETECTED</div>

        <!-- Foreground: Pre-flood baseline -->
        <div class="top-layer" id="topLayer">
          <img class="img-layer" id="topImg" src="{img_before}" alt="Pre-flood baseline satellite data">
          <div class="hud-tag tag-left">PRE-FLOOD BASELINE (DRY SEASON)</div>
        </div>

        <!-- Draggable Handle -->
        <div class="slider-handle" id="sliderHandle">
          <div class="handle-knob">◀ ▶</div>
        </div>

        <input type="range" min="0" max="100" value="50" class="slider-input" id="rangeInput" aria-label="Swipe slider">
      </div>

      <script>
        const input = document.getElementById('rangeInput');
        const topLayer = document.getElementById('topLayer');
        const handle = document.getElementById('sliderHandle');
        const container = document.getElementById('compContainer');
        const topImg = document.getElementById('topImg');

        function updateSlider(val) {{
          topLayer.style.width = val + '%';
          handle.style.left = val + '%';
          topImg.style.width = container.offsetWidth + 'px';
        }}

        window.addEventListener('resize', () => {{
          topImg.style.width = container.offsetWidth + 'px';
        }});

        topImg.style.width = container.offsetWidth + 'px';

        input.addEventListener('input', (e) => {{
          updateSlider(e.target.value);
        }});
      </script>
    </body>
    </html>
    """
    components.html(slider_html, height=395, scrolling=False)


# ==========================================
# SIDEBAR NAVIGATION & SETTINGS
# ==========================================
with st.sidebar:
    st.markdown("""
    <div class="brand">
      <div class="brand-mark">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="2"></circle>
          <path d="M16.24 7.76a6 6 0 0 1 0 8.49m-8.48-.01a6 6 0 0 1 0-8.49m11.31-2.82a10 10 0 0 1 0 14.14m-14.14 0a10 10 0 0 1 0-14.14"></path>
        </svg>
      </div>
      <div>
        <div class="brand-name">TERAI FLOODWATCH</div>
        <div class="brand-sub">SATELLITE INTELLIGENCE</div>
      </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="side-caption">Navigation</div>', unsafe_allow_html=True)
    page = st.radio("Navigate", ["Overview", "Impact & priorities", "Data management report", "Methodology"], label_visibility="collapsed")
    
    st.markdown('<div class="side-caption">Analysis parameters</div>', unsafe_allow_html=True)
    region = st.selectbox("Region of interest", list(REGIONS))
    sensor = st.selectbox("Detection sensor", ["Sentinel-1 SAR", "Sentinel-1 + Sentinel-2", "Sentinel-1 + Landsat 8/9"])
    st.caption("SAR leads detection with 100% cloud penetration. Optical validation is optional when cloud cover allows.")
    
    today = date.today()
    if REGIONS[region].get("event"):
        default_before = (date(2026, 8, 1), date(2026, 8, 25))
        default_after = (date(2026, 8, 26), date(2026, 9, 5))
    else:
        default_before = (today - timedelta(days=46), today - timedelta(days=27))
        default_after = (today - timedelta(days=19), today - timedelta(days=7))
    before_range = st.date_input(
        "Pre-flood baseline window", value=default_before, max_value=today,
        key=f"baseline-window-{region}",
    )
    after_range = st.date_input(
        "Post-flood event window", value=default_after, max_value=today,
        key=f"event-window-{region}",
    )
    threshold = st.slider("SAR change threshold (dB)", 0.05, 0.50, 0.20, 0.01, help="Calibrated threshold for backscatter difference classification.")
    
    st.markdown('<div class="side-caption">Geospatial overlays</div>', unsafe_allow_html=True)
    show_settlements = st.checkbox("Settlements & building clusters", value=True)
    show_roads = st.checkbox("Transportation & road network", value=True)
    
    run = st.button("⚡  Analyze flood event", type="primary", use_container_width=True)
    if run:
        if len(before_range) != 2 or len(after_range) != 2:
            st.error("Select both start and end dates for each period.")
        elif before_range[0] >= before_range[1] or after_range[0] >= after_range[1]:
            st.error("Each date window needs a start date before its end date.")
        elif before_range[1] >= after_range[0]:
            st.error("The baseline period must end before the post-flood period begins.")
        else:
            request_payload = {
                "before_start": before_range[0].isoformat(),
                "before_end": (before_range[1] + timedelta(days=1)).isoformat(),
                "after_start": after_range[0].isoformat(),
                "after_end": (after_range[1] + timedelta(days=1)).isoformat(),
                "region_name": region,
                "region": "custom",
                "bounds": REGIONS[region]["bounds"],
                "optical_sensor": {
                    "Sentinel-1 SAR": "none",
                    "Sentinel-1 + Sentinel-2": "sentinel2",
                    "Sentinel-1 + Landsat 8/9": "landsat89",
                }[sensor],
            }
            selection = {
                "region": region,
                "sensor": sensor,
                "before": [value.isoformat() for value in before_range],
                "after": [value.isoformat() for value in after_range],
            }
            st.session_state.pop("gee_error", None)
            try:
                with st.spinner("Connecting to Earth Engine and analyzing satellite imagery…"):
                    api_response = requests.post(ANALYZE_URL, json=request_payload, timeout=300)
                    api_response.raise_for_status()
                    live_result = api_response.json()
                if not isinstance(live_result, dict):
                    raise ValueError("The analysis API returned an invalid response.")
                st.session_state.gee_result = live_result
                st.session_state.gee_selection = selection
                st.toast("Earth Engine analysis completed.", icon="🛰️")
            except requests.HTTPError as exc:
                try:
                    detail = exc.response.json().get("error", str(exc))
                except (AttributeError, ValueError):
                    detail = str(exc)
                st.session_state.gee_error = f"Analysis API error: {detail}"
            except requests.RequestException as exc:
                st.session_state.gee_error = (
                    f"Could not reach {API_URL}. Start the Flask backend in its own terminal. Details: {exc}"
                )
            except ValueError as exc:
                st.session_state.gee_error = str(exc)
        
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    st.caption("OPERATIONAL STATUS · Earth Engine connected after a successful analysis; otherwise illustrative demo panels")

d = REGIONS[region]
current_selection = {
    "region": region,
    "sensor": sensor,
    "before": [value.isoformat() for value in before_range] if len(before_range) == 2 else [],
    "after": [value.isoformat() for value in after_range] if len(after_range) == 2 else [],
}
live_result = st.session_state.get("gee_result") if st.session_state.get("gee_selection") == current_selection else None
if st.session_state.get("gee_error"):
    st.error(st.session_state["gee_error"])
if st.session_state.get("gee_selection") and st.session_state["gee_selection"] != current_selection:
    st.warning("Settings changed since the last live analysis. Run analysis again to refresh the map and report.")
if d.get("event"):
    st.caption("Bhote Koshi preset uses the 26 Aug 2026 event dates. The map is this app's Sentinel-1 estimate, not the official UNOSAT impact layer.")


# ==========================================
# TOP AEROSPACE HUD BAR (LIGHT THEME)
# ==========================================
st.markdown(f"""
<div class="aerospace-hud">
  <div class="hud-telemetry">
    <div>SATELLITE: <span>SENTINEL-1A (C-SAR)</span></div>
    <div>ORBIT: <span>693 KM POLAR LEO</span></div>
    <div>COORDINATES: <span>{d['coords']}</span></div>
    <div>POLARIZATION: <span>VV + VH</span></div>
  </div>
  <div class="hud-tag">
    <div class="pulse-dot"></div>
    <span>EARTH OBSERVATION ACTIVE</span>
  </div>
</div>
""", unsafe_allow_html=True)


# ==========================================
# PAGE 1: OVERVIEW
# ==========================================
if page == "Overview":
    # Luminous Hero Section
    st.markdown(f"""
    <div class="hero-card">
      <img class="hero-bg-img" src="{IMG_HERO}" alt="Earth observation satellite orbiting over Nepal Terai">
      <div class="hero-overlay">
        <div class="hero-badge">ESA COPERNICUS COMPATIBLE · RAPID MAPPING INITIATIVE</div>
        <div class="hero-title">SEE THE FLOOD. MAP THE IMPACT. ACT FASTER.</div>
        <div class="hero-sub">
          Satellite-powered flood extent mapping and settlement impact assessment for Nepal's vulnerable Terai region.
          Overcoming persistent monsoon cloud barriers through active microwave synthetic aperture radar.
        </div>
        <div class="hero-quote">
          “From pixels in orbit to decisions on the ground.”
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Show numeric values available from the live analysis.
    metric_sources = [
        ("flood_area_km2", "Newly detected inundation", "km²", "Earth Engine candidate extent"),
        ("settlements_affected", "Settlements affected", "", "Mapped OSM intersections"),
        ("roads_affected_km", "Roads affected", "km", "OpenStreetMap intersection"),
        ("population_affected", "Population affected", "people", "WorldPop estimate"),
    ]
    live_values = {
        "flood_area_km2": live_result.get("candidate_flood_area_km2") if live_result else None,
        "settlements_affected": live_result.get("affected_settlements") if live_result else None,
        "roads_affected_km": live_result.get("affected_roads_km") if live_result else None,
        "population_affected": live_result.get("population_exposed_estimate") if live_result else None,
    }
    metrics = []
    for key, label, unit, source_note in metric_sources:
        raw_value = live_values.get(key)
        if isinstance(raw_value, (int, float)) and not isinstance(raw_value, bool):
            shown = f"{raw_value:,.1f}" if isinstance(raw_value, float) and not raw_value.is_integer() else f"{raw_value:,.0f}"
            metrics.append((label, f"{shown}{f' {unit}' if unit else ''}", source_note))
    if metrics:
        for offset in range(0, len(metrics), 4):
            row = metrics[offset:offset + 4]
            cols = st.columns(len(row), gap="medium")
            for col, (label, value, note) in zip(cols, row):
                with col:
                    st.markdown(f"""
                    <div class="card">
                      <div class="metric-label">{label}</div>
                      <div class="metric-value">{value}</div>
                      <div class="metric-note">{note}</div>
                    </div>
                    """, unsafe_allow_html=True)
    else:
        st.info("No live metric values yet. Run an Earth Engine analysis to show available parameters. Unavailable parameters are hidden.")

    # About The Project & Problem Section
    st.markdown('<div class="section-head"><div><h3>About The Project & Terai Flood Vulnerability</h3><p>Why satellite remote sensing is vital for Nepal\'s southern lowlands</p></div></div>', unsafe_allow_html=True)
    ab1, ab2 = st.columns([1.1, 1], gap="medium")
    with ab1:
        st.markdown(f"""
        <div class="card" style="height:100%">
          <div class="metric-label">PROBLEM STATEMENT & REGIONAL CONTEXT</div>
          <p style="font-size:13px;color:#334155;line-height:1.65;margin-top:8px;">
            The Nepal Terai constitutes the northern fringe of the Indo-Gangetic Plain, characterized by dense rural settlements, fertile agrarian floodplains, and extreme susceptibility to recurring monsoon flash floods across the Koshi, Bagmati, and Gandaki river basins. Heavy monsoon precipitation routinely causes transboundary river overflows, submerging thousands of hectares within hours.
          </p>
          <p style="font-size:13px;color:#475569;line-height:1.65;">
            During intense weather emergencies, traditional optical satellites (e.g. Landsat, basic multispectral) are completely obstructed by dense, persistent cloud cover. Terai FloodWatch uses active C-band Synthetic Aperture Radar (SAR) on Sentinel-1, which operates at microwave frequencies to pierce clouds day and night, delivering automated damage assessments to disaster responders before floodwaters recede.
          </p>
          <div style="display:flex;gap:12px;margin-top:14px;">
            <div style="background:#F0F9FF;border:1px solid #BAE6FD;border-radius:8px;padding:8px 12px;flex:1;">
              <div style="font-size:10px;color:#0369A1;font-family:'JetBrains Mono',monospace;font-weight:600;">CLOUD PENETRATION</div>
              <div style="font-size:16px;font-weight:700;color:#0F172A;margin-top:2px;">100% (SAR)</div>
            </div>
            <div style="background:#F0F9FF;border:1px solid #BAE6FD;border-radius:8px;padding:8px 12px;flex:1;">
              <div style="font-size:10px;color:#0369A1;font-family:'JetBrains Mono',monospace;font-weight:600;">GROUND RESOLUTION</div>
              <div style="font-size:16px;font-weight:700;color:#0F172A;margin-top:2px;">10 Meters</div>
            </div>
            <div style="background:#F0F9FF;border:1px solid #BAE6FD;border-radius:8px;padding:8px 12px;flex:1;">
              <div style="font-size:10px;color:#0369A1;font-family:'JetBrains Mono',monospace;font-weight:600;">RESPONSE LATENCY</div>
              <div style="font-size:16px;font-weight:700;color:#0F172A;margin-top:2px;">&lt; 4 Hours</div>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)
    with ab2:
        st.markdown("""
        <div class="card" style="height:100%">
          <div class="metric-label">OPERATIONAL BOTTLENECKS OVERCOME</div>
          <div style="display:flex;flex-direction:column;gap:12px;margin-top:10px;">
            <div style="display:flex;gap:12px;align-items:flex-start;">
              <div style="color:#EA580C;font-size:20px;line-height:1;">⚠️</div>
              <div>
                <b style="color:#0F172A;font-size:13px;">Monsoon Cloud Cover Barrier</b>
                <p style="color:#475569;font-size:12px;margin:2px 0 0;">Optical instruments cannot penetrate monsoon storm clouds. Sentinel-1 microwave pulses guarantee detection.</p>
              </div>
            </div>
            <div style="display:flex;gap:12px;align-items:flex-start;">
              <div style="color:#0284C7;font-size:20px;line-height:1;">🌊</div>
              <div>
                <b style="color:#0F172A;font-size:13px;">Flatland Water Spread Dynamics</b>
                <p style="color:#475569;font-size:12px;margin:2px 0 0;">The low topographical gradient causes floodwaters to expand laterally across multiple districts simultaneously.</p>
              </div>
            </div>
            <div style="display:flex;gap:12px;align-items:flex-start;">
              <div style="color:#2563EB;font-size:20px;line-height:1;">🛰️</div>
              <div>
                <b style="color:#0F172A;font-size:13px;">Automated Settlement Spatial Intersection</b>
                <p style="color:#475569;font-size:12px;margin:2px 0 0;">Immediate overlay against ward boundaries and OpenStreetMap road layers highlights marooned communities.</p>
              </div>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

    # Interactive Before / After Satellite Comparison (Swipe Slider)
    st.markdown('<div class="section-head"><div><h3>Interactive Satellite Comparison & Change Detection</h3><p>Drag the interactive swipe slider below to compare pre-flood baseline vs detected flood extent</p></div><span class="metric-label">INTERACTIVE COMPARISON</span></div>', unsafe_allow_html=True)
    if live_result:
        live_bounds = live_result.get("analysis_bounds", d["bounds"])
        preview_cols = st.columns(2, gap="medium")
        for col, tile_key, label in (
            (preview_cols[0], "before_tile_url", "Pre-flood baseline · Sentinel-1"),
            (preview_cols[1], "after_tile_url", "Post-flood event · Sentinel-1"),
        ):
            with col:
                st.caption(label)
                if live_result.get(tile_key):
                    render_leaflet_map({}, live_bounds, height=360, tile_url=live_result[tile_key], label=label)
                else:
                    st.info("Earth Engine did not return this preview tile.")
        st.caption("These basemap previews and candidate extent tiles come from the selected Earth Engine analysis dates.")
    else:
        render_swipe_slider(IMG_PREFLOOD, IMG_POSTFLOOD)
        st.caption("Illustrative image comparison. Run a live analysis to replace it with selected-date Earth Engine tiles.")

    # Side-by-side Synthetic SAR Panels
    st.markdown('<div class="section-head"><div><h3>Sensor Backscatter Visualization · Dual Swaths</h3><p>Synthetic Aperture Radar specular reflection vs baseline roughness</p></div><span class="metric-label">{}</span></div>'.format(sensor), unsafe_allow_html=True)
    if live_result:
        st.info("Synthetic radar illustrations are hidden after a live analysis. Use the Earth Engine tile maps above for this run.")
    else:
        a, b = st.columns(2, gap="medium")
        with a:
            st.markdown('<div style="font-family:\'JetBrains Mono\',monospace;font-size:11px;color:#475569;font-weight:600;padding-bottom:6px;">PRE-FLOOD BASELINE · ILLUSTRATIVE</div>', unsafe_allow_html=True)
            render_svg(river_svg(False, region), height=270)
        with b:
            st.markdown('<div style="font-family:\'JetBrains Mono\',monospace;font-size:11px;color:#0284C7;font-weight:600;padding-bottom:6px;">POST-FLOOD EXTENT · ILLUSTRATIVE</div>', unsafe_allow_html=True)
            render_svg(river_svg(True, region), height=270)

    # Estimated Flood Extent Map & Exposure
    st.markdown('<div class="section-head"><div><h3>Estimated Flood Extent & Settlement Exposure</h3><p>Geospatial analysis layer focused on {}</p></div><span class="metric-label">{}</span></div>'.format(region, d['district']), unsafe_allow_html=True)
    m1, m2 = st.columns([1.7, 1], gap="medium")
    with m1:
        if live_result:
            render_leaflet_map(live_result, live_result.get("analysis_bounds", d["bounds"]), height=420,
                               show_settlements=show_settlements, show_roads=show_roads)
        else:
            render_svg(flood_map(region, show_settlements, show_roads), height=315, background="#FFFFFF")
    with m2:
        field_accuracy = (live_result.get("field_validation") or {}).get("accuracy_percent") if live_result else None
        if field_accuracy is not None:
            confidence_width = f"{max(0, min(100, field_accuracy)):.1f}%"
            st.markdown(f'''
        <div class="card">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <div>
              <div class="metric-label">Field validation accuracy</div>
              <div class="metric-value" style="color:#0284C7;">{field_accuracy:.1f}%</div>
            </div>
            <div style="font-size:26px;color:#0284C7">◈</div>
          </div>
          <div class="confidence-track">
            <div class="confidence-fill" style="width:{confidence_width}"></div>
          </div>
          <div class="metric-note">Calculated from supplied field validation points only.</div>
        </div>
        ''', unsafe_allow_html=True)
        else:
            st.info("Field validation points were not supplied, so no accuracy score is shown.")
        st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)
        st.markdown('<div class="note"><b>Verification Protocol</b><br>Radar specular reflection identifies smooth surface water. Wet mudflats, dense vegetation canopy, and urban corners can modulate backscatter. Always cross-verify with local administrative ward reports.</div>', unsafe_allow_html=True)

    # Satellite Technology Deep Dive (Sentinel-1 SAR vs Sentinel-2 Optical)
    st.markdown('<div class="section-head"><div><h3>Satellite Technology & Sensor Complementarity</h3><p>Understanding SAR radar backscatter vs multispectral optical reflectance</p></div></div>', unsafe_allow_html=True)
    tech1, tech2 = st.columns(2, gap="medium")
    with tech1:
        st.markdown(f"""
        <div class="card">
          <img src="{IMG_SENTINEL1}" style="width:100%;height:185px;object-fit:cover;border-radius:10px;margin-bottom:12px;border:1px solid #E2E8F0;" alt="Sentinel-1 SAR Satellite">
          <div class="metric-label" style="color:#0284C7;">PRIMARY SENSOR: SENTINEL-1 C-SAR</div>
          <h4 style="margin:4px 0 8px;font-size:16px;color:#0F172A;">Active Microwave Radar (5.405 GHz)</h4>
          <p style="font-size:12px;color:#475569;line-height:1.55;">
            <b>Physics Principle:</b> Smooth open floodwaters act as specular reflectors, scattering radar pulses away from the antenna and returning very low backscatter (&lt; -18 dB, appearing dark). Surrounding rough terrain scatters energy back, producing a high contrast boundary.
          </p>
          <div style="font-family:'JetBrains Mono',monospace;font-size:11px;color:#0369A1;background:#F0F9FF;padding:8px 10px;border-radius:6px;margin-top:8px;border:1px solid #BAE6FD;">
            λ: 5.6 cm (C-band) | Polarization: VV + VH | Swath: 250 km
          </div>
        </div>
        """, unsafe_allow_html=True)
    with tech2:
        st.markdown(f"""
        <div class="card">
          <img src="{IMG_SENTINEL2}" style="width:100%;height:185px;object-fit:cover;border-radius:10px;margin-bottom:12px;border:1px solid #E2E8F0;" alt="Sentinel-2 Optical Satellite">
          <div class="metric-label" style="color:#2563EB;">CROSS-VALIDATION: SENTINEL-2 MSI</div>
          <h4 style="margin:4px 0 8px;font-size:16px;color:#0F172A;">Multispectral Optical (13 Bands)</h4>
          <p style="font-size:12px;color:#475569;line-height:1.55;">
            <b>Physics Principle:</b> When sky conditions permit, Sentinel-2 validates detected floodplains via the Modified Normalized Difference Water Index: <i>MNDWI = (Green - SWIR) / (Green + SWIR)</i>, separating water from dense vegetation and built structures.
          </p>
          <div style="font-family:'JetBrains Mono',monospace;font-size:11px;color:#1E40AF;background:#EFF6FF;padding:8px 10px;border-radius:6px;margin-top:8px;border:1px solid #BFDBFE;">
            Spatial: 10m / 20m | Revisit: 5 days | Band 3 (Green) &amp; Band 11 (SWIR)
          </div>
        </div>
        """, unsafe_allow_html=True)

    # Processing Workflow
    st.markdown('<div class="section-head"><div><h3>Automated 6-Stage Remote Sensing Pipeline</h3><p>From orbital ingestion to spatial impact reporting</p></div></div>', unsafe_allow_html=True)
    workflow_steps = [
        ("Acquire", "Ingest Sentinel-1 GRD event & baseline swaths"),
        ("Preprocess", "Orbit file correction, calibration to σ°, Lee speckle filter"),
        ("Detect change", "Log-ratio backscatter thresholding (Δσ° < -3.2 dB)"),
        ("Filter artifacts", "Apply slope exclusion (>5°) & JRC permanent water mask"),
        ("Assess impact", "Vector overlay with OSM settlements & road networks"),
        ("Export", "Publish GeoJSON polygons, CSV summaries & PDF briefs")
    ]
    st.markdown('<div class="workflow">' + ''.join(
        f'<div class="step"><div class="step-n">STAGE 0{i+1}</div><div class="step-title">{title}</div><div class="step-copy">{copy}</div></div>'
        for i, (title, copy) in enumerate(workflow_steps)
    ) + '</div>', unsafe_allow_html=True)

    # Priority Areas Dataframe
    st.markdown('<div class="section-head"><div><h3>Settlement Priority & Vulnerability Register</h3><p>Ranked for rapid rescue and relief dispatch based on spatial intersections</p></div></div>', unsafe_allow_html=True)
    overview_ranked = rank_settlements(live_result.get("settlements_geojson")) if live_result else []
    if live_result:
        pri = pd.DataFrame([
            {
                "Rank": row["rank"] if row["rank"] is not None else "—",
                "Settlement": row["settlement"],
                "OSM type": row["type"],
                "Exposed population (estimate)": row["exposed_population_estimate"],
                "Tier": row["tier"],
                "Candidate overlap (km²)": row["candidate_overlap_km2"],
                "Conditions": "; ".join(row["conditions"]),
            }
            for row in overview_ranked
        ])
        st.dataframe(pri, width="stretch", hide_index=True)
        st.caption("Ranking is calculated from the live result. Unavailable per-settlement estimates remain unclassified; the polygons are screening candidates.")
    else:
        pri = pd.DataFrame(columns=["Rank", "Settlement", "Exposed population", "Tier", "Conditions"])
        st.info("No settlement-level ranking is available yet. Run live analysis to calculate it; annual-report totals are not enough to rank individual settlements.")

    # Export & Reports
    if live_result:
        geojson = live_result.get("settlements_geojson") or {"type": "FeatureCollection", "features": []}
        report_parameters = {
            "region_name": region,
            "before_start": before_range[0].isoformat(),
            "before_end": (before_range[1] + timedelta(days=1)).isoformat(),
            "after_start": after_range[0].isoformat(),
            "after_end": (after_range[1] + timedelta(days=1)).isoformat(),
        }
        report = build_local_management_report(
            parameters=report_parameters,
            result=live_result,
            ranked_settlements=overview_ranked,
            generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
    else:
        geojson = {"type": "FeatureCollection", "name": "terai_floodwatch_empty", "features": []}
        report = f"# TERAI FLOODWATCH report\n\nRegion: {region}\n\nRun live analysis to generate the impact report."
    csv = pri.to_csv(index=False).encode("utf-8")
    st.markdown('<div class="section-head"><div><h3>Export & Dissemination Hub</h3><p>Download structured emergency layers and operational briefs</p></div></div>', unsafe_allow_html=True)
    ec = st.columns(3)
    ec[0].download_button("↓  Priority Areas · CSV", csv, "terai-floodwatch-priority-areas.csv", "text/csv", use_container_width=True)
    geojson_name = "terai-floodwatch-settlement-intersections.geojson" if live_result else "terai-floodwatch-extent.geojson"
    ec[1].download_button("↓  Impact Layers · GeoJSON", json.dumps(geojson, indent=2), geojson_name, "application/geo+json", use_container_width=True)
    ec[2].download_button("↓  Impact Brief · Markdown", report, "terai-floodwatch-incident-brief.md", "text/markdown", use_container_width=True)


# ==========================================
# PAGE 2: IMPACT & PRIORITIES
# ==========================================
elif page == "Impact & priorities":
    st.markdown(f'''
    <div style="margin-bottom:18px;">
      <div style="font-family:'JetBrains Mono',monospace;color:#0284C7;font-size:11px;letter-spacing:1px;text-transform:uppercase;font-weight:600;">
        SETTLEMENT IMPACT ASSESSMENT · {region}
      </div>
      <h2 style="font-family:'Space Grotesk',sans-serif;font-size:30px;margin:4px 0 6px;color:#0F172A;">
        Exposed Settlements & Rescue Priority Triage
      </h2>
      <p style="color:#475569;font-size:13.5px;max-width:850px;line-height:1.55;">
        Spatial intersection of radar-derived inundation masks against municipal settlement boundaries and OpenStreetMap infrastructure networks.
      </p>
    </div>
    ''', unsafe_allow_html=True)
    
    if live_result:
        ranked = rank_settlements(live_result.get("settlements_geojson"))
        render_leaflet_map(live_result, live_result.get("analysis_bounds", d["bounds"]), height=440,
                           show_settlements=show_settlements, show_roads=show_roads)
        st.markdown('<div class="section-head"><div><h3>Priority settlement triage</h3><p>Ranked by WorldPop estimated exposure with the tier conditions shown per settlement</p></div></div>', unsafe_allow_html=True)
        rules = " · ".join(
            f"{rule['tier']}: {rule['minimum']:,}+" + (f" up to {rule['maximum']:,}" if rule["maximum"] is not None else "")
            for rule in TIER_RULES
        )
        st.caption(f"Prototype thresholds—not official response standards: {rules}. Unavailable estimates stay unclassified.")
        priority_table = pd.DataFrame([
            {
                "Rank": row["rank"] if row["rank"] is not None else "—",
                "Settlement": row["settlement"],
                "OSM type": row["type"],
                "Exposed population estimate": row["exposed_population_estimate"],
                "Tier": row["tier"],
                "Overlap (km²)": row["candidate_overlap_km2"],
                "Conditions": "; ".join(row["conditions"]),
            }
            for row in ranked
        ])
        st.dataframe(priority_table, width="stretch", hide_index=True)
        st.caption("Point place labels use a 300 m buffer. Settlement overlaps may overlap each other; do not sum this ranking to calculate the total exposed population.")

    else:
        st.info("No live settlement ranking is available. Run Earth Engine analysis; estimates that cannot be derived are omitted.")

# ==========================================
# PAGE 3: DATA MANAGEMENT REPORT
# ==========================================
elif page == "Data management report":
    st.markdown(f'''
    <div style="margin-bottom:18px;">
      <div style="font-family:'JetBrains Mono',monospace;color:#0284C7;font-size:11px;letter-spacing:1px;text-transform:uppercase;font-weight:600;">LOCAL REPORT · NO API KEY REQUIRED</div>
      <h2 style="font-family:'Space Grotesk',sans-serif;font-size:30px;margin:4px 0 6px;color:#0F172A;">Data management report</h2>
      <p style="color:#475569;font-size:13.5px;max-width:850px;line-height:1.55;">Create and download a response planning draft from the current live flood analysis, settlement ranking, tier conditions, and data limitations. The report is prepared on this computer.</p>
    </div>
    ''', unsafe_allow_html=True)

    if not live_result:
        st.info("Run Analyze flood event first. The report will use the resulting flood extent and settlement exposure estimates.")
    else:
        ranked_for_report = rank_settlements(live_result.get("settlements_geojson"))
        report_parameters = {
            "region_name": region,
            "before_start": before_range[0].isoformat(),
            "before_end": (before_range[1] + timedelta(days=1)).isoformat(),
            "after_start": after_range[0].isoformat(),
            "after_end": (after_range[1] + timedelta(days=1)).isoformat(),
        }
        st.caption(f"Region: {region} · Ranked settlements: {len(ranked_for_report)} · Generated locally from current dashboard analysis.")
        if st.button("Generate data management report", type="primary", help="Creates a local draft from this live analysis; no data is sent externally."):
            report_key = f"local-report-{region}-{before_range[0]}-{after_range[0]}"
            st.session_state[report_key] = build_local_management_report(
                parameters=report_parameters,
                result=live_result,
                ranked_settlements=ranked_for_report,
                generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            )
        report_key = f"local-report-{region}-{before_range[0]}-{after_range[0]}"
        management_report = st.session_state.get(report_key)
        if management_report:
            st.markdown(management_report)
            st.download_button(
                "Download report · Markdown",
                data=management_report.encode("utf-8"),
                file_name="terai-floodwatch-management-report.md",
                mime="text/markdown",
                width="content",
            )


# ==========================================
# PAGE 3: METHODOLOGY
# ==========================================
else:
    st.markdown(f'''
    <div style="margin-bottom:18px;">
      <div style="font-family:'JetBrains Mono',monospace;color:#0284C7;font-size:11px;letter-spacing:1px;text-transform:uppercase;font-weight:600;">
        SCIENTIFIC ARCHITECTURE & VALIDATION
      </div>
      <h2 style="font-family:'Space Grotesk',sans-serif;font-size:30px;margin:4px 0 6px;color:#0F172A;">
        Methodology & Limitations
      </h2>
      <p style="color:#475569;font-size:13.5px;max-width:850px;line-height:1.55;">
        A robust, cloud-resilient Earth observation pipeline engineered specifically for the complex physiography of the Nepal Terai.
      </p>
    </div>
    ''', unsafe_allow_html=True)
    
    st.markdown('<div class="workflow">' + ''.join(
        f'<div class="step"><div class="step-n">STAGE 0{i+1}</div><div class="step-title">{title}</div><div class="step-copy">{copy}</div></div>'
        for i, (title, copy) in enumerate([
            ("Data Ingestion", "Acquire dual-pol VV+VH Sentinel-1 GRD products from Copernicus Open Access Hub."),
            ("Radiometric Calibration", "Apply precise orbit files, thermal noise removal, and calibrate digital numbers to σ° (dB)."),
            ("Terrain Correction", "Orthorectify using Copernicus 30m DEM (GLO-30) to correct geometric foreshortening."),
            ("Change Thresholding", "Log-ratio difference detection: Δσ° = σ°_event - σ°_baseline < τ_threshold."),
            ("Hydrological Filtering", "Mask out permanent water (JRC GSW) and high terrain slopes (>5°) to eliminate false positives."),
            ("Impact Intersection", "Spatial overlay against high-resolution settlement layers, roads, and WorldPop rasters.")
        ])
    ) + '</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="section-head"><div><h3>Sensor Physics & Complementary Strategy</h3></div></div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        st.markdown("""
        <div class="card">
          <div class="metric-label" style="color:#0284C7;">PRIMARY · SENTINEL-1 C-BAND SAR</div>
          <p style="font-size:12.5px;color:#334155;line-height:1.6;margin-top:6px;">
            Synthetic Aperture Radar operates at microwave wavelengths (5.6 cm) unaffected by cloud cover, rain droplets, or nightfall. It guarantees observation of the flood event during active monsoon downpours when optical sensors fail.
          </p>
          <div class="metric-label" style="color:#2563EB;margin-top:14px;">CROSS-VALIDATION · SENTINEL-2 / LANDSAT 8/9</div>
          <p style="font-size:12.5px;color:#334155;line-height:1.6;margin-top:6px;margin-bottom:0">
            High-resolution optical multispectral imagery provides auxiliary validation when cloud cover drops below 20%. Automated water indices (NDWI, MNDWI) cross-check doubtful water pixels in urban fringe zones.
          </p>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown("""
        <div class="card" style="border-color:#FED7AA;background:#FFFDFB;">
          <div class="metric-label" style="color:#EA580C;">INHERENT REMOTE SENSING CONSTRAINTS & MITIGATION</div>
          <p style="font-size:12.5px;color:#334155;line-height:1.6;margin-top:6px;">
            <b>• Wet Soils & Sandbars:</b> Saturated bare soil can mirror low backscatter values. We apply a multi-temporal dry-season baseline stack to filter recurring seasonal depressions.<br>
            <b>• Emergent Vegetation:</b> Flooded rice paddies or flooded forests cause double-bounce scattering, paradoxically increasing radar brightness. Dual-polarization VH/VV ratio analysis helps disentangle submerged vegetation.<br>
            <b>• Revisit Frequency:</b> Sentinel-1 has a 6 to 12 day repeat cycle over Nepal. We integrate ascending and descending passes to shorten observation gaps.
          </p>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('<div class="section-head"><div><h3>Mathematical Formulation</h3></div></div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="card" style="font-family:'JetBrains Mono',monospace;font-size:12px;line-height:1.8;color:#0F172A;background:#F8FAFC;">
      <span style="color:#0284C7;font-weight:600;">// SAR Change Detection Criterion</span><br>
      Flood_Mask(x, y) = [σ°_event(x, y) - σ°_baseline(x, y) &lt; τ] ∧ [Slope(x, y) &lt; 5°] ∧ [Permanent_Water(x, y) == 0]<br><br>
      <span style="color:#0284C7;font-weight:600;">// Settlement Intersection</span><br>
      Impacted_Settlements = { S_i ∈ Settlements | Area(S_i ∩ Flood_Mask) &gt; 0.05 · Area(S_i) }
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="section-head"><div><h3>Prototype Data Notice</h3></div></div>', unsafe_allow_html=True)
    st.info("TERAI FLOODWATCH demonstration mode: Data layers, synthetic satellite panels, and vulnerability rankings are calibrated demonstration scenarios modeled after typical Koshi/Bagmati monsoon flood events. Verify with local administrative emergency command centers before making operational field decisions.")


# ==========================================
# FOOTER (BRIGHT THEME)
# ==========================================
st.markdown("""
<div style="margin-top:40px;padding-top:18px;border-top:1px solid #E2E8F0;color:#64748B;font-size:11.5px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;">
  <div>
    <span style="color:#0F172A;font-weight:700;font-family:'Space Grotesk',sans-serif;letter-spacing:0.04em;">TERAI FLOODWATCH</span>
    <span style="color:#0284C7;margin-left:6px;font-family:'JetBrains Mono',monospace;font-weight:600;">· SATELLITE FLOOD INTELLIGENCE SYSTEM</span>
  </div>
  <div style="font-family:'JetBrains Mono',monospace;font-size:10.5px;">
    NEPAL TERAI EXPEDITION · ESA COPERNICUS OPEN ACCESS DATA · DECISION SUPPORT PROTOTYPE
  </div>
</div>
""", unsafe_allow_html=True)
