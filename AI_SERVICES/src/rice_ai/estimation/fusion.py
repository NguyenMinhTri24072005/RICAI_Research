"""Fusion and Final Estimate Selection Policy."""
from __future__ import annotations

from typing import Any, Dict, Optional

from rice_ai.contracts import EstimateSet, PipelineError
from rice_ai.estimation.bayes_hybrid import BayesPredictionOutput


def select_final_estimate(
    mode: str,
    geometry_est: Optional[int],
    weight_est: Optional[int],
    regression_est: Optional[float],
    regression_model_name: Optional[str] = None,
    bayes_est_result: Optional[BayesPredictionOutput] = None,
) -> EstimateSet:
    """Quyết định kết quả ước lượng cuối cùng theo chính sách phân cấp.
    
    Quy tắc:
    - bayes: Bắt buộc có kết quả Bayesian Hybrid; ném PipelineError 503 nếu không khả dụng.
    - regression: Bắt buộc có kết quả hồi quy; ném PipelineError 503 nếu không khả dụng.
    - geometry: Bắt buộc có kết quả hình học; ném PipelineError 422 nếu thiếu mẫu hạt.
    - weight: Bắt buộc có kết quả cân mẫu; ném PipelineError 422 nếu thiếu tham số cân.
    - auto: Ưu tiên Bayesian Hybrid (khi có file tham số) -> hồi quy ExtraTrees -> hybrid -> geometry -> weight.
    """
    mode_normalized = mode.strip().lower() if mode else "auto"

    bayes_dict: Optional[Dict[str, Any]] = bayes_est_result.to_dict() if bayes_est_result else None
    ci90_lo: Optional[int] = bayes_est_result.ci90_lower if bayes_est_result else None
    ci90_hi: Optional[int] = bayes_est_result.ci90_upper if bayes_est_result else None
    branch_ests: Optional[Dict[str, Any]] = bayes_est_result.branch_estimates if bayes_est_result else None

    if mode_normalized == "bayes":
        if bayes_est_result is None:
            raise PipelineError(
                status_code=503,
                error_code="MODEL_UNAVAILABLE",
                message="Mô-đun Bayesian Calibration không khả dụng hoặc dự đoán thất bại ở chế độ bayes mode.",
            )
        final_val = bayes_est_result.final_count
        method = "bayes_hybrid"

    elif mode_normalized == "regression":
        if regression_est is None:
            raise PipelineError(
                status_code=503,
                error_code="MODEL_UNAVAILABLE",
                message="Mô hình hồi quy không khả dụng hoặc dự đoán thất bại ở chế độ regression mode.",
            )
        final_val = int(round(regression_est))
        method = f"regression_{regression_model_name or 'model'}"

    elif mode_normalized == "geometry":
        if geometry_est is None:
            raise PipelineError(
                status_code=422,
                error_code="INVALID_INPUT",
                message="Không thể ước lượng theo phương pháp hình học do không có hạt hợp lệ được đo.",
            )
        final_val = geometry_est
        method = "geometry"

    elif mode_normalized == "weight":
        if weight_est is None:
            raise PipelineError(
                status_code=422,
                error_code="INVALID_INPUT",
                message="Không thể ước lượng theo cân nặng do thiếu hoặc sai lệch thông số cân mẫu.",
            )
        final_val = weight_est
        method = "weight"

    elif mode_normalized == "auto":
        # Ưu tiên số 1: Bayesian Few-Shot Calibration (theo quyết định phê duyệt Q3)
        if bayes_est_result is not None:
            final_val = bayes_est_result.final_count
            method = "bayes_hybrid"
        elif regression_est is not None and regression_est >= 0:
            final_val = int(round(regression_est))
            method = f"regression_{regression_model_name or 'model'}"
        elif geometry_est is not None and weight_est is not None:
            final_val = int(round((geometry_est + weight_est) / 2.0))
            method = "hybrid"
        elif geometry_est is not None:
            final_val = geometry_est
            method = "geometry"
        elif weight_est is not None:
            final_val = weight_est
            method = "weight"
        else:
            final_val = None
            method = "none"

    else:
        raise PipelineError(
            status_code=422,
            error_code="INVALID_INPUT",
            message=f"estimator_mode '{mode}' không hợp lệ. Các mode được hỗ trợ: auto, bayes, regression, geometry, weight.",
        )

    return EstimateSet(
        geometry_est=geometry_est,
        weight_est=weight_est,
        regression_est=regression_est,
        final=final_val,
        method_used=method,
        bayes_est=bayes_dict,
        ci90_lower=ci90_lo,
        ci90_upper=ci90_hi,
        branch_estimates=branch_ests,
    )

