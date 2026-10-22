# KẾ HOẠCH TÍCH HỢP MÔ-ĐUN BAYESIAN FEW-SHOT CALIBRATION (PLAN.md)

> **Dự án**: Rice Vision AI Inference Service  
> **Tài liệu**: Kế hoạch tích hợp (Integration Plan)  
> **Trạng thái**: Bản thảo đặc tả (Draft - Read & Document Only)  
> **Tác giả**: ML / Backend Engineering Team  
> **Ngày lập**: 14/10/2026  

---

## 1. TỔNG QUAN & BỐI CẢNH KỸ THUẬT

### 1.1. Mục tiêu tích hợp
Tích hợp thuật toán **Hiệu chuẩn Bayes ít mẫu (Few-Shot Bayesian Calibration)** từ thư mục nghiên cứu `FromThanh/` vào hệ sinh thái microservice `AI_SERVICES/` nhằm giải quyết dứt điểm các sai số hệ thống trong ước lượng số lượng hạt lúa, đồng thời cung cấp khoảng tin cậy (Confidence Interval 90%) và cơ chế cổng kiểm soát xung đột đo lường thị giác - khối lượng.

### 1.2. Hiện trạng và Các vấn đề cốt lõi đã xác minh
Hệ thống hiện tại của `AI_SERVICES` gồm luồng pipeline:
1. Phát hiện cốc & mặt lúa (`vision/container_detector.py` v3, bao lồi độ bão hòa, tính scale $\text{px/mm}$).
2. Cắt lát và phân đoạn hạt lúa bằng YOLOv8m-seg + SAHI (`vision/grain_segmenter.py`).
3. Làm sạch mặt cắt và phân loại hạt nguyên bằng CNN DenseNet121 (`vision/grain_classifier.py`).
4. Đo kích thước hình học 3D Ellipsoid (`vision/ellipsoid_geometry.py`).
5. Tổng hợp vector 31 đặc trưng (`pipeline/features.py`).
6. Dự đoán số hạt qua ExtraTrees (`models/regression_loader.py`) và hợp nhất (`estimation/fusion.py`).

**4 vấn đề kỹ thuật nghiêm trọng trong code hiện hữu:**
1. **Sai lệch hệ số điền đầy (Packing Fraction mismatch)**:
   - `src/rice_ai/settings.py:66` cố định `packing_fraction_geometry = 0.55`.
   - `src/rice_ai/estimation/geometry.py:14` đặt mặc định `packing_fraction = 0.82`.
   - `src/rice_ai/estimation/feature_schema.py:23` dùng `TRAINED_HYBRID_PACKING_FRACTION = 1.0` (tỷ số thể tích thuần).
   - *Thực tế dữ liệu*: Hệ số packing ngầm định đo theo từng loại ly (lot) dao động mạnh từ **0.44 đến 0.64**, dẫn đến việc nhánh vật lý bị sai lệch hệ thống từ **1.5 đến 2.3 lần** nếu không được hiệu chuẩn theo lot.
2. **Hiện tượng Overfitting nghiêm trọng của mô hình hồi quy (ExtraTrees)**:
   - Mô hình ExtraTrees huấn luyện trên 593 mẫu bị dồn **99.89% Feature Importance** vào biến `Weight_g` và các metadata kích thước cốc.
   - Sai số $MAE \approx 0.8 - 0.9$ thực chất là sai số nội suy (in-sample overfit trên cùng loại cốc đã học), suy giảm độ chính xác khi gặp loại cốc mới.
3. **Mâu thuẫn đường kính cốc trong tính toán thể tích và tỷ lệ ảnh**:
   - Tại `src/rice_ai/pipeline/container.py:63-64`, thể tích khối lúa `bulk_vol_mm3` được tính từ đường kính ly do người dùng nhập tay (`diam_mm`).
   - Trong khi đó, hệ số quy đổi không gian `pixels_per_mm` lại được tính từ bao lồi phát hiện mặt lúa (`inner_diam_px / inner_diam_mm`). Nếu góc nghiêng phối cảnh hoặc mép nước/mặt lúa lệch với kích thước ly, hai đại lượng này sử dụng hai hệ quy chiếu khác nhau mà không có kiểm định chéo.
4. **Độ tin cậy của Detector chưa được kiểm chứng tự động**:
   - `src/rice_ai/vision/container_detector.py:594` trả về cờ chẩn đoán cố định: `'metric_accuracy_validated': False`.
   - Một số điều kiện môi trường chụp (như ảnh mẫu M0382 chụp trên nền vân gỗ có cùng dải màu và độ bão hòa với vỏ trấu) làm bộ tách biên ellipse và bao lồi thất bại hoàn toàn.

### 1.3. Giải pháp FromThanh và Số liệu thực nghiệm
Thuật toán hiệu chuẩn Bayes (đã kiểm chứng qua giao thức Leave-One-Lot-Out - LOLO trên 155 cốc thuộc 4 loại đường kính ly: 18mm, 23mm, 33mm, 42mm):
- **Nhánh Thị giác V (không cân)**: $\log N = \log V_{\text{bulk}} - \log V_g + b_{\text{lot}} + g(z)$.
- **Nhánh Cân W (có cảm biến cân)**: $\log N = \log W + b_{\text{lot}} + g(z)$.
- **Cập nhật ít mẫu (Few-shot adaptation)**: Sử dụng $K$ cốc mẫu chuẩn có nhãn ($K = 0 \to 10$) để cập nhật phân phối hậu nghiệm cho độ lệch theo lô $b_{\text{lot}}$ theo mô hình liên hợp (Conjugate Normal-Normal / Normal-Inverse-Gamma).
- **Hợp nhất không gian log & Cổng bất đồng $3\sigma$**: Phát hiện mâu thuẫn giữa nhánh cân và thị giác (như các mẫu cân sai M0262–M0268) với tỷ lệ báo nhầm chỉ 1.2%.
- **Kết quả thực nghiệm đã xác minh**:
  - Nhánh thuần thị giác (Vision-only): MAPE giảm từ $5.73\%$ ($K=0$) xuống $5.02\%$ ($K=10$).
  - Nhánh có cân (Weight-assisted): MAPE giảm từ $3.76\%$ ($K=0$) xuống $1.78\%$ ($K=10$) (tương ứng khoảng $3.5\% \to 2.4\%$).
- **Hạn chế đã biết**:
  - Dữ liệu thử nghiệm mới chỉ gồm 4 loại đường kính ly (chưa có biến động về giống lúa).
  - Khoảng tin cậy 90% của nhánh cân bị phủ thiếu ($\approx 81 - 85\%$) ở $K=1$.
  - Nhánh thị giác phụ thuộc trực tiếp vào độ chuẩn xác của `pixels_per_mm` từ detector.

---

## 2. HIỆN TRẠNG AI_SERVICES (CODEBASE AUDIT)

Bảng tổng hợp đối chiếu mã nguồn thực tế tại `AI_SERVICES/src/rice_ai/`:

| File | Vai trò hiện tại | Điểm bị ảnh hưởng / Cần can thiệp | Dẫn chứng (file:dòng) |
| :--- | :--- | :--- | :--- |
| `src/rice_ai/settings.py` | Quản lý cấu hình toàn cục & đường dẫn mô hình | - Khai báo cấu hình đường dẫn file tham số Bayes offline (`bayes_calibration_path`).<br>- Khai báo các ngưỡng mặc định cho cổng bất đồng $3\sigma$, ngưỡng cảnh báo grain count tối thiểu.<br>- Chỉnh sửa/đồng bộ lại hệ số packing fraction. | `L66`: `packing_fraction_geometry = 0.55`<br>`L67-70`: `packing_fraction_feature_hybrid = 1.0`<br>`L145-255`: Các hàm `get_yolo_path`, `get_cnn_path`, `get_regression_dir` |
| `src/rice_ai/contracts.py` | Định nghĩa hợp đồng dữ liệu nội bộ (Pydantic / Dataclass) | - `PredictionInput`: Bổ sung trường `support_cups: List[Dict]` và `rice_core_diam_mm: Optional[float]`.<br>- Mở rộng enum `estimator_mode` cho phép giá trị `"bayes"`. Hiện tại chỉ cho phép `("auto", "regression", "geometry", "weight")`.<br>- `EstimateSet`: Thêm các trường `bayes_est`, `ci90_lower`, `ci90_upper`, `branch_estimates`, `flags`. | `L11-26`: Khai báo `PipelineError`<br>`L41-70`: `PredictionInput.validate()` (L64-69 chặn mode lạ)<br>`L72-84`: `ContainerResult`<br>`L86-105`: `GrainAnalysis`<br>`L108-115`: `EstimateSet`<br>`L118-128`: `PipelineResult` |
| `src/rice_ai/pipeline/container.py` | Phát hiện biên ly, tính `pixels_per_mm` và thể tích khối | - Chuẩn hóa quy tắc sử dụng đường kính: Ưu tiên một đường kính duy nhất (`inner_diam_mm` từ ảnh hoặc form) cho cả tính scale và tính $V_{\text{bulk}}$.<br>- Xuất cờ cảnh báo nếu đường kính phát hiện và đường kính nhập tay lệch nhau quá dung sai. | `L41-49`: Gọi `detect_container_and_scale`<br>`L63-64`: Tính `bulk_vol_mm3 = pi * (diam_mm / 2)^2 * rice_h_mm` (lấy `diam_mm` từ input thay vì detector) |
| `src/rice_ai/vision/container_detector.py` | Thuật toán dò miệng ly & bề mặt lúa (v3) | - Trả về cờ trạng thái phát hiện bề mặt.<br>- Xác thực độ tin cậy của scale hình học. | `L594`: `'metric_accuracy_validated': False`<br>`L1100-1250`: Dò bao lồi bằng phân ngưỡng bão hòa màu HSV |
| `src/rice_ai/pipeline/grains.py` | Điều phối SAHI $\to$ Cleaner $\to$ CNN $\to$ Ellipsoid 3D $\to$ Size Filter | - Cần trích xuất và tính toán thể tích hạt logarit có trọng số theo số hạt: $o = \frac{\sum n_i \log V_{g,i}}{\sum n_i}$.<br>- Đảm bảo xuất tổng số hạt nguyên hợp lệ $n_{\text{whole}}$ dùng cho tính toán phương sai chất lượng (Heteroscedastic noise). | `L70-80`: CNN lọc hạt nguyên (`hat_nguyen`)<br>`L97-108`: Đo ellipsoid hạt<br>`L121-129`: Lọc kích thước IQR<br>`L146-168`: Đóng gói `GrainAnalysis` |
| `src/rice_ai/pipeline/features.py` | Tổng hợp 31 đặc trưng từ container và grain analysis | - Bổ sung trích xuất tham số $o$ ($\log V_g$) và $n_i$ sang dictionary kết quả để chuyển tiếp sang mô-đun Bayes.<br>- Không làm phá vỡ schema 31 biến chuẩn hóa `31v1`. | `L26-144`: `assemble_31_features`<br>`L72-74`: Tính Feature 11 `Estimated_Total_Seeds_Hybrid`<br>`L137-144`: Trả về dict 31 đặc trưng |
| `src/rice_ai/pipeline/runner.py` | Trình thực thi pipeline chính (Orchestrator) | - Nhánh routing ước lượng: Khi `estimator_mode == "bayes"`, hoặc trong chế độ `"auto"`, gọi mô-đun `bayes_hybrid`.<br>- Bắt các cảnh báo `weight_conflict`, `scale_unvalidated` chuyển vào `PipelineResult.warnings`. | `L88-100`: Tính `geometry_est`<br>`L101-105`: Tính `weight_est`<br>`L108-120`: Khởi tạo và nạp hồi quy<br>`L127-136`: Gọi `assemble_31_features`<br>`L161-167`: Gọi `select_final_estimate` |
| `src/rice_ai/estimation/geometry.py` | Ước lượng thuần hình học | - Giữ nguyên làm baseline/fallback.<br>- Lưu ý xung đột hệ số packing `0.82` (mặc định tại L14) so với `0.55` trong settings. | `L10-43`: `compute_geometry_estimate` |
| `src/rice_ai/estimation/weight.py` | Ước lượng theo khối lượng mẫu | - Hiện tại chỉ hỗ trợ khi có đủ `weight_total`, `sample_weight`, `sample_count`. Khi chỉ có `weight_total`, hàm trả về `None`.<br>- Giữ nguyên làm baseline/fallback. | `L8-29`: `compute_weight_estimate` |
| `src/rice_ai/estimation/regression.py` | Ước lượng theo mô hình hồi quy ExtraTrees | - Giữ nguyên phục vụ chế độ `estimator_mode="regression"` cho tương thích ngược. | `L10-24`: `predict_regression` |
| `src/rice_ai/estimation/fusion.py` | Chọn kết quả cuối cùng theo chính sách ưu tiên | - Bổ sung nhánh xử lý cho `estimator_mode="bayes"`.<br>- Cập nhật chính sách `"auto"` để tích hợp Bayes Hybrid khi có sẵn file tham số. | `L9-87`: `select_final_estimate`<br>`L74-79`: Raise `PipelineError(400, "INVALID_INPUT")` nếu gặp mode không hợp lệ |
| `src/rice_ai/estimation/feature_schema.py` | Nguồn chân lý cho 31 đặc trưng (Single Source of Truth) | - Giữ nguyên không sửa đổi 31 biến để bảo vệ ExtraTrees model bundle.<br>- Chỉ import các hằng số. | `L21`: `FEATURE_SCHEMA_VERSION = "31v1"`<br>`L23`: `TRAINED_HYBRID_PACKING_FRACTION = 1.0`<br>`L92-124`: Khai báo `FEATURE_DEFS` |
| `src/rice_ai/models/regression_loader.py` | Quản lý vòng đời và nạp mô hình scikit-learn | - Giữ nguyên. Cần tạo loader riêng tương tự cho file tham số Bayes (`bayes_loader.py`) để không can thiệp logic scikit-learn hiện hữu. | `L27-93`: `_predict_single_vector`<br>`L130-220`: `LoadedRegressionProvider` |
| `src/rice_ai/api/schemas.py` | Đặc tả DTO Request / Response của FastAPI | - Thêm `BAYES_HYBRID = "bayes_hybrid"` vào `EstimationMethod`.<br>- Mở rộng `EstimationResult`: Thêm `bayes_est`, `ci90_low`, `ci90_high`, `branch_estimates`, `disagreement_detected`. | `L9-21`: `ErrorCode`<br>`L23-31`: `EstimationMethod`<br>`L64-91`: `EstimationResult`<br>`L110-148`: `PredictResponse` |
| `src/rice_ai/api/routes.py` | Khai báo các endpoints HTTP `/predict`, `/api/status` | - Endpoint `/predict`: Tiếp nhận trường form `support_cups` (chuỗi JSON), `rice_core_diam_mm`, cập nhật parsing `estimator_mode="bayes"`.<br>- Endpoint `/api/status`: Báo cáo trạng thái sẵn sàng của mô-đun Bayes Calibrator. | `L58-157`: `get_system_status`<br>`L191-250`: Khởi tạo và validation `PredictionInput`<br>`L286-295`: Đóng gói `EstimationResult` |
| `tests/` | Bộ kiểm thử tự động của hệ thống | - Bổ sung các unit test, test hồi quy cho mô-đun Bayes mới. | `test_estimators.py:26-120`<br>`test_pipeline.py:1-120` |

---

## 3. HIỆN TRẠNG FROMTHANH (RESEARCH AUDIT)

### 3.1. Danh mục và vai trò các file trong `FromThanh/`
1. `FromThanh/bayes_fewshot.py` (9.7 KB):
   - Chứa hiện thực gốc của thuật toán Bayesian Few-Shot (phiên bản v1).
   - Hàm `build_cups(path)`: Gom nhóm ảnh theo `Physical_Sample_ID`, tính $o = \frac{\sum n \cdot \text{lvg}}{\sum n}$, xác định lot theo đường kính làm tròn `round(Inner_Diameter_mm)`.
   - Lớp `BayesLotCalibrator`: Chứa `fit_source` (ước lượng $b_0, \tau, s_0, s_g$ qua NNLS và Ridge within-lot), `adapt` (cập nhật liên hợp Normal từ $K$ cốc support), `predict` (trả về giá trị trung bình Lognormal và khoảng tin cậy 90%).
   - Tập baseline B1–B5 và hàm chạy benchmark thực nghiệm Leave-One-Lot-Out.
2. `FromThanh/baseline_comparison.py` (9.5 KB):
   - Script đánh giá mở rộng 16 phương pháp baseline (Physics, Tabular ML, Gaussian Process, Weight-based) trên cùng tập dữ liệu và cùng seed chia support.
3. `FromThanh/Copy of rice_fewshot_v2_colab.ipynb` (300 KB):
   - Notebook Google Colab hoàn chỉnh, tại Cell 04 chứa toàn bộ mã nguồn của `rice_fewshot_v2.py`.
   - Các cải tiến then chốt so với v1:
     - Tích hợp mô hình phương sai liên hợp Normal-Inverse-Gamma (`nig=True`).
     - Tự động tính hệ số mở rộng phương sai $\lambda$ qua nested leave-one-source-lot-out (`_nested_lambda`) để đảm bảo khoảng 90% thực sự bao phủ 90% trên dữ liệu chưa biết.
     - Triển khai song song hoá qua `joblib.Parallel`.
4. `FromThanh/results_v2/` và `FromThanh/results_v2.zip`:
   - Chứa toàn bộ artifact kết quả thực nghiệm: `paper_table.md`, `paired_tests.csv`, `curves.png`, `results_macro.csv`, `results_per_lot.csv`, `results_raw.csv`.
5. **CÁC FILE THIẾU THEO DỰ KIẾN**:
   - `rice_hybrid.py`: **KHÔNG TÌM THẤY** trên toàn bộ hệ thống file.
   - `GIAI_PHAP_KET_HOP.md`: **KHÔNG TÌM THẤY** trên toàn bộ hệ thống file.
   - *Đánh giá*: Toàn bộ thuật toán hợp nhất kép (Dual-branch V và W) và các kết quả công bố đã được lưu vết trọn vẹn và đầy đủ bên trong `Copy of rice_fewshot_v2_colab.ipynb` (Cell 04) và `results_v2/paper_table.md`. Việc thiếu 2 file trên không làm gián đoạn việc lập kế hoạch kỹ thuật.

### 3.2. Phân định ranh giới Nghiên cứu vs Dịch vụ vận hành (Production Separation)
Để đưa vào dịch vụ backend `AI_SERVICES`, tuyệt đối không sao chép nguyên trạng file nghiên cứu mà phải phân tách nghiêm ngặt:

| Thành phần trong `FromThanh` | Phân loại | Giải pháp xử lý kiến trúc |
| :--- | :--- | :--- |
| 16 mô hình Baselines (RandomForest, GradientBoosting, GaussianProcess, TabPFN) | **Chỉ dùng nghiên cứu** | **Loại bỏ hoàn toàn**. Không đưa vào backend service để tránh phụ thuộc nặng nề và làm chậm hệ thống. |
| Vòng lặp mô phỏng lặp Monte Carlo (`reps=50`, hoán vị tập dữ liệu, seed) | **Chỉ dùng nghiên cứu** | **Loại bỏ hoàn toàn** khỏi runtime. Runtime chỉ nhận 1 query cốc và danh sách support do người dùng/client truyền vào. |
| Vẽ biểu đồ Matplotlib (`curves.png`), lưu file Markdown báo cáo bài báo | **Chỉ dùng nghiên cứu** | **Loại bỏ hoàn toàn** khỏi runtime service. |
| Quy trình huấn luyện nguồn: `fit_source`, Ridge regression, NNLS, nested $\lambda$ calibration | **Huấn luyện Offline** | Tách thành công cụ CLI độc lập: `scripts/fit_bayes_params.py`. Chạy offline khi có dữ liệu mới để xuất ra file cấu hình `bayes_params_v1.json`. |
| Cấu trúc dữ liệu hậu nghiệm & suy diễn trực tuyến: `posterior(support)`, `predict(query)` | **Dịch vụ Trực tuyến (Runtime)** | Chuyển đổi thành mô-đun tinh gọn `src/rice_ai/estimation/bayes_hybrid.py`. Chỉ sử dụng phép nhân ma trận thuần túy bằng NumPy và SciPy, thời gian tính toán $< 1.0\text{ms}$. |

---

## 4. KẾ HOẠCH TÍCH HỢP TỪNG BƯỚC (INCREMENTAL INTEGRATION ROADMAP)

Mỗi bước dưới đây được thiết kế độc lập, có phạm vi hẹp, có tiêu chí hoàn thành đo lường được (Definition of Done) và kịch bản hoàn tác (Rollback Plan) rõ ràng.

### Bước 1: Mở rộng Hợp đồng Dữ liệu & Cấu hình Settings (Contracts & Settings)
- **Mục tiêu**: Bổ sung các định nghĩa kiểu dữ liệu và tham số cấu hình mà không làm thay đổi hành vi hiện tại của hệ thống.
- **Phạm vi tác động**:
  - `src/rice_ai/settings.py`: Thêm cấu hình đường dẫn `bayes_params_path`, tham số dung sai bất đồng `disagreement_sigma_threshold = 3.0`.
  - `src/rice_ai/contracts.py`: Mở rộng `PredictionInput` cho phép `support_cups: List[Dict[str, Any]] = []`, `rice_core_diam_mm: Optional[float] = None`, và cho phép `"bayes"` trong `estimator_mode`. Mở rộng `EstimateSet`.
  - `src/rice_ai/api/schemas.py`: Thêm `BAYES_HYBRID` vào `EstimationMethod`, mở rộng `EstimationResult`.
- **Tiêu chí hoàn thành (DoD)**:
  - Tất cả các unit test hiện có trong `tests/` chạy vượt qua 100% (`pytest tests/`).
  - Gửi request cũ không có trường mới đến `/predict` vẫn trả kết quả nguyên vẹn, không có bất kỳ cảnh báo lỗi phân giải schema nào.
- **Kịch bản hoàn tác (Rollback)**:
  - Khôi phục lại 3 file `settings.py`, `contracts.py`, `schemas.py` từ git commit gốc.

### Bước 2: Chuẩn hóa Đo lường Kích thước & Trích xuất Đặc trưng Hình học (Container & Features)
- **Mục tiêu**: Đồng nhất cách tính đường kính ly và trích xuất tham số thể tích hạt có trọng số $o$ và số lượng hạt hợp lệ $n$.
- **Phạm vi tác động**:
  - `src/rice_ai/pipeline/container.py`: Bổ sung kiểm tra chéo giữa đường kính nhập tay và đường kính dò được từ mặt lúa. Thiết lập cờ cảnh báo `scale_unvalidated = True` nếu detector chưa được kiểm định (`metric_accuracy_validated == False`).
  - `src/rice_ai/pipeline/grains.py`: Tính toán thêm $o = \frac{\sum n_i \log V_{g,i}}{\sum n_i}$ và gán vào `GrainAnalysis.uniformity_metrics["weighted_log_grain_volume"]`.
  - `src/rice_ai/pipeline/features.py`: Bảo lưu nguyên vẹn 31 đặc trưng của `31v1`, đồng thời xuất thêm trường phụ `_bayes_inputs: {"o": float, "n": int, "V_bulk": float, "W": float, "D": float}` trong kết quả xử lý.
- **Tiêu chí hoàn thành (DoD)**:
  - Chạy `tests/test_feature_schema.py` xác nhận mã băm `schema_hash` của 31 đặc trưng không bị xáo trộn hay thay đổi.
  - Giá trị $o$ và $n$ được trích xuất chính xác từ tập ảnh kiểm thử trong `tests/fixtures/`.
- **Kịch bản hoàn tác (Rollback)**:
  - Hoàn tác thay đổi tại `container.py`, `grains.py`, `features.py`.

### Bước 3: Phát triển Mô-đun Bayesian Inference Độc lập & Script Fit Offline
- **Mục tiêu**: Xây dựng mô-đun tính toán suy diễn Bayes trực tuyến và công cụ sinh tham số offline.
- **Phạm vi tác động**:
  - Tạo file mới `src/rice_ai/estimation/bayes_hybrid.py`: Chứa class `BayesHybridEstimator` thực thi dự đoán nhánh V, nhánh W, hợp nhất không gian log, cổng bất đồng $3\sigma$, tính CI90.
  - Tạo file mới `src/rice_ai/models/bayes_loader.py`: Thực hiện nạp file JSON tham số lúc khởi động ứng dụng, xác thực SHA-256 checksum và định dạng schema.
  - Tạo script offline `scripts/fit_bayes_params.py`: Chạy fit trên CSV huấn luyện, tính toán ma trận Ridge và độ phóng đại $\lambda$, xuất ra `assets/models/bayes_params_v1.json`.
- **Tiêu chí hoàn thành (DoD)**:
  - Script offline chạy sinh ra file JSON hợp lệ có mã SHA-256 xác thực.
  - Viết unit test riêng `tests/test_bayes_hybrid.py`: Kiểm thử toán học đối chiếu với kết quả của `FromThanh/Copy of rice_fewshot_v2_colab.ipynb` với sai lệch số học $< 10^{-6}$.
- **Kịch bản hoàn tác (Rollback)**:
  - Xóa bỏ các file mới tạo trong `estimation/`, `models/`, `scripts/`. Do là module viết mới, không gây xung đột code sẵn có.

### Bước 4: Tích hợp Hợp nhất (Fusion Engine) & Bộ điều phối Pipeline (Pipeline Runner)
- **Mục tiêu**: Kết nối mô-đun Bayes vào luồng điều phối của `RicePipeline`.
- **Phạm vi tác động**:
  - `src/rice_ai/estimation/fusion.py`: Tiếp nhận kết quả từ `BayesHybridEstimator`. Nếu `estimator_mode == "bayes"`, trả về kết quả Bayes. Nếu `estimator_mode == "auto"`, kích hoạt chính sách ưu tiên đã thống nhất (xem Quyết định Mở).
  - `src/rice_ai/pipeline/runner.py`: Gọi `bayes_estimator.predict(...)` khi đủ điều kiện, thu thập các cờ cảnh báo (`weight_conflict`, `scale_unvalidated`, `lot_unseen`) vào danh sách warnings của `PipelineResult`.
- **Tiêu chí hoàn thành (DoD)**:
  - Chạy toàn bộ pipeline trên ảnh kiểm thử: Trả về đầy đủ `final`, `bayes_est`, `ci90`, `flags`.
  - Cổng bất đồng $3\sigma$ kích hoạt chính xác khi đưa dữ liệu cân bất thường, không gây sập ứng dụng.
- **Kịch bản hoàn tác (Rollback)**:
  - Hoàn tác thay đổi tại `fusion.py` và `runner.py`, hệ thống trở về sử dụng ExtraTrees / Geometry như cũ.

### Bước 5: Mở rộng API Route `/predict` & Báo cáo Trạng thái `/api/status`
- **Mục tiêu**: Mở cổng giao tiếp cho client truyền dữ liệu support cốc và nhận khoảng tin cậy.
- **Phạm vi tác động**:
  - `src/rice_ai/api/routes.py`: Bổ sung tham số Form `support_cups` (tùy chọn) và `rice_core_diam_mm` (tùy chọn). Đóng gói trường `estimation` trong `PredictResponse`. Bổ sung thành phần `bayes_calibrator` vào danh sách components của `/api/status`.
- **Tiêu chí hoàn thành (DoD)**:
  - `tests/test_api_endpoints.py` và `tests/test_api_lifecycle.py` chạy qua 100%.
  - Endpoint `/api/status` trả về trạng thái `"loaded"` cho `bayes_calibrator`.
- **Kịch bản hoàn tác (Rollback)**:
  - Hoàn tác thay đổi tại `routes.py`.

### Bước 6: Kiểm thử Toàn diện & Đối chuẩn Hồi quy (Verification & Benchmarking)
- **Mục tiêu**: Đảm bảo an toàn tuyệt đối cho toàn bộ hệ thống sản xuất.
- **Phạm vi tác động**:
  - Bổ sung file test `tests/test_bayes_integration.py`.
  - Thực hiện kiểm thử 5 nhóm ca kiểm thử: (1) Unit test toán học, (2) Test tương thích ngược, (3) Test tái lập kết quả LOLO trên 155 cốc, (4) Test phát hiện gian lận cân (cổng $3\sigma$), (5) Test xử lý file tham số hỏng/thiếu.
- **Tiêu chí hoàn thành (DoD)**:
  - Toàn bộ suite test vượt qua với 0 lỗi.
  - Báo cáo kết quả tái lập LOLO khớp với `FromThanh/results_v2/paper_table.md` trong biên độ sai số cho phép $\le 0.1\%$.

---

## 5. MA TRẬN QUẢN TRỊ RỦI RO (RISK MATRIX)

| STT | Rủi ro kỹ thuật | Xác suất | Tác động | Biện pháp giảm thiểu khả thi |
| :---: | :--- | :---: | :---: | :--- |
| **1** | **Sai số tỉ lệ ảnh (Pixels-per-mm) làm lệch Nhánh Thị giác V**<br>Detector v3 bắt bao lồi mặt lúa chưa chuẩn hoặc nền gỗ gây nhiễu làm `pixels_per_mm` bị sai, dẫn tới $V_{\text{bulk}}$ sai lập phương ($D^2 \cdot H$). | **Cao** | **Nghiêm trọng** | Kích hoạt cờ `scale_unvalidated`. Khi có cân hợp lệ ($W > 0$), cổng bất đồng sẽ phát hiện chênh lệch và tự động giảm trọng số của Nhánh V, ưu tiên Nhánh W. |
| **2** | **Khoảng tin cậy 90% của Nhánh Cân bị phủ thiếu (Under-coverage ~81%)**<br>Khi số cốc support $K \ge 1$, phân phối hậu nghiệm Normal-Inverse-Gamma bị co hẹp quá mức ở lot mới. | **Trung bình** | **Vừa** | Áp dụng hệ số lạm phát phương sai $\lambda$ qua nested calibration (tương tự Cell 04 trong Colab notebook) hoặc tăng bậc tự do tiên nghiệm $\nu_0$ để không làm thu hẹp phương sai quá sớm. |
| **3** | **Loại ly chưa từng thấy (Lot Unseen / Out-of-Distribution)**<br>Người dùng sử dụng loại ly có đường kính khác xa 4 loại trong tập huấn luyện (18, 23, 33, 42 mm). | **Cao** | **Trung bình** | Khi độ lệch $|D_{\text{input}} - D_{\text{source}}| > 5\text{mm}$, kích hoạt cờ cảnh báo `lot_unseen`, tự động nới rộng phương sai tiên nghiệm $\tau^2$ và khuyến khích người dùng cung cấp $K \ge 3$ cốc support. |
| **4** | **File cấu hình tham số Bayes bị hỏng, mất hoặc sai phiên bản**<br>Quá trình deploy thiếu file JSON hoặc file bị chỉnh sửa trái phép làm hỏng quá trình khởi động service. | **Thấp** | **Nghiêm trọng** | Tích hợp cơ chế xác thực SHA-256 lúc khởi động. Nếu file lỗi, ứng dụng ghi log cảnh báo và tự động chuyển trạng thái component sang `DEGRADED`, fallback về ExtraTrees/Geometry mà không làm crash service. |
| **5** | **Xung đột trải nghiệm người dùng khi Cổng Bất đồng $3\sigma$ kích hoạt**<br>Khi cân và ảnh lệch nhau, hệ thống trả về cảnh báo `weight_conflict`, khiến người dùng phân vân không biết tin vào con số nào. | **Trung bình** | **Vừa** | Trả về rõ ràng hai giá trị ước lượng của từng nhánh riêng biệt trong response (`branch_estimates`), kèm giải thích nguyên nhân và khuyến nghị kiểm tra lại cân hoặc góc chụp. |

---

## 6. CÁC QUYẾT ĐỊNH CÒN MỞ (OPEN ARCHITECTURAL DECISIONS)

Dưới đây là các câu hỏi mang tính kiến trúc hệ thống cần xin ý kiến định hướng từ bạn trước khi tiến hành viết code:

### Q1: Cơ chế tiếp nhận $K$ Cốc Support qua API - Stateless hay Stateful Session?
- **Bối cảnh**: Để hiệu chuẩn Bayes ít mẫu, mô hình cần thông tin của $K$ cốc mẫu đã đếm thực tế ($K=1 \to 10$).
- **Phương án A (Khuyến nghị - Stateless Payload)**: Client gửi danh sách $K$ cốc support ngay trong trường form `support_cups` của request POST `/predict`. Backend cập nhật nhanh hậu nghiệm trong RAM và suy diễn cho cốc query hiện tại rồi giải phóng.
  - *Ưu điểm*: Đơn giản, an toàn tuyệt đối cho kiến trúc microservice không trạng thái (stateless), dễ scale horizontal, không cần database lưu session.
  - *Nhược điểm*: Client phải lưu giữ danh sách cốc support và gửi kèm mỗi lần gọi API.
- **Phương án B (Stateful Session / Database)**: Tạo bảng cơ sở dữ liệu và API riêng (`POST /api/support-lots`) để đăng ký $K$ cốc support cho từng lot ly. Khi gọi `/predict`, chỉ cần truyền `lot_id`.
  - *Ưu điểm*: Payload request gọn nhẹ hơn.
  - *Nhược điểm*: Cần quản lý vòng đời session, phân quyền người dùng, phức tạp hóa hạ tầng.

### Q2: Chính sách Ưu tiên trong chế độ mặc định `"auto"` của `fusion.py`
- **Bối cảnh**: Hiện tại `fusion.py:100-120` ưu tiên: `regression_ExtraTrees` $\to$ `hybrid (geometry + weight)` $\to$ `geometry` $\to$ `weight`.
- **Phương án A (Khuyến nghị - Thay thế vị trí số 1)**: Ưu tiên: `bayes_hybrid` (nếu có tham số) $\to$ `regression_ExtraTrees` $\to$ `hybrid` $\to$ `geometry` $\to$ `weight`.
  - *Lý do*: Bayes Hybrid đã chứng minh vượt trội hơn về bản chất thống kê, không bị overfit và có khoảng tin cậy.
- **Phương án B (Chỉ kích hoạt khi được yêu cầu rõ ràng)**: Giữ nguyên thứ tự cũ cho `"auto"`, chỉ kích hoạt Bayes khi client chỉ định rõ ràng `estimator_mode="bayes"`.
  - *Lý do*: Giữ nguyên vẹn 100% hành vi đầu ra hiện có của endpoint `/predict` với client cũ.

### Q3: Xử lý mâu thuẫn giữa Đường kính nhập tay và Đường kính dò được
- **Bối cảnh**: Tại `pipeline/container.py:63-64`, $V_{\text{bulk}}$ dùng đường kính nhập tay `diam_mm`, còn tỷ lệ mm/pixel lại lấy từ `inner_diam_px / diam_mm` của mặt lúa.
- **Phương án A (Khuyến nghị - Bổ sung tham số tùy chọn `rice_core_diam_mm`)**: Nếu người dùng cung cấp `rice_core_diam_mm` (đo riêng cho mặt lúa) thì dùng cho scale; nếu không thì dùng chung `diam_mm` cho cả hai, đồng thời kiểm tra chéo độ tròn của ellipse bao lồi.
- **Phương án B (Buộc dùng 1 đường kính duy nhất)**: Luôn áp đặt `inner_diam_mm` cho cả scale và thể tích hình trụ, coi lòng ly là hình trụ hoàn hảo thẳng đứng.

---
*Hết tài liệu PLAN.md. Mọi nội dung kỹ thuật đều dẫn chứng trực tiếp từ mã nguồn thực tế.*
