#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
🌾 RICE VISION AI — CÔNG CỤ TỔNG HỢP TOÀN BỘ CODEBASE (CODEBASE COMBINER)
=============================================================================
File: AI_SERVICES/combine_codebase.py
Mục đích:
  - Gom toàn bộ mã nguồn, cấu hình, cây cấu trúc thư mục và tài liệu của AI_SERVICES
    thành MỘT tệp Markdown/Text duy nhất.
  - Phục vụ việc đưa toàn bộ ngữ cảnh dự án vào các mô hình AI bên ngoài (ChatGPT,
    Claude, Gemini, DeepSeek, v.v.) để phân tích, phản biện, viết tài liệu hoặc code.
  - Tự động loại trừ các thư mục rác, virtualenv (.venv), node_modules, cache (__pycache__).
  - Tự động làm sạch Jupyter Notebooks (loại bỏ outputs ảnh base64 khổng lồ, giữ trọn vẹn code).
  - Tự động tạo cây thư mục ASCII/Unicode và mục lục điều hướng chi tiết.
=============================================================================
"""

import os
import sys
import json
import argparse
import datetime
from pathlib import Path

# Đảm bảo UTF-8 cho console Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Thư mục cần bỏ qua hoàn toàn
IGNORE_DIRS = {
    ".venv", "venv", "env",
    "__pycache__", ".pytest_cache",
    ".ipynb_checkpoints", ".git",
    "node_modules", ".idea", ".vscode",
    "site-packages", "dist", "build"
}

# Các đuôi file văn bản sẽ được đọc và đưa toàn văn nội dung
TEXT_EXTENSIONS = {
    ".py", ".json", ".yaml", ".yml",
    ".md", ".txt", ".toml", ".ini",
    ".cfg", ".sh", ".bat", ".ps1",
    ".env", ".csv"
}

# Các đuôi file nhị phân lớn / ảnh / mô hình (chỉ ghi metadata)
BINARY_EXTENSIONS = {
    ".pt", ".pth", ".keras", ".h5",
    ".joblib", ".pkl", ".onnx",
    ".jpg", ".jpeg", ".png", ".bmp", ".webp",
    ".zip", ".tar", ".gz",
    ".exe", ".dll", ".so", ".pyd", ".node"
}


def build_directory_tree(dir_path: Path, prefix: str = "", max_depth: int = 5, current_depth: int = 0) -> list:
    """Tạo cây thư mục dạng danh sách các dòng văn bản ASCII/Unicode"""
    if current_depth > max_depth:
        return [f"{prefix}└── ... (vượt quá độ sâu tối đa)"]

    try:
        entries = sorted(list(dir_path.iterdir()), key=lambda x: (not x.is_dir(), x.name.lower()))
    except PermissionError:
        return [f"{prefix}└── [Truy cập bị từ chối]"]

    entries = [e for e in entries if e.name not in IGNORE_DIRS and not e.name.startswith(".")]

    lines = []
    for i, entry in enumerate(entries):
        is_last = (i == len(entries) - 1)
        connector = "└── " if is_last else "├── "

        if entry.is_dir():
            lines.append(f"{prefix}{connector}{entry.name}/")
            sub_prefix = prefix + ("    " if is_last else "│   ")
            lines.extend(build_directory_tree(entry, sub_prefix, max_depth, current_depth + 1))
        else:
            size_kb = entry.stat().st_size / 1024
            size_str = f"({size_kb:.1f} KB)" if size_kb < 1024 else f"({size_kb/1024:.2f} MB)"
            lines.append(f"{prefix}{connector}{entry.name} {size_str}")

    return lines


def clean_notebook_content(nb_path: Path) -> str:
    """Đọc tệp Jupyter Notebook, lược bỏ outputs ảnh base64, chỉ giữ lại Markdown và Code"""
    try:
        with open(nb_path, "r", encoding="utf-8") as f:
            nb = json.load(f)
    except Exception as e:
        return f"# Lỗi đọc Notebook: {e}\n"

    lines = []
    lines.append(f"# 📓 JUPYTER NOTEBOOK: {nb_path.name}")
    lines.append(f"# Tổng số cells: {len(nb.get('cells', []))}\n")

    for idx, cell in enumerate(nb.get("cells", [])):
        cell_type = cell.get("cell_type", "code")
        source = "".join(cell.get("source", []))

        if cell_type == "markdown":
            lines.append(f"<!-- ===== CELL {idx:02d} [MARKDOWN] ===== -->")
            lines.append(source.strip())
            lines.append("")
        elif cell_type == "code":
            lines.append(f"# ===== CELL {idx:02d} [PYTHON CODE] =====")
            lines.append(source.strip())
            lines.append("")

    return "\n".join(lines)


def scan_and_collect_files(root_dir: Path, max_file_size_kb: int = 1000):
    """Quét toàn bộ thư mục và phân loại các tệp"""
    text_files = []
    notebook_files = []
    binary_files = []

    for item in sorted(root_dir.rglob("*")):
        if not item.is_file():
            continue

        # Bỏ qua nếu nằm trong thư mục bị ignore
        if any(part in IGNORE_DIRS for part in item.parts):
            continue

        ext = item.suffix.lower()
        size_kb = item.stat().st_size / 1024

        if ext == ".ipynb":
            notebook_files.append((item, size_kb))
        elif ext in TEXT_EXTENSIONS:
            if size_kb <= max_file_size_kb:
                text_files.append((item, size_kb))
            else:
                binary_files.append((item, size_kb, f"Văn bản lớn (> {max_file_size_kb} KB)"))
        else:
            desc = "Nhị phân / Model / Dữ liệu"
            if ext in {".pt", ".pth"}:
                desc = "Trọng số PyTorch YOLO"
            elif ext in {".keras", ".h5"}:
                desc = "Mô hình Keras CNN"
            elif ext == ".joblib":
                desc = "Mô hình Scikit-Learn (Extra Trees)"
            elif ext in {".jpg", ".jpeg", ".png"}:
                desc = "Tệp hình ảnh"
            elif ext == ".xlsx":
                desc = "Bảng tính Excel"
            binary_files.append((item, size_kb, desc))

    return text_files, notebook_files, binary_files


def combine_codebase(root_dir: Path, output_file: Path, max_file_size_kb: int = 1000):
    """Tạo file tổng hợp toàn bộ codebase"""
    print(f"🔍 Bắt đầu quét thư mục: {root_dir}...")
    text_files, notebook_files, binary_files = scan_and_collect_files(root_dir, max_file_size_kb)

    total_code_lines = 0
    all_files_for_toc = []

    print(f"🌳 Đang tạo cây cấu trúc thư mục...")
    tree_lines = build_directory_tree(root_dir, max_depth=4)

    timestamp_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    print(f"📝 Đang tổng hợp nội dung {len(text_files)} files code và {len(notebook_files)} notebooks...")

    with open(output_file, "w", encoding="utf-8") as out:
        # ─────────────────────────────────────────────────────────────────────
        # PHẦN 1: HEADER TỔNG QUAN
        # ─────────────────────────────────────────────────────────────────────
        out.write("# 🌾 RICE VISION AI — TOÀN BỘ MÃ NGUỒN VÀ CẤU TRÚC HỆ THỐNG\n\n")
        out.write(f"> **Thời gian xuất**: `{timestamp_str}`  \n")
        out.write(f"> **Thư mục gốc**: `{root_dir.resolve()}`  \n")
        out.write(f"> **Tổng số tệp mã nguồn đưa vào**: `{len(text_files) + len(notebook_files)}` tệp  \n")
        out.write(f"> **Tổng số tệp nhị phân / mô hình / ảnh**: `{len(binary_files)}` tệp  \n\n")

        out.write("## 📌 MÔ TẢ TỔNG QUAN HỆ THỐNG\n")
        out.write("Hệ thống **Rice Vision AI** là giải pháp thị giác máy tính và học máy kết hợp đo đạc 3D để ước lượng số lượng hạt lúa trong vật chứa hình trụ:\n")
        out.write("1. **Tầng 1 (Container Detection)**: Dò miệng ly bằng hình elip, tính độ phân giải thực tế `pixels_per_mm` và thể tích khối lúa `bulk_volume_mm3`.\n")
        out.write("2. **Tầng 2 (SAHI + YOLOv8m-seg)**: Cắt lát ảnh phân giải cao (Slicing Aided Hyper Inference) và phân đoạn từng hạt lúa.\n")
        out.write("3. **Tầng 3 (Cleaner Watershed)**: Thuật toán làm sạch 2 bước (Opening, Distance Transform, Watershed) để bẻ eo và tách các hạt dính nhau.\n")
        out.write("4. **Tầng 4 (CNN DenseNet121 v3)**: Phân loại hạt nguyên vẹn vs hạt khuyết tật/vụn.\n")
        out.write("5. **Tầng 5 (3D Ellipsoid & IQR)**: Đo đạc kích thước 3D (dài, rộng, dày, thể tích) và lọc ngoại lai theo IQR.\n")
        out.write("6. **Tầng 6 & 7 (AI SOTA Extra Trees Regressor)**: Vector 31 đặc trưng kết hợp thể tích và cân nặng để dự đoán chính xác số hạt.\n\n")
        out.write("---\n\n")

        # ─────────────────────────────────────────────────────────────────────
        # PHẦN 2: CÂY CẤU TRÚC THƯ MỤC DỰ ÁN
        # ─────────────────────────────────────────────────────────────────────
        out.write("## 🌳 1. CÂY CẤU TRÚC DỰ ÁN (PROJECT DIRECTORY TREE)\n\n")
        out.write("```text\n")
        out.write(f"{root_dir.name}/\n")
        out.write("\n".join(tree_lines))
        out.write("\n```\n\n")
        out.write("---\n\n")

        # ─────────────────────────────────────────────────────────────────────
        # PHẦN 3: KHO MÔ HÌNH VÀ TỆP DỮ LIỆU NHỊ PHÂN
        # ─────────────────────────────────────────────────────────────────────
        out.write("## 📦 2. KHO MÔ HÌNH AI & TỆP DỮ LIỆU NHỊ PHÂN (ARTIFACTS MANIFEST)\n\n")
        out.write("*(Các tệp nhị phân, trọng số mô hình lớn và ảnh chụp không nhúng mã thô để tối ưu dung lượng)*\n\n")
        out.write("| STT | Đường Dẫn Tương Đối | Dung Lượng | Loại Tài Nguyên |\n")
        out.write("| :---: | :--- | :---: | :--- |\n")
        for i, (bfile, bsize, bdesc) in enumerate(binary_files[:60], 1):
            rel_path = bfile.relative_to(root_dir)
            size_fmt = f"{bsize:.1f} KB" if bsize < 1024 else f"{bsize/1024:.2f} MB"
            out.write(f"| {i} | `{rel_path}` | {size_fmt} | {bdesc} |\n")
        if len(binary_files) > 60:
            out.write(f"| ... | *(và {len(binary_files) - 60} tệp ảnh/dữ liệu khác trong `test_data/1_Raw_Images`)* | ... | ... |\n")
        out.write("\n---\n\n")

        # ─────────────────────────────────────────────────────────────────────
        # PHẦN 4: MỤC LỤC ĐIỀU HƯỚNG TẬP TIN
        # ─────────────────────────────────────────────────────────────────────
        out.write("## 📑 3. MỤC LỤC TẬP TIN MÃ NGUỒN (SOURCE CODE INDEX)\n\n")
        all_text_entries = [(f, s, "code") for f, s in text_files] + [(f, s, "notebook") for f, s in notebook_files]
        all_text_entries.sort(key=lambda x: str(x[0].relative_to(root_dir)))

        for i, (tfile, tsize, ttype) in enumerate(all_text_entries, 1):
            rel_path = tfile.relative_to(root_dir)
            anchor = str(rel_path).lower().replace("\\", "-").replace("/", "-").replace(".", "-").replace(" ", "-")
            icon = "📓" if ttype == "notebook" else "📄"
            out.write(f"{i:02d}. {icon} [{rel_path}](#file-{anchor}) `({tsize:.1f} KB)`\n")
        out.write("\n---\n\n")

        # ─────────────────────────────────────────────────────────────────────
        # PHẦN 5: NỘI DUNG CHI TIẾT TỪNG TỆP MÃ NGUỒN
        # ─────────────────────────────────────────────────────────────────────
        out.write("## 💻 4. NỘI DUNG CHI TIẾT CÁC TỆP MÃ NGUỒN\n\n")

        for idx, (tfile, tsize, ttype) in enumerate(all_text_entries, 1):
            rel_path = tfile.relative_to(root_dir)
            anchor = str(rel_path).lower().replace("\\", "-").replace("/", "-").replace(".", "-").replace(" ", "-")
            lang = "python"
            if tfile.suffix in {".json"}:
                lang = "json"
            elif tfile.suffix in {".yaml", ".yml"}:
                lang = "yaml"
            elif tfile.suffix in {".md"}:
                lang = "markdown"
            elif tfile.suffix in {".toml", ".ini", ".cfg"}:
                lang = "ini"

            out.write(f'<a id="file-{anchor}"></a>\n\n')
            out.write("=" * 80 + "\n")
            out.write(f"FILE #{idx:02d}: {rel_path}\n")
            out.write(f"ĐƯỜNG DẪN TUYỆT ĐỐI: {tfile.resolve()}\n")
            out.write(f"DUNG LƯỢNG: {tsize:.1f} KB | LOẠI: {ttype.upper()}\n")
            out.write("=" * 80 + "\n\n")

            if ttype == "notebook":
                nb_cleaned = clean_notebook_content(tfile)
                lines_count = len(nb_cleaned.splitlines())
                total_code_lines += lines_count
                out.write(f"```python\n{nb_cleaned}\n```\n\n")
            else:
                try:
                    content = tfile.read_text(encoding="utf-8", errors="replace")
                    lines_count = len(content.splitlines())
                    total_code_lines += lines_count
                    out.write(f"```{lang}\n{content}\n```\n\n")
                except Exception as e:
                    out.write(f"*(Lỗi khi đọc file {rel_path}: {e})*\n\n")

    out_size_mb = output_file.stat().st_size / (1024 * 1024)
    print("\n" + "=" * 75)
    print(f"🎉 ĐÃ HOÀN TẤT TỔNG HỢP TOÀN BỘ CODEBASE THÀNH CÔNG!")
    print("=" * 75)
    print(f"   📁 Tệp kết hợp đã lưu tại : {output_file.resolve()}")
    print(f"   📊 Dung lượng tệp Markdown: {out_size_mb:.2f} MB")
    print(f"   📄 Tổng số tệp đã gom     : {len(all_text_entries)} files")
    print(f"   💻 Tổng số dòng mã nguồn  : {total_code_lines:,} dòng")
    print("=" * 75)
    print("💡 BÂY GIỜ BẠN CÓ THỂ:")
    print("   1. Mở tệp Markdown này lên hoặc tải vào ChatGPT, Claude, Gemini Web.")
    print("   2. AI bên ngoài sẽ nắm được toàn bộ 100% ngữ cảnh, vị trí file và code dự án!")
    print("=" * 75)


def main():
    parser = argparse.ArgumentParser(description="Gom toàn bộ codebase AI_SERVICES thành 1 file duy nhất.")
    parser.add_argument("--root", type=str, default=None, help="Thư mục gốc cần quét (mặc định là thư mục chứa script)")
    parser.add_argument("--output", type=str, default=None, help="Đường dẫn tệp đầu ra (mặc định là AI_SERVICES_COMBINED_CODEBASE.md)")
    parser.add_argument("--max-size", type=int, default=1000, help="Dung lượng tối đa (KB) cho 1 file văn bản để nhúng (mặc định: 1000 KB)")

    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    root_dir = Path(args.root).resolve() if args.root else script_dir

    if args.output:
        out_file = Path(args.output).resolve()
    else:
        out_file = root_dir / "AI_SERVICES_COMBINED_CODEBASE.md"

    combine_codebase(root_dir, out_file, args.max_size)


if __name__ == "__main__":
    main()
