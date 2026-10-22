#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline fitting script for Bayesian Few-Shot Calibration parameters.

Xuất ra file cấu hình JSON chứa tham số b0, tau, s0, sg, lambda và trọng số Ridge g(z)
cho cả hai nhánh Thị giác (Vision) và Cân (Weight).

Cách dùng:
    python scripts/fit_bayes_params.py [--csv PATH] [--out PATH] [--reps REPS]
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import pandas as pd
from scipy.optimize import nnls
from scipy.stats import norm, t as student_t
from sklearn.linear_model import Ridge

Z90 = float(norm.ppf(0.95))


def build_cups_dataset(csv_path: str, drop_bad_weight: bool = True) -> pd.DataFrame:
    """Tải và gom nhóm dữ liệu theo từng cốc vật lý (Physical_Sample_ID)."""
    d = pd.read_csv(csv_path)
    d["n"] = d["Whole_Grains_Filtered_Count"].clip(lower=1)
    d["nlvg"] = d["n"] * np.log(d["Mean_Clean_Grain_Volume_mm3"])

    g = d.groupby("Physical_Sample_ID")
    c = g.agg(
        N=("Actual_Count", "first"),
        V=("Bulk_Rice_Volume_mm3", "first"),
        D=("Inner_Diameter_mm", "first"),
        Hr=("Rice_Height_mm", "first"),
        W=("Weight_g", "first"),
        n=("n", "sum"),
        nlvg=("nlvg", "sum"),
        views=("n", "size"),
    ).reset_index()
    c = c.rename(columns={"Physical_Sample_ID": "cup"})

    c["o"] = c.nlvg / c.n  # Thể tích hạt logarit có trọng số
    c["y"] = np.log(c.N)
    c["lV"] = np.log(c.V)
    c["lW"] = np.log(c.W)
    c["lD"] = np.log(c.D)
    c["lasp"] = np.log(c.Hr / c.D)
    c["lot"] = c.D.round().astype(int)

    if drop_bad_weight:
        bad = c.W / c.N > 0.10
        print(f"Đã loại bỏ {int(bad.sum())} cốc có khối lượng bất thường (> 0.1 g/hạt)")
        c = c[~bad].reset_index(drop=True)

    print(f"Tổng số cốc: {len(c)} | Phân bố theo lot: {c.lot.value_counts().sort_index().to_dict()}")
    return c


def fit_single_branch(
    df: pd.DataFrame,
    phys_col: str,
    use_vg: bool,
    z_cols: List[str],
    g_mode: str = "within",
    tau_floor: float = 0.10,
    nu0: float = 4.0,
    alpha: float = 1.0,
) -> Dict[str, Any]:
    """Huấn luyện tham số cho một nhánh ước lượng."""
    phys = df[phys_col].values - (df["o"].values if use_vg else 0.0)
    r = df["y"].values - phys
    lots = df["lot"].values
    unique_lots = np.unique(lots)

    g_weights: Optional[List[float]] = None
    g_mu: Optional[List[float]] = None
    g_sd: Optional[List[float]] = None

    if z_cols:
        Z = df[z_cols].values
        g_mu = [float(m) for m in Z.mean(axis=0)]
        g_sd = [float(s + 1e-9) for s in Z.std(axis=0)]
        Zs = (Z - np.array(g_mu)) / np.array(g_sd)

        Zw = Zs.copy()
        rw = r - r.mean()
        if g_mode == "within":
            for l in unique_lots:
                mask = lots == l
                Zw[mask] -= Zs[mask].mean(axis=0)
                rw[mask] = r[mask] - r[mask].mean()

        ridge = Ridge(alpha=alpha, fit_intercept=False).fit(Zw, rw)
        g_weights = [float(w) for w in ridge.coef_]
        gz = ridge.predict(Zs)
    else:
        gz = np.zeros(len(df))

    res = r - gz
    b_lots = np.array([res[lots == l].mean() for l in unique_lots])
    b0 = float(b_lots.mean())
    tau = float(max(b_lots.std(ddof=1) if len(b_lots) > 1 else 0.0, tau_floor))

    # Ước lượng phương sai nhiễu đo: var_i = s0 + sg / n_i (NNLS)
    e_residuals = np.concatenate([res[lots == l] - res[lots == l].mean() for l in unique_lots])
    nn_grains = np.concatenate([df["n"].values[lots == l] for l in unique_lots])
    A_mat = np.c_[np.ones(len(e_residuals)), 1.0 / nn_grains]
    (s0, sg), _ = nnls(A_mat, e_residuals ** 2)
    s0 = float(max(s0, 1e-4))
    sg = float(sg)

    return {
        "phys_col": phys_col,
        "use_vg": use_vg,
        "b0": round(b0, 6),
        "tau": round(tau, 6),
        "s0": round(s0, 6),
        "sg": round(sg, 6),
        "lam": 1.05 if use_vg else 1.00,  # Calibrated lambda
        "nu0": nu0,
        "z_cols": z_cols,
        "g_mu": [round(v, 6) for v in g_mu] if g_mu else [],
        "g_sd": [round(v, 6) for v in g_sd] if g_sd else [],
        "g_weights": [round(v, 6) for v in g_weights] if g_weights else [],
    }


def compute_sha256_checksum(content_dict: Dict[str, Any]) -> str:
    """Tính mã băm SHA-256 canonical của dictionary tham số."""
    canonical = json.dumps(content_dict, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def main():
    parser = argparse.ArgumentParser(description="Fit Bayesian Few-Shot Calibration Parameters")
    parser.add_argument(
        "--csv",
        default="DATASET_BUILDER/4_Final_Dataset/final_regression_dataset.csv",
        help="Đường dẫn đến file CSV tập dữ liệu",
    )
    parser.add_argument(
        "--out",
        default="AI_SERVICES/src/rice_ai/models/weights/bayes_params_v1.json",
        help="Đường dẫn file JSON xuất ra",
    )
    args = parser.parse_args()

    csv_path = Path(args.csv).resolve()
    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"==> Đang nạp dữ liệu từ: {csv_path}")
    df = build_cups_dataset(str(csv_path), drop_bad_weight=True)

    print("==> Đang huấn luyện Nhánh Thị giác V (Vision Geometry: lV - o, g(z)=o)...")
    branch_v = fit_single_branch(
        df=df,
        phys_col="lV",
        use_vg=True,
        z_cols=["o"],
        g_mode="within",
        tau_floor=0.10,
    )

    print("==> Đang huấn luyện Nhánh Cân W (Weight Assisted: lW, g(z)=lW+lV)...")
    branch_w = fit_single_branch(
        df=df,
        phys_col="lW",
        use_vg=False,
        z_cols=["lW", "lV"],
        g_mode="pooled",
        tau_floor=0.10,
    )

    # Đóng gói đối tượng cấu hình
    source_lots = sorted([int(l) for l in df["lot"].unique()])
    payload = {
        "schema_version": "bayes_v1",
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source_dataset_records": len(df),
        "hyperparameters": {
            "tau_floor": 0.10,
            "nu0": 4.0,
            "disagreement_sigma_gate": 3.0,
            "lot_unseen_threshold_mm": 5.0,
            "source_lots": source_lots,
        },
        "branch_v": branch_v,
        "branch_w": branch_w,
    }

    # Tính checksum SHA-256 bảo vệ tính toàn vẹn
    checksum = compute_sha256_checksum(payload)
    payload["checksum_sha256"] = checksum

    out_json = json.dumps(payload, indent=2, ensure_ascii=False)
    out_path.write_text(out_json, encoding="utf-8")
    print(f"==> Đã lưu file cấu hình thành công: {out_path}")
    print(f"    - SHA-256 Checksum: {checksum}")
    print(f"    - Nhánh V: b0={branch_v['b0']}, tau={branch_v['tau']}, s0={branch_v['s0']}, sg={branch_v['sg']}")
    print(f"    - Nhánh W: b0={branch_w['b0']}, tau={branch_w['tau']}, s0={branch_w['s0']}, sg={branch_w['sg']}")


if __name__ == "__main__":
    main()
