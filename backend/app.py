
from flask import Flask, request, jsonify
from backend.flood_analysis import analyze_flood
from datetime import date

app = Flask(__name__)

def validate_dates(data):
    required = [
        "before_start",
        "before_end",
        "after_start",
        "after_end",
    ]

    # Check missing fields
    missing = [
        field for field in required
        if not data.get(field)
    ]

    if missing:
        return f"Missing required fields: {', '.join(missing)}"

    # Check whether dates are valid ISO dates
    parsed = {}

    for field in required:
        try:
            parsed[field] = date.fromisoformat(data[field])
        except (ValueError, TypeError):
            return f"Invalid date for '{field}'. Use YYYY-MM-DD."

    # Check each period
    if parsed["before_start"] >= parsed["before_end"]:
        return "before_start must be earlier than before_end."

    if parsed["after_start"] >= parsed["after_end"]:
        return "after_start must be earlier than after_end."

    # Before period should finish before or when after period starts
    if parsed["before_end"] > parsed["after_start"]:
        return "The before period must not overlap the after period."

    return None

@app.get("/")
def home():
    return jsonify({
        "project": "Jal Drishti",
        "status": "running",
        "endpoints": ["/health", "/analyze"]
    })


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/analyze")
def analyze():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "error": "Request body must be a valid JSON object."
        }), 400

    error = validate_dates(data)

    if error:
        return jsonify({"error": error}), 400

    try:
        result = analyze_flood(
            data["before_start"],
            data["before_end"],
            data["after_start"],
            data["after_end"],
        )
        return jsonify(result)

    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422

    except Exception as exc:
        app.logger.exception("Flood analysis failed")
        message = str(exc).lower()
        if "serviceusage.services.use" in message or "required permission to use project" in message:
            return jsonify({
                "error": "Earth Engine login succeeded, but this Google account needs the Service Usage Consumer role (roles/serviceusage.serviceUsageConsumer) on project annular-mercury-512512-v1. Ask the project owner to grant it in Google Cloud Console IAM, then retry."
            }), 403
        if "authorize access to your earth engine account" in str(exc).lower():
            return jsonify({
                "error": "Google Earth Engine is not authorized. Run this in the project PowerShell terminal: .\\.venv\\Scripts\\python.exe -c \"import ee; ee.Authenticate(); ee.Initialize(project='annular-mercury-512512-v1')\""
            }), 503
        return jsonify({
            "error": "Analysis failed. Check the Flask terminal."
        }), 500


if __name__ == "__main__":
    app.run(debug=False, port=5000)





