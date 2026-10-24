# TERAI FLOODWATCH · Earth Engine dashboard

A dark, responsive Streamlit interface for Sentinel-1 flood extent analysis in the Nepal Terai. The dashboard calls the Flask API in the parent repository and displays live Earth Engine map tiles, WorldPop exposure estimates, OpenStreetMap intersections, optional optical cross-checks, and sample-only validation from uploaded field observations.

## Run locally (PowerShell)

From the repository root (`nakshatra-Jaldrishti`), install the root dependencies and authorize Earth Engine once:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -c "import ee; ee.Authenticate(); ee.Initialize(project='annular-mercury-512512-v1')"
```

Start the API in one terminal:

```powershell
.\.venv\Scripts\python.exe -m flask --app backend.app run --host 127.0.0.1 --port 5000 --no-debugger --no-reload
```

Start this dashboard in a second terminal:

```powershell
.\.venv\Scripts\python.exe -m streamlit run myportfolio23432/app.py --server.address :: --server.port 8501
```

Open <http://localhost:8501/>. Set `JALDRISHTI_API_URL` if the Flask API is hosted somewhere other than `http://127.0.0.1:5000`.

## Data and interpretation

Earth Engine Sentinel-1 tiles and acquisition counts are fetched for the selected region and dates. Population exposure is a WorldPop raster estimate. Settlement and road impacts are intersections with OpenStreetMap and can be incomplete when mapping coverage is sparse. Empty OSM results do not mean there are no residents or roads.

Flood extent is a candidate SAR classification, not a ground-verified boundary. Upload a GeoJSON `FeatureCollection` containing labeled `Point` observations (`properties.flooded` set to `1` or `0`) to calculate accuracy for those sample points; this does not certify the complete map. Sentinel-2 or Landsat agreement is cross-sensor corroboration, not field validation. Network access is required for Earth Engine, OSM basemap tiles, and the Leaflet assets.
