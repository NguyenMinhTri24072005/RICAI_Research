#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
End-to-end integration tests for Bayesian Few-Shot Calibration in FastAPI Rice Vision AI.
Covers API endpoints, auto-mode priority, support cups adaptation, disagreement gating,
backward compatibility, and corrupted parameters handling.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import cv2
import numpy as np

# Ensure AI_SERVICES is in sys.path
AI_SERVICES_DIR = Path(__file__).resolve().parent.parent
if str(AI_SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(AI_SERVICES_DIR))

from fastapi.testclient import TestClient
from app import app
from rice_ai.contracts import ContainerResult, GrainAnalysis, PipelineError
from rice_ai.models.bayes_loader import LoadedBayesProvider, load_bayes_estimator_from_file


class TestBayesIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        # Prepare a valid blank image bytes buffer
        img = np.ones((100, 100, 3), dtype=np.uint8) * 128
        _, buf = cv2.imencode(".jpg", img)
        cls.dummy_img_bytes = buf.tobytes()

    def _get_mock_container(self, diam_mm=17.8, bulk_vol=5724.8):
        return ContainerResult(
            inner_diam_mm=diam_mm,
            container_height_mm=33.9,
            empty_height_mm=10.9,
            rice_height_mm=23.0,
            bulk_volume_mm3=bulk_vol,
            pixels_per_mm=67.0,
            raw_dict={"inner_w_px": 1192.6, "surface_isolated_bgr": np.zeros((100, 100, 3), dtype=np.uint8)},
        )

    def _get_mock_grains(self, n=5):
        whole_grains = [
            {
                "length_mm": 7.5,
                "width_mm": 2.5,
                "thickness_mm": 1.8,
                "area_mm2": 15.0,
                "volume_mm3": 17.5,
                "vol_px3": 5200.0,
            }
            for _ in range(n)
        ]
        return GrainAnalysis(
            whole_grains=whole_grains,
            broken_grains=[],
            chalky_grains=[],
            foreign_objects=[],
            total_detected=n,
            classified_counts={"hat_nguyen": n, "hat_khuyet_tat": 0},
            volumes_px3=[5200.0] * n,
            skipped_measurement_count=0,
            uniformity_metrics={
                "uniformity_rate_pct": 94.5,
                "weighted_log_grain_volume": float(np.log(17.5)),
                "whole_grains_measured_count": n,
            },
        )

    def test_01_api_status_reports_bayes_ready(self):
        """Verify GET /api/status exposes Bayesian Few-Shot calibration readiness and capabilities."""
        res = self.client.get("/api/status")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("bayes", data.get("components", {}))
        bayes_comp = data["components"]["bayes"]
        self.assertIn(bayes_comp.get("status"), ["loaded", "configured"])
        self.assertEqual(data.get("readiness"), "ready")
        self.assertIn("bayesian_fewshot_calibration", data.get("capabilities", []))
        self.assertIn("disagreement_gate_3sigma", data.get("capabilities", []))

    @patch("rice_ai.pipeline.runner.analyze_container")
    @patch("rice_ai.pipeline.runner.process_grains")
    def test_02_predict_bayes_mode_without_support(self, mock_grains, mock_container):
        """Verify POST /predict with estimator_mode='bayes' generates 90% CI and branch estimates."""
        mock_container.return_value = self._get_mock_container()
        mock_grains.return_value = self._get_mock_grains(5)

        files = {"file": ("cup.jpg", self.dummy_img_bytes, "image/jpeg")}
        data = {
            "diam": 1.78,
            "height": 3.39,
            "empty": 1.09,
            "weight_total": 2.69,
            "rice_core_diam_mm": 17.8,
            "estimator_mode": "bayes",
        }

        res = self.client.post("/predict", data=data, files=files)
        self.assertEqual(res.status_code, 200)
        resp_data = res.json()
        self.assertEqual(resp_data.get("status"), "success")
        
        estimation = resp_data["estimation"]
        self.assertEqual(estimation.get("method_used"), "bayes_hybrid")
        self.assertIsNotNone(estimation.get("bayes_est"))
        
        bayes = estimation["bayes_est"]
        self.assertGreater(bayes["estimate"], 0)
        self.assertLess(bayes["ci90_lower"], bayes["estimate"])
        self.assertGreater(bayes["ci90_upper"], bayes["estimate"])
        self.assertIn("vision_only", bayes["branch_estimates"])
        self.assertIn("weight_assisted", bayes["branch_estimates"])
        self.assertFalse(bayes["disagreement_flag"])

    @patch("rice_ai.pipeline.runner.analyze_container")
    @patch("rice_ai.pipeline.runner.process_grains")
    def test_03_predict_bayes_mode_with_support_cups(self, mock_grains, mock_container):
        """Verify few-shot adaptation when support_cups JSON payload is supplied."""
        mock_container.return_value = self._get_mock_container()
        mock_grains.return_value = self._get_mock_grains(5)

        files = {"file": ("cup.jpg", self.dummy_img_bytes, "image/jpeg")}
        support_cups = [
            {
                "bulk_volume_mm3": 5700.0,
                "weight_g": 2.65,
                "mean_clean_grain_volume_mm3": 17.5,
                "actual_count": 142,
                "whole_grains_measured_count": 5,
            },
            {
                "bulk_volume_mm3": 5720.0,
                "weight_g": 2.68,
                "mean_clean_grain_volume_mm3": 17.4,
                "actual_count": 145,
                "whole_grains_measured_count": 5,
            },
        ]
        data = {
            "diam": 1.78,
            "height": 3.39,
            "empty": 1.09,
            "weight_total": 2.69,
            "estimator_mode": "bayes",
            "support_cups": json.dumps(support_cups),
        }

        res = self.client.post("/predict", data=data, files=files)
        self.assertEqual(res.status_code, 200)
        resp_data = res.json()
        bayes = resp_data["estimation"]["bayes_est"]
        self.assertGreater(bayes["estimate"], 0)
        self.assertEqual(bayes["support_cups_used"], 2)
        self.assertLess(bayes["ci90_lower"], bayes["estimate"])
        self.assertGreater(bayes["ci90_upper"], bayes["estimate"])

    @patch("rice_ai.pipeline.runner.analyze_container")
    @patch("rice_ai.pipeline.runner.process_grains")
    def test_04_auto_mode_prioritizes_bayes_hybrid(self, mock_grains, mock_container):
        """Verify that in estimator_mode='auto', bayes_hybrid is chosen as Priority #1."""
        mock_container.return_value = self._get_mock_container()
        mock_grains.return_value = self._get_mock_grains(5)

        files = {"file": ("cup.jpg", self.dummy_img_bytes, "image/jpeg")}
        data = {
            "diam": 1.78,
            "height": 3.39,
            "empty": 1.09,
            "weight_total": 2.69,
            "estimator_mode": "auto",
        }

        res = self.client.post("/predict", data=data, files=files)
        self.assertEqual(res.status_code, 200)
        estimation = res.json()["estimation"]
        self.assertEqual(estimation.get("method_used"), "bayes_hybrid")
        self.assertEqual(estimation.get("final"), estimation.get("bayes_est", {}).get("estimate"))

    @patch("rice_ai.pipeline.runner.analyze_container")
    @patch("rice_ai.pipeline.runner.process_grains")
    def test_05_disagreement_gate_triggers_on_weight_conflict(self, mock_grains, mock_container):
        """Verify 3-sigma disagreement gate flags anomalous weight and falls back to branch V."""
        mock_container.return_value = self._get_mock_container()
        mock_grains.return_value = self._get_mock_grains(5)

        files = {"file": ("cup.jpg", self.dummy_img_bytes, "image/jpeg")}
        # Anomalous weight: 45.0 grams for ~140 grains (normal is ~2.7g)
        data = {
            "diam": 1.78,
            "height": 3.39,
            "empty": 1.09,
            "weight_total": 45.0,
            "estimator_mode": "bayes",
        }

        res = self.client.post("/predict", data=data, files=files)
        self.assertEqual(res.status_code, 200)
        resp_data = res.json()
        bayes = resp_data["estimation"]["bayes_est"]
        self.assertIn("WEIGHT_CONFLICT", [f.upper() for f in bayes["flags"]])
        # When weight conflict occurs, estimate falls back to vision_only branch
        self.assertAlmostEqual(bayes["estimate"], bayes["branch_estimates"]["vision_only"]["predicted_count"], places=1)

    @patch("rice_ai.pipeline.runner.analyze_container")
    @patch("rice_ai.pipeline.runner.process_grains")
    def test_06_backward_compatibility_legacy_modes(self, mock_grains, mock_container):
        """Verify legacy modes ('regression', 'geometry') remain intact and functional."""
        mock_container.return_value = self._get_mock_container()
        mock_grains.return_value = self._get_mock_grains(5)

        files = {"file": ("cup.jpg", self.dummy_img_bytes, "image/jpeg")}
        
        # Test legacy regression mode
        res_reg = self.client.post(
            "/predict",
            data={"diam": 1.78, "height": 3.39, "empty": 1.09, "weight_total": 2.69, "estimator_mode": "regression"},
            files=files,
        )
        self.assertEqual(res_reg.status_code, 200)
        self.assertEqual(res_reg.json()["estimation"]["method_used"], "regression_ExtraTrees")

        # Test legacy geometry mode
        res_geo = self.client.post(
            "/predict",
            data={"diam": 1.78, "height": 3.39, "empty": 1.09, "estimator_mode": "geometry"},
            files=files,
        )
        self.assertEqual(res_geo.status_code, 200)
        self.assertEqual(res_geo.json()["estimation"]["method_used"], "geometry")

    def test_07_corrupted_parameter_file_graceful_handling(self):
        """Verify load_bayes_estimator_from_file raises ARTIFACT_INCOMPATIBLE and provider marks error."""
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write('{"version": "bayes_v1", "checksum_sha256": "bad_hash", "branch_V": {}}')
            temp_path = f.name

        try:
            # 1. Direct load fails checksum validation
            with self.assertRaises(PipelineError) as ctx:
                load_bayes_estimator_from_file(Path(temp_path))
            self.assertIn(ctx.exception.error_code, ["ARTIFACT_INCOMPATIBLE", "MODEL_CORRUPTED"])

            # 2. Provider transitions to error state
            mock_settings = MagicMock()
            mock_settings.get_bayes_params_path.return_value = Path(temp_path)
            provider = LoadedBayesProvider(settings=mock_settings)
            self.assertFalse(provider.is_loaded())
            
            with self.assertRaises(PipelineError):
                provider.get_estimator()
            
            self.assertEqual(provider.get_status().get("status"), "error")
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_08_invalid_support_cups_rejected(self):
        """Verify that malformed JSON or non-array support_cups returns 422 INVALID_INPUT."""
        files = {"file": ("cup.jpg", self.dummy_img_bytes, "image/jpeg")}
        
        # 1. Malformed JSON string
        data_bad_json = {
            "diam": 1.78, "height": 3.39, "empty": 1.09,
            "support_cups": "{not_a_valid_json}"
        }
        res1 = self.client.post("/predict", data=data_bad_json, files=files)
        self.assertEqual(res1.status_code, 422)
        self.assertEqual(res1.json().get("error", {}).get("code"), "INVALID_INPUT")
        self.assertEqual(res1.json().get("error", {}).get("field"), "support_cups")

        # 2. Valid JSON but not a list (e.g. dict)
        data_dict_json = {
            "diam": 1.78, "height": 3.39, "empty": 1.09,
            "support_cups": json.dumps({"actual_count": 500})
        }
        res2 = self.client.post("/predict", data=data_dict_json, files=files)
        self.assertEqual(res2.status_code, 422)
        self.assertEqual(res2.json().get("error", {}).get("code"), "INVALID_INPUT")

    def test_09_invalid_core_diameter_rejected(self):
        """Verify that invalid rice_core_diam_mm (e.g. <=0 or >200) returns 422 INVALID_INPUT."""
        files = {"file": ("cup.jpg", self.dummy_img_bytes, "image/jpeg")}
        
        # Negative core diameter
        data_neg = {
            "diam": 1.78, "height": 3.39, "empty": 1.09,
            "rice_core_diam_mm": -5.0
        }
        res = self.client.post("/predict", data=data_neg, files=files)
        self.assertEqual(res.status_code, 422)
        self.assertEqual(res.json().get("error", {}).get("code"), "INVALID_INPUT")


if __name__ == "__main__":
    unittest.main()

