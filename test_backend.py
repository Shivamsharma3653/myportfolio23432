
import unittest
from unittest.mock import patch

from backend.app import app


class TestJalDrishtiAPI(unittest.TestCase):

    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_home_endpoint(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["project"], "Jal Drishti")

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "ok")

    def test_missing_dates(self):
        response = self.client.post("/analyze", json={})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Missing required fields", response.get_json()["error"])

    def test_non_object_json(self):
        response = self.client.post(
            "/analyze",
            json=["2024-06-15", "2024-07-15"],
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()["error"],
            "Request body must be a valid JSON object."
        )

    def test_invalid_date(self):
        data = {
            "before_start": "2024-99-45",
            "before_end": "2024-07-15",
            "after_start": "2024-07-15",
            "after_end": "2024-08-15",
        }
        response = self.client.post("/analyze", json=data)
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid date", response.get_json()["error"])

    def test_reversed_before_dates(self):
        data = {
            "before_start": "2024-07-15",
            "before_end": "2024-06-15",
            "after_start": "2024-07-20",
            "after_end": "2024-08-15",
        }
        response = self.client.post("/analyze", json=data)
        self.assertEqual(response.status_code, 400)
        self.assertIn("before_start must be earlier", response.get_json()["error"])

    def test_overlapping_periods(self):
        data = {
            "before_start": "2024-06-15",
            "before_end": "2024-07-20",
            "after_start": "2024-07-15",
            "after_end": "2024-08-15",
        }
        response = self.client.post("/analyze", json=data)
        self.assertEqual(response.status_code, 400)
        self.assertIn("must not overlap", response.get_json()["error"])

    @patch("backend.app.analyze_flood")
    def test_successful_analysis(self, mock_analyze):
        mock_analyze.return_value = {
            "before_images": 16,
            "after_images": 15,
            "candidate_flood_area_km2": 0.66,
            "flood_detected": True,
            "flood_tile_url": "https://example.com/tiles/{z}/{x}/{y}",
            "method": "Sentinel-1 VV backscatter change",
            "warning": "Candidate flood extent only; not ground-validated.",
        }

        data = {
            "before_start": "2024-06-15",
            "before_end": "2024-07-15",
            "after_start": "2024-07-15",
            "after_end": "2024-08-15",
        }

        response = self.client.post("/analyze", json=data)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["flood_detected"])
        self.assertEqual(response.get_json()["before_images"], 16)
        self.assertEqual(response.get_json()["after_images"], 15)
        mock_analyze.assert_called_once()
    

    def test_no_satellite_images(self):
        with patch(
            "backend.app.analyze_flood",
            side_effect=ValueError(
                "No Sentinel-1 images found. Try different dates."
            ),
        ):
            response = self.client.post(
                "/analyze",
                json={
                    "before_start": "2024-06-15",
                    "before_end": "2024-07-15",
                    "after_start": "2024-07-15",
                    "after_end": "2024-08-15",
                },
            )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.get_json()["error"],
            "No Sentinel-1 images found. Try different dates.",
        )

    @patch("backend.app.analyze_flood")
    def test_analysis_failure(self, mock_analyze):
        mock_analyze.side_effect = RuntimeError(
            "Simulated Earth Engine failure"
        )

        data = {
            "before_start": "2024-06-15",
            "before_end": "2024-07-15",
            "after_start": "2024-07-15",
            "after_end": "2024-08-15",
        }

        response = self.client.post("/analyze", json=data)

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.get_json()["error"],
            "Analysis failed. Check the Flask terminal.",
        )



if __name__ == "__main__":
    unittest.main(verbosity=2)
