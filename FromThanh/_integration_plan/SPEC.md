# ĐẶC TẢ KỸ THUẬT TÍCH HỢP MÔ-ĐUN BAYESIAN HYBRID (SPEC.md)

> **Dự án**: Rice Vision AI Inference Service  
> **Tài liệu**: Đặc tả kỹ thuật chi tiết (Technical Specification)  
> **Trạng thái**: Đã phê duyệt đặc tả thiết kế (Design Approved)  
> **Mã đặc tả**: `SPEC-BAYES-2026-V1`  
> **Mục tiêu**: Tích hợp thuật toán Bayesian Few-Shot Calibration vào `AI_SERVICES`  

---

## 1. HỢP ĐỒNG API (API CONTRACT SPECIFICATION)

### 1.1. Yêu cầu Tương thích Ngược (Backward Compatibility Guarantee)
- Mọi client hiện có khi gọi đến `POST /predict` mà **không gửi thêm các trường mới** vẫn sẽ nhận được kết quả với schema và cấu trúc dữ liệu hoàn toàn tương thích như phiên bản 2.2.0 hiện tại.
- Tất cả các trường mới đều có **giá trị mặc định an toàn (safe default values)**.
- Khi tham số `estimator_mode` mang giá trị cũ (`"auto"`, `"regression"`, `"geometry"`, `"weight"`), các hành vi logic đã định nghĩa trước đó không bị phá vỡ.

### 1.2. Đặc tả Trường Request mới tại `POST /predict`
Các trường dữ liệu được bổ sung vào dạng `Form-Data` của endpoint `POST /predict`:

| Tên trường (Field Name) | Kiểu dữ liệu | Bắt buộc | Giá trị mặc định | Giải thích ngữ nghĩa & Ràng buộc miền giá trị |
| :--- | :--- | :---: | :--- | :--- |
| `file` | `UploadFile` (binary) | **Có** | *N/A* | File ảnh chụp cốc lúa (JPEG/PNG). |
| `diam` | `float` | **Có** | *N/A* | Đường kính trong của cốc ($D_{\text{in}}$, mm). Ràng buộc: $10.0 \le \text{diam} \le 120.0$. |
| `height` | `float` | **Có** | *N/A* | Chiều cao toàn bộ cốc ($H_{\text{cup}}$, mm). Ràng buộc: $10.0 \le \text{height} \le 200.0$. |
| `empty` | `float` | **Có** | *N/A* | Khoảng cách từ miệng cốc đến mặt lúa ($H_{\text{empty}}$, mm). Ràng buộc: $0.0 \le \text{empty} < \text{height}$. |
| `wall_thickness` | `float` | Không | `1.0` | Độ dày thành cốc (mm). |
| `weight_total` | `Optional[float]` | Không | `None` | Khối lượng tổng của mẫu lúa trong cốc (gam). $W > 0$. |
| `sample_weight` | `Optional[float]` | Không | `None` | Khối lượng mẫu cân nhỏ (cho nhánh `weight` truyền thống). |
| `sample_count` | `Optional[int]` | Không | `None` | Số hạt đếm trong mẫu cân nhỏ. |
| `estimator_mode` | `str` | Không | `"auto"` | Phương pháp ước lượng. Bổ sung giá trị `"bayes"`.<br>Tập hợp hợp lệ: `{"auto", "bayes", "regression", "geometry", "weight"}`. |
| `debug` | `bool` | Không | `False` | Trả về thông tin gỡ lỗi chi tiết và ảnh trực quan hóa. |
| **`rice_core_diam_mm`** | `Optional[float]` | Không | `None` | *(Mới)* Đường kính hiệu dụng riêng của bề mặt lúa (mm). Dùng để tính scale `pixels_per_mm` độc lập với đường kính miệng cốc nếu cốc có dạng côn. Nếu bỏ trống, hệ thống mặc định lấy giá trị của `diam`. |
| **`support_cups`** | `Optional[str]` | Không | `None` | *(Mới)* Chuỗi JSON serialized danh sách $K$ cốc mẫu chuẩn có nhãn dùng cho hiệu chuẩn Bayes ít mẫu. Chi tiết schema xem mục 1.3. |

### 1.3. Cấu trúc Schema của Danh sách `support_cups`
Mỗi phần tử trong danh sách `support_cups` đại diện cho một cốc đã biết chính xác số lượng hạt (Ground Truth) để thực hiện cập nhật liên hợp (Conjugate Updating) cho lô ly hiện tại:

```json
[
  {
    "actual_count": 520,
    "weight_g": 12.45,
    "bulk_volume_mm3": 18250.0,
    "mean_clean_grain_volume_mm3": 21.35,
    "whole_grains_measured_count": 14
  }
]
```

- **Ràng buộc trường trong mỗi cốc support**:
  - `actual_count`: `int`, bắt buộc, $> 0$.
  - `weight_g`: `Optional[float]`, khối lượng lúa trong cốc (gam). Nếu nhánh W được sử dụng thì trường này bắt buộc $> 0$.
  - `bulk_volume_mm3`: `Optional[float]`, thể tích hình trụ của khối lúa ($V_{\text{bulk}}$, mm³). Bắt buộc cho nhánh V.
  - `mean_clean_grain_volume_mm3`: `Optional[float]`, thể tích trung bình của hạt nguyên sạch ($V_g$, mm³).
  - `whole_grains_measured_count`: `Optional[int]`, mặc định `14` (số lượng hạt đo được dùng để tính trọng số phương sai chất lượng $n_i$).

### 1.4. Đặc tả Trường Response mới tại `POST /predict`
Đối tượng `estimation` (thuộc class `EstimationResult`) trong `PredictResponse` được mở rộng như sau:

```json
{
  "status": "success",
  "request_id": "a1b2c3d4e5f6",
  "estimation": {
    "final": 518,
    "method_used": "bayes_hybrid",
    "regression_est": 522.4,
    "geometry_est": 485,
    "weight_est": 516,
    "ai_est": 485,
    "feature_schema_version": "31v1",
    "model_bundle": "bayes_params_v1.json",
    "bayes_est": {
      "predicted_count": 518,
      "ci90_lower": 504,
      "ci90_upper": 532,
      "relative_ci90_width_pct": 5.4,
      "disagreement_gate": {
        "status": "passed",
        "sigma_distance": 0.82,
        "discrepancy_ratio": 1.018
      },
      "branch_estimates": {
        "vision_only": {
          "predicted_count": 510,
          "ci90_lower": 486,
          "ci90_upper": 535,
          "variance": 0.00184
        },
        "weight_assisted": {
          "predicted_count": 519,
          "ci90_lower": 507,
          "ci90_upper": 531,
          "variance": 0.00042
        }
      },
      "support_cups_used": 1
    }
  },
  "warnings": [
    "SCALE_UNVALIDATED: Hệ số quy đổi ảnh pixels_per_mm chưa qua kiểm định vật lý độc lập."
  ]
}
```

- **Mô tả các trường bổ sung trong `bayes_est`**:
  - `predicted_count` (`int`): Giá trị kỳ vọng ước lượng cuối cùng của mô hình Bayes (làm tròn số nguyên).
  - `ci90_lower` (`int`), `ci90_upper` (`int`): Biên dưới và biên trên của khoảng tin cậy danh nghĩa 90% đã qua hiệu chuẩn $\lambda$.
  - `relative_ci90_width_pct` (`float`): Độ rộng tương đối của khoảng tin cậy: $\frac{\text{ci90\_upper} - \text{ci90\_lower}}{\text{predicted\_count}} \times 100\%$.
  - `disagreement_gate` (`object`): Trạng thái kiểm tra độ lệch giữa 2 nhánh:
    - `status`: `"passed"` (hợp nhất thành công), `"diverged"` (xung đột vượt ngưỡng $3\sigma$), hoặc `"single_branch"` (chỉ chạy 1 nhánh do thiếu cân/ảnh).
    - `sigma_distance`: Khoảng cách độ lệch chuẩn $|\log N_W - \log N_V| / \sigma_{\Delta}$.
  - `branch_estimates` (`object`): Chi tiết ước lượng độc lập của từng nhánh để phục vụ giám sát và giải thích quyết định.
  - `support_cups_used` (`int`): Số lượng cốc mẫu chuẩn $K$ đã sử dụng để cập nhật hậu nghiệm.

---

## 2. ĐẶC TẢ MÔ-ĐUN `src/rice_ai/estimation/bayes_hybrid.py`

### 2.1. Cấu trúc Lớp & Kiểu Dữ liệu (Typing & Architecture)
Mô-đun mới được thiết kế theo hướng phi trạng thái (Stateless Runtime Engine), độc lập hoàn toàn với việc huấn luyện.

```python
"""Bayesian Few-Shot Calibration Engine for Rice AI."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from scipy.stats import norm, t as student_t

Z90 = float(norm.ppf(0.95))  # 1.6448536269514722

@dataclass(frozen=True)
class BranchFittedParams:
    """Tham số đã huấn luyện offline của một nhánh (Vision hoặc Weight)."""
    phys_type: str                   # "vision" (lV - o) hoặc "weight" (lW)
    b0: float                        # Kỳ vọng tiên nghiệm của b_lot
    tau: float                       # Độ lệch chuẩn tiên nghiệm của b_lot
    s0: float                        # Phương sai nhiễu đo nền tối thiểu
    sg: float                        # Hệ số phương sai phụ thuộc số lượng hạt (sg / n)
    lam: float = 1.0                 # Hệ số phóng đại khoảng tin cậy 90% (calibrated lambda)
    nu0: float = 4.0                 # Bậc tự do tiên nghiệm cho phân phối Inverse-Gamma
    g_weights: Optional[List[float]] = None # Trọng số Ridge g(z)
    g_mu: Optional[List[float]] = None      # Mean chuẩn hóa vector z
    g_sd: Optional[List[float]] = None      # Std chuẩn hóa vector z
    z_cols: Tuple[str, ...] = ()            # Tên các biến đặc trưng đầu vào của g(z)

@dataclass
class BayesPredictionOutput:
    """Kết quả tính toán của mô-đun Bayes."""
    final_count: int
    ci90_low: int
    ci90_high: int
    fused_mean_log: float
    fused_var_log: float
    gate_status: str                 # "passed", "diverged", "single_branch"
    sigma_distance: float
    branch_v: Optional[Dict[str, Any]] = None
    branch_w: Optional[Dict[str, Any]] = None
    flags: List[str] = field(default_factory=list)
```

### 2.2. Công thức Toán học Chi tiết (Mathematical Formulation)

#### (1) Mô hình Vật lý cơ sở trong không gian log (Log-scale physics)
- **Nhánh Thị giác V (Vision Geometry)**:
  $$\text{phys}_V = \log(V_{\text{bulk}}) - \log(V_g) = \log(V_{\text{bulk}}) - o$$
  Trong đó: $V_{\text{bulk}} = \frac{\pi}{4} D_{\text{inner}}^2 \cdot H_{\text{rice}}$ (mm³), và $o = \frac{\sum_{i=1}^{n} \log(V_{g,i})}{n}$ là thể tích trung bình logarit của các hạt nguyên sạch đo được qua Ellipsoid 3D.
- **Nhánh Cân W (Weight Sensor)**:
  $$\text{phys}_W = \log(W)$$
  Trong đó: $W$ là khối lượng tổng của mẫu lúa (gam).

#### (2) Mô hình phần dư chung $g(z)$ (Shared Residual Model)
- Chuẩn hóa vector biến giải thích $z$:
  $$z_{\text{scaled}} = \frac{z - \mu_z}{\sigma_z}$$
- Dự đoán phần dư bù trừ:
  $$g(z) = z_{\text{scaled}}^T \cdot w_{\text{ridge}}$$
  - Nhánh V dùng $z_V = (o)$ hoặc $(o, \log D, \log(H/D))$.
  - Nhánh W dùng $z_W = (\log W, \log V_{\text{bulk}})$.

#### (3) Phương sai nhiễu đo nhận thức chất lượng (Heteroscedastic Quality Variance)
Mỗi cốc có số hạt nguyên đo được $n$ sẽ có phương sai quan sát riêng:
$$\text{var}_i = s_0 + \frac{s_g}{n_i}$$
Với cốc chuẩn tham chiếu ($n_{\text{ref}} \approx 14$ hạt):
$$s_{\text{ref}} = s_0 + \frac{s_g}{14.0}$$
Độ chính xác tương đối (quality weight) của cốc $i$:
$$w_i = \frac{s_{\text{ref}}}{\text{var}_i}$$

#### (4) Cập nhật Liên hợp Bayes cho Lô Cốc từ $K$ Cốc Mẫu (Conjugate Posterior Update)
Nếu không có cốc support ($K = 0$):
$$m_n = b_0, \quad k_n = \frac{s_{\text{ref}}}{\tau^2}, \quad a_n = \frac{\nu_0}{2}, \quad b_n = \frac{\nu_0 \cdot s_{\text{ref}}}{2}$$
Nếu có $K \ge 1$ cốc support $\{ (x_j, y_j = \log N_j) \}_{j=1}^K$:
- Phần dư hiệu chuẩn của từng cốc support:
  $$r_{s,j} = \log(N_j) - \text{phys}(x_j) - g(z_j)$$
- Cập nhật tham số Normal-Inverse-Gamma:
  $$k_n = k_0 + \sum_{j=1}^K w_j$$
  $$m_n = \frac{k_0 \cdot b_0 + \sum_{j=1}^K w_j \cdot r_{s,j}}{k_n}$$
  $$a_n = a_0 + \frac{K}{2}$$
  $$b_n = b_0 + \frac{1}{2} \left[ \sum_{j=1}^K w_j \cdot r_{s,j}^2 + k_0 \cdot b_0^2 - k_n \cdot m_n^2 \right]$$

#### (5) Phân phối Dự đoán cho Cốc Query (Predictive Moments)
Với cốc query $q$:
$$\mu_{\text{log}} = \text{phys}(q) + g(z_q) + m_n$$
$$\sigma_{\text{lot}}^2 = \frac{b_n}{a_n}, \quad \text{dof} = 2 a_n, \quad h_q = \frac{\text{var}(q)}{s_{\text{ref}}}$$
Phương sai dự đoán đã qua hiệu chuẩn $\lambda$:
$$v_{\text{pred}} = \sigma_{\text{lot}}^2 \left( h_q + \frac{1}{k_n} \right) \cdot \lambda^2$$
$$\text{sd}_{\text{pred}} = \sqrt{v_{\text{pred}}}$$

#### (6) Hợp nhất Hai Nhánh trong Không gian Log & Cổng Bất đồng $3\sigma$
Khi cả hai nhánh V và W đều khả dụng:
- Độ lệch chuẩn sai biệt:
  $$\sigma_{\Delta} = \sqrt{v_{\text{pred}}^{(W)} + v_{\text{pred}}^{(V)}}$$
- Khoảng cách khoảng sai biệt:
  $$\Delta = |\mu_{\text{log}}^{(W)} - \mu_{\text{log}}^{(V)}|$$
- **Điều kiện Cổng Bất đồng (Disagreement Gate)**:
  - Nếu $\Delta \le 3.0 \cdot \sigma_{\Delta}$: Hai nhánh thống nhất. Thực hiện hợp nhất tối ưu theo trọng số nghịch đảo phương sai (Inverse-Variance Pooling):
    $$v_{\text{fused}} = \left( \frac{1}{v_{\text{pred}}^{(W)}} + \frac{1}{v_{\text{pred}}^{(V)}} \right)^{-1}$$
    $$\mu_{\text{fused}} = v_{\text{fused}} \left( \frac{\mu_{\text{log}}^{(W)}}{v_{\text{pred}}^{(W)}} + \frac{\mu_{\text{log}}^{(V)}}{v_{\text{pred}}^{(V)}} \right)$$
  - Nếu $\Delta > 3.0 \cdot \sigma_{\Delta}$: **Xung đột nghiêm trọng (Cổng bật cảnh báo)**:
    - Bật cờ `weight_conflict = True`.
    - Chính sách phân giải: Do cảm biến cân cơ học thường có độ tin cậy nền cao hơn thị giác (trừ khi khối lượng bị vô lý $W/N > 0.1$), hệ thống sẽ lấy Nhánh W làm giá trị chính thức nhưng gán khoảng tin cậy mở rộng bao phủ cả Nhánh V, đồng thời trả về cảnh báo chi tiết.

#### (7) Khoảng tin cậy 90% (Calibrated 90% Confidence Interval)
Với phân vị Student-t tương ứng với bậc tự do $\text{dof}$ (hoặc phân vị Gaussian $Z_{0.95} \approx 1.645$ khi $\text{dof} = \infty$):
$$N_{\text{est}} = \exp(\mu_{\text{log}})$$
$$N_{\text{lower}} = \exp(\mu_{\text{log}} - t_{0.95, \text{dof}} \cdot \text{sd}_{\text{pred}})$$
$$N_{\text{upper}} = \exp(\mu_{\text{log}} + t_{0.95, \text{dof}} \cdot \text{sd}_{\text{pred}})$$

### 2.3. Xử lý các Tình huống Biên & Dữ liệu Khuyết (Edge Cases)
Mô-đun phải đảm bảo tính lũy tiến và không bao giờ gây lỗi sập dịch vụ:

1. **Trường hợp không có khối lượng ($W$ là `None` hoặc $\le 0$)**:
   - Tự động hạ cấp sang chế độ **Chỉ dùng Nhánh Thị giác (Vision-only)**.
   - Trả về `gate_status = "single_branch"`.
   - Kết quả cuối cùng và CI90 lấy hoàn toàn từ Nhánh V.
2. **Trường hợp không có cốc support ($K = 0$)**:
   - Sử dụng trực tiếp phân phối tiên nghiệm $b_0$ và $\tau^2$ từ tập source lots.
   - Tuyệt đối không ném lỗi; mô hình hoạt động ở chế độ Zero-Shot ($K=0$).
3. **Trường hợp ảnh không phát hiện được hạt nào ($n_{\text{whole}} = 0$) hoặc thiếu $V_g$**:
   - Nếu có khối lượng hợp lệ $W > 0$: Hạ cấp sang chế độ **Chỉ dùng Nhánh Cân (Weight-only)**.
   - Nếu cũng không có khối lượng: Ném ngoại lệ nghiệp vụ chuẩn `PipelineError(status_code=422, error_code="NO_VALID_GRAINS", message="Không phát hiện được hạt nguyên hợp lệ để đo kích thước.")`.
4. **Trường hợp khối lượng bất thường / Gian lận cân**:
   - Điều kiện kiểm tra sơ bộ: Tỷ lệ khối lượng trung bình hạt ước tính $\frac{W}{N_V} > 0.1\text{g/hạt}$ (hạt lúa thông thường chỉ nặng khoảng $0.02 - 0.03\text{g}$) hoặc $W < 0.5\text{g}$.
   - Kích hoạt ngay cờ cảnh báo `weight_conflict`, vô hiệu hóa Nhánh W và chỉ tin tưởng Nhánh V.

---

## 3. ĐỊNH DẠNG FILE THAM SỐ ĐÃ HUẤN LUYỆN OFFLINE (JSON SPECIFICATION)

### 3.1. Cấu trúc File JSON (`bayes_params_v1.json`)
File tham số này được sinh ra offline bởi script `scripts/fit_bayes_params.py` và đặt tại thư mục `src/rice_ai/models/weights/bayes_params_v1.json`:

```json
{
  "schema_version": "bayes_v1",
  "created_at": "2026-10-14T08:00:00Z",
  "source_dataset_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "hyperparameters": {
    "tau_floor": 0.10,
    "nu0": 4.0,
    "disagreement_sigma_gate": 3.0,
    "source_lots": [18, 23, 33, 42]
  },
  "branch_v": {
    "phys_col": "lV",
    "use_vg": true,
    "b0": -0.6842,
    "tau": 0.1285,
    "s0": 0.0012,
    "sg": 0.0094,
    "lam": 1.05,
    "z_cols": ["o"],
    "g_mu": [3.0451],
    "g_sd": [0.1824],
    "g_weights": [-0.3421]
  },
  "branch_w": {
    "phys_col": "lW",
    "use_vg": false,
    "b0": 3.7512,
    "tau": 0.1000,
    "s0": 0.0003,
    "sg": 0.0018,
    "lam": 1.00,
    "z_cols": ["lW", "lV"],
    "g_mu": [2.8510, 9.7820],
    "g_sd": [0.4215, 0.5120],
    "g_weights": [0.0821, -0.0415]
  },
  "checksum_sha256": "8f4e2d3c9a1b0c7e5f6a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e"
}
```

### 3.2. Cơ chế Nạp lúc Khởi động (Warmup Loader) & Xác thực Checksum
Lớp `BayesModelProvider` trong `src/rice_ai/models/bayes_loader.py`:
1. **Kiểm tra sự tồn tại**: Nếu file không tồn tại, ghi log warning `BAYES_PARAMS_MISSING`, đặt component status = `NOT_FOUND` và cho phép service khởi động ở chế độ suy giảm (Degraded), dùng ExtraTrees thay thế.
2. **Kiểm tra tính toàn vẹn (Integrity Check)**:
   - Đọc nội dung file JSON.
   - Tách trường `checksum_sha256` ra khỏi object.
   - Tính toán mã băm SHA-256 canonical của phần còn lại.
   - Nếu không khớp checksum: Ném lỗi `PipelineError(500, "ARTIFACT_INCOMPATIBLE", "Mã checksum của file tham số Bayes không hợp lệ!")`.
3. **Smoke Test tự động**:
   - Thực thi một lượt tính toán giả lập với $V_{\text{bulk}} = 10000$, $V_g = 20$, $W = 10.0$, $K = 0$.
   - Nếu kết quả trả về hữu hạn và nằm trong khoảng $[200, 800]$, đánh dấu status = `LOADED` và cache đối tượng estimator vào `request.app.state`.

### 3.3. Quy trình Sinh File Offline (`scripts/fit_bayes_params.py`)
Script chạy định kỳ khi tập dữ liệu được bổ sung:
```bash
python scripts/fit_bayes_params.py \
  --csv DATASET_BUILDER/4_Final_Dataset/final_regression_dataset.csv \
  --out src/rice_ai/models/weights/bayes_params_v1.json \
  --reps 50
```
Các bước xử lý bên trong script:
1. Nạp CSV, lọc bỏ 7 mẫu cân lỗi đã biết ($W/N > 0.1$).
2. Huấn luyện tham số $b_0, \tau, s_0, s_g$ và Ridge $g(z)$ cho cả hai nhánh V và W trên toàn bộ các lot nguồn.
3. Chạy nested leave-one-source-lot-out để tối ưu hệ số $\lambda$ đảm bảo độ phủ 90%.
4. Đóng gói JSON, tự động tính mã SHA-256 và ghi ra đĩa.

---

## 4. ĐẶC TẢ THAY ĐỔI TẠI `pipeline/features.py` VÀ `pipeline/container.py`

### 4.1. Thay đổi tại `src/rice_ai/pipeline/container.py`
- **Vấn đề cần giải quyết**: Loại bỏ sự không nhất quán giữa đường kính nhập tay và đường kính dò từ bao lồi.
- **Quy tắc mới**:
  1. Nếu người dùng nhập `rice_core_diam_mm` (đường kính bề mặt lúa):
     - Dùng `rice_core_diam_mm` để tính scale `pixels_per_mm = inner_diam_px / rice_core_diam_mm`.
     - Dùng `diam_mm` (đường kính lòng ly) để tính $V_{\text{bulk}} = \frac{\pi}{4} \cdot \text{diam\_mm}^2 \cdot H_{\text{rice}}$.
  2. Nếu người dùng **không nhập** `rice_core_diam_mm`:
     - Dùng duy nhất một giá trị `diam_mm` cho cả tính scale và tính $V_{\text{bulk}}$.
  3. Bổ sung kiểm tra chéo: Nếu đường kính phát hiện trên ảnh `detected_diam_px / pixels_per_mm` lệch so với `diam_mm` quá $15\%$, kích hoạt cờ cảnh báo `scale_unvalidated = True`.

### 4.2. Thay đổi tại `src/rice_ai/pipeline/features.py`
- **Vấn đề cần giải quyết**: Cung cấp trực tiếp các biến đầu vào cho mô-đun Bayes mà không xáo trộn vector 31 đặc trưng của ExtraTrees.
- **Quy tắc mới**:
  - Hàm `assemble_31_features` giữ nguyên 100% logic và thứ tự của 31 đặc trưng trong `ALL_31_FEATURES`.
  - Bổ sung hàm tiện ích:
    ```python
    def extract_bayes_inputs(
        container: ContainerResult,
        grain_analysis: GrainAnalysis,
        weight_total: Optional[float],
    ) -> Dict[str, Any]:
        """Trích xuất gọn các đại lượng vật lý phục vụ mô-đun Bayesian."""
        whole_grains = grain_analysis.physical_grains
        vols = [float(g["volume_mm3"]) for g in whole_grains if g.get("volume_mm3") and g["volume_mm3"] > 0]
        n_count = len(vols)
        
        # Thể tích hạt logarit có trọng số
        log_vg_weighted = float(np.mean(np.log(vols))) if vols else None
        
        return {
            "lV": math.log(container.bulk_volume_mm3) if container.bulk_volume_mm3 > 0 else None,
            "lW": math.log(weight_total) if weight_total and weight_total > 0 else None,
            "o": log_vg_weighted,
            "n": max(n_count, 1),
            "inner_diameter_mm": container.inner_diam_mm,
            "rice_height_mm": container.rice_height_mm,
            "raw_weight_g": weight_total,
        }
    ```

---

## 5. DANH SÁCH CỜ CẢNH BÁO (WARNING FLAGS SPECIFICATION)

Toàn bộ các cờ chẩn đoán bất thường được tổng hợp và trả về trong mảng `warnings` của `PredictResponse`:

| Mã Cờ (Flag Name) | Điều kiện Kích hoạt | Hành động Xử lý của Hệ thống | Ảnh hưởng đến Kết quả `final` |
| :--- | :--- | :--- | :--- |
| `SCALE_UNVALIDATED` | - Detector trả về `metric_accuracy_validated == False` (L594).<br>- Hoặc đường kính miệng ly phát hiện lệch $> 15\%$ so với đường kính khai báo. | Ghi log cảnh báo. Nếu có cân hợp lệ, giảm độ tin cậy của Nhánh V, ưu tiên Nhánh W. | Không làm dừng hệ thống. Khoảng tin cậy CI90 của Nhánh V được nới rộng thêm $20\%$. |
| `WEIGHT_CONFLICT` | - Khoảng cách bất đồng $|\log N_W - \log N_V| > 3.0 \cdot \sigma_{\Delta}$.<br>- Hoặc tỷ lệ $W / N_V > 0.1\text{g/hạt}$ (cân sai/đặt sai mẫu). | Vô hiệu hóa việc pooling trung bình; chọn Nhánh W làm `final` (nếu $W$ hợp lý) hoặc Nhánh V (nếu $W$ vô lý). Gắn cảnh báo chi tiết. | Giá trị `final` không bị trộn lẫn giữa 2 nguồn số liệu mâu thuẫn. |
| `LOT_UNSEEN` | - Đường kính cốc $D_{\text{in}}$ lệch $> 5.0\text{mm}$ so với tất cả các lot trong tập nguồn $\{18, 23, 33, 42\text{mm}\}$. | Tự động tăng độ lệch chuẩn tiên nghiệm $\tau$ lên gấp đôi ($\tau_{\text{inflated}} = 2.0 \cdot \tau$). | Khoảng tin cậy CI90 tự động giãn rộng ra để phản ánh đúng sự không chắc chắn khi gặp loại cốc mới. |
| `LOW_GRAIN_COUNT` | - Số lượng hạt nguyên sạch đo được $n < 5$ hạt. | Phương sai chất lượng $\text{var} = s_0 + s_g / n$ tăng cao tự nhiên theo công thức toán học. | Nhánh V tự động giảm mạnh trọng số khi hợp nhất với Nhánh W. |
| `DETECTOR_FAILED` | - Container detector không tìm thấy miệng ly hoặc diện tích mặt lúa $\le 0$. | Báo lỗi `PipelineError(422, "INVALID_INPUT")` nếu không có cân. Nếu có cân, fallback sang chạy duy nhất Nhánh W. | `final` lấy theo Nhánh W (nếu có cân). |

---

## 6. HÀNG ĐỢI KIỂM THỬ (TESTING SUITE SPECIFICATION)

Bộ kiểm thử tự động được triển khai trong file mới `tests/test_bayes_integration.py` gồm 5 nhóm bài test nghiêm ngặt:

### Test 1: Unit Test Thuật toán Toán học Bayes (`test_bayes_math_primitives`)
- **Mục tiêu**: Kiểm tra tính đúng đắn của công thức cập nhật liên hợp và pooling.
- **Đầu vào**: Dữ liệu cốc giả lập với $b_0 = 0.0, \tau = 0.2, s_0 = 0.001, s_g = 0.01$. Cung cấp 2 cốc support với phần dư đã biết.
- **Kỳ vọng**:
  - Giá trị $m_n$ và $k_n$ tính ra khớp chính xác với công thức Normal-Inverse-Gamma trong vòng sai số $10^{-7}$.
  - Khi $n \to \infty$, phương sai quan sát tiến về $s_0$.

### Test 2: Test Tương thích Ngược Tuyệt đối (`test_backward_compatibility`)
- **Mục tiêu**: Đảm bảo toàn bộ kết quả của các chế độ cũ không bị xê dịch dù chỉ 1 hạt.
- **Phương pháp**:
  - Chạy `RicePipeline.run` trên ảnh fixture `tests/fixtures/detection_test_images/M0270.jpg` với `estimator_mode="regression"`.
  - So sánh giá trị `final` và `regression_est` trước và sau khi tích hợp.
- **Kỳ vọng**: Sai số tuyệt đối giữa 2 phiên bản bằng đúng **0 hạt**.

### Test 3: Test Tái lập Số liệu LOLO Thực nghiệm (`test_lolo_replication`)
- **Mục tiêu**: Tái lập lại bảng số liệu trong `FromThanh/results_v2/paper_table.md`.
- **Phương pháp**: Chạy script kiểm thử trên 155 cốc của dataset `final_regression_dataset.csv`.
- **Dung sai cho phép**:
  - MAPE Nhánh V tại $K=0$: $5.73\% \pm 0.1\%$.
  - MAPE Nhánh V tại $K=10$: $5.02\% \pm 0.1\%$.
  - MAPE Nhánh W tại $K=0$: $3.76\% \pm 0.1\%$.
  - MAPE Nhánh W tại $K=10$: $1.78\% \pm 0.1\%$.

### Test 4: Test Cổng Bất đồng $3\sigma$ trên Mẫu Cân Sai (`test_disagreement_gate_anomaly_detection`)
- **Mục tiêu**: Xác thực khả năng bắt lỗi gian lận cân hoặc ghi nhầm số đo.
- **Đầu vào**: Mẫu M0262 (thuộc nhóm 7 cốc có khối lượng ghi nhận sai lệch nghiêm trọng trong dữ liệu).
- **Kỳ vọng**:
  - Cổng bất đồng phải kích hoạt: `gate_status == "diverged"`.
  - Mảng warnings chứa cờ `WEIGHT_CONFLICT`.
  - Hệ thống không bị treo hoặc ném Unhandled Exception.

### Test 5: Test Khả năng Chống chịu File Tham số Hỏng (`test_resilience_corrupted_params`)
- **Mục tiêu**: Đảm bảo tính ổn định cao của backend service.
- **Kịch bản**:
  1. File `bayes_params_v1.json` bị xóa.
  2. File bị sửa đổi 1 byte (sai lệch SHA-256).
  3. File bị khuyết trường `branch_v`.
- **Kỳ vọng**:
  - Service ghi log lỗi rõ ràng mức độ WARNING/ERROR.
  - Endpoint `/api/status` báo component `bayes_calibrator` trạng thái `error` hoặc `not_found`.
  - Ứng dụng không bị crash khi khởi động, tự động chuyển hướng request sang mô hình ExtraTrees hiện có.

---
*Hết tài liệu SPEC.md. Mọi thông số và trường dữ liệu đều có kiểu và giá trị mặc định rõ ràng.*
