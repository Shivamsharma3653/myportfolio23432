
from flask import Flask, request, jsonify
from datetime import date

from backend.flood_analysis import analyze_flood, REGIONS

app = Flask(__name__)


def validate_dates(data):
    required = [
        "before_start",
        "before_end",
        "after_start",
        "after_end",
    ]

    missing = [
        field for field in required
        if not data.get(field)
    ]

    if missing:
        return f"Missing required fields: {', '.join(missing)}"

    parsed = {}

    for field in required:
        try:
            parsed[field] = date.fromisoformat(data[field])
        except (ValueError, TypeError):
            return f"Invalid date for '{field}'. Use YYYY-MM-DD."

    if parsed["before_start"] >= parsed["before_end"]:
        return "before_start must be earlier than before_end."

    if parsed["after_start"] >= parsed["after_end"]:
        return "after_start must be earlier than after_end."

    if parsed["before_end"] > parsed["after_start"]:
        return "The before period must not overlap the after period."

    return None


@app.get("/")
def home():
    return jsonify({
        "project": "Jal Drishti",
        "status": "running",
        "endpoints": ["/health", "/analyze"],
        "regions": {
            key: value["label"]
            for key, value in REGIONS.items()
        },
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

    region_key = data.get("region", "koshi")

    if region_key not in REGIONS:
        return jsonify({
            "error": (
                "Unknown region. Choose one of: "
                + ", ".join(REGIONS.keys())
            )
        }), 400

    try:
        result = analyze_flood(
            data["before_start"],
            data["before_end"],
            data["after_start"],
            data["after_end"],
            region_key,
        )
        return jsonify(result)

    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422

    except Exception as exc:
        app.logger.exception("Flood analysis failed")
        message = str(exc).lower()

        if (
            "serviceusage.services.use" in message
            or "required permission to use project" in message
        ):
            return jsonify({
                "error": (
                    "Earth Engine login succeeded, but the Google "
                    "account needs the Service Usage Consumer role "
                    "on the configured Google Cloud project."
                )
            }), 403

        if "authorize access to your earth engine account" in message:
            return jsonify({
                "error": (
                    "Google Earth Engine is not authorized. "
                    "Authenticate and initialize Earth Engine "
                    "using the configured project."
                )
            }), 503

        return jsonify({
            "error": "Analysis failed. Check the Flask terminal."
        }), 500


if __name__ == "__main__":
    app.run(debug=False, port=5000)

