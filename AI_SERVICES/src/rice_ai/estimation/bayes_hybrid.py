"""Bayesian Few-Shot Calibration Engine for Rice AI (Seed Counting).

Đặc tả: SPEC-BAYES-2026-V1
Căn cứ: FromThanh/Copy of rice_fewshot_v2_colab.ipynb (Cell 04: rice_fewshot_v2.py)

Mô hình:
    log N = phys(x) + b_lot + g(z)
    - Nhánh V (Vision geometry): phys = log V_bulk - log V_g
    - Nhánh W (Weight sensor):    phys = log W
    - Nhiễu đo chất lượng:        var_i = s0^2 + sg^2 / n_i  (n_i = số hạt nguyên sạch)
    - Cập nhật liên hợp:         Normal-Inverse-Gamma từ K cốc support
    - Hợp nhất không gian log & Cổng bất đồng 3σ giữa 2 nhánh
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy.stats import norm, t as student_t

Z90: float = float(norm.ppf(0.95))  # 1.6448536269514722


@dataclass(frozen=True)
class BranchFittedParams:
    """Tham số đã huấn luyện offline của một nhánh ước lượng."""
    phys_type: str                   # "vision" (lV - o) hoặc "weight" (lW)
    b0: float                        # Kỳ vọng tiên nghiệm của b_lot
    tau: float                       # Độ lệch chuẩn tiên nghiệm của b_lot
    s0: float                        # Phương sai quan sát nền tối thiểu
    sg: float                        # Hệ số phương sai chất lượng (sg / n)
    lam: float = 1.0                 # Hệ số hiệu chuẩn khoảng tin cậy 90% (calibrated lambda)
    nu0: float = 4.0                 # Bậc tự do tiên nghiệm cho phân phối Inverse-Gamma
    g_weights: Optional[List[float]] = None  # Trọng số Ridge g(z)
    g_mu: Optional[List[float]] = None       # Vector trung bình chuẩn hóa của z
    g_sd: Optional[List[float]] = None       # Vector độ lệch chuẩn chuẩn hóa của z
    z_cols: Tuple[str, ...] = ()             # Danh sách tên các biến đặc trưng trong z


@dataclass
class BayesPredictionOutput:
    """Kết quả ước lượng của mô-đun Bayesian Hybrid."""
    final_count: int
    ci90_lower: int
    ci90_upper: int
    relative_ci90_width_pct: float
    fused_mean_log: float
    fused_var_log: float
    gate_status: str                 # "passed", "diverged", "single_branch"
    sigma_distance: float
    branch_estimates: Dict[str, Any] = field(default_factory=dict)
    flags: List[str] = field(default_factory=list)
    support_cups_used: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Chuyển đổi thành dictionary cho response API."""
        return {
            "predicted_count": self.final_count,
            "estimate": self.final_count,
            "ci90_lower": self.ci90_lower,
            "ci90_upper": self.ci90_upper,
            "relative_ci90_width_pct": round(self.relative_ci90_width_pct, 2),
            "disagreement_flag": (self.gate_status == "diverged"),
            "disagreement_gate": {
                "status": self.gate_status,
                "sigma_distance": round(self.sigma_distance, 3),
            },
            "branch_estimates": self.branch_estimates,
            "support_cups_used": self.support_cups_used,
            "flags": self.flags,
        }


class BayesHybridEstimator:
    """Trình ước lượng hiệu chuẩn Bayes ít mẫu (Bayesian Few-Shot Estimator)."""

    def __init__(
        self,
        branch_v: BranchFittedParams,
        branch_w: Optional[BranchFittedParams] = None,
        disagreement_sigma_gate: float = 3.0,
        lot_unseen_threshold_mm: float = 5.0,
        source_lots: Sequence[float] = (18.0, 23.0, 33.0, 42.0),
    ) -> None:
        self.branch_v = branch_v
        self.branch_w = branch_w
        self.disagreement_sigma_gate = float(disagreement_sigma_gate)
        self.lot_unseen_threshold_mm = float(lot_unseen_threshold_mm)
        self.source_lots = [float(l) for l in source_lots]

    # ─────────────────────────────────────────────────────────────────────────
    # Thuật toán tính toán từng nhánh
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _phys(params: BranchFittedParams, data: Dict[str, Any]) -> float:
        """Tính giá trị thành phần vật lý cơ sở trong không gian log."""
        if params.phys_type == "vision":
            lV = float(data.get("lV") or 0.0)
            o = float(data.get("o") or 0.0)
            return lV - o
        elif params.phys_type == "weight":
            return float(data.get("lW") or 0.0)
        raise ValueError(f"phys_type không hợp lệ: {params.phys_type}")

    @staticmethod
    def _gz(params: BranchFittedParams, data: Dict[str, Any]) -> float:
        """Dự đoán phần dư chia sẻ g(z) từ mô hình Ridge."""
        if not params.g_weights or not params.z_cols:
            return 0.0

        z_vals: List[float] = []
        for col in params.z_cols:
            val = data.get(col)
            if val is None or not math.isfinite(float(val)):
                return 0.0
            z_vals.append(float(val))

        mu = params.g_mu or [0.0] * len(z_vals)
        sd = params.g_sd or [1.0] * len(z_vals)
        weights = params.g_weights

        z_scaled = [(z - m) / (s if s > 1e-9 else 1.0) for z, m, s in zip(z_vals, mu, sd)]
        return float(sum(w * z for w, z in zip(weights, z_scaled)))

    @staticmethod
    def _var(params: BranchFittedParams, n: int) -> float:
        """Phương sai nhiễu đo chất lượng: var_i = s0 + sg / n_i."""
        effective_n = max(1, int(n))
        return float(params.s0 + params.sg / float(effective_n))

    def _posterior(
        self,
        params: BranchFittedParams,
        support_cups: Optional[List[Dict[str, Any]]],
        is_lot_unseen: bool = False,
    ) -> Dict[str, float]:
        """Cập nhật phân phối hậu nghiệm Normal-Inverse-Gamma từ K cốc support."""
        s_ref = params.s0 + params.sg / 14.0  # Phương sai cốc tham chiếu chuẩn (n ~ 14 hạt)
        tau = params.tau * (2.0 if is_lot_unseen else 1.0)  # Tăng phương sai tiên nghiệm nếu lot lạ
        k0 = s_ref / (tau ** 2)
        a0 = params.nu0 / 2.0
        b0 = params.nu0 * s_ref / 2.0

        if not support_cups:
            return {"m": params.b0, "k": k0, "a": a0, "b": b0, "s_ref": s_ref}

        valid_supports: List[Tuple[float, float]] = []  # (residual rs, weight w)
        for cup in support_cups:
            n_actual = cup.get("actual_count")
            if n_actual is None or n_actual <= 0:
                continue
            y_j = math.log(float(n_actual))

            # Trích xuất dữ liệu của cốc support
            sup_data: Dict[str, Any] = {}
            if params.phys_type == "vision":
                v_bulk = cup.get("bulk_volume_mm3")
                v_g = cup.get("mean_clean_grain_volume_mm3")
                if v_bulk is None or v_bulk <= 0:
                    continue
                sup_data["lV"] = math.log(float(v_bulk))
                sup_data["o"] = math.log(float(v_g)) if v_g and v_g > 0 else 0.0
            else:
                w_val = cup.get("weight_g")
                if w_val is None or w_val <= 0:
                    continue
                sup_data["lW"] = math.log(float(w_val))
                v_bulk = cup.get("bulk_volume_mm3")
                if v_bulk and v_bulk > 0:
                    sup_data["lV"] = math.log(float(v_bulk))

            n_grains = int(cup.get("whole_grains_measured_count", 14) or 14)
            phys_j = self._phys(params, sup_data)
            gz_j = self._gz(params, sup_data)
            rs_j = y_j - phys_j - gz_j
            var_j = self._var(params, n_grains)
            w_j = s_ref / var_j
            valid_supports.append((rs_j, w_j))

        k_count = len(valid_supports)
        if k_count == 0:
            return {"m": params.b0, "k": k0, "a": a0, "b": b0, "s_ref": s_ref}

        sum_w = sum(w for _, w in valid_supports)
        sum_w_rs = sum(w * rs for rs, w in valid_supports)
        sum_w_rs2 = sum(w * (rs ** 2) for rs, w in valid_supports)

        kn = k0 + sum_w
        mn = (k0 * params.b0 + sum_w_rs) / kn
        an = a0 + k_count / 2.0
        bn = b0 + 0.5 * (sum_w_rs2 + k0 * (params.b0 ** 2) - kn * (mn ** 2))
        bn = max(bn, 1e-12)

        return {"m": mn, "k": kn, "a": an, "b": bn, "s_ref": s_ref}

    def _predict_branch(
        self,
        params: BranchFittedParams,
        query_data: Dict[str, Any],
        post: Dict[str, float],
    ) -> Dict[str, Any]:
        """Tính phân phối dự đoán Lognormal cho một nhánh."""
        n_grains = int(query_data.get("n", 14) or 14)
        h = self._var(params, n_grains) / post["s_ref"]

        sig2 = post["b"] / post["a"]
        dof = 2.0 * post["a"]
        v_pred = sig2 * (h + 1.0 / post["k"]) * (params.lam ** 2)
        sd_pred = math.sqrt(v_pred)

        mean_log = self._phys(params, query_data) + self._gz(params, query_data) + post["m"]
        zq = Z90 if not math.isfinite(dof) or dof > 100 else float(student_t.ppf(0.95, dof))

        n_est = math.exp(mean_log)
        n_lo = math.exp(mean_log - zq * sd_pred)
        n_hi = math.exp(mean_log + zq * sd_pred)

        return {
            "mean_log": mean_log,
            "var_log": v_pred,
            "sd_log": sd_pred,
            "dof": dof,
            "predicted_count": int(round(n_est)),
            "ci90_lower": max(0, int(round(n_lo))),
            "ci90_upper": max(0, int(round(n_hi))),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Luồng suy luận chính (Runtime Prediction & Fusion)
    # ─────────────────────────────────────────────────────────────────────────

    def predict(
        self,
        query_data: Dict[str, Any],
        support_cups: Optional[List[Dict[str, Any]]] = None,
        scale_unvalidated: bool = False,
    ) -> BayesPredictionOutput:
        """Thực hiện ước lượng số hạt Bayes có hợp nhất hai nhánh và cổng bất đồng 3σ."""
        flags: List[str] = []
        if scale_unvalidated:
            flags.append("SCALE_UNVALIDATED")

        # 1. Kiểm tra lot chưa từng thấy (Lot Unseen)
        inner_diam = float(query_data.get("inner_diameter_mm", 0.0) or 0.0)
        is_lot_unseen = False
        if inner_diam > 0 and self.source_lots:
            min_dist = min(abs(inner_diam - lot) for lot in self.source_lots)
            if min_dist > self.lot_unseen_threshold_mm:
                is_lot_unseen = True
                flags.append("LOT_UNSEEN")

        # 2. Kiểm tra số lượng hạt đo được (Low Grain Count)
        n_grains = int(query_data.get("n", 14) or 14)
        if n_grains < 5:
            flags.append("LOW_GRAIN_COUNT")

        # 3. Tính toán Nhánh Thị giác V
        can_run_v = query_data.get("lV") is not None and math.isfinite(float(query_data["lV"]))
        res_v: Optional[Dict[str, Any]] = None
        if can_run_v:
            post_v = self._posterior(self.branch_v, support_cups, is_lot_unseen)
            res_v = self._predict_branch(self.branch_v, query_data, post_v)
            if scale_unvalidated:
                # Nới rộng khoảng tin cậy của nhánh V thêm 25% nếu scale chưa kiểm chứng
                res_v["var_log"] *= (1.25 ** 2)
                res_v["sd_log"] = math.sqrt(res_v["var_log"])
                zq = Z90
                res_v["ci90_lower"] = max(0, int(round(math.exp(res_v["mean_log"] - zq * res_v["sd_log"]))))
                res_v["ci90_upper"] = max(0, int(round(math.exp(res_v["mean_log"] + zq * res_v["sd_log"]))))

        # 4. Tính toán Nhánh Cân W
        raw_w = query_data.get("weight_g") or (math.exp(query_data["lW"]) if query_data.get("lW") is not None else None)
        can_run_w = (
            self.branch_w is not None
            and raw_w is not None
            and raw_w > 0
            and math.isfinite(raw_w)
        )

        # Kiểm tra bất thường cân sơ bộ (khối lượng trung bình hạt > 0.1g/hạt)
        if can_run_w and res_v is not None and res_v["predicted_count"] > 0:
            avg_weight_per_grain = float(raw_w) / float(res_v["predicted_count"])
            if avg_weight_per_grain > 0.10:
                flags.append("WEIGHT_CONFLICT")
                can_run_w = False  # Khối lượng vô lý, loại bỏ nhánh cân

        res_w: Optional[Dict[str, Any]] = None
        if can_run_w and self.branch_w is not None:
            post_w = self._posterior(self.branch_w, support_cups, is_lot_unseen)
            res_w = self._predict_branch(self.branch_w, query_data, post_w)

        # 5. Phân xử và Hợp nhất (Log-space Fusion & Disagreement Gate)
        branch_estimates: Dict[str, Any] = {}
        if res_v is not None:
            branch_estimates["vision_only"] = {
                "predicted_count": res_v["predicted_count"],
                "ci90_lower": res_v["ci90_lower"],
                "ci90_upper": res_v["ci90_upper"],
                "variance": round(res_v["var_log"], 6),
            }
        if res_w is not None:
            branch_estimates["weight_assisted"] = {
                "predicted_count": res_w["predicted_count"],
                "ci90_lower": res_w["ci90_lower"],
                "ci90_upper": res_w["ci90_upper"],
                "variance": round(res_w["var_log"], 6),
            }

        k_used = len(support_cups) if support_cups else 0

        # Tình huống 5A: Cả 2 nhánh đều khả dụng -> Kiểm tra Cổng 3σ
        if res_v is not None and res_w is not None:
            mean_v, var_v = res_v["mean_log"], res_v["var_log"]
            mean_w, var_w = res_w["mean_log"], res_w["var_log"]

            sigma_delta = math.sqrt(var_w + var_v)
            delta = abs(mean_w - mean_v)
            sigma_dist = delta / sigma_delta if sigma_delta > 1e-9 else 0.0

            if sigma_dist <= self.disagreement_sigma_gate:
                # Cổng kiểm soát: Hai nhánh thống nhất -> Inverse-variance pooling
                gate_status = "passed"
                fused_var = 1.0 / (1.0 / var_w + 1.0 / var_v)
                fused_mean = fused_var * (mean_w / var_w + mean_v / var_v)
                fused_sd = math.sqrt(fused_var)
                fused_est = int(round(math.exp(fused_mean)))
                fused_lo = max(0, int(round(math.exp(fused_mean - Z90 * fused_sd))))
                fused_hi = max(0, int(round(math.exp(fused_mean + Z90 * fused_sd))))
            else:
                # Cổng kiểm soát: Bất đồng 3σ -> Kích hoạt cờ WEIGHT_CONFLICT
                gate_status = "diverged"
                if "WEIGHT_CONFLICT" not in flags:
                    flags.append("WEIGHT_CONFLICT")
                # Chính sách phân giải: Ưu tiên nhánh cân, mở rộng khoảng bao quát cả 2 nhánh
                fused_mean = mean_w
                fused_var = var_w
                fused_est = res_w["predicted_count"]
                fused_lo = min(res_w["ci90_lower"], res_v["ci90_lower"])
                fused_hi = max(res_w["ci90_upper"], res_v["ci90_upper"])

        # Tình huống 5B: Chỉ có Nhánh Cân W
        elif res_w is not None:
            gate_status = "single_branch"
            sigma_dist = 0.0
            fused_mean = res_w["mean_log"]
            fused_var = res_w["var_log"]
            fused_est = res_w["predicted_count"]
            fused_lo = res_w["ci90_lower"]
            fused_hi = res_w["ci90_upper"]

        # Tình huống 5C: Chỉ có Nhánh Thị giác V
        elif res_v is not None:
            gate_status = "single_branch"
            sigma_dist = 0.0
            fused_mean = res_v["mean_log"]
            fused_var = res_v["var_log"]
            fused_est = res_v["predicted_count"]
            fused_lo = res_v["ci90_lower"]
            fused_hi = res_v["ci90_upper"]

        else:
            raise ValueError("Không thể thực thi Bayes: Cả hai nhánh V và W đều thiếu dữ liệu đầu vào.")

        width_pct = (float(fused_hi - fused_lo) / float(fused_est) * 100.0) if fused_est > 0 else 0.0

        return BayesPredictionOutput(
            final_count=fused_est,
            ci90_lower=fused_lo,
            ci90_upper=fused_hi,
            relative_ci90_width_pct=width_pct,
            fused_mean_log=fused_mean,
            fused_var_log=fused_var,
            gate_status=gate_status,
            sigma_distance=sigma_dist,
            branch_estimates=branch_estimates,
            flags=flags,
            support_cups_used=k_used,
        )
