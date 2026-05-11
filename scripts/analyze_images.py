#!/usr/bin/env python
"""
图片尺寸分析工具
================
报告文件夹中所有图片的客观参数（宽、高、宽高比、类别）。
本工具不预设布局——叙事意图（hero / atmosphere / side-by-side / accent）由 Strategist
根据 references/strategist.md §h 决定；本工具仅提供数值。

指定画布时，还会报告若图片与正文并排放置时的参考图片/文本区域尺寸。
这些数值仅在 Strategist 选择 side-by-side 意图时适用。

用法：
    python scripts/analyze_images.py

输出：
    - 控制台显示分析报告
    - 在图片目录的父目录生成 image_analysis.csv
"""

import os
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("错误: 未安装 PIL/Pillow，请运行: pip install Pillow")
    sys.exit(1)

try:
    from config import CANVAS_FORMATS, LAYOUT_MARGINS
except ImportError:
    CANVAS_FORMATS = {
        'ppt169': {
            'name': 'PPT 16:9',
            'width': 1280,
            'height': 720,
        },
    }
    LAYOUT_MARGINS = {
        'ppt169': {
            'top': 60, 'right': 60, 'bottom': 60, 'left': 60,
            'content_width': 1160, 'content_height': 600
        },
    }

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".tif"}
REPORT_WIDTH = 100
CATEGORY_WIDTH = 50

# Title area height and gap between image/text areas (px)
TITLE_HEIGHT = 60
LAYOUT_GAP = 20
# Minimum text area dimensions (px)
MIN_TEXT_HEIGHT = 150
MIN_TEXT_WIDTH = 280

ImageAnalysis = dict[str, str | float | int]


def classify_ratio(aspect_ratio: float) -> str:
    """Classify image aspect ratio into layout category.

    Thresholds aligned with image-layout-spec.md:
      >2.0 ultra-wide, 1.5-2.0 wide, 1.2-1.5 standard landscape,
      0.8-1.2 square, <0.8 portrait.
    """
    if aspect_ratio > 2.0:
        return "超宽幅"
    elif aspect_ratio > 1.5:
        return "宽幅横版"
    elif aspect_ratio > 1.2:
        return "标准横版"
    elif aspect_ratio > 0.8:
        return "近正方形"
    else:
        return "竖版"


def compute_layout_dimensions(
    ratio: float,
    content_w: int,
    content_h: int,
    gap: int = LAYOUT_GAP,
) -> dict:
    """Compute image and text area dimensions following image-layout-spec.md.

    Returns dict with layout_type, image_w, image_h, text_w, text_h.
    """
    # Effective content height (below title)
    H = content_h
    W = content_w

    def _try_top_bottom() -> dict | None:
        img_w = W
        img_h = int(round(W / ratio))
        text_h = H - img_h - gap
        if text_h >= MIN_TEXT_HEIGHT:
            return {
                'layout_type': 'top-bottom',
                'image_w': img_w,
                'image_h': img_h,
                'text_w': W,
                'text_h': text_h,
            }
        return None

    def _try_left_right_height_first() -> dict | None:
        img_h = H
        img_w = int(round(H * ratio))
        text_w = W - img_w - gap
        if text_w >= MIN_TEXT_WIDTH:
            return {
                'layout_type': 'left-right',
                'image_w': img_w,
                'image_h': img_h,
                'text_w': text_w,
                'text_h': H,
            }
        return None

    def _try_left_right_width_constrained() -> dict:
        img_w = int(round(W * 0.7))
        img_h = int(round(img_w / ratio))
        text_w = W - img_w - gap
        return {
            'layout_type': 'left-right',
            'image_w': img_w,
            'image_h': min(img_h, H),
            'text_w': max(text_w, MIN_TEXT_WIDTH),
            'text_h': H,
        }

    # Decision tree per image-layout-spec.md
    if ratio > 1.5:
        # Ultra-wide or wide → try top-bottom first
        result = _try_top_bottom()
        if result:
            return result
        # Fallback to left-right (wide-constrained)
        return _try_left_right_width_constrained()
    else:
        # Standard landscape, square, portrait → try left-right (height-first)
        result = _try_left_right_height_first()
        if result:
            return result
        # Fallback to left-right (width-constrained)
        return _try_left_right_width_constrained()


def analyze_images(images_dir: str) -> list[ImageAnalysis]:
    """Analyze all image files in a directory.

    Args:
        images_dir: Directory that contains image files.

    Returns:
        A list of image analysis records sorted by filename.
    """

    results: list[ImageAnalysis] = []

    # Iterate through all files in the directory
    for filename in sorted(os.listdir(images_dir)):
        filepath = os.path.join(images_dir, filename)

        # Check if it is an image file
        if os.path.isfile(filepath) and Path(filename).suffix.lower() in IMAGE_EXTENSIONS:
            try:
                with Image.open(filepath) as img:
                    width, height = img.size
                    aspect_ratio = width / height
                    layout_hint = classify_ratio(aspect_ratio)

                    results.append({
                        'filename': filename,
                        'width': width,
                        'height': height,
                        'aspect_ratio': aspect_ratio,
                        'layout_hint': layout_hint,
                        'filesize_kb': os.path.getsize(filepath) / 1024
                    })
            except Exception as e:
                print(f"[WARN] 无法读取 {filename}: {e}")

    return results


def enrich_with_layout(
    results: list[ImageAnalysis],
    canvas_key: str,
) -> None:
    """Add computed layout dimensions to each result in-place."""
    fmt = CANVAS_FORMATS.get(canvas_key, {})
    margins = LAYOUT_MARGINS.get(canvas_key)

    if not margins:
        print(f"[WARN] 画布 '{canvas_key}' 无布局边距，跳过尺寸计算")
        return

    content_w = margins['content_width']
    content_h = margins['content_height']

    for img in results:
        dims = compute_layout_dimensions(img['aspect_ratio'], content_w, content_h)
        img.update(dims)


def print_results(results: list[ImageAnalysis]) -> None:
    """Print the analysis report to stdout."""

    print("\n" + "=" * REPORT_WIDTH)
    print("图片尺寸分析报告")
    print("=" * REPORT_WIDTH)

    has_layout = 'layout_type' in results[0] if results else False

    if has_layout:
        print("\n注意: '图片(并排)' 仅在 Strategist 为该图选择 side-by-side 意图时适用。")
        print("请先决定叙事意图——见 references/strategist.md §h。Hero / atmosphere / accent 意图忽略此列。\n")
        print(f"{'序号':<4} {'宽度':<7} {'高度':<7} {'宽高比':<7} {'大小':<10} {'类别':<16} {'图片(并排)':<14} {'文件名'}")
    else:
        print(f"\n{'序号':<4} {'宽度':<7} {'高度':<7} {'宽高比':<7} {'大小':<10} {'类别':<16} {'文件名'}")
    print("-" * REPORT_WIDTH)

    for i, img in enumerate(results, 1):
        base = f"{i:<4} {img['width']:<7} {img['height']:<7} {img['aspect_ratio']:<7.2f} {img['filesize_kb']:<10.1f}KB {img['layout_hint']:<20}"
        if has_layout:
            img_area = f"{img['image_w']}x{img['image_h']}"
            print(f"{base} {img_area:<14} {img['filename'][:35]}")
        else:
            print(f"{base} {img['filename'][:40]}")

    print("-" * REPORT_WIDTH)
    print(f"合计: {len(results)} 张图片\n")

    # Group statistics by aspect ratio (aligned with image-layout-spec.md thresholds)
    print("\n按宽高比分组:")
    print("-" * CATEGORY_WIDTH)

    categories = {
        "超宽幅 (>2.0)": [],
        "宽幅 (1.5-2.0)": [],
        "标准横版 (1.2-1.5)": [],
        "正方形 (0.8-1.2)": [],
        "竖版 (<0.8)": [],
    }

    for img in results:
        ar = img['aspect_ratio']
        if ar > 2.0:
            categories["超宽幅 (>2.0)"].append(img)
        elif ar > 1.5:
            categories["宽幅 (1.5-2.0)"].append(img)
        elif ar > 1.2:
            categories["标准横版 (1.2-1.5)"].append(img)
        elif ar > 0.8:
            categories["正方形 (0.8-1.2)"].append(img)
        else:
            categories["竖版 (<0.8)"].append(img)

    for cat, imgs in categories.items():
        if imgs:
            print(f"\n{cat}: {len(imgs)} 张")
            for img in imgs[:5]:  # Show only the first 5
                print(f"  - {img['width']}x{img['height']} (宽高比 {img['aspect_ratio']:.2f}) - {img['filename'][:35]}...")
            if len(imgs) > 5:
                print(f"  ... 等 {len(imgs) - 5} 张更多")


def generate_markdown(results: list[ImageAnalysis], canvas_key: str) -> None:
    """Print a Markdown-ready image inventory section."""
    print("\n" + "=" * REPORT_WIDTH)
    print("Markdown 代码片段（供 Strategist 复制粘贴）")
    print("=" * REPORT_WIDTH)

    has_layout = 'layout_type' in results[0] if results else False
    fmt_name = CANVAS_FORMATS.get(canvas_key, {}).get('name', canvas_key)

    print(f"\n## 图片资源清单（自动扫描结果 — {fmt_name}）\n")

    print("> 请先根据 `references/strategist.md` §h 为每张图决定叙事意图（hero / atmosphere /")
    print("> side-by-side / accent），再填写下表。`图片区域(并排)` / `文本区域(并排)` 列")
    print("> 仅在 side-by-side 意图时适用；hero / atmosphere / accent 意图请忽略。\n")

    if has_layout:
        print("| 文件名 | 尺寸 | 宽高比 | 类别 | 图片区域(并排) | 文本区域(并排) | 意图 | 用途 | 类型 |")
        print("|----------|------|-------|----------|----------------|-----------------|--------|-------|------|")
    else:
        print("| 文件名 | 尺寸 | 宽高比 | 类别 | 意图 | 用途 | 类型 |")
        print("|----------|------|-------|----------|--------|-------|------|")

    for img in results:
        ratio_str = f"{img['aspect_ratio']:.2f}"

        if has_layout:
            img_area = f"{img['image_w']}x{img['image_h']}"
            text_area = f"{img['text_w']}x{img['text_h']}"
            print(f"| {img['filename']} | {img['width']}x{img['height']} | {ratio_str} | {img['layout_hint']} | {img_area} | {text_area} | (待填写) | (待填写) | |")
        else:
            print(f"| {img['filename']} | {img['width']}x{img['height']} | {ratio_str} | {img['layout_hint']} | (待填写) | (待填写) | |")

    print("\n" + "=" * REPORT_WIDTH + "\n")


def save_csv(results: list[ImageAnalysis], csv_path: str) -> None:
    """Save analysis results to a CSV file."""
    has_layout = 'layout_type' in results[0] if results else False

    # NOTE: ImageArea_SxS / TextArea_SxS apply only if Strategist picks the
    # side-by-side intent for this image (see strategist.md §h). The tool
    # does not prescribe a layout.
    with open(csv_path, 'w', encoding='utf-8') as f:
        if has_layout:
            f.write("No,Filename,Width,Height,AspectRatio,SizeKB,Category,ImageArea_SxS,TextArea_SxS\n")
            for i, img in enumerate(results, 1):
                f.write(f"{i},{img['filename']},{img['width']},{img['height']},{img['aspect_ratio']:.2f},{img['filesize_kb']:.1f},{img['layout_hint']},{img['image_w']}x{img['image_h']},{img['text_w']}x{img['text_h']}\n")
        else:
            f.write("No,Filename,Width,Height,AspectRatio,SizeKB,Category\n")
            for i, img in enumerate(results, 1):
                f.write(f"{i},{img['filename']},{img['width']},{img['height']},{img['aspect_ratio']:.2f},{img['filesize_kb']:.1f},{img['layout_hint']}\n")
    print(f"\nCSV 已保存: {csv_path}")


def main() -> None:
    """Run the CLI entry point."""
    from scripts.pathutil import IMAGES_DIR
    
    images_dir = str(IMAGES_DIR)
    canvas_key = "ppt169"
    
    if not os.path.exists(images_dir):
        print(f"错误: 目录未找到: {images_dir}")
        sys.exit(1)

    if not os.path.isdir(images_dir):
        print(f"错误: 不是目录: {images_dir}")
        sys.exit(1)

    if canvas_key not in CANVAS_FORMATS:
        print(f"错误: 未知画布格式 '{canvas_key}'。可用: {', '.join(sorted(CANVAS_FORMATS.keys()))}")
        sys.exit(1)

    fmt = CANVAS_FORMATS[canvas_key]
    print(f"正在分析: {images_dir}")
    print(f"画布: {fmt.get('name', canvas_key)} ({fmt.get('width', '?')}x{fmt.get('height', '?')})")

    results = analyze_images(images_dir)

    if results:
        enrich_with_layout(results, canvas_key)
        print_results(results)
        generate_markdown(results, canvas_key)

        # Save to CSV file (saved in the parent directory of the images folder)
        parent_dir = os.path.dirname(images_dir)
        csv_path = os.path.join(parent_dir, "image_analysis.csv")
        save_csv(results, csv_path)
    else:
        print("目录中未找到图片文件。")


if __name__ == "__main__":
    main()
