#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
🌾 RICE VISION AI — TRÌNH XEM VÀ KIỂM TRA MẪU DỮ LIỆU THỰC ĐỊA (GUI VIEWER)
=============================================================================
File: AI_SERVICES/test_data/view_sample.py
Tính năng:
  - Giao diện đồ họa (GUI Tkinter) đầy đủ:
      • Dropdown Combobox chọn mẫu trực tiếp trên giao diện
      • Nút "📂 Chọn ảnh từ máy tính..." mở hộp thoại chọn bất kỳ file ảnh nào
      • Nút điều hướng trực quan: [◀ Trước], [🎲 Ngẫu nhiên], [Sau ▶]
  - Hiển thị ảnh chụp độ phân giải cao, tự động co giãn theo kích thước cửa sổ
  - Bảng thẻ thông số đo thực tế (Actual Count, Cân nặng, Kích thước ly, Thể tích V_bulk)
  - Phím tắt bàn phím: [←]/[P], [→]/[N], [R], [O], [Esc]
=============================================================================
"""

import math
import os
import random
import sys
from pathlib import Path

# Đảm bảo UTF-8 cho console Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import pandas as pd
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# ─────────────────────────────────────────────────────────────────────────────
# 1. ĐỊNH VỊ ĐƯỜNG DẪN DỮ LIỆU
# ─────────────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
RAW_IMG_DIR = BASE_DIR / "1_Raw_Images"
EXCEL_PATH = BASE_DIR / "2_Manual_Records" / "manual_data.xlsx"

df_samples = pd.DataFrame()
if EXCEL_PATH.exists():
    try:
        df_samples = pd.read_excel(EXCEL_PATH)
        df_samples["Sample_ID_str"] = df_samples["Sample_ID"].astype(str).str.strip()
    except Exception as ex:
        print(f"⚠️ Lỗi đọc file Excel {EXCEL_PATH}: {ex}")

TOTAL_SAMPLES = len(df_samples)


def get_sample_data(idx: int):
    """Trích xuất toàn bộ thông số và đường dẫn ảnh của mẫu tại chỉ số idx"""
    if df_samples.empty or idx < 0 or idx >= TOTAL_SAMPLES:
        return None

    row = df_samples.iloc[idx]
    sample_id = str(row["Sample_ID_str"])

    # Tìm tệp ảnh tương ứng trong 1_Raw_Images
    img_candidates = [
        RAW_IMG_DIR / f"{sample_id}.jpg",
        RAW_IMG_DIR / f"{sample_id}.png",
        RAW_IMG_DIR / f"{sample_id}.jpeg",
        RAW_IMG_DIR / f"{sample_id.upper()}.jpg",
        RAW_IMG_DIR / f"{sample_id.lower()}.jpg",
    ]
    img_path = None
    for cand in img_candidates:
        if cand.exists():
            img_path = cand
            break

    weight_g = float(row.get("Weight_g", 0.0))
    diam_mm = float(row.get("Inner_Diameter_mm", 41.7))
    height_mm = float(row.get("Container_Height_mm", 59.5))
    empty_mm = float(row.get("Empty_Height_mm", 0.0))
    actual_count = float(row.get("Actual_Count", 0.0))

    rice_height_mm = max(0.0, height_mm - empty_mm)
    radius_mm = diam_mm / 2.0
    bulk_vol_mm3 = math.pi * (radius_mm ** 2) * rice_height_mm
    bulk_vol_ml = bulk_vol_mm3 / 1000.0

    img_w, img_h, file_size_mb = 0, 0, 0.0
    if img_path and img_path.exists():
        file_size_mb = img_path.stat().st_size / (1024 * 1024)
        try:
            with Image.open(img_path) as im:
                img_w, img_h = im.size
        except Exception:
            pass

    return {
        "index": idx,
        "sample_id": sample_id,
        "img_path": img_path,
        "img_w": img_w,
        "img_h": img_h,
        "file_size_mb": file_size_mb,
        "weight_g": weight_g,
        "diam_mm": diam_mm,
        "height_mm": height_mm,
        "empty_mm": empty_mm,
        "rice_height_mm": rice_height_mm,
        "bulk_vol_mm3": bulk_vol_mm3,
        "bulk_vol_ml": bulk_vol_ml,
        "actual_count": actual_count,
        "original_id": str(row.get("Original_Sample_ID", "")),
        "physical_id": str(row.get("Physical_Sample_ID", "")),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2. GIAO DIỆN NGƯỜI DÙNG TKINTER ĐỒ HỌA TRỰC QUAN
# ─────────────────────────────────────────────────────────────────────────────
class SampleViewerGUI(tk.Tk):
    def __init__(self, initial_idx: int = 0):
        super().__init__()
        self.title("🌾 Rice Vision AI — Trình Xem và Kiểm Tra Mẫu Thực Địa")
        self.geometry("1280x820")
        self.minsize(1000, 680)

        # Cài đặt theme & màu sắc
        self.configure(bg="#0f172a")
        self.current_idx = initial_idx
        self.custom_img_path = None
        self.current_pil_img = None
        self.photo_img = None

        # Trạng thái Phóng to / Thu nhỏ & Kéo rê (Zoom & Pan)
        self.zoom_level = 1.0  # 1.0 = Vừa khung màn hình (Fit to canvas)
        self.offset_x = 0
        self.offset_y = 0
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.is_dragging = False

        self._init_styles()
        self._build_toolbar()
        self._build_main_layout()
        self._bind_shortcuts()

        # Hiển thị mẫu ban đầu
        if TOTAL_SAMPLES > 0:
            self.load_sample_by_index(self.current_idx)

    def _init_styles(self):
        self.style = ttk.Style(self)
        self.style.theme_use("clam")

        # Style Combobox
        self.style.configure("TCombobox", fieldbackground="#1e293b", background="#334155",
                             foreground="#f8fafc", arrowcolor="#38bdf8", font=("Segoe UI", 10))
        self.option_add("*TCombobox*Listbox.background", "#1e293b")
        self.option_add("*TCombobox*Listbox.foreground", "#f8fafc")
        self.option_add("*TCombobox*Listbox.selectBackground", "#2563eb")

    def _build_toolbar(self):
        """Thanh công cụ chọn ảnh và điều hướng trên đỉnh giao diện"""
        tb = tk.Frame(self, bg="#1e293b", height=60, padx=16, pady=10)
        tb.pack(side=tk.TOP, fill=tk.X)

        # 1. Logo / Tiêu đề nhỏ
        lbl_logo = tk.Label(tb, text="🌾 RICE VIEWER", font=("Segoe UI", 12, "bold"), fg="#38bdf8", bg="#1e293b")
        lbl_logo.pack(side=tk.LEFT, padx=(0, 20))

        # 2. Dropdown chọn mẫu
        lbl_select = tk.Label(tb, text="Chọn mẫu:", font=("Segoe UI", 10), fg="#94a3b8", bg="#1e293b")
        lbl_select.pack(side=tk.LEFT, padx=(0, 6))

        sample_options = []
        if not df_samples.empty:
            for i, r in df_samples.iterrows():
                sid = str(r["Sample_ID_str"])
                cnt = r.get("Actual_Count", 0)
                wt = r.get("Weight_g", 0)
                sample_options.append(f"[{i+1:03d}] {sid}  ({cnt:.0f} hạt | {wt:.2f}g)")

        self.cb_samples = ttk.Combobox(tb, values=sample_options, width=32, state="readonly")
        if sample_options:
            self.cb_samples.current(self.current_idx)
        self.cb_samples.pack(side=tk.LEFT, padx=(0, 15))
        self.cb_samples.bind("<<ComboboxSelected>>", self._on_combobox_selected)

        # 3. Nút "📂 Chọn ảnh từ máy tính..."
        btn_open = tk.Button(tb, text="📂 Chọn tệp ảnh bất kỳ...", font=("Segoe UI", 9, "bold"),
                             bg="#2563eb", fg="#ffffff", activebackground="#1d4ed8", activeforeground="#ffffff",
                             relief=tk.FLAT, padx=12, pady=4, cursor="hand2", command=self._on_choose_image_file)
        btn_open.pack(side=tk.LEFT, padx=(0, 20))

        # 4. Nhóm nút điều hướng [◀ Trước], [🎲 Ngẫu nhiên], [Sau ▶]
        btn_prev = tk.Button(tb, text="◀ Trước (P)", font=("Segoe UI", 9), bg="#334155", fg="#f8fafc",
                             activebackground="#475569", activeforeground="#ffffff", relief=tk.FLAT, padx=10, pady=4,
                             cursor="hand2", command=self.prev_sample)
        btn_prev.pack(side=tk.LEFT, padx=3)

        btn_rand = tk.Button(tb, text="🎲 Ngẫu nhiên (R)", font=("Segoe UI", 9), bg="#334155", fg="#f8fafc",
                             activebackground="#475569", activeforeground="#ffffff", relief=tk.FLAT, padx=10, pady=4,
                             cursor="hand2", command=self.random_sample)
        btn_rand.pack(side=tk.LEFT, padx=3)

        btn_next = tk.Button(tb, text="Sau ▶ (N)", font=("Segoe UI", 9), bg="#334155", fg="#f8fafc",
                             activebackground="#475569", activeforeground="#ffffff", relief=tk.FLAT, padx=10, pady=4,
                             cursor="hand2", command=self.next_sample)
        btn_next.pack(side=tk.LEFT, padx=3)

        # 5. Nhãn trạng thái vị trí bên phải
        self.lbl_counter = tk.Label(tb, text=f"Mẫu: {self.current_idx+1}/{TOTAL_SAMPLES}",
                                    font=("Segoe UI", 10, "bold"), fg="#38bdf8", bg="#1e293b")
        self.lbl_counter.pack(side=tk.RIGHT, padx=10)

    def _build_main_layout(self):
        """Bố cục 2 cột: Trái hiển thị ảnh Canvas, Phải bảng thông số Dashboard"""
        content = tk.Frame(self, bg="#0f172a")
        content.pack(fill=tk.BOTH, expand=True, padx=14, pady=12)

        # CỘT TRÁI: KHU VỰC HIỂN THỊ ẢNH
        left_frame = tk.Frame(content, bg="#1e293b", relief=tk.FLAT, bd=0)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        # Tiêu đề ảnh
        self.lbl_img_title = tk.Label(left_frame, text="HÌNH ẢNH MẪU", font=("Segoe UI", 11, "bold"),
                                      fg="#f8fafc", bg="#1e293b", anchor="w", padx=12, pady=6)
        self.lbl_img_title.pack(side=tk.TOP, fill=tk.X)

        # Thanh công cụ Phóng to / Thu nhỏ & Thao tác hình ảnh
        zoom_bar = tk.Frame(left_frame, bg="#1e293b", padx=10, pady=4)
        zoom_bar.pack(side=tk.TOP, fill=tk.X)

        btn_zoom_out = tk.Button(zoom_bar, text="🔍- Thu nhỏ (-)", font=("Segoe UI", 8, "bold"),
                                 bg="#334155", fg="#f8fafc", activebackground="#475569", activeforeground="#ffffff",
                                 relief=tk.FLAT, padx=8, pady=2, cursor="hand2", command=self.zoom_out)
        btn_zoom_out.pack(side=tk.LEFT, padx=(0, 4))

        self.lbl_zoom_val = tk.Label(zoom_bar, text="100% (Vừa khung)", font=("Segoe UI", 9, "bold"),
                                     fg="#38bdf8", bg="#1e293b", width=16)
        self.lbl_zoom_val.pack(side=tk.LEFT, padx=2)

        btn_zoom_in = tk.Button(zoom_bar, text="🔍+ Phóng to (+)", font=("Segoe UI", 8, "bold"),
                                bg="#334155", fg="#f8fafc", activebackground="#475569", activeforeground="#ffffff",
                                relief=tk.FLAT, padx=8, pady=2, cursor="hand2", command=self.zoom_in)
        btn_zoom_in.pack(side=tk.LEFT, padx=(4, 6))

        btn_reset_zoom = tk.Button(zoom_bar, text="↺ Vừa khung (0)", font=("Segoe UI", 8),
                                   bg="#334155", fg="#cbd5e1", activebackground="#475569", activeforeground="#ffffff",
                                   relief=tk.FLAT, padx=6, pady=2, cursor="hand2", command=self.reset_zoom)
        btn_reset_zoom.pack(side=tk.LEFT, padx=3)

        btn_orig_zoom = tk.Button(zoom_bar, text="1:1 Gốc", font=("Segoe UI", 8),
                                  bg="#334155", fg="#cbd5e1", activebackground="#475569", activeforeground="#ffffff",
                                  relief=tk.FLAT, padx=6, pady=2, cursor="hand2", command=self.zoom_original)
        btn_orig_zoom.pack(side=tk.LEFT, padx=3)

        lbl_zoom_tip = tk.Label(zoom_bar, text="💡 Lăn chuột: Zoom  •  Kéo chuột: Di chuyển  •  Nhấp đúp: Reset",
                                font=("Segoe UI", 8), fg="#64748b", bg="#1e293b")
        lbl_zoom_tip.pack(side=tk.RIGHT)

        # Canvas vẽ ảnh
        self.canvas_img = tk.Canvas(left_frame, bg="#0f172a", highlightthickness=0)
        self.canvas_img.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.canvas_img.bind("<Configure>", self._on_canvas_resize)
        self.canvas_img.bind("<MouseWheel>", self._on_mouse_wheel)
        self.canvas_img.bind("<ButtonPress-1>", self._on_pan_start)
        self.canvas_img.bind("<B1-Motion>", self._on_pan_move)
        self.canvas_img.bind("<ButtonRelease-1>", self._on_pan_end)
        self.canvas_img.bind("<Double-Button-1>", self.reset_zoom)

        # Nhãn phụ thông tin ảnh dưới đáy canvas
        self.lbl_img_meta = tk.Label(left_frame, text="", font=("Segoe UI", 9), fg="#94a3b8", bg="#1e293b", pady=6)
        self.lbl_img_meta.pack(side=tk.BOTTOM, fill=tk.X)

        # CỘT PHẢI: DASHBOARD THÔNG SỐ ĐO
        right_frame = tk.Frame(content, bg="#1e293b", width=420, relief=tk.FLAT)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(4, 0))
        right_frame.pack_propagate(False)

        # Tiêu đề bảng thông số
        lbl_right_title = tk.Label(right_frame, text="BÁO CÁO THÔNG SỐ ĐO THỰC TẾ", font=("Segoe UI", 11, "bold"),
                                   fg="#38bdf8", bg="#1e293b", pady=10)
        lbl_right_title.pack(side=tk.TOP, fill=tk.X)

        # 1. Thẻ nổi bật: SỐ HẠT THỰC TẾ (GROUND TRUTH)
        card_gt = tk.Frame(right_frame, bg="#064e3b", padx=14, pady=12, relief=tk.SOLID, bd=1)
        card_gt.pack(fill=tk.X, padx=12, pady=(0, 12))

        tk.Label(card_gt, text="SỐ HẠT THỰC TẾ (GROUND TRUTH)", font=("Segoe UI", 9, "bold"),
                 fg="#a7f3d0", bg="#064e3b").pack(anchor="w")
        self.lbl_gt_count = tk.Label(card_gt, text="--", font=("Segoe UI", 32, "bold"),
                                     fg="#34d399", bg="#064e3b")
        self.lbl_gt_count.pack(pady=(2, 0))
        tk.Label(card_gt, text="hạt đếm tay chuẩn xác", font=("Segoe UI", 8),
                 fg="#6ee7b7", bg="#064e3b").pack()

        # 2. Thẻ Thông số Vật lý & Vật chứa
        card_props = tk.Frame(right_frame, bg="#1e293b", padx=12, pady=10, highlightbackground="#334155", highlightthickness=1)
        card_props.pack(fill=tk.X, padx=12, pady=(0, 12))

        tk.Label(card_props, text="THÔNG SỐ VẬT LÝ & VẬT CHỨA", font=("Segoe UI", 9, "bold"),
                 fg="#94a3b8", bg="#1e293b").pack(anchor="w", pady=(0, 8))

        self.prop_labels = {}
        props_list = [
            ("weight", "⚖️ Khối lượng mẫu (Weight):", "g"),
            ("diam", "📏 Đường kính trong ly (D):", "mm"),
            ("height", "📐 Chiều cao thân ly (Height):", "mm"),
            ("empty", "📉 Khoảng hụt miệng ly (Empty):", "mm"),
            ("rice_h", "🌾 Chiều cao lớp lúa (Rice_H):", "mm"),
            ("bulk_vol", "🧪 Thể tích khối lúa (V_bulk):", "mm³"),
            ("bulk_ml", "🥤 Thể tích tương đương (~ml):", "ml"),
        ]

        for key, text, unit in props_list:
            row = tk.Frame(card_props, bg="#1e293b")
            row.pack(fill=tk.X, pady=3)
            tk.Label(row, text=text, font=("Segoe UI", 9), fg="#cbd5e1", bg="#1e293b").pack(side=tk.LEFT)
            val_lbl = tk.Label(row, text="--", font=("Segoe UI", 9, "bold"), fg="#f8fafc", bg="#1e293b")
            val_lbl.pack(side=tk.RIGHT)
            self.prop_labels[key] = (val_lbl, unit)

        # 3. Thẻ Thông tin Metadata Mẫu
        card_meta = tk.Frame(right_frame, bg="#1e293b", padx=12, pady=10, highlightbackground="#334155", highlightthickness=1)
        card_meta.pack(fill=tk.X, padx=12, pady=(0, 10))

        tk.Label(card_meta, text="THÔNG TIN FILE & METADATA", font=("Segoe UI", 9, "bold"),
                 fg="#94a3b8", bg="#1e293b").pack(anchor="w", pady=(0, 6))

        self.lbl_meta_sample_id = tk.Label(card_meta, text="Mã mẫu: --", font=("Segoe UI", 8), fg="#94a3b8", bg="#1e293b", anchor="w")
        self.lbl_meta_sample_id.pack(fill=tk.X, pady=1)

        self.lbl_meta_filepath = tk.Label(card_meta, text="Tệp ảnh: --", font=("Segoe UI", 8), fg="#94a3b8", bg="#1e293b", anchor="w")
        self.lbl_meta_filepath.pack(fill=tk.X, pady=1)

        self.lbl_meta_res = tk.Label(card_meta, text="Kích thước: --", font=("Segoe UI", 8), fg="#94a3b8", bg="#1e293b", anchor="w")
        self.lbl_meta_res.pack(fill=tk.X, pady=1)

        # Hướng dẫn phím tắt ở đáy cột phải
        hint_box = tk.Frame(right_frame, bg="#0f172a", padx=10, pady=8)
        hint_box.pack(side=tk.BOTTOM, fill=tk.X, padx=12, pady=12)
        hint_text = "💡 Phím tắt:\n[→] / [N]: Mẫu kế tiếp   |   [←] / [P]: Mẫu trước đó\n[R]: Chọn ngẫu nhiên     |   [O]: Mở ảnh từ máy\n[Esc]: Đóng cửa sổ"
        tk.Label(hint_box, text=hint_text, font=("Segoe UI", 8), fg="#64748b", bg="#0f172a", justify=tk.LEFT).pack(anchor="w")

    def _bind_shortcuts(self):
        """Bắt sự kiện phím tắt trên toàn cửa sổ"""
        self.bind("<Right>", lambda e: self.next_sample())
        self.bind("<Left>", lambda e: self.prev_sample())
        self.bind("<n>", lambda e: self.next_sample())
        self.bind("<N>", lambda e: self.next_sample())
        self.bind("<p>", lambda e: self.prev_sample())
        self.bind("<P>", lambda e: self.prev_sample())
        self.bind("<r>", lambda e: self.random_sample())
        self.bind("<R>", lambda e: self.random_sample())
        self.bind("<o>", lambda e: self._on_choose_image_file())
        self.bind("<O>", lambda e: self._on_choose_image_file())
        self.bind("<plus>", lambda e: self.zoom_in())
        self.bind("<equal>", lambda e: self.zoom_in())
        self.bind("<KP_Add>", lambda e: self.zoom_in())
        self.bind("<minus>", lambda e: self.zoom_out())
        self.bind("<underscore>", lambda e: self.zoom_out())
        self.bind("<KP_Subtract>", lambda e: self.zoom_out())
        self.bind("<0>", lambda e: self.reset_zoom())
        self.bind("<Escape>", lambda e: self.destroy())

    def _on_combobox_selected(self, event):
        idx = self.cb_samples.current()
        if idx >= 0:
            self.load_sample_by_index(idx)

    def _on_choose_image_file(self):
        """Hộp thoại Windows chọn bất kỳ ảnh nào trên máy tính"""
        initial_dir = RAW_IMG_DIR if RAW_IMG_DIR.exists() else Path.home()
        file_path = filedialog.askopenfilename(
            parent=self,
            title="Chọn ảnh chụp mẫu lúa từ máy tính",
            initialdir=str(initial_dir),
            filetypes=[
                ("Tệp hình ảnh", "*.jpg *.jpeg *.png *.bmp *.webp"),
                ("Tất cả tệp", "*.*")
            ]
        )
        if not file_path:
            return

        chosen_path = Path(file_path)
        # Kiểm tra xem tên file có khớp với mẫu nào trong dataset không (ví dụ M0010.jpg -> M0010)
        stem_name = chosen_path.stem.strip().upper()

        found_idx = None
        if not df_samples.empty:
            matches = df_samples.index[df_samples["Sample_ID_str"].str.upper() == stem_name].tolist()
            if matches:
                found_idx = matches[0]

        if found_idx is not None:
            # Khớp mẫu trong Excel: tải đầy đủ thông số
            self.load_sample_by_index(found_idx, override_img_path=chosen_path)
        else:
            # Ảnh ngoài dataset: hiển thị ảnh và thông tin ảnh cơ bản
            self.load_custom_image(chosen_path)

    def load_sample_by_index(self, idx: int, override_img_path: Path = None):
        """Nạp dữ liệu mẫu theo chỉ số index từ bảng dataset"""
        if df_samples.empty:
            return

        self.current_idx = max(0, min(idx, TOTAL_SAMPLES - 1))
        data = get_sample_data(self.current_idx)
        if not data:
            return

        if override_img_path and override_img_path.exists():
            data["img_path"] = override_img_path
            try:
                with Image.open(override_img_path) as im:
                    data["img_w"], data["img_h"] = im.size
                data["file_size_mb"] = override_img_path.stat().st_size / (1024 * 1024)
            except Exception:
                pass

        # Cập nhật Combobox
        self.cb_samples.current(self.current_idx)
        self.lbl_counter.config(text=f"Mẫu: {self.current_idx+1}/{TOTAL_SAMPLES}")

        # Cập nhật bảng bên phải
        self.lbl_gt_count.config(text=f"{data['actual_count']:.0f}")
        self.prop_labels["weight"][0].config(text=f"{data['weight_g']:.2f} g")
        self.prop_labels["diam"][0].config(text=f"{data['diam_mm']:.2f} mm")
        self.prop_labels["height"][0].config(text=f"{data['height_mm']:.2f} mm")
        self.prop_labels["empty"][0].config(text=f"{data['empty_mm']:.2f} mm")
        self.prop_labels["rice_h"][0].config(text=f"{data['rice_height_mm']:.2f} mm")
        self.prop_labels["bulk_vol"][0].config(text=f"{data['bulk_vol_mm3']:,.1f} mm³")
        self.prop_labels["bulk_ml"][0].config(text=f"{data['bulk_vol_ml']:.1f} ml")

        img_name = data["img_path"].name if data["img_path"] else "Không tìm thấy file ảnh"
        self.lbl_meta_sample_id.config(text=f"Mã mẫu: {data['sample_id']}  (ID Gốc: {data['original_id'] or 'N/A'})")
        self.lbl_meta_filepath.config(text=f"Tệp: {img_name}")
        self.lbl_meta_res.config(text=f"Kích thước: {data['img_w']} × {data['img_h']} px ({data['file_size_mb']:.2f} MB)")

        # Tiêu đề ảnh
        self.lbl_img_title.config(text=f"ẢNH CHỤP MẪU: {data['sample_id']}  [{self.current_idx+1}/{TOTAL_SAMPLES}]")
        self.lbl_img_meta.config(text=f"📸 {img_name}  |  {data['img_w']} × {data['img_h']} px  |  {data['file_size_mb']:.2f} MB")

        # Reset zoom state về vừa khung cho mẫu mới
        self.zoom_level = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self._update_zoom_label()

        # Nạp ảnh lên Canvas
        if data["img_path"] and data["img_path"].exists():
            try:
                self.current_pil_img = Image.open(data["img_path"])
                self._draw_image_on_canvas()
            except Exception as ex:
                self.canvas_img.delete("all")
                self.canvas_img.create_text(
                    self.canvas_img.winfo_width() // 2 or 300,
                    self.canvas_img.winfo_height() // 2 or 200,
                    text=f"Lỗi đọc ảnh: {ex}", fill="#ef4444", font=("Segoe UI", 12)
                )
        else:
            self.canvas_img.delete("all")
            self.canvas_img.create_text(
                self.canvas_img.winfo_width() // 2 or 300,
                self.canvas_img.winfo_height() // 2 or 200,
                text="❌ Không tìm thấy tệp ảnh trên đĩa", fill="#f87171", font=("Segoe UI", 12)
            )

    def load_custom_image(self, file_path: Path):
        """Hiển thị ảnh được người dùng chọn từ ngoài thư mục dataset"""
        try:
            self.current_pil_img = Image.open(file_path)
            w, h = self.current_pil_img.size
            size_mb = file_path.stat().st_size / (1024 * 1024)

            self.lbl_counter.config(text="Ảnh chọn từ ngoài")
            self.lbl_gt_count.config(text="N/A")
            for key in self.prop_labels:
                self.prop_labels[key][0].config(text="Chưa có dữ liệu")

            self.lbl_meta_sample_id.config(text=f"Tên: {file_path.stem} (Ảnh tùy chọn ngoài)")
            self.lbl_meta_filepath.config(text=f"Đường dẫn: {file_path.name}")
            self.lbl_meta_res.config(text=f"Kích thước: {w} × {h} px ({size_mb:.2f} MB)")

            self.lbl_img_title.config(text=f"ẢNH TỰ CHỌN: {file_path.name}")
            self.lbl_img_meta.config(text=f"📸 {file_path.name}  |  {w} × {h} px  |  {size_mb:.2f} MB")

            # Reset zoom state cho ảnh mới
            self.zoom_level = 1.0
            self.offset_x = 0
            self.offset_y = 0
            self._update_zoom_label()

            self._draw_image_on_canvas()
        except Exception as ex:
            messagebox.showerror("Lỗi mở ảnh", f"Không thể nạp tệp ảnh này: {ex}")

    def _update_zoom_label(self):
        """Cập nhật nhãn hiển thị tỷ lệ thu phóng trên thanh công cụ"""
        pct = int(round(self.zoom_level * 100))
        if abs(self.zoom_level - 1.0) < 0.02:
            self.lbl_zoom_val.config(text="100% (Vừa khung)")
        else:
            self.lbl_zoom_val.config(text=f"{pct}%")

    def zoom_in(self):
        """Phóng to ảnh (tăng 25%)"""
        self._zoom(1.25)

    def zoom_out(self):
        """Thu nhỏ ảnh (giảm 25%)"""
        self._zoom(1.0 / 1.25)

    def reset_zoom(self, event=None):
        """Khôi phục ảnh về trạng thái vừa vặn khung nhìn (Fit to window)"""
        self.zoom_level = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self._update_zoom_label()
        self._draw_image_on_canvas()

    def zoom_original(self):
        """Phóng to kích thước gốc 1:1 (1 pixel ảnh = 1 pixel màn hình)"""
        if not self.current_pil_img:
            return
        cw = self.canvas_img.winfo_width()
        ch = self.canvas_img.winfo_height()
        if cw < 50 or ch < 50:
            cw, ch = 650, 600
        iw, ih = self.current_pil_img.size
        base_scale = min((cw - 16) / iw, (ch - 16) / ih)
        self.zoom_level = max(0.2, min((1.0 / base_scale) if base_scale > 0 else 1.0, 20.0))
        self.offset_x = 0
        self.offset_y = 0
        self._update_zoom_label()
        self._draw_image_on_canvas()

    def _on_mouse_wheel(self, event):
        """Lăn chuột để phóng to / thu nhỏ tại đúng vị trí trỏ chuột"""
        if not self.current_pil_img:
            return
        # Trên Windows event.delta dương là cuộn lên (phóng to), âm là cuộn xuống (thu nhỏ)
        factor = 1.2 if event.delta > 0 else (1.0 / 1.2)
        self._zoom(factor, mouse_x=event.x, mouse_y=event.y)

    def _zoom(self, factor: float, mouse_x: int = None, mouse_y: int = None):
        """Xử lý toán học thu phóng giữ tâm hoặc theo vị trí con trỏ chuột"""
        if not self.current_pil_img:
            return

        cw = self.canvas_img.winfo_width()
        ch = self.canvas_img.winfo_height()
        if cw < 50 or ch < 50:
            cw, ch = 650, 600

        iw, ih = self.current_pil_img.size
        base_scale = min((cw - 16) / iw, (ch - 16) / ih)

        old_zoom = self.zoom_level
        new_zoom = max(0.3, min(old_zoom * factor, 25.0))  # Giới hạn từ 30% đến 2500%
        if abs(new_zoom - old_zoom) < 1e-4:
            return

        old_total_scale = base_scale * old_zoom
        new_total_scale = base_scale * new_zoom

        if mouse_x is not None and mouse_y is not None:
            # Thu phóng tương đối giữ nguyên vị trí pixel ảnh ngay dưới con trỏ chuột
            old_cx = cw / 2.0 + self.offset_x
            old_cy = ch / 2.0 + self.offset_y

            img_px = (mouse_x - old_cx) / old_total_scale
            img_py = (mouse_y - old_cy) / old_total_scale

            new_cx = mouse_x - img_px * new_total_scale
            new_cy = mouse_y - img_py * new_total_scale

            self.offset_x = new_cx - cw / 2.0
            self.offset_y = new_cy - ch / 2.0
        else:
            self.offset_x *= factor
            self.offset_y *= factor

        self.zoom_level = new_zoom
        if self.zoom_level <= 1.01:
            self.offset_x = 0
            self.offset_y = 0

        self._update_zoom_label()
        self._draw_image_on_canvas()

    def _on_pan_start(self, event):
        """Bắt đầu nhấn giữ chuột trái để kéo rê (Pan)"""
        self.drag_start_x = event.x
        self.drag_start_y = event.y
        self.is_dragging = True
        self.canvas_img.config(cursor="fleur")

    def _on_pan_move(self, event):
        """Kéo chuột để di chuyển vùng nhìn ảnh"""
        if not self.is_dragging or not self.current_pil_img:
            return
        dx = event.x - self.drag_start_x
        dy = event.y - self.drag_start_y
        self.drag_start_x = event.x
        self.drag_start_y = event.y
        self.offset_x += dx
        self.offset_y += dy
        self._draw_image_on_canvas()

    def _on_pan_end(self, event):
        """Thả chuột kết thúc kéo rê"""
        self.is_dragging = False
        self.canvas_img.config(cursor="")

    def _draw_image_on_canvas(self):
        """Vẽ và căn chỉnh ảnh trên canvas với tốc độ cao, hỗ trợ zoom và viewport crop"""
        if not self.current_pil_img:
            return

        cw = self.canvas_img.winfo_width()
        ch = self.canvas_img.winfo_height()
        if cw < 50 or ch < 50:
            cw, ch = 650, 600

        iw, ih = self.current_pil_img.size
        base_scale = min((cw - 16) / iw, (ch - 16) / ih)
        total_scale = base_scale * self.zoom_level

        center_x = cw / 2.0 + self.offset_x
        center_y = ch / 2.0 + self.offset_y

        target_w = max(1, int(iw * total_scale))
        target_h = max(1, int(ih * total_scale))

        # Tối ưu hiệu năng: Nếu kích thước phóng to quá lớn (>3200px), chỉ cắt vùng nhìn thấy trong canvas
        if target_w <= 3200 and target_h <= 3200:
            resized = self.current_pil_img.resize((target_w, target_h), Image.Resampling.BILINEAR)
            self.photo_img = ImageTk.PhotoImage(resized)
            self.canvas_img.delete("all")
            self.canvas_img.create_image(int(center_x), int(center_y), image=self.photo_img, anchor=tk.CENTER)
        else:
            # Tính toán tọa độ hộp bao (bounding box) tương ứng trên ảnh gốc
            left_img = max(0, int((0 - center_x) / total_scale + iw / 2.0))
            top_img = max(0, int((0 - center_y) / total_scale + ih / 2.0))
            right_img = min(iw, int((cw - center_x) / total_scale + iw / 2.0) + 1)
            bottom_img = min(ih, int((ch - center_y) / total_scale + ih / 2.0) + 1)

            if right_img > left_img and bottom_img > top_img:
                cropped = self.current_pil_img.crop((left_img, top_img, right_img, bottom_img))
                crop_w = max(1, int((right_img - left_img) * total_scale))
                crop_h = max(1, int((bottom_img - top_img) * total_scale))
                resized = cropped.resize((crop_w, crop_h), Image.Resampling.BILINEAR)
                self.photo_img = ImageTk.PhotoImage(resized)

                draw_x = int((left_img - iw / 2.0) * total_scale + center_x)
                draw_y = int((top_img - ih / 2.0) * total_scale + center_y)
                self.canvas_img.delete("all")
                self.canvas_img.create_image(draw_x, draw_y, image=self.photo_img, anchor=tk.NW)
            else:
                self.canvas_img.delete("all")

    def _on_canvas_resize(self, event):
        """Khi người dùng phóng to/thu nhỏ cửa sổ, ảnh tự co giãn theo"""
        if self.current_pil_img:
            self._draw_image_on_canvas()

    def next_sample(self):
        if TOTAL_SAMPLES > 0:
            new_idx = (self.current_idx + 1) % TOTAL_SAMPLES
            self.load_sample_by_index(new_idx)

    def prev_sample(self):
        if TOTAL_SAMPLES > 0:
            new_idx = (self.current_idx - 1) % TOTAL_SAMPLES
            self.load_sample_by_index(new_idx)

    def random_sample(self):
        if TOTAL_SAMPLES > 0:
            new_idx = random.randint(0, TOTAL_SAMPLES - 1)
            self.load_sample_by_index(new_idx)


def main():
    initial_idx = 0
    if len(sys.argv) > 1:
        arg = sys.argv[1].strip()
        if arg.isdigit():
            initial_idx = max(0, min(int(arg) - 1, TOTAL_SAMPLES - 1))
        elif not df_samples.empty:
            matches = df_samples.index[df_samples["Sample_ID_str"].str.upper() == arg.upper()].tolist()
            if matches:
                initial_idx = matches[0]

    app = SampleViewerGUI(initial_idx=initial_idx)
    app.mainloop()


if __name__ == "__main__":
    main()
