from __future__ import annotations

import json
import base64
import os
from datetime import date, timedelta

import requests

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


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
    "Koshi Basin · Eastern Terai": {"key": "koshi", "district": "Koshi Basin, Nepal", "coords": "26.40° N, 87.00° E"},
    "Rautahat · Central Terai": {"key": "rautahat", "district": "Rautahat, Nepal", "coords": "27.00° N, 85.08° E"},
    "Karnali Floodplain · Western Terai": {"key": "karnali", "district": "Karnali Floodplain, Nepal", "coords": "28.50° N, 81.13° E"},
}
BACKEND_URL = os.getenv("JALDRISHTI_API_URL", "http://127.0.0.1:5000").rstrip("/")


def analyze_with_backend(region, before_range, after_range, optical_sensor="none", ground_truth=None):
    payload = {
        "region": REGIONS[region]["key"],
        "before_start": before_range[0].isoformat(),
        "before_end": before_range[1].isoformat(),
        "after_start": after_range[0].isoformat(),
        "after_end": after_range[1].isoformat(),
        "optical_sensor": optical_sensor,
    }
    if ground_truth:
        payload["ground_truth_geojson"] = ground_truth
    response = requests.post(f"{BACKEND_URL}/analyze", json=payload, timeout=(10, 240))
    try:
        body = response.json()
    except ValueError:
        body = {"error": f"Backend returned HTTP {response.status_code} with a non-JSON response."}
    if not response.ok:
        raise RuntimeError(body.get("error", f"Flood analysis failed (HTTP {response.status_code})."))
    return body


def render_live_map(tile_url, bounds, title, settlements=None, roads=None, height=390):
    'Render actual Earth Engine tiles with an OSM basemap and returned impact vectors.'
    west, south, east, north = (bounds[k] for k in ("west", "south", "east", "north"))
    center = [(south + north) / 2, (west + east) / 2]
    vectors = {"type": "FeatureCollection", "features": []}
    for layer in (settlements or {}, roads or {}):
        vectors["features"].extend(layer.get("features", []))
    vector_json = json.dumps(vectors, separators=(",", ":")).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    html = f'''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>html,body,#map{{height:100%;width:100%;margin:0;background:#081426}}.leaflet-container{{font:12px Inter,Arial,sans-serif}}.leaflet-control-layers,.leaflet-control-attribution{{border-radius:8px!important}}.ee-layer{{filter:hue-rotate(125deg) saturate(1.25)}}.map-label{{position:absolute;z-index:500;top:12px;left:52px;background:#081426dd;color:#e8f2fb;padding:7px 10px;border:1px solid #26c8df;border-radius:7px;font:600 12px Inter,Arial}}</style></head>
<body><div id="map"></div><div class="map-label">{title}</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script><script>
const map=L.map('map',{{zoomControl:true,scrollWheelZoom:true}}).setView({json.dumps(center)},10);
const osm=L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',{{maxZoom:19,attribution:'© OpenStreetMap contributors'}}).addTo(map);
const layers={{'OpenStreetMap':osm}};
const url={json.dumps(tile_url or '')};
if(url){{layers['Sentinel-1 / Earth Engine'] = L.tileLayer(url,{{maxZoom:18,opacity:.78,attribution:'Google Earth Engine',className:'ee-layer'}}).addTo(map);}}
const geo={vector_json};
if(geo.features.length){{layers['OSM impact features']=L.geoJSON(geo,{{style:f=>({{color:f.properties&&f.properties.highway?'#ff9d57':'#f6d36b',weight:f.properties&&f.properties.highway?3:1,fillColor:'#ff9d57',fillOpacity:.4}}),pointToLayer:(f,latlng)=>L.circleMarker(latlng,{{radius:6,color:'#081426',weight:1,fillColor:'#ff9d57',fillOpacity:.95}}),onEachFeature:(f,l)=>{{const p=f.properties||{{}};l.bindPopup(p.name||p.place||p.highway||'OSM feature')}}}}).addTo(map);}}
L.control.layers(null,layers,{{collapsed:true}}).addTo(map);map.fitBounds([[{south},{west}],[{north},{east}]],{{padding:[10,10]}});
</script></body></html>'''
    components.html(html, height=height, scrolling=False)


st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&family=Space+Grotesk:wght@500;600;700;800&display=swap');

:root {
  --bg-primary: #050B18;
  --bg-secondary: #0A1630;
  --bg-card: rgba(10, 22, 48, 0.78);
  --bg-card-hover: rgba(14, 30, 64, 0.9);
  --accent-cyan: #42D9F5;
  --accent-blue: #3978FF;
  --flood-orange: #FF9D57;
  --text-primary: #F4F7FC;
  --text-secondary: #9BAAC2;
  --border-line: rgba(66, 217, 245, 0.18);
  --border-subtle: rgba(255, 255, 255, 0.08);
}

html, body, [class*="css"] {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  color: var(--text-primary);
}

.stApp {
  background-color: var(--bg-primary);
  background-image: 
    radial-gradient(circle at 85% 5%, rgba(66, 217, 245, 0.09) 0%, transparent 45%),
    radial-gradient(circle at 10% 30%, rgba(57, 120, 255, 0.07) 0%, transparent 50%),
    radial-gradient(circle at 50% 90%, rgba(10, 22, 48, 0.95) 0%, transparent 60%);
  color: var(--text-primary);
}

header[data-testid="stHeader"] { background: transparent; }

section[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #070e1e 0%, #050b18 100%) !important;
  border-right: 1px solid var(--border-line);
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
  letter-spacing: 0.04em;
}

/* Aerospace Top HUD Bar */
.aerospace-hud {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: rgba(10, 22, 48, 0.85);
  border: 1px solid var(--border-line);
  backdrop-filter: blur(12px);
  border-radius: 12px;
  padding: 10px 18px;
  margin-bottom: 22px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.35);
}
.hud-telemetry {
  display: flex;
  gap: 18px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: var(--text-secondary);
}
.hud-telemetry span {
  color: var(--accent-cyan);
  font-weight: 600;
}
.hud-tag {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  font-weight: 600;
  color: #42D9F5;
  background: rgba(66, 217, 245, 0.12);
  border: 1px solid rgba(66, 217, 245, 0.35);
  padding: 4px 10px;
  border-radius: 20px;
}
.pulse-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #42D9F5;
  box-shadow: 0 0 10px #42D9F5;
  animation: pulse 2s infinite;
}
@keyframes pulse {
  0% { transform: scale(0.95); opacity: 0.7; }
  50% { transform: scale(1.3); opacity: 1; }
  100% { transform: scale(0.95); opacity: 0.7; }
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
  background: linear-gradient(135deg, #42D9F5 0%, #3978FF 100%);
  display: grid;
  place-items: center;
  color: #050B18;
  box-shadow: 0 0 20px rgba(66, 217, 245, 0.35);
}
.brand-name {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 0.05em;
  color: #F4F7FC;
  line-height: 1.15;
}
.brand-sub {
  color: var(--accent-cyan);
  font-size: 9.5px;
  letter-spacing: 0.15em;
  font-weight: 600;
  font-family: 'JetBrains Mono', monospace;
  margin-top: 2px;
}

.side-caption {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #6C82A3;
  font-weight: 700;
  margin: 22px 0 8px;
}

/* Hero Section */
.hero-card {
  position: relative;
  border-radius: 18px;
  overflow: hidden;
  border: 1px solid rgba(66, 217, 245, 0.25);
  background: linear-gradient(180deg, rgba(10, 22, 48, 0.4) 0%, rgba(5, 11, 24, 0.95) 100%);
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5);
  margin-bottom: 26px;
}
.hero-bg-img {
  width: 100%;
  height: 340px;
  object-fit: cover;
  object-position: center;
  filter: brightness(0.65) contrast(1.15);
  display: block;
}
.hero-overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, rgba(5, 11, 24, 0.1) 0%, rgba(5, 11, 24, 0.85) 65%, #050B18 100%);
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  padding: 30px 36px;
}
.hero-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: rgba(66, 217, 245, 0.15);
  border: 1px solid rgba(66, 217, 245, 0.4);
  color: #42D9F5;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  padding: 4px 12px;
  border-radius: 20px;
  width: fit-content;
  margin-bottom: 12px;
  font-weight: 600;
}
.hero-title {
  font-family: 'Space Grotesk', sans-serif;
  font-size: clamp(28px, 3.8vw, 44px);
  font-weight: 800;
  letter-spacing: -0.035em;
  color: #FFFFFF;
  margin: 0 0 10px;
  line-height: 1.12;
  text-shadow: 0 4px 20px rgba(0,0,0,0.6);
}
.hero-sub {
  color: #C3D2E8;
  font-size: clamp(14px, 1.2vw, 16.5px);
  line-height: 1.55;
  max-width: 860px;
  margin: 0 0 16px;
}
.hero-quote {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 14px;
  color: #42D9F5;
  font-weight: 600;
  letter-spacing: 0.04em;
  border-left: 2px solid #42D9F5;
  padding-left: 12px;
  margin-top: 6px;
}

/* Aerospace Cards */
.card {
  background: var(--bg-card);
  border: 1px solid var(--border-line);
  backdrop-filter: blur(12px);
  border-radius: 14px;
  padding: 18px 20px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
  transition: all 0.25s ease;
  position: relative;
  overflow: hidden;
}
.card:hover {
  border-color: rgba(66, 217, 245, 0.4);
  background: var(--bg-card-hover);
  box-shadow: 0 14px 40px rgba(66, 217, 245, 0.08);
}
.card::before {
  content: "";
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(66, 217, 245, 0.45), transparent);
}

.metric-label {
  color: var(--text-secondary);
  font-size: 11.5px;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  font-family: 'JetBrains Mono', monospace;
}
.metric-value {
  color: #FFFFFF;
  font-family: 'Space Grotesk', sans-serif;
  font-weight: 700;
  font-size: 28px;
  letter-spacing: -0.03em;
  margin: 8px 0 4px;
}
.metric-note {
  color: #798FA8;
  font-size: 11px;
}
.metric-icon {
  float: right;
  color: var(--accent-cyan);
  font-size: 20px;
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
  color: #F4F7FC;
}
.section-head p {
  color: var(--text-secondary);
  font-size: 12px;
  margin: 4px 0 0;
}

.confidence-track {
  height: 7px;
  border-radius: 8px;
  background: #11233B;
  margin: 12px 0 6px;
  overflow: hidden;
}
.confidence-fill {
  height: 100%;
  border-radius: 8px;
  background: linear-gradient(90deg, #3978FF, #42D9F5);
  box-shadow: 0 0 10px rgba(66, 217, 245, 0.5);
}

.note {
  border: 1px solid rgba(255, 157, 87, 0.3);
  background: rgba(30, 20, 10, 0.45);
  border-radius: 12px;
  padding: 14px 16px;
  color: #FFD4B2;
  font-size: 11.5px;
  line-height: 1.55;
}

.workflow {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 10px;
}
.step {
  background: rgba(10, 22, 48, 0.85);
  border: 1px solid var(--border-line);
  border-radius: 12px;
  padding: 14px;
  min-height: 98px;
  position: relative;
  transition: transform 0.2s ease, border-color 0.2s ease;
}
.step:hover {
  transform: translateY(-2px);
  border-color: #42D9F5;
}
.step-n {
  color: var(--accent-cyan);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.12em;
  font-family: 'JetBrains Mono', monospace;
}
.step-title {
  color: #FFFFFF;
  font-family: 'Space Grotesk', sans-serif;
  font-size: 12px;
  font-weight: 700;
  margin: 6px 0 4px;
}
.step-copy {
  color: var(--text-secondary);
  font-size: 10px;
  line-height: 1.4;
}

/* Streamlit component overrides */
div[data-testid="stDataFrame"] {
  border: 1px solid var(--border-line);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
}
.stButton>button, .stDownloadButton>button {
  border-radius: 10px;
  border: 1px solid rgba(66, 217, 245, 0.3);
  background: rgba(10, 22, 48, 0.85);
  color: #E2F1FC;
  font-weight: 600;
  font-family: 'Inter', sans-serif;
  transition: all 0.25s ease;
}
.stButton>button[kind="primary"] {
  background: linear-gradient(135deg, #3978FF 0%, #42D9F5 100%) !important;
  border: 0;
  color: #050B18 !important;
  font-weight: 700;
  box-shadow: 0 4px 18px rgba(66, 217, 245, 0.35);
}
.stButton>button:hover, .stDownloadButton>button:hover {
  border-color: #42D9F5;
  box-shadow: 0 0 15px rgba(66, 217, 245, 0.35);
  color: #FFFFFF;
}
div[data-baseweb="select"]>div, div[data-baseweb="input"]>div {
  background: #0A1630 !important;
  border-color: rgba(66, 217, 245, 0.25) !important;
  border-radius: 9px;
  color: #F4F7FC !important;
}
label, div[data-testid="stWidgetLabel"] p {
  color: #C3D2E8 !important;
  font-size: 12px !important;
  font-weight: 500;
}
.stCaption, small {
  color: #798FA8 !important;
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
    <g fill="#42D9F5" opacity=".92" filter="drop-shadow(0 0 6px rgba(66,217,245,0.6))">
      <path d="M92 79l20-8 12 11-8 13-25 2z"/><path d="M157 122l17-8 19 9-7 18-24 2z"/>
      <path d="M250 70l16-11 21 7 3 15-22 10-19-7z"/><path d="M309 145l21-12 20 8-4 17-25 8z"/>
      <path d="M387 91l20-8 12 12-5 16-22 5z"/><path d="M213 183l17-7 20 7 4 15-21 12-19-9z"/>
      <path d="M64 170l13-8 16 6-2 16-20 5z"/><path d="M354 197l20-10 16 9-8 16-24-2z"/>
      <path d="M115 208l22-7 12 10-6 13-23 2z"/>
    </g>
    <g fill="#FF9D57" opacity=".85">
      <circle cx="152" cy="116" r="3.5"/><circle cx="258" cy="74" r="3.5"/><circle cx="315" cy="142" r="3.5"/>
    </g>""" if after else ""
    extra = "" if after else '<text x="18" y="25" fill="#9BAAC2" font-family="JetBrains Mono, monospace" font-size="10" letter-spacing="1">PRE-FLOOD BASELINE (SAR C-BAND)</text>'
    after_tag = '<text x="18" y="25" fill="#42D9F5" font-family="JetBrains Mono, monospace" font-size="10" letter-spacing="1">EVENT DETECTION (INUNDATION DETECTED)</text>' if after else ""
    
    return f'''<svg viewBox="0 0 500 270" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{'Post' if after else 'Pre'} flood satellite radar image">
    <defs>
      <linearGradient id="ground" x2="0" y2="1"><stop stop-color="#1b2a3c"/><stop offset="1" stop-color="#0b1420"/></linearGradient>
      <pattern id="grain" width="30" height="30" patternUnits="userSpaceOnUse">
        <path d="M0 15h30M15 0v30" stroke="#42D9F5" stroke-width=".3" opacity=".1"/>
        <circle cx="15" cy="15" r=".7" fill="#42D9F5" opacity=".2"/>
      </pattern>
    </defs>
    <rect width="500" height="270" fill="url(#ground)"/>
    <rect width="500" height="270" fill="url(#grain)"/>
    <!-- Topographic contour lines -->
    <path d="M-10 40Q120 20 240 60T510 30" fill="none" stroke="#253a52" stroke-width="1" stroke-dasharray="3 3"/>
    <path d="M-10 120Q150 140 300 110T510 150" fill="none" stroke="#253a52" stroke-width="1" stroke-dasharray="3 3"/>
    <path d="M-10 210Q180 180 320 230T510 190" fill="none" stroke="#253a52" stroke-width="1" stroke-dasharray="3 3"/>
    <!-- River channel baseline -->
    <g fill="none" stroke="#08101a" stroke-width="22" stroke-linecap="round"><path d="M257 -20 C230 23 285 38 250 74S267 116 241 148s29 45 3 79 5 35-7 63"/></g>
    <g fill="none" stroke="#04080e" stroke-width="10" stroke-linecap="round"><path d="M257 -20 C230 23 285 38 250 74S267 116 241 148s29 45 3 79 5 35-7 63"/></g>
    <!-- Radar coordinates overlay -->
    <g fill="none" stroke="#42D9F5" stroke-width=".8" opacity=".2"><path d="M0 88l156 30 160-15 184 30M10 224l132-51 185 34 173-50M95 0l32 270M416 0l-35 270"/></g>
    {patches}{extra}{after_tag}
    <rect x="12" y="235" width="85" height="23" rx="4" fill="#050B18" opacity=".88" stroke="#42D9F5" stroke-width=".5"/>
    <text x="18" y="250" fill="#42D9F5" font-family="JetBrains Mono, monospace" font-size="9.5">SENTINEL-1 · 10m</text>
    <text x="435" y="253" fill="#9BAAC2" font-family="JetBrains Mono, monospace" font-size="9.5">GRID N ↑</text>
    </svg>'''


def flood_map(region: str, settlements: bool, roads: bool) -> str:
    road = '<g fill="none" stroke="#FF9D57" stroke-width="2" stroke-dasharray="5 4"><path d="M28 247Q150 214 235 156T478 42"/><path d="M77 30Q143 87 217 103t194 89"/></g>' if roads else ''
    homes = '<g fill="#FF9D57" stroke="#050B18" stroke-width="2"><circle cx="102" cy="110" r="6"/><circle cx="145" cy="146" r="6"/><circle cx="330" cy="77" r="6"/><circle cx="370" cy="177" r="6"/><circle cx="250" cy="215" r="6"/><circle cx="416" cy="124" r="6"/></g>' if settlements else ''
    
    return f'''<svg viewBox="0 0 600 315" xmlns="http://www.w3.org/2000/svg" aria-label="Illustrative flood extent map for {region}">
    <defs>
      <linearGradient id="mapBg" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stop-color="#081426"/>
        <stop offset="100%" stop-color="#050B18"/>
      </linearGradient>
      <pattern id="geogrid" width="40" height="40" patternUnits="userSpaceOnUse">
        <path d="M40 0H0V40" fill="none" stroke="#42D9F5" stroke-width=".4" opacity=".18"/>
        <circle cx="20" cy="20" r=".6" fill="#42D9F5" opacity=".25"/>
      </pattern>
    </defs>
    <rect width="600" height="315" fill="url(#mapBg)"/>
    <rect width="600" height="315" fill="url(#geogrid)"/>
    
    <!-- Elevation contours -->
    <path d="M0 45Q180 30 320 65T600 40" fill="none" stroke="#1d3148" stroke-width="1.2"/>
    <path d="M0 130Q160 160 340 125T600 150" fill="none" stroke="#1d3148" stroke-width="1.2"/>
    <path d="M0 240Q200 210 380 250T600 230" fill="none" stroke="#1d3148" stroke-width="1.2"/>
    
    <!-- River corridors -->
    <path d="M-20 62Q78 30 151 74T277 109 397 83 620 117M-14 257Q95 208 186 226t190 16 243-63" fill="none" stroke="#16273c" stroke-width="26" opacity=".7"/>
    <path d="M-20 60Q78 28 151 72T277 107 397 81 620 115M-14 255Q95 206 186 224t190 16 243-63" fill="none" stroke="#0a1523" stroke-width="12"/>
    
    <!-- Detected Inundation Polygons (Cyan) -->
    <path d="M90 87l56-20 48 14 17 45-32 33-64-4-39-31zM293 48l60-8 40 23-4 42-53 19-49-25zM342 183l55-27 46 17 16 47-52 25-63-18zM158 210l44-18 31 24-12 39-52 11-26-24z" 
          fill="#42D9F5" fill-opacity=".45" stroke="#42D9F5" stroke-width="2" filter="drop-shadow(0 0 8px rgba(66,217,245,0.4))"/>
    
    {road}{homes}
    
    <!-- Map HUD Labels -->
    <g fill="#F4F7FC" font-family="Space Grotesk, sans-serif" font-weight="700">
      <text x="20" y="26" font-size="12" letter-spacing="1">{region.upper()}</text>
    </g>
    <g fill="#9BAAC2" font-family="JetBrains Mono, monospace" font-size="9.5">
      <text x="20" y="42">SENTINEL-1 C-SAR · REVISIT CYCLE 6D</text>
      <text x="440" y="295">SCALE 1:50,000 · 10 km</text>
    </g>
    
    <!-- Symbology Legend -->
    <g transform="translate(18 282)">
      <rect width="11" height="11" rx="2" fill="#42D9F5" opacity=".8"/>
      <text x="17" y="9.5" fill="#F4F7FC" font-size="9" font-family="Inter, sans-serif">Detected inundation</text>
      <circle cx="140" cy="5.5" r="5" fill="#FF9D57"/>
      <text x="152" y="9.5" fill="#F4F7FC" font-size="9" font-family="Inter, sans-serif">Settlement</text>
      <path d="M230 5.5h16" stroke="#FF9D57" stroke-width="2" stroke-dasharray="4 3"/>
      <text x="252" y="9.5" fill="#F4F7FC" font-size="9" font-family="Inter, sans-serif">Road network</text>
    </g>
    </svg>'''


def render_svg(svg: str, height: int, background: str = "#0A1630") -> None:
    svg_data = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    components.html(
        f"""<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1">
        <style>html,body{{margin:0;padding:0;background:{background};overflow:hidden;border-radius:12px;}}
        img{{display:block;width:100%;height:auto;border-radius:12px;}}</style></head>
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
          border: 1px solid rgba(66, 217, 245, 0.3);
          box-shadow: 0 10px 30px rgba(0,0,0,0.5);
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
          border-right: 2px solid #42D9F5;
          box-shadow: 2px 0 15px rgba(66, 217, 245, 0.5);
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
          background: #050B18;
          border: 2px solid #42D9F5;
          box-shadow: 0 0 16px rgba(66, 217, 245, 0.7);
          display: flex;
          align-items: center;
          justify-content: center;
          color: #42D9F5;
          font-size: 13px;
          font-weight: bold;
        }}
        .hud-tag {{
          position: absolute;
          top: 14px;
          padding: 6px 12px;
          background: rgba(5, 11, 24, 0.85);
          border: 1px solid rgba(66, 217, 245, 0.3);
          backdrop-filter: blur(8px);
          border-radius: 6px;
          font-size: 11px;
          font-family: monospace;
          color: #F4F7FC;
          z-index: 5;
        }}
        .tag-left {{ left: 14px; color: #9BAAC2; }}
        .tag-right {{ right: 14px; color: #42D9F5; }}
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
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#050B18" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
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
    page = st.radio("Navigate", ["Overview", "Impact & priorities", "Methodology"], label_visibility="collapsed")
    
    st.markdown('<div class="side-caption">Analysis parameters</div>', unsafe_allow_html=True)
    region = st.selectbox("Region of interest", list(REGIONS))
    sensor = st.selectbox("Detection sensor", ["Sentinel-1 SAR", "Sentinel-1 + Sentinel-2 validation", "Sentinel-1 + Landsat 8/9 validation"])
    optical_sensor = {"Sentinel-1 SAR": "none", "Sentinel-1 + Sentinel-2 validation": "sentinel2", "Sentinel-1 + Landsat 8/9 validation": "landsat89"}[sensor]
    st.caption("Sentinel-1 SAR is the detection source. Optical imagery is an optional validation step when clear scenes are available.")
    
    today = date.today()
    before_range = st.date_input("Pre-flood baseline window", value=(today-timedelta(days=53), today-timedelta(days=34)), max_value=today, key="before_dates")
    after_range = st.date_input("Post-flood event window", value=(today-timedelta(days=20), today-timedelta(days=7)), max_value=today, key="after_dates")
    ground_truth_file = st.file_uploader("Optional field observations (GeoJSON)", type=["geojson", "json"], help="Upload a GeoJSON FeatureCollection of verified flood / non-flood observations.")
    ground_truth = None
    if ground_truth_file:
        try:
            ground_truth = json.load(ground_truth_file)
            if ground_truth.get("type") != "FeatureCollection":
                st.error("Ground observations must be a GeoJSON FeatureCollection.")
                ground_truth = None
        except (ValueError, AttributeError):
            st.error("That file is not valid GeoJSON.")
    
    st.markdown('<div class="side-caption">Geospatial overlays</div>', unsafe_allow_html=True)
    show_settlements = st.checkbox("Settlements & building clusters", value=True)
    show_roads = st.checkbox("Transportation & road network", value=True)
    
    run = st.button("⚡  Analyze flood event", type="primary", width="stretch")
    if run:
        if len(before_range) != 2 or len(after_range) != 2:
            st.error("Select a start and end date for both date windows.")
        elif before_range[1] > after_range[0]:
            st.error("The pre-flood window must end on or before the post-flood window starts.")
        else:
            try:
                st.session_state.analysis_result = None
                with st.spinner("Connecting to Google Earth Engine and calculating flood / impact layers…"):
                    st.session_state.analysis_result = analyze_with_backend(region, before_range, after_range, optical_sensor, ground_truth)
                    st.session_state.analysis_parameters = {"region": region, "sensor": sensor, "before": [d.isoformat() for d in before_range], "after": [d.isoformat() for d in after_range]}
                    st.session_state.analysis_error = None
                st.toast("Earth Engine analysis completed.", icon="🛰️")
            except requests.RequestException as exc:
                st.session_state.analysis_error = f"Cannot reach the Flask API at {BACKEND_URL}. Start backend/app.py and retry. Details: {exc}"
            except RuntimeError as exc:
                st.session_state.analysis_error = str(exc)
        
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    st.caption(f"API STATUS · {BACKEND_URL}")

result = st.session_state.get("analysis_result")
analysis_error = st.session_state.get("analysis_error")
analysis_parameters = st.session_state.get("analysis_parameters")
current_parameters = {"region": region, "sensor": sensor, "before": [x.isoformat() for x in before_range] if len(before_range) == 2 else [], "after": [x.isoformat() for x in after_range] if len(after_range) == 2 else []}
if result and analysis_parameters != current_parameters:
    result = None
    st.info("Analysis controls changed since the last run. Run the analysis again to refresh maps, cards, and downloads.")
d = REGIONS[region]
if analysis_error:
    st.error(analysis_error, icon="⚠️")
if result:
    st.info(result.get("warning") or "Earth Engine analysis completed. Candidate flood extent is not field verified.", icon="🛰️")


def display_number(value, suffix="", digits=1):
    if value is None:
        return "Not available"
    return f"{value:,.{digits}f}{suffix}" if isinstance(value, (int, float)) else f"{value}{suffix}"


# ==========================================
# TOP AEROSPACE HUD BAR
# ==========================================
st.markdown(f"""
<div class="aerospace-hud">
  <div class="hud-telemetry">
    <div>SATELLITE: <span>SENTINEL-1 GRD · EARTH ENGINE</span></div>
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
    # Cinematic Hero Section
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
    
    # 4 Key Metrics Cards
    cols = st.columns(4, gap="medium")
    metrics = [
        ("Candidate flood extent", display_number(result.get("candidate_flood_area_km2"), " km²", 3) if result else "Run analysis", "Sentinel-1 estimate · not ground verified", "◈"),
        ("OSM settlements intersected", display_number(result.get("affected_settlements")) if result else "Run analysis", "Mapped features only; absence is not proof of no residents", "⌂"),
        ("OSM road length intersected", display_number(result.get("affected_roads_km"), " km", 3) if result else "Run analysis", "OpenStreetMap road features", "⌁"),
        ("Modeled population exposure", (f"{result.get('population_exposed_estimate'):,}" if result and result.get("population_exposed_estimate") is not None else "Not available") if result else "Run analysis", f"WorldPop estimate · {result.get('population_dataset_year', 'year unavailable')}" if result else "WorldPop estimate after analysis", "♙")
    ]
    for col, (label, value, note, icon) in zip(cols, metrics):
        with col:
            st.markdown(f"""
            <div class="card">
              <span class="metric-icon">{icon}</span>
              <div class="metric-label">{label}</div>
              <div class="metric-value">{value}</div>
              <div class="metric-note">{note}</div>
            </div>
            """, unsafe_allow_html=True)

    # About The Project & Problem Section
    st.markdown('<div class="section-head"><div><h3>About The Project & Terai Flood Vulnerability</h3><p>Why satellite remote sensing is vital for Nepal\'s southern lowlands</p></div></div>', unsafe_allow_html=True)
    ab1, ab2 = st.columns([1.1, 1], gap="medium")
    with ab1:
        st.markdown(f"""
        <div class="card" style="height:100%">
          <div class="metric-label">PROBLEM STATEMENT & REGIONAL CONTEXT</div>
          <p style="font-size:12.5px;color:#C3D2E8;line-height:1.65;margin-top:8px;">
            The Nepal Terai constitutes the northern fringe of the Indo-Gangetic Plain, characterized by dense rural settlements, fertile agrarian floodplains, and extreme susceptibility to recurring monsoon flash floods across the Koshi, Bagmati, and Gandaki river basins. Heavy monsoon precipitation routinely causes transboundary river overflows, submerging thousands of hectares within hours.
          </p>
          <p style="font-size:12.5px;color:#9BAAC2;line-height:1.65;">
            During intense weather emergencies, traditional optical satellites (e.g. Landsat, basic multispectral) are completely obstructed by dense, persistent cloud cover. Terai FloodWatch uses active C-band Synthetic Aperture Radar (SAR) on Sentinel-1, which operates at microwave frequencies to pierce clouds day and night, delivering automated damage assessments to disaster responders before floodwaters recede.
          </p>
          <div style="display:flex;gap:12px;margin-top:14px;">
            <div style="background:rgba(66,217,245,0.08);border:1px solid rgba(66,217,245,0.25);border-radius:8px;padding:8px 12px;flex:1;">
              <div style="font-size:10px;color:#42D9F5;font-family:'JetBrains Mono',monospace;">CLOUD PENETRATION</div>
              <div style="font-size:16px;font-weight:700;color:#F4F7FC;margin-top:2px;">100% (SAR)</div>
            </div>
            <div style="background:rgba(66,217,245,0.08);border:1px solid rgba(66,217,245,0.25);border-radius:8px;padding:8px 12px;flex:1;">
              <div style="font-size:10px;color:#42D9F5;font-family:'JetBrains Mono',monospace;">GROUND RESOLUTION</div>
              <div style="font-size:16px;font-weight:700;color:#F4F7FC;margin-top:2px;">10 Meters</div>
            </div>
            <div style="background:rgba(66,217,245,0.08);border:1px solid rgba(66,217,245,0.25);border-radius:8px;padding:8px 12px;flex:1;">
              <div style="font-size:10px;color:#42D9F5;font-family:'JetBrains Mono',monospace;">RESPONSE LATENCY</div>
              <div style="font-size:16px;font-weight:700;color:#F4F7FC;margin-top:2px;">&lt; 4 Hours</div>
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
              <div style="color:#FF9D57;font-size:18px;">⚠️</div>
              <div>
                <b style="color:#F4F7FC;font-size:12.5px;">Monsoon Cloud Cover Barrier</b>
                <p style="color:#9BAAC2;font-size:11.5px;margin:2px 0 0;">Optical instruments cannot penetrate monsoon storm clouds. Sentinel-1 microwave pulses can observe through clouds and at night, although radar interpretation still requires validation.</p>
              </div>
            </div>
            <div style="display:flex;gap:12px;align-items:flex-start;">
              <div style="color:#42D9F5;font-size:18px;">🌊</div>
              <div>
                <b style="color:#F4F7FC;font-size:12.5px;">Flatland Water Spread Dynamics</b>
                <p style="color:#9BAAC2;font-size:11.5px;margin:2px 0 0;">The low topographical gradient causes floodwaters to expand laterally across multiple districts simultaneously.</p>
              </div>
            </div>
            <div style="display:flex;gap:12px;align-items:flex-start;">
              <div style="color:#3978FF;font-size:18px;">🛰️</div>
              <div>
                <b style="color:#F4F7FC;font-size:12.5px;">Automated Settlement Spatial Intersection</b>
                <p style="color:#9BAAC2;font-size:11.5px;margin:2px 0 0;">Immediate overlay against ward boundaries and OpenStreetMap road layers highlights marooned communities.</p>
              </div>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<div class="section-head"><div><h3>Live Sentinel-1 imagery comparison</h3><p>Earth Engine pre-event and post-event image composites for the selected date windows</p></div><span class="metric-label">LIVE EARTH ENGINE</span></div>', unsafe_allow_html=True)
    if result:
        before_tile = result.get("before_tile_url")
        after_tile = result.get("after_tile_url")
        map_bounds = result.get("analysis_bounds", {})
        pre_col, post_col = st.columns(2, gap="medium")
        with pre_col:
            st.caption(f"PRE-FLOOD · {before_range[0]} to {before_range[1]} · {result.get('before_images', 0)} scenes")
            if before_tile:
                render_live_map(before_tile, map_bounds, "PRE-FLOOD SENTINEL-1", height=330)
            else:
                st.info("No pre-event Earth Engine tile was returned.")
        with post_col:
            st.caption(f"POST-FLOOD · {after_range[0]} to {after_range[1]} · {result.get('after_images', 0)} scenes")
            if after_tile:
                render_live_map(after_tile, map_bounds, "POST-FLOOD SENTINEL-1", height=330)
            else:
                st.info("No post-event Earth Engine tile was returned.")
    else:
        st.info("Choose baseline and event windows, then select **Analyze flood event** to load real satellite composites.")

    st.markdown('<div class="section-head"><div><h3>Flood extent & exposure map</h3><p>Live Sentinel-1 candidate extent with available OpenStreetMap impact features</p></div><span class="metric-label">{}</span></div>'.format(region), unsafe_allow_html=True)
    if result:
        map_bounds = result.get("analysis_bounds", {})
        if map_bounds:
            render_live_map(result.get("flood_tile_url"), map_bounds, "CANDIDATE FLOOD EXTENT", result.get("settlements_geojson") if show_settlements else None, result.get("roads_geojson") if show_roads else None, height=440)
        else:
            st.warning("The backend returned no map bounds.")
        if result.get("field_validation"):
            validation = result["field_validation"]
            st.metric("Field-sample accuracy", f"{validation.get('accuracy_percent', 0)}%", help=f"Based on {validation.get('sample_points', 0)} uploaded sample points; this does not certify the full map.")
        else:
            st.warning("Detection confidence is not independently scored. Candidate flood extent is not ground-validated; upload labeled GeoJSON field points to calculate sample accuracy.")
        optical = result.get("optical_validation")
        if optical:
            if optical.get("available"):
                st.info(f"{optical['sensor']} cross-check: {optical.get('sar_candidate_overlap_percent', 'n/a')}% overlap across {optical.get('before_images', 0)} baseline and {optical.get('after_images', 0)} event scenes. Optical agreement is not field verification.")
            else:
                st.info(optical.get("warning", "Optical validation imagery is unavailable for these date windows."))
        if result.get("warning"):
            st.caption(result["warning"])
    else:
        st.info("The live flood map appears after a successful Earth Engine analysis. Static illustrative map panels have been removed from the results view.")

    # Satellite Technology Deep Dive (Sentinel-1 SAR vs Sentinel-2 Optical)
    st.markdown('<div class="section-head"><div><h3>Satellite Technology & Sensor Complementarity</h3><p>Understanding SAR radar backscatter vs multispectral optical reflectance</p></div></div>', unsafe_allow_html=True)
    tech1, tech2 = st.columns(2, gap="medium")
    with tech1:
        st.markdown(f"""
        <div class="card">
          <img src="{IMG_SENTINEL1}" style="width:100%;height:180px;object-fit:cover;border-radius:10px;margin-bottom:12px;" alt="Sentinel-1 SAR Satellite">
          <div class="metric-label" style="color:#42D9F5;">PRIMARY SENSOR: SENTINEL-1 C-SAR</div>
          <h4 style="margin:4px 0 8px;font-size:16px;">Active Microwave Radar (5.405 GHz)</h4>
          <p style="font-size:11.5px;color:#9BAAC2;line-height:1.55;">
            <b>Physics Principle:</b> Smooth open floodwaters act as specular reflectors, scattering radar pulses away from the antenna and returning very low backscatter (&lt; -18 dB, appearing dark). Surrounding rough terrain scatters energy back, producing a high contrast boundary.
          </p>
          <div style="font-family:'JetBrains Mono',monospace;font-size:10.5px;color:#42D9F5;background:rgba(66,217,245,0.08);padding:8px;border-radius:6px;margin-top:8px;">
            λ: 5.6 cm (C-band) | Polarization: VV + VH | Swath: 250 km
          </div>
        </div>
        """, unsafe_allow_html=True)
    with tech2:
        st.markdown(f"""
        <div class="card">
          <img src="{IMG_SENTINEL2}" style="width:100%;height:180px;object-fit:cover;border-radius:10px;margin-bottom:12px;" alt="Sentinel-2 Optical Satellite">
          <div class="metric-label" style="color:#3978FF;">CROSS-VALIDATION: SENTINEL-2 MSI</div>
          <h4 style="margin:4px 0 8px;font-size:16px;">Multispectral Optical (13 Bands)</h4>
          <p style="font-size:11.5px;color:#9BAAC2;line-height:1.55;">
            <b>Physics Principle:</b> When sky conditions permit, Sentinel-2 validates detected floodplains via the Modified Normalized Difference Water Index: <i>MNDWI = (Green - SWIR) / (Green + SWIR)</i>, separating water from dense vegetation and built structures.
          </p>
          <div style="font-family:'JetBrains Mono',monospace;font-size:10.5px;color:#3978FF;background:rgba(57,120,255,0.08);padding:8px;border-radius:6px;margin-top:8px;">
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

    st.markdown('<div class="section-head"><div><h3>Settlement & road impact register</h3><p>Features returned by the spatial intersection; no invented ward-level priority rows</p></div></div>', unsafe_allow_html=True)
    if result:
        settlement_features = (result.get("settlements_geojson") or {}).get("features", [])
        road_features = (result.get("roads_geojson") or {}).get("features", [])
        rows = []
        for feature in settlement_features:
            props = feature.get("properties", {})
            rows.append({"Feature type": "Settlement / residential area", "Name": props.get("name", "Unnamed OSM feature"), "Class": props.get("place") or "residential", "Overlap area (km²)": props.get("candidate_overlap_km2")})
        for feature in road_features:
            props = feature.get("properties", {})
            rows.append({"Feature type": "Road", "Name": props.get("name", "Unnamed OSM road"), "Class": props.get("highway", "road"), "Overlap area (km²)": None})
        if rows:
            pri = pd.DataFrame(rows)
            st.dataframe(pri, width="stretch", hide_index=True)
        else:
            st.info("No settlement or road features were returned as intersecting the candidate extent. This can reflect missing OpenStreetMap coverage and does not mean the area has no residents or roads.")
        if result.get("osm_warning"):
            st.caption(result["osm_warning"])
        st.caption(f"OpenStreetMap attribution: {result.get('osm_attribution', '© OpenStreetMap contributors')}. Dataset queried {result.get('osm_data_timestamp', 'timestamp unavailable')}.")
        export_features = settlement_features + road_features
        impact_geojson = {"type": "FeatureCollection", "name": "jaldrishti_osm_impact_features", "features": export_features}
        priority_csv = pd.DataFrame(rows).to_csv(index=False).encode("utf-8") if rows else b"Feature type,Name,Class,Overlap area (km2)\n"
        parameters = st.session_state.get("analysis_parameters", {})
        report = f"""# TERAI FLOODWATCH · Earth Engine analysis

- Region: {parameters.get('region', region)}
- Sensor: {parameters.get('sensor', sensor)}
- Baseline: {parameters.get('before', before_range)}
- Event: {parameters.get('after', after_range)}
- Candidate flood extent: {display_number(result.get('candidate_flood_area_km2'), ' km²', 3)}
- Sentinel-1 scenes: {result.get('before_images', 0)} baseline; {result.get('after_images', 0)} event
- WorldPop exposure estimate: {display_number(result.get('population_exposed_estimate'))} (dataset year {result.get('population_dataset_year', 'unknown')})
- OSM settlements intersected: {display_number(result.get('affected_settlements'))}
- OSM road length intersected: {display_number(result.get('affected_roads_km'), ' km', 3)}
- Field validation: {result.get('field_validation') or 'Not supplied; map remains an unverified candidate extent'}

## Limitations
This is a Sentinel-1 candidate flood map, not a ground-verified boundary. Population is a modeled raster estimate. Settlement and road results depend on OpenStreetMap completeness. Optical overlap, if enabled, is cross-sensor corroboration and not field validation.

{result.get('warning', '')}
"""
        st.markdown('<div class="section-head"><div><h3>Export & dissemination hub</h3><p>Download values from this analysis run</p></div></div>', unsafe_allow_html=True)
        ec = st.columns(3)
        ec[0].download_button("↓  OSM impacts · CSV", priority_csv, "jaldrishti-impact-features.csv", "text/csv", width="stretch")
        ec[1].download_button("↓  OSM impacts · GeoJSON", json.dumps(impact_geojson, indent=2), "jaldrishti-osm-impacts.geojson", "application/geo+json", width="stretch")
        ec[2].download_button("↓  Analysis brief · Markdown", report, "jaldrishti-analysis-brief.md", "text/markdown", width="stretch")
    else:
        st.caption("Exports become available after a live analysis completes.")


# ==========================================
# PAGE 2: IMPACT & PRIORITIES
# ==========================================
elif page == "Impact & priorities":
    st.markdown(f'''
    <div style="margin-bottom:18px;">
      <div style="font-family:'JetBrains Mono',monospace;color:#42D9F5;font-size:11px;letter-spacing:1px;text-transform:uppercase;">
        SETTLEMENT IMPACT ASSESSMENT · {region}
      </div>
      <h2 style="font-family:'Space Grotesk',sans-serif;font-size:30px;margin:4px 0 6px;">
        Exposed Settlements & Rescue Priority Triage
      </h2>
      <p style="color:#9BAAC2;font-size:13px;max-width:850px;line-height:1.55;">
        Spatial intersection of radar-derived inundation masks against municipal settlement boundaries and OpenStreetMap infrastructure networks.
      </p>
    </div>
    ''', unsafe_allow_html=True)
    
    if result:
        map_bounds = result.get("analysis_bounds", {})
        if map_bounds:
            render_live_map(result.get("flood_tile_url"), map_bounds, "CANDIDATE FLOOD EXTENT", result.get("settlements_geojson") if show_settlements else None, result.get("roads_geojson") if show_roads else None, height=440)
        settlement_features = (result.get("settlements_geojson") or {}).get("features", [])
        road_features = (result.get("roads_geojson") or {}).get("features", [])
        rows = [{"Type": "Settlement / residential area", **feature.get("properties", {})} for feature in settlement_features]
        rows += [{"Type": "Road", **feature.get("properties", {})} for feature in road_features]
        st.markdown('<div class="section-head"><div><h3>Observed impact features</h3><p>Only mapped OSM features intersecting the candidate extent are listed</p></div></div>', unsafe_allow_html=True)
        if rows:
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        else:
            st.info("No OSM settlement or road features intersected the candidate flood extent. OSM coverage may be incomplete; this is not evidence of zero real-world exposure.")
        if result.get("field_validation"):
            st.metric("Uploaded-point accuracy", f"{result['field_validation'].get('accuracy_percent', 0)}%", help=f"{result['field_validation'].get('sample_points', 0)} submitted field points only; not full-map certification.")
        else:
            st.warning("No ground observations were supplied. This map is an unvalidated candidate extent; do not treat it as verified flood detection.")
    else:
        st.info("Run an Earth Engine analysis to populate this page with live map and impact data.")


# ==========================================
# PAGE 3: METHODOLOGY
# ==========================================
else:
    st.markdown(f'''
    <div style="margin-bottom:18px;">
      <div style="font-family:'JetBrains Mono',monospace;color:#42D9F5;font-size:11px;letter-spacing:1px;text-transform:uppercase;">
        SCIENTIFIC ARCHITECTURE & VALIDATION
      </div>
      <h2 style="font-family:'Space Grotesk',sans-serif;font-size:30px;margin:4px 0 6px;">
        Methodology & Limitations
      </h2>
      <p style="color:#9BAAC2;font-size:13px;max-width:850px;line-height:1.55;">
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
          <div class="metric-label" style="color:#42D9F5;">PRIMARY · SENTINEL-1 C-BAND SAR</div>
          <p style="font-size:12px;color:#C3D2E8;line-height:1.6;margin-top:6px;">
            Synthetic Aperture Radar operates at microwave wavelengths (5.6 cm) unaffected by cloud cover, rain droplets, or nightfall. It guarantees observation of the flood event during active monsoon downpours when optical sensors fail.
          </p>
          <div class="metric-label" style="color:#3978FF;margin-top:14px;">CROSS-VALIDATION · SENTINEL-2 / LANDSAT 8/9</div>
          <p style="font-size:12px;color:#C3D2E8;line-height:1.6;margin-top:6px;margin-bottom:0">
            High-resolution optical multispectral imagery provides auxiliary validation when cloud cover drops below 20%. Automated water indices (NDWI, MNDWI) cross-check doubtful water pixels in urban fringe zones.
          </p>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown("""
        <div class="note" style="border-color:rgba(66,217,245,0.3);background:rgba(10,22,48,0.7);">
          <b style="color:#42D9F5;font-size:13px;">Inherent Remote Sensing Constraints & Mitigation</b><br><br>
          <span style="color:#F4F7FC;">• Wet Soils & Sandbars:</span> Saturated bare soil can mirror low backscatter values. We apply a multi-temporal dry-season baseline stack to filter recurring seasonal depressions.<br><br>
          <span style="color:#F4F7FC;">• Emergent Vegetation:</span> Flooded rice paddies or flooded forests cause double-bounce scattering, paradoxically increasing radar brightness. Dual-polarization VH/VV ratio analysis helps disentangle submerged vegetation.<br><br>
          <span style="color:#F4F7FC;">• Revisit Frequency:</span> Sentinel-1 has a 6 to 12 day repeat cycle over Nepal. We integrate ascending and descending passes to shorten observation gaps.
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('<div class="section-head"><div><h3>Mathematical Formulation</h3></div></div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="card" style="font-family:'JetBrains Mono',monospace;font-size:12px;line-height:1.8;color:#C3D2E8;">
      <span style="color:#42D9F5;">// SAR Change Detection Criterion</span><br>
      Flood_Mask(x, y) = [σ°_event(x, y) - σ°_baseline(x, y) &lt; τ] ∧ [Slope(x, y) &lt; 5°] ∧ [Permanent_Water(x, y) == 0]<br><br>
      <span style="color:#42D9F5;">// Settlement Intersection</span><br>
      Impacted_Settlements = { S_i ∈ Settlements | Area(S_i ∩ Flood_Mask) &gt; 0.05 · Area(S_i) }
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="section-head"><div><h3>Live data & limitations</h3></div></div>', unsafe_allow_html=True)
    st.info("Live mode uses the configured Earth Engine backend. The flood layer is a candidate SAR estimate; optical agreement is not ground verification. Population is modeled, and settlement / road counts depend on OpenStreetMap coverage. Uploaded labeled field points produce sample-only validation metrics.")


# ==========================================
# FOOTER
# ==========================================
st.markdown("""
<div style="margin-top:40px;padding-top:18px;border-top:1px solid rgba(66,217,245,0.2);color:#6C82A3;font-size:11px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;">
  <div>
    <span style="color:#F4F7FC;font-weight:700;font-family:'Space Grotesk',sans-serif;letter-spacing:0.04em;">TERAI FLOODWATCH</span>
    <span style="color:#42D9F5;margin-left:6px;font-family:'JetBrains Mono',monospace;">· SATELLITE FLOOD INTELLIGENCE SYSTEM</span>
  </div>
  <div style="font-family:'JetBrains Mono',monospace;font-size:10.5px;">
    NEPAL TERAI EXPEDITION · ESA COPERNICUS OPEN ACCESS DATA · DECISION SUPPORT PROTOTYPE
  </div>
</div>
""", unsafe_allow_html=True)
