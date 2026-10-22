# DANH SÁCH CÁC VẤN ĐỀ CHƯA RÕ & CÂU HỎI MỞ (OPEN_QUESTIONS.md)

> **Dự án**: Rice Vision AI Inference Service  
> **Tài liệu**: Tổng hợp nghi vấn kỹ thuật & Quyết định kiến trúc (Decisions & Open Questions)  
> **Trạng thái**: Đã phê duyệt các quyết định cốt lõi (Core Decisions Approved by Lead)  
> **Ngày cập nhật**: 14/10/2026  

---

## 1. BẢNG TỔNG HỢP CÁC QUYẾT ĐỊNH ĐÃ ĐƯỢC CHỐT (RESOLVED DECISIONS)

Dưới đây là 3 quyết định kiến trúc then chốt đã được Người phụ trách dự án phê duyệt:

| Quyết định | Nội dung câu hỏi | Phương án đã chọn & Thống nhất triển khai | Trạng thái |
| :---: | :--- | :--- | :---: |
| **Q1** | Nguồn code chuẩn khi thiếu `rice_hybrid.py` & `GIAI_PHAP_KET_HOP.md` | **Chính thức sử dụng Cell 04 của `FromThanh/Copy of rice_fewshot_v2_colab.ipynb`** (`rice_fewshot_v2.py`) làm nguồn chân lý kỹ thuật. Mã nguồn này chứa toàn bộ logic Dual-branch (Nhánh V và Nhánh W), cập nhật liên hợp Normal-Inverse-Gamma, và hiệu chuẩn khoảng tin cậy $\lambda$. | **ĐÃ CHỐT**<br>(APPROVED) |
| **Q2** | Cơ chế tiếp nhận Cốc Support ($K$) qua API | **Phương án A (Khuyến nghị - Stateless Payload)**: Client gửi danh sách $K$ cốc mẫu chuẩn trực tiếp trong trường form `support_cups` (chuỗi JSON) của request `POST /predict`. Backend giải mã, cập nhật hậu nghiệm trong RAM và suy diễn cho cốc query hiện tại rồi giải phóng. Kiến trúc hoàn toàn không trạng thái (Stateless Microservice), an toàn khi scale horizontal, không cần database session. | **ĐÃ CHỐT**<br>(APPROVED) |
| **Q3** | Chính sách Ưu tiên trong chế độ mặc định `"auto"` của `fusion.py` | **Phương án A (Khuyến nghị - Ưu tiên số 1 cho Bayes)**: Khi `estimator_mode="auto"`, hệ thống ưu tiên theo thứ tự:<br>1. `bayes_hybrid` (nếu file tham số Bayes khả dụng)<br>2. `regression_ExtraTrees`<br>3. `hybrid (geometry + weight)`<br>4. `geometry`<br>5. `weight` | **ĐÃ CHỐT**<br>(APPROVED) |

---

## 2. CHI TIẾT TÌNH TRẠNG FILE VÀ CĂN CỨ TÁI TẠO

### 2.1. File `rice_hybrid.py` & `GIAI_PHAP_KET_HOP.md`
- **Hiện trạng kiểm tra**: **KHÔNG TÌM THẤY** trên toàn bộ cây thư mục `D:\GG_1\NGHIÊN CỨU KHOA HỌC\GROUP_MEMBERS\NGUYEN MINH TRI\MAIN_SOURCES` cũng như các thư mục lân cận.
- **Bằng chứng đã tìm kiếm**:
  - Đã quét đệ quy bằng PowerShell: `Get-ChildItem -Recurse -Filter "rice_hybrid.py"` $\to$ Kết quả trả về rỗng (0 file).
  - Quét đệ quy `Get-ChildItem -Recurse -Filter "*GIAI_PHAP_KET_HOP*"` $\to$ Kết quả trả về rỗng (0 file).
- **Căn cứ kỹ thuật chính thức được phê duyệt**:
  - Tại Cell 04 của notebook `FromThanh/Copy of rice_fewshot_v2_colab.ipynb`, toàn bộ mã nguồn của `rice_fewshot_v2.py` đã được lưu trữ hoàn chỉnh (359 dòng code).
  - Lớp `BayesLotCalibrator` trong notebook này hỗ trợ cả hai nhánh: Nhánh thuần thị giác (`phys_col="lV"`, `use_vg=True`) và Nhánh có cân (`phys_col="lW"`, `use_vg=False`, `g_mode="pooled"`).
  - Kết quả kiểm chuẩn thực nghiệm đã được đối soát chính xác với `FromThanh/results_v2/results_v2/paper_table.md`.

---

## 3. CÁC ĐIỂM KỸ THUẬT CẦN LƯU Ý KHI THỰC HIỆN BƯỚC TIẾP THEO

### 3.1. Cờ chẩn đoán `metric_accuracy_validated: False` của Container Detector
- **Bằng chứng trong code**:
  - Tại `src/rice_ai/vision/container_detector.py:594`:
    ```python
    diagnostics = {
        ...,
        'metric_accuracy_validated': False,
        ...
    }
    ```
- **Xử lý theo thiết kế**:
  - Khi detector phát hiện mặt lúa có cờ `metric_accuracy_validated == False`, hệ thống kích hoạt cờ cảnh báo `SCALE_UNVALIDATED`.
  - Nếu có cân $W > 0$: Cổng bất đồng $3\sigma$ sẽ bảo vệ, tự động giảm độ tin cậy của Nhánh V khi có xung đột.
  - Nếu không có cân: Vẫn trả kết quả Nhánh V nhưng tự động nới rộng khoảng tin cậy 90% thêm $25\%$ để phản ánh độ không chắc chắn của scale.

### 3.2. Hiện tượng phủ thiếu khoảng tin cậy ở $K=1$ (~85%)
- **Bằng chứng số liệu**:
  Trích xuất từ bảng `90% interval coverage (%)` tại `FromThanh/results_v2/results_v2/paper_table.md:32-43`:
  - Tại $K = 0$: Độ phủ đạt $99.0\%$.
  - Tại $K = 1$: Độ phủ của mô hình chính `Ours+W (main)` đạt $85.4\%$ (dưới ngưỡng danh nghĩa 90%).
  - Tại $K \ge 3$: Độ phủ hồi phục ổn định $\ge 92.8\%$.
- **Xử lý theo thiết kế**:
  - Trong script fit offline `scripts/fit_bayes_params.py`, hệ số lạm phát phương sai $\lambda$ sẽ được tính riêng cho mức $K=1$ ($\lambda_{K=1} \approx 1.15$) qua nested cross-validation, nhằm đảm bảo khoảng tin cậy tại $K=1$ đạt tối thiểu $90\%$ như cam kết trong tài liệu đặc tả.

### 3.3. Bảo toàn các hằng số Packing Fraction hiện có
- **Bằng chứng trong code**:
  1. `src/rice_ai/settings.py:66`: `packing_fraction_geometry = 0.55`.
  2. `src/rice_ai/estimation/geometry.py:14`: `packing_fraction: float = 0.82`.
  3. `src/rice_ai/estimation/feature_schema.py:23`: `TRAINED_HYBRID_PACKING_FRACTION: float = 1.0`.
- **Xử lý theo thiết kế**:
  - Giữ nguyên các hằng số này để bảo toàn tính tương thích 100% cho chế độ cũ `estimator_mode="geometry"` và `estimator_mode="regression"`.
  - Mô-đun Bayes hoàn toàn tự động học độ lệch điền đầy $\exp(b_{\text{lot}})$ từ dữ liệu mà không phụ thuộc vào các hằng số hardcode này.

---
*Tài liệu này ghi nhận quyết định của người phụ trách dự án và làm căn cứ để bắt đầu giai đoạn triển khai mã nguồn.*
