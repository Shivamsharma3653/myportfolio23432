# JALDRISHTI Rapid Flood Mapping Dashboard

A responsive Streamlit prototype based on the supplied dashboard reference and proposed solution. It presents a Sentinel-1 SAR-led flood mapping workflow with optional Sentinel-2 / Landsat 8/9 validation, impact estimates, confidence cues, priority areas, and sample exports.

## Run locally

Python 3.10 or newer is recommended.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## Prototype data notice

No Earth Engine or satellite catalog is connected. Satellite comparison panels, flood geometry, exposure figures, confidence values, and priority rows are illustrative mock data. CSV, GeoJSON, and Markdown exports are labeled demo samples. The prototype is for presentation and workflow review; verify any operational decisions with satellite products and ground reports.

## Connecting real data

Replace the demonstration values and SVG scene/map generators in `app.py` with configured acquisition and processing services. The proposed pipeline is acquisition → preprocessing and quality checks → SAR change detection → permanent-water / artifact filtering → settlement, road, and population overlay → export. Optical cross-validation is optional and should run only when clear imagery is available.
