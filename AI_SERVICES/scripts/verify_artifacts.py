#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
CLI: XÁC THỰC KHO LƯU TRỮ MÔ HÌNH (PREFLIGHT ARTIFACTS VERIFIER)
===============================================================================
Mục đích:
  - Nạp và thẩm định toàn bộ các mô hình triển khai của hệ thống Rice Vision AI:
    1. YOLO Segmentation Model (.pt)
    2. CNN DenseNet121 Classification Model (.keras)
    3. Extra Trees Regression Bundle (model.joblib, scaler.joblib, feature_schema.json)
  - Đảm bảo tính tương thích, giao diện inference, kích thước, và smoke prediction.
  - Trả về exit code 0 nếu tất cả đạt chuẩn (PASS), khác 0 nếu thất bại (FAIL).

Cách sử dụng:
    python scripts/verify_artifacts.py                  # Xác thực toàn bộ 3 mô hình
    python scripts/verify_artifacts.py --all            # Xác thực toàn bộ 3 mô hình
    python scripts/verify_artifacts.py --yolo           # Chỉ xác thực YOLO
    python scripts/verify_artifacts.py --cnn            # Chỉ xác thực CNN
    python scripts/verify_artifacts.py --regression     # Chỉ xác thực Regression
    python scripts/verify_artifacts.py --model-dir <dir># Xác thực thư mục regression chỉ định
===============================================================================
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

CURRENT_DIR = Path(__file__).resolve().parent
AI_SERVICES_DIR = CURRENT_DIR.parent
SRC_DIR = AI_SERVICES_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(AI_SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(AI_SERVICES_DIR))

from rice_ai.estimation.feature_schema import ALL_31_FEATURES, FEATURE_SCHEMA_VERSION
from rice_ai.models.regression_loader import load_regression_folder
from rice_ai.settings import Settings


def verify_regression_dir(model_dir: Path) -> bool:
    print("\n" + "=" * 80)
    print("🌲 [1/3] VERIFY REGRESSION MODEL BUNDLE")
    print("=" * 80)
    print(f"📁 Thư mục hồi quy  : {model_dir}")

    try:
        loaded = load_regression_folder(model_dir)
    except Exception as ex:
        print(f"❌ FAIL: Không thể nạp hoặc xác thực thư mục mô hình hồi quy: {ex}")
        return False

    print(f"🤖 Tên mô hình       : {loaded.model_name}")
    print(f"🌳 Lớp mô hình       : {type(loaded.model).__module__}.{type(loaded.model).__qualname__}")
    if loaded.scaler is not None:
        print(f"📏 Lớp tiền xử lý    : {type(loaded.scaler).__module__}.{type(loaded.scaler).__qualname__}")
    else:
        print(f"📏 Lớp tiền xử lý    : None (Explicit 'preprocessing': 'none')")
    print(f"📐 Phiên bản schema  : {loaded.schema_version}")
    print(f"📊 Số lượng đặc trưng: {len(loaded.feature_names)} / 31 (OK)")
    print(f"🏛️ Chuẩn đóng gói   : {'Legacy Adapter' if loaded.is_legacy else 'Canonical Bundle'}")

    if loaded.warnings:
        print("⚠️ Cảnh báo (không gây lỗi):")
        for w in loaded.warnings:
            print(f"   • {w}")

    # Chạy thử nghiệm dự đoán kiểm chứng
    smoke_vector = [10.0] * 31
    try:
        pred_val = loaded.predict(smoke_vector)
        print(f"🎯 Smoke Prediction  : Input [10.0]*31 -> Output: {pred_val:.2f} (PASS)")
    except Exception as ex:
        print(f"❌ FAIL: Smoke prediction gặp lỗi: {ex}")
        return False

    print("✅ REGRESSION MODEL VERIFIED: PASS")
    return True


def verify_yolo_model(settings: Settings) -> bool:
    print("\n" + "=" * 80)
    print("👁️ [2/3] VERIFY YOLO SEGMENTATION MODEL")
    print("=" * 80)

    try:
        yolo_path = settings.get_yolo_path()
        print(f"📁 Tệp mô hình YOLO : {yolo_path}")
        if not yolo_path.is_file():
            print(f"❌ FAIL: Tệp YOLO không tồn tại: {yolo_path}")
            return False
        
        file_size_mb = yolo_path.stat().st_size / (1024 * 1024)
        print(f"📦 Dung lượng tệp    : {file_size_mb:.2f} MB")

        # Thử nạp mô hình Ultralytics YOLO
        from ultralytics import YOLO
        model = YOLO(str(yolo_path))
        print(f"🤖 Kiến trúc YOLO   : {getattr(model, 'task', 'segment')}")
        print(f"🏷️ Số lượng lớp     : {len(getattr(model, 'names', {}))} ({getattr(model, 'names', {})})")
    except Exception as ex:
        print(f"❌ FAIL: Lỗi khi kiểm tra YOLO: {ex}")
        return False

    print("✅ YOLO MODEL VERIFIED: PASS")
    return True


def verify_cnn_model(settings: Settings) -> bool:
    print("\n" + "=" * 80)
    print("🌾 [3/3] VERIFY CNN GRAIN CLASSIFIER MODEL")
    print("=" * 80)

    try:
        cnn_path = settings.get_cnn_path()
        print(f"📁 Tệp mô hình CNN  : {cnn_path}")
        if not cnn_path.is_file():
            print(f"❌ FAIL: Tệp CNN không tồn tại: {cnn_path}")
            return False

        file_size_mb = cnn_path.stat().st_size / (1024 * 1024)
        print(f"📦 Dung lượng tệp    : {file_size_mb:.2f} MB")

        # Nạp GrainClassifier
        from rice_ai.vision.grain_classifier import GrainClassifier
        classifier = GrainClassifier(model_path=str(cnn_path))
        print(f"🤖 Lớp phân loại     : {type(classifier).__name__}")
        print(f"💻 Thiết bị nạp      : {getattr(classifier, 'device', 'cpu')}")
    except Exception as ex:
        print(f"❌ FAIL: Lỗi khi kiểm tra CNN: {ex}")
        return False

    print("✅ CNN MODEL VERIFIED: PASS")
    return True


def main() -> int:
    settings = Settings()

    parser = argparse.ArgumentParser(
        description="Kiểm tra tính hợp lệ và sẵn sàng của kho mô hình đóng gói (Preflight Artifacts Verifier)."
    )
    parser.add_argument(
        "--model-dir",
        type=str,
        default=None,
        help="Đường dẫn thư mục chứa mô hình hồi quy (tương thích backward).",
    )
    parser.add_argument(
        "--yolo",
        action="store_true",
        help="Chỉ kiểm tra mô hình YOLO.",
    )
    parser.add_argument(
        "--cnn",
        action="store_true",
        help="Chỉ kiểm tra mô hình CNN.",
    )
    parser.add_argument(
        "--regression",
        action="store_true",
        help="Chỉ kiểm tra mô hình Regression.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Kiểm tra toàn bộ cả 3 mô hình (mặc định nếu không chỉ định tùy chọn khác).",
    )

    args = parser.parse_args()

    # Nếu chỉ định --model-dir cụ thể, chỉ kiểm tra thư mục hồi quy đó
    if args.model_dir:
        target_dir = settings.resolve_path(args.model_dir)
        success = verify_regression_dir(target_dir)
        return 0 if success else 1

    run_all = args.all or (not args.yolo and not args.cnn and not args.regression)
    all_success = True

    print("=" * 80)
    print("🔍 RICE VISION AI — PREFLIGHT ARTIFACTS VERIFICATION SUITE")
    print("=" * 80)

    if run_all or args.regression:
        try:
            reg_dir = settings.get_regression_dir()
            if not verify_regression_dir(reg_dir):
                all_success = False
        except Exception as ex:
            print(f"❌ FAIL khi định vị thư mục hồi quy: {ex}")
            all_success = False

    if run_all or args.yolo:
        if not verify_yolo_model(settings):
            all_success = False

    if run_all or args.cnn:
        if not verify_cnn_model(settings):
            all_success = False

    print("\n" + "=" * 80)
    if all_success:
        print("🎉 TẤT CẢ CÁC MÔ HÌNH TRONG ARTIFACTS ĐÃ ĐẠT CHUẨN SẴN SÀNG TRIỂN KHAI (100% PASS)")
    else:
        print("❌ CÓ MÔ HÌNH CHƯA ĐẠT CHUẨN HOẶC GẶP LỖI.")
    print("=" * 80)

    return 0 if all_success else 1


if __name__ == "__main__":
    sys.exit(main())
