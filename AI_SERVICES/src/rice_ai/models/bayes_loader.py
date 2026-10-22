"""Bayesian Calibration Model and Configuration Loader.

Đặc tả: SPEC-BAYES-2026-V1
Cung cấp cơ chế nạp, xác thực mã băm SHA-256, smoke test và quản lý vòng đời
của mô hình Bayesian Few-Shot Calibration trong dịch vụ AI_SERVICES.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from rice_ai.contracts import PipelineError
from rice_ai.estimation.bayes_hybrid import (
    BayesHybridEstimator,
    BranchFittedParams,
)
from rice_ai.settings import Settings

logger = logging.getLogger("rice_ai.models.bayes_loader")


@dataclass
class LoadedBayesEstimator:
    """Đối tượng mô-đun Bayes đã nạp hoàn tất và sẵn sàng suy luận."""
    estimator: BayesHybridEstimator
    params_path: Path
    checksum: str
    schema_version: str
    source_lots: List[int]
    warnings: List[str] = field(default_factory=list)


def verify_bayes_checksum(raw_dict: Dict[str, Any], expected_checksum: str) -> bool:
    """Xác thực mã băm SHA-256 canonical của nội dung file cấu hình."""
    content_copy = {k: v for k, v in raw_dict.items() if k != "checksum_sha256"}
    canonical = json.dumps(content_copy, sort_keys=True, separators=(",", ":"))
    actual_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return actual_hash.lower() == expected_checksum.lower()


def parse_branch_params(b_dict: Dict[str, Any]) -> BranchFittedParams:
    """Chuyển đổi dictionary cấu hình nhánh thành dataclass BranchFittedParams."""
    return BranchFittedParams(
        phys_type=str(b_dict.get("phys_type") or ("vision" if b_dict.get("use_vg") else "weight")),
        b0=float(b_dict["b0"]),
        tau=float(b_dict["tau"]),
        s0=float(b_dict["s0"]),
        sg=float(b_dict["sg"]),
        lam=float(b_dict.get("lam", 1.0)),
        nu0=float(b_dict.get("nu0", 4.0)),
        g_weights=b_dict.get("g_weights"),
        g_mu=b_dict.get("g_mu"),
        g_sd=b_dict.get("g_sd"),
        z_cols=tuple(b_dict.get("z_cols", ())),
    )


def load_bayes_estimator_from_file(params_path: Path) -> LoadedBayesEstimator:
    """Nạp file cấu hình JSON, xác thực tính toàn vẹn và smoke test."""
    if not params_path.is_file():
        raise FileNotFoundError(f"Không tìm thấy file tham số Bayes: {params_path}")

    try:
        content_text = params_path.read_text(encoding="utf-8")
        raw = json.loads(content_text)
    except Exception as ex:
        raise PipelineError(
            500,
            "ARTIFACT_INCOMPATIBLE",
            f"File tham số Bayes bị hỏng hoặc không đúng định dạng JSON: {ex}",
        ) from ex

    schema_version = str(raw.get("schema_version") or "")
    if schema_version != "bayes_v1":
        raise PipelineError(
            500,
            "ARTIFACT_INCOMPATIBLE",
            f"Phiên bản schema tham số Bayes không được hỗ trợ: '{schema_version}', kỳ vọng 'bayes_v1'",
        )

    expected_checksum = str(raw.get("checksum_sha256") or "")
    if not expected_checksum or not verify_bayes_checksum(raw, expected_checksum):
        raise PipelineError(
            500,
            "ARTIFACT_INCOMPATIBLE",
            f"Mã checksum SHA-256 của file tham số Bayes không hợp lệ hoặc file đã bị chỉnh sửa!",
        )

    warnings_list: List[str] = []
    hyper = raw.get("hyperparameters", {})
    source_lots = [int(l) for l in hyper.get("source_lots", [18, 23, 33, 42])]
    disagreement_gate = float(hyper.get("disagreement_sigma_gate", 3.0))
    lot_unseen_thresh = float(hyper.get("lot_unseen_threshold_mm", 5.0))

    # Khởi tạo hai nhánh
    if "branch_v" not in raw:
        raise PipelineError(500, "ARTIFACT_INCOMPATIBLE", "Thiếu cấu hình 'branch_v' trong file tham số Bayes")
    branch_v = parse_branch_params(raw["branch_v"])

    branch_w: Optional[BranchFittedParams] = None
    if "branch_w" in raw:
        branch_w = parse_branch_params(raw["branch_w"])

    estimator = BayesHybridEstimator(
        branch_v=branch_v,
        branch_w=branch_w,
        disagreement_sigma_gate=disagreement_gate,
        lot_unseen_threshold_mm=lot_unseen_thresh,
        source_lots=source_lots,
    )

    # Smoke Test kiểm tra tính toán thực tế
    try:
        test_query = {
            "lV": math.log(15000.0),
            "lW": math.log(12.5),
            "o": math.log(20.0),
            "n": 14,
            "inner_diameter_mm": 23.0,
            "rice_height_mm": 35.0,
            "weight_g": 12.5,
        }
        test_out = estimator.predict(test_query)
        if test_out.final_count <= 0 or not math.isfinite(test_out.final_count):
            raise ValueError(f"Smoke test trả về kết quả không hợp lệ: {test_out.final_count}")
    except Exception as ex:
        raise PipelineError(
            500,
            "INFERENCE_FAILED",
            f"Smoke test cho mô-đun Bayes thất bại: {ex}",
        ) from ex

    logger.info(
        "Nạp thành công mô-đun Bayesian Hybrid từ %s (Checksum: %s...)",
        params_path.name,
        expected_checksum[:12],
    )

    return LoadedBayesEstimator(
        estimator=estimator,
        params_path=params_path,
        checksum=expected_checksum,
        schema_version=schema_version,
        source_lots=source_lots,
        warnings=warnings_list,
    )


class LoadedBayesProvider:
    """Quản lý nạp lười (lazy loading) an toàn luồng cho mô-đun Bayes."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._loaded: Optional[LoadedBayesEstimator] = None
        self._error: Optional[str] = None
        self._lock = threading.Lock()

    def get_estimator(self) -> LoadedBayesEstimator:
        """Lấy đối tượng mô-đun Bayes đã nạp, nạp tự động nếu chưa có."""
        if self._loaded is not None:
            return self._loaded

        with self._lock:
            if self._loaded is not None:
                return self._loaded
            if self._error is not None:
                raise PipelineError(503, "MODEL_UNAVAILABLE", self._error)

            try:
                params_path = self.settings.get_bayes_params_path()
                self._loaded = load_bayes_estimator_from_file(params_path)
                return self._loaded
            except Exception as ex:
                self._error = str(ex)
                logger.error("Không thể nạp mô-đun Bayes: %s", ex)
                raise PipelineError(503, "MODEL_UNAVAILABLE", f"Mô-đun Bayes không khả dụng: {ex}") from ex

    def is_loaded(self) -> bool:
        return self._loaded is not None

    def get_error(self) -> Optional[str]:
        return self._error

    def get_status(self) -> Dict[str, Any]:
        """Báo cáo trạng thái component phục vụ /api/status."""
        if self.is_loaded():
            return {
                "status": "loaded",
                "file": self._loaded.params_path.name if self._loaded else "unknown",
                "checksum": self._loaded.checksum[:12] if self._loaded else "",
                "schema_version": self._loaded.schema_version if self._loaded else "",
            }
        if self._error:
            return {"status": "error", "error": self._error}
        try:
            p = self.settings.get_bayes_params_path()
            return {"status": "configured", "file": p.name}
        except Exception:
            return {"status": "not_found"}
