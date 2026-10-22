# 🌾 Rice Vision AI — System Validation & Test Data

Thư mục này dùng để lưu trữ **ảnh chụp thực tế và số liệu nhãn thủ công (Ground Truth)** được xuất trực tiếp từ ứng dụng **Rice Dataset Capture (CAPTURE_APP)** nhằm phục vụ kiểm nghiệm, đánh giá độ chính xác của hệ thống AI Services.

---

## 1. Cấu trúc thư mục

```text
AI_SERVICES/test_data/
├── 1_Raw_Images/        <--- Chứa 100 ảnh mẫu kiểm thử ngẫu nhiên (.jpg): M0001.jpg, M0003.jpg... (hoặc nhận ảnh mới từ CAPTURE_APP)
├── 2_Manual_Records/    <--- Chứa bảng tính manual_data.xlsx & capture_data.sqlite3 tương ứng với 100 mẫu
└── README.md
```

> **Ghi chú dữ liệu mẫu sẵn có:**
> Thư mục đã được nạp sẵn **100 mẫu ngẫu nhiên** được trích xuất từ 500 mẫu đầu của `DATASET_BUILDER`. Bạn có thể sử dụng ngay để chạy kiểm thử độ chính xác hoặc trỏ `CAPTURE_APP` vào đây để tiếp tục chụp thêm các mẫu mới.

---

## 2. Hướng dẫn thiết lập đường dẫn khi mở CAPTURE_APP

Khi khởi động ứng dụng **`CAPTURE_APP`** (qua `run_capture_app.bat`), tại giao diện thiết lập lần đầu hoặc menu cấu hình:

1. **Thư mục lưu ảnh (Image Directory)**:
   * Bấm chọn đường dẫn trỏ đến:
     ```text
     D:\GG_1\NGHIÊN CỨU KHOA HỌC\GROUP_MEMBERS\NGUYEN MINH TRI\MAIN_SOURCES\AI_SERVICES\test_data\1_Raw_Images
     ```
   * Ứng dụng sẽ tự động lưu ảnh chụp dưới định dạng phẳng: `M0001.jpg`, `M0002.jpg`...

2. **File bảng tính Excel (Manual Data File)**:
   * Bấm chọn hoặc tạo file Excel tại:
     ```text
     D:\GG_1\NGHIÊN CỨU KHOA HỌC\GROUP_MEMBERS\NGUYEN MINH TRI\MAIN_SOURCES\AI_SERVICES\test_data\2_Manual_Records\manual_data.xlsx
     ```
   * Ứng dụng sẽ tự động ghi các thông số:
     * `Sample_ID` (M0001, M0002...)
     * `Actual_Count` (Số hạt đếm tay thực tế làm Ground Truth)
     * `Inner_Diameter_mm` (Đường kính trong của ly)
     * `Container_Height_mm` (Chiều cao ly)
     * `Empty_Height_mm` (Khoảng trống miệng ly)
     * `Weight_g` (Khối lượng cân điện tử)

---

## 3. Cách sử dụng dữ liệu để kiểm nghiệm AI Services

Dữ liệu thu thập tại đây có thể được sử dụng trực tiếp để:
1. **Kiểm thử tự động End-to-End**: Trỏ fixture trong `tests/test_real_pipeline.py` tới ảnh bất kỳ trong `1_Raw_Images/` và đối chiếu kết quả dự đoán với `Actual_Count` trong `manual_data.xlsx`.
2. **Kiểm thử giao diện API / Postman**: Gửi request `POST /predict` kèm ảnh và các thông số vật lý tương ứng.
3. **Thử nghiệm trên Jupyter Notebook**: Mở `src/notebooks/experiments/RICE_VISION_MAIN_PIPELINE.ipynb` để trực quan hóa từng bước phân đoạn hạt, mô hình 3D ellipsoid và dự đoán hồi quy.
