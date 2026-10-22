#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for Bayesian Few-Shot Calibration Engine and Loader."""

import math
import sys
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
AI_SERVICES_DIR = TEST_DIR.parent
SRC_DIR = AI_SERVICES_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(AI_SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(AI_SERVICES_DIR))

from rice_ai.contracts import PipelineError
from rice_ai.estimation.bayes_hybrid import (
    BayesHybridEstimator,
    BranchFittedParams,
)
from rice_ai.models.bayes_loader import (
    LoadedBayesProvider,
    load_bayes_estimator_from_file,
    verify_bayes_checksum,
)
from rice_ai.settings import Settings


class TestBayesEstimators(unittest.TestCase):
    def setUp(self):
        self.branch_v = BranchFittedParams(
            phys_type="vision",
            b0=-0.80,
            tau=0.20,
            s0=0.01,
            sg=0.05,
            lam=1.05,
            nu0=4.0,
            g_weights=[-0.25],
            g_mu=[3.0],
            g_sd=[0.2],
            z_cols=("o",),
        )
        self.branch_w = BranchFittedParams(
            phys_type="weight",
            b0=3.70,
            tau=0.10,
            s0=0.001,
            sg=0.01,
            lam=1.00,
            nu0=4.0,
            g_weights=[0.05, -0.02],
            g_mu=[2.5, 9.5],
            g_sd=[0.4, 0.5],
            z_cols=("lW", "lV"),
        )
        self.estimator = BayesHybridEstimator(
            branch_v=self.branch_v,
            branch_w=self.branch_w,
            disagreement_sigma_gate=3.0,
            lot_unseen_threshold_mm=5.0,
            source_lots=(18.0, 23.0, 33.0, 42.0),
        )

    def test_vision_only_prediction(self):
        """Kiểm tra khi chỉ có dữ liệu thị giác (không có cân)."""
        query = {
            "lV": math.log(15000.0),
            "o": math.log(20.0),
            "n": 14,
            "inner_diameter_mm": 23.0,
            "rice_height_mm": 35.0,
            "weight_g": None,
        }
        res = self.estimator.predict(query)
        self.assertGreater(res.final_count, 0)
        self.assertEqual(res.gate_status, "single_branch")
        self.assertIn("vision_only", res.branch_estimates)
        self.assertNotIn("weight_assisted", res.branch_estimates)
        self.assertLessEqual(res.ci90_lower, res.final_count)
        self.assertGreaterEqual(res.ci90_upper, res.final_count)

    def test_weight_only_prediction(self):
        """Kiểm tra khi chỉ có dữ liệu cân."""
        query = {
            "lV": None,
            "lW": math.log(12.5),
            "o": None,
            "n": 14,
            "inner_diameter_mm": 23.0,
            "rice_height_mm": 35.0,
            "weight_g": 12.5,
        }
        res = self.estimator.predict(query)
        self.assertGreater(res.final_count, 0)
        self.assertEqual(res.gate_status, "single_branch")
        self.assertIn("weight_assisted", res.branch_estimates)
        self.assertNotIn("vision_only", res.branch_estimates)

    def test_fused_dual_branch_passed_gate(self):
        """Kiểm tra hợp nhất 2 nhánh khi thống nhất (passed)."""
        query = {
            "lV": math.log(15000.0),
            "lW": math.log(12.5),
            "o": math.log(20.0),
            "n": 14,
            "inner_diameter_mm": 23.0,
            "rice_height_mm": 35.0,
            "weight_g": 12.5,
        }
        res = self.estimator.predict(query)
        self.assertGreater(res.final_count, 0)
        self.assertIn("vision_only", res.branch_estimates)
        self.assertIn("weight_assisted", res.branch_estimates)
        self.assertLessEqual(res.ci90_lower, res.final_count)
        self.assertGreaterEqual(res.ci90_upper, res.final_count)

    def test_disagreement_gate_diverged(self):
        """Kiểm tra cổng 3σ khi khối lượng và thể tích xung đột lớn."""
        # Khối lượng 100g (quá lớn so với thể tích)
        query = {
            "lV": math.log(15000.0),
            "lW": math.log(100.0),
            "o": math.log(20.0),
            "n": 14,
            "inner_diameter_mm": 23.0,
            "rice_height_mm": 35.0,
            "weight_g": 100.0,
        }
        res = self.estimator.predict(query)
        # Sẽ kích hoạt WEIGHT_CONFLICT
        self.assertIn("WEIGHT_CONFLICT", res.flags)

    def test_support_adaptation(self):
        """Kiểm tra cập nhật hậu nghiệm từ K cốc support."""
        query = {
            "lV": math.log(15000.0),
            "lW": math.log(12.5),
            "o": math.log(20.0),
            "n": 14,
            "inner_diameter_mm": 23.0,
            "rice_height_mm": 35.0,
            "weight_g": 12.5,
        }
        # Zero-shot prediction
        res0 = self.estimator.predict(query, support_cups=None)
        self.assertEqual(res0.support_cups_used, 0)

        # Few-shot với 1 cốc support
        support = [{
            "actual_count": 520,
            "weight_g": 12.5,
            "bulk_volume_mm3": 15000.0,
            "mean_clean_grain_volume_mm3": 20.0,
            "whole_grains_measured_count": 14,
        }]
        res1 = self.estimator.predict(query, support_cups=support)
        self.assertEqual(res1.support_cups_used, 1)

    def test_lot_unseen_flag(self):
        """Kiểm tra kích hoạt cờ LOT_UNSEEN khi gặp đường kính ly lạ (ví dụ 60mm)."""
        query = {
            "lV": math.log(15000.0),
            "lW": math.log(12.5),
            "o": math.log(20.0),
            "n": 14,
            "inner_diameter_mm": 60.0,
            "rice_height_mm": 35.0,
            "weight_g": 12.5,
        }
        res = self.estimator.predict(query)
        self.assertIn("LOT_UNSEEN", res.flags)

    def test_loader_real_params_file(self):
        """Kiểm tra nạp file tham số thực tế sinh bởi fit_bayes_params.py."""
        settings = Settings()
        provider = LoadedBayesProvider(settings)
        loaded = provider.get_estimator()
        self.assertTrue(provider.is_loaded())
        self.assertEqual(loaded.schema_version, "bayes_v1")
        self.assertGreater(len(loaded.source_lots), 0)

        # Test predict qua loaded estimator
        query = {
            "lV": math.log(18000.0),
            "lW": math.log(14.0),
            "o": math.log(21.0),
            "n": 14,
            "inner_diameter_mm": 23.0,
            "rice_height_mm": 40.0,
            "weight_g": 14.0,
        }
        out = loaded.estimator.predict(query)
        self.assertGreater(out.final_count, 0)


if __name__ == "__main__":
    unittest.main()
