"""Container detection and physical geometry stage."""
from __future__ import annotations

import math
from typing import Any, Dict, Union

import numpy as np

from rice_ai.contracts import ContainerResult, PipelineError
from rice_ai.vision.container_detector import ContainerDetectionError, detect_container_and_scale


def analyze_container(
    image: np.ndarray,
    diam_mm: float,
    height_mm: float,
    empty_mm: float,
    wall_thickness_mm: float = 1.0,
    rice_core_diam_mm: Optional[float] = None,
) -> ContainerResult:
    """Xác thực thông số vật lý và phân tích hình học vật chứa (toàn bộ tính theo đơn vị mm)."""
    # 1. Kiểm tra tính hợp lệ của tham số vật lý
    if not math.isfinite(diam_mm) or diam_mm <= 0:
        raise PipelineError(422, "INVALID_INPUT", f"Đường kính ly (diam={diam_mm}mm) phải là số dương hữu hạn.")
    if not math.isfinite(height_mm) or height_mm <= 0:
        raise PipelineError(422, "INVALID_INPUT", f"Chiều cao ly (height={height_mm}mm) phải là số dương hữu hạn.")
    if not math.isfinite(empty_mm) or empty_mm < 0:
        raise PipelineError(422, "INVALID_INPUT", f"Khoảng trống miệng ly (empty={empty_mm}mm) phải >= 0.")
    if empty_mm > height_mm:
        raise PipelineError(422, "INVALID_INPUT", f"Khoảng trống (empty={empty_mm}mm) không được lớn hơn chiều cao ly ({height_mm}mm).")
    if not math.isfinite(wall_thickness_mm) or wall_thickness_mm < 0:
        raise PipelineError(422, "INVALID_INPUT", f"Độ dày thành ly (wall_thickness={wall_thickness_mm}mm) phải >= 0.")
    if rice_core_diam_mm is not None:
        if not math.isfinite(rice_core_diam_mm) or rice_core_diam_mm <= 0:
            raise PipelineError(422, "INVALID_INPUT", f"Đường kính mặt lúa (rice_core_diam_mm={rice_core_diam_mm}mm) phải > 0.")

    # 2. Sử dụng trực tiếp giá trị chuẩn mm người dùng nhập vào (không nhân x10)
    diam_mm = float(diam_mm)
    height_mm = float(height_mm)
    empty_mm = float(empty_mm)
    wall_mm = float(wall_thickness_mm)

    # 3. Xác định đường kính dùng để tính scale thị giác (nếu có rice_core_diam_mm thì dùng cho mặt lúa)
    scale_diam_mm = float(rice_core_diam_mm) if rice_core_diam_mm is not None else diam_mm

    # 4. Gọi module thị giác phát hiện miệng ly và tỷ lệ scale (với auto-fallback adaptive -> radial)
    try:
        raw_res = detect_container_and_scale(
            image_input=image,
            inner_diam_mm=scale_diam_mm,
            container_height_mm=height_mm,
            empty_height_mm=empty_mm,
            wall_thickness_mm=wall_mm,
            detect_mode="inner",
            surface_method="adaptive",
        )
    except ContainerDetectionError as adaptive_exc:
        try:
            raw_res = detect_container_and_scale(
                image_input=image,
                inner_diam_mm=scale_diam_mm,
                container_height_mm=height_mm,
                empty_height_mm=empty_mm,
                wall_thickness_mm=wall_mm,
                detect_mode="inner",
                surface_method="radial",
            )
        except ContainerDetectionError as exc:
            raise PipelineError(422, "DETECTION_FAILED", str(exc)) from exc

    pixels_per_mm = float(raw_res.get("pixels_per_mm", 0.0))
    if pixels_per_mm <= 0 or not math.isfinite(pixels_per_mm):
        raise PipelineError(
            status_code=422,
            error_code="DETECTION_FAILED",
            message="Không thể phát hiện miệng ly hoặc tỷ lệ pixels/mm không hợp lệ.",
        )

    # Kiểm tra chéo độ tin cậy của scale hình học
    # Nếu detector chưa kiểm chứng hoặc đường kính phát hiện lệch quá 15% so với khai báo
    detected_diam_px = float(raw_res.get("inner_diameter_px", 0.0))
    metric_validated = bool(raw_res.get("metric_accuracy_validated", False))
    scale_unvalidated = not metric_validated
    if detected_diam_px > 0 and pixels_per_mm > 0:
        implied_diam_mm = detected_diam_px / pixels_per_mm
        if abs(implied_diam_mm - scale_diam_mm) / scale_diam_mm > 0.15:
            scale_unvalidated = True
    raw_res["scale_unvalidated"] = scale_unvalidated

    # The project protocol defines the cup as a cylinder with constant inner
    # diameter. Do not use a detector-specific bulk-volume approximation.
    rice_h_mm = float(max(0.0, height_mm - empty_mm))
    bulk_vol_mm3 = math.pi * ((diam_mm / 2.0) ** 2) * rice_h_mm

    return ContainerResult(
        inner_diam_mm=diam_mm,
        container_height_mm=height_mm,
        empty_height_mm=empty_mm,
        rice_height_mm=rice_h_mm,
        bulk_volume_mm3=bulk_vol_mm3,
        pixels_per_mm=pixels_per_mm,
        raw_dict=raw_res,
        visual_overlay=raw_res.get("overlay_bgr"),
    )
