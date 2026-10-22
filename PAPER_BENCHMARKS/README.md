# 🌾 Rice Vision AI — Experimental Benchmarks & Paper Artifacts

Thư mục này tổng hợp toàn bộ **số liệu thực nghiệm, bảng đối sánh và biểu đồ độ phân giải cao** phục vụ công bố khoa học (Scientific Paper) và báo cáo nghiên cứu của đề tài **Hệ Thống Đếm & Đo Kích Thước Hạt Gạo Tự Động (Rice Vision AI)**.

Tất cả các số liệu tại đây được trích xuất trực tiếp từ các thực nghiệm huấn luyện và kiểm định mô hình, không chứa mã nguồn nặng hay checkpoint để thuận tiện cho việc tra cứu, trích dẫn vào Word/LaTeX.

---

## 📂 Cấu Trúc Tổng Quan

```text
PAPER_BENCHMARKS/
├── 01_segmentation_benchmarks/               <-- Tầng Thị Giác Máy Tính (Instance Segmentation)
│   ├── benchmark_summary_all_models.csv      <-- Bảng đối sánh 8 mô hình (mAP50, mAP50-95, thời gian, FPS)
│   ├── benchmark_summary_tables.xlsx         <-- Bảng số liệu định dạng Excel
│   └── charts/                               <-- 5 biểu đồ đối sánh: Radar, Pareto Frontier, mAP so sánh...
│
├── 02_regression_benchmarks/                 <-- Tầng Học Máy Dạng Bảng (Tabular Regression)
│   ├── comparison.csv                        <-- Đánh giá 16 thuật toán hồi quy (ExtraTrees, ARD, RF, Ridge...)
│   ├── split_membership.csv                  <-- Danh sách mẫu tập Train / Validation / Test
│   ├── data_quality_report.json              <-- Đánh giá phân phối và độ lệch của 31 đặc trưng đầu vào
│   └── run_metadata.json                     <-- Thông số phần cứng và môi trường chạy thực nghiệm
│
└── 03_pipeline_and_bayes_benchmarks/         <-- Tầng Tích Hợp Hệ Thống & Hiệu Chuẩn Bayes
    ├── benchmark_100_results.csv             <-- Kết quả kiểm thử End-to-End trên 100 mẫu thực tế
    ├── benchmark_metrics_summary.json        <-- Chỉ số tổng hợp sai số toàn hệ thống
    ├── benchmark_report.txt                  <-- Báo cáo chi tiết định dạng văn bản
    ├── benchmark_visual_analytics.png        <-- Biểu đồ tổng quan phân tích sai số
    ├── visual_gallery/                       <-- 5 biểu đồ phân tích chuyên sâu (phân phối, lot size, best/worst)
    └── bayes_fewshot/                        <-- Nghiên cứu chuyên sâu: Hiệu chuẩn Bayes (Few-Shot Calibration)
        ├── results_macro.csv                 <-- Bảng kết quả Macro metrics theo số lượng mẫu K (K=0, 1, 5, 10)
        ├── paired_tests.csv                  <-- Kết quả kiểm định thống kê Paired t-test
        ├── paper_table.md                    <-- Bảng Markdown chuẩn định dạng bài báo khoa học
        └── curves.png                        <-- Biểu đồ hội tụ sai số theo số shot
```

---

## 1. Tầng Phân Đoạn Hạt Gạo (Instance Segmentation)

- **Mục tiêu:** So sánh hiệu năng phát hiện và tách biên từng hạt gạo rời rạc từ ảnh chụp trên nền đĩa/ly chứa.
- **Tập mô hình đánh giá:** YOLOv8 (nano, small, medium), YOLOv10 (nano, small), YOLO26s, YOLOv12-MobileSAM.
- **Tài liệu nguồn:**
  - Bảng số liệu tổng hợp: [`01_segmentation_benchmarks/benchmark_summary_all_models.csv`](01_segmentation_benchmarks/benchmark_summary_all_models.csv)
  - Biểu đồ phân tích Pareto: [`01_segmentation_benchmarks/charts/chart4_pareto_frontier.png`](01_segmentation_benchmarks/charts/chart4_pareto_frontier.png)
  - Biểu đồ Radar đa tiêu chí: [`01_segmentation_benchmarks/charts/chart2_radar_benchmark.png`](01_segmentation_benchmarks/charts/chart2_radar_benchmark.png)
- **Tái lập thí nghiệm:** Chạy lại notebook [`RESULTS/Segmentation Model Results/SEGMENTATION_MODELS_BENCHMARK.ipynb`](../RESULTS/Segmentation%20Model%20Results/SEGMENTATION_MODELS_BENCHMARK.ipynb).

---

## 2. Tầng Hồi Quy Đếm Số Hạt (Machine Learning Regression)

- **Mục tiêu:** Dự đoán chính xác tổng số lượng hạt gạo từ vector 31 đặc trưng hình học (thể tích bulk, độ nén packing, kích thước elip trung bình...).
- **Tập mô hình đánh giá:** 16 thuật toán thuộc các họ Tree Ensemble, Robust Linear, Bayesian Linear, Kernel Ridge:
  - **Mô hình tốt nhất:** **Extra Trees Regressor** đạt $R^2 = 0.9994$, $\text{MAE} = 1.79$ hạt, $\text{MAPE} = 1.28\%$.
- **Tài liệu nguồn:**
  - Bảng đối chiếu 16 mô hình: [`02_regression_benchmarks/comparison.csv`](02_regression_benchmarks/comparison.csv)
  - Báo cáo chất lượng dữ liệu: [`02_regression_benchmarks/data_quality_report.json`](02_regression_benchmarks/data_quality_report.json)
- **Tái lập thí nghiệm:** Thực thi script [`LINEAR_REGRESSION_MODEL/train_linear_regression.py`](../LINEAR_REGRESSION_MODEL/train_linear_regression.py).

---

## 3. Tầng Kiểm Thử Tích Hợp Toàn Diện (End-to-End Pipeline Validation)

- **Mục tiêu:** Đánh giá độ chính xác thực tế khi toàn bộ hệ thống phối hợp: Chụp ảnh $\rightarrow$ Dò miệng ly $\rightarrow$ Phân đoạn hạt $\rightarrow$ Trích xuất 31 đặc trưng $\rightarrow$ Mô hình Hồi quy dự đoán.
- **Dữ liệu kiểm thử:** 100 mẫu ngẫu nhiên độc lập đối chiếu trực tiếp với số hạt đếm thủ công (Ground Truth).
- **Tài liệu nguồn:**
  - Bảng dữ liệu 100 mẫu: [`03_pipeline_and_bayes_benchmarks/benchmark_100_results.csv`](03_pipeline_and_bayes_benchmarks/benchmark_100_results.csv)
  - Tóm tắt chỉ số sai số: [`03_pipeline_and_bayes_benchmarks/benchmark_metrics_summary.json`](03_pipeline_and_bayes_benchmarks/benchmark_metrics_summary.json)
  - Biểu đồ phân tích trực quan: [`03_pipeline_and_bayes_benchmarks/visual_gallery/`](03_pipeline_and_bayes_benchmarks/visual_gallery/)
- **Tái lập thí nghiệm:** Chạy kiểm thử tự động tại [`AI_SERVICES/tests/test_real_pipeline.py`](../AI_SERVICES/tests/test_real_pipeline.py) hoặc xem phân tích tại [`AI_SERVICES/test_data/VISUALIZE_BENCHMARK_RESULTS.ipynb`](../AI_SERVICES/test_data/VISUALIZE_BENCHMARK_RESULTS.ipynb).

---

## 4. Tầng Hiệu Chuẩn Bayes Chống Overfitting (Few-Shot Lot Calibration)

- **Mục tiêu:** Khắc phục sự sai lệch phân phối giữa các mẻ gạo khác nhau (cross-lot distribution shift) bằng mô hình Bayesian Normal-Inverse-Gamma kết hợp hiệu chuẩn Few-Shot.
- **Kết quả nổi bật:**
  - Khi không có mẫu hiệu chuẩn ($K=0$): $\text{MAE} = 6.0$ hạt ($\text{MAPE} = 3.76\%$).
  - Chỉ với $K=1$ mẫu hiệu chuẩn: $\text{MAE}$ giảm còn $2.8$ hạt ($\text{MAPE} = 2.33\%$).
  - Với $K=5$ mẫu: $\text{MAE}$ đạt $2.2$ hạt ($\text{MAPE} = 1.88\%$).
- **Tài liệu nguồn:**
  - Bảng Markdown chuẩn bài báo: [`03_pipeline_and_bayes_benchmarks/bayes_fewshot/paper_table.md`](03_pipeline_and_bayes_benchmarks/bayes_fewshot/paper_table.md)
  - Bảng kiểm định thống kê $t$-test ($p < 0.05$): [`03_pipeline_and_bayes_benchmarks/bayes_fewshot/paired_tests.csv`](03_pipeline_and_bayes_benchmarks/bayes_fewshot/paired_tests.csv)
  - Đồ thị hội tụ sai số: [`03_pipeline_and_bayes_benchmarks/bayes_fewshot/curves.png`](03_pipeline_and_bayes_benchmarks/bayes_fewshot/curves.png)
- **Tái lập thí nghiệm:** Chạy script [`FromThanh/baseline_comparison.py`](../FromThanh/baseline_comparison.py).
