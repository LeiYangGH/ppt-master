#!/usr/bin/env python
"""
PPT Master - SVG 后处理工具（统一入口）

将 svg_output/ 中的 SVG 文件处理后输出到 svg_final/。
默认执行所有处理步骤，也可通过参数指定单独步骤。

用法：
    # 执行所有处理步骤（推荐）
    python scripts/finalize_svg.py workspace

    # 仅执行指定步骤
    python scripts/finalize_svg.py workspace --only embed-icons fix-rounded

示例：
    python scripts/finalize_svg.py workspace
    python scripts/finalize_svg.py examples/ppt169_demo --only embed-icons

处理选项：
    repair-xml    - 使用 sloppy-xml 修复格式错误的 XML（先于其他基于 XML 的步骤）
    embed-icons   - 将 <use data-icon="..."/> 替换为实际图标 SVG
    crop-images   - 基于 preserveAspectRatio="slice" 智能裁剪图片
    fix-aspect    - 修正图片宽高比（防止 PPT 形状转换时拉伸）
    embed-images  - 将外部图片转换为 Base64 嵌入
    flatten-text  - 将 <tspan> 转为独立 <text>（用于特殊渲染器）
    fix-rounded   - 将 <rect rx="..."/> 转为 <path>（用于 PPT 形状转换）
"""

import os
import sys
import shutil
import argparse
from pathlib import Path

# Import finalize helpers from the internal package.
sys.path.insert(0, str(Path(__file__).parent))
from svg_finalize.crop_images import process_svg_images as crop_images_in_svg
from svg_finalize.embed_icons import process_svg_file as embed_icons_in_file
from svg_finalize.embed_images import embed_images_in_svg
from svg_finalize.fix_image_aspect import fix_image_aspect_in_svg

try:
    from svg_repair import repair_svg_file as _repair_svg_file
    _HAS_REPAIR = True
except ImportError:
    _HAS_REPAIR = False


def safe_print(text: str) -> None:
    """Print text while tolerating Windows terminal encoding limits."""
    try:
        print(text)
    except UnicodeEncodeError:
        replacements = {
            chr(0x23F3): "[..]",
            chr(0x2705): "[DONE]",
            chr(0x274C): "[ERROR]",
            chr(0x26A0) + chr(0xFE0F): "[WARN]",
            chr(0x1F4C1): "[DIR]",
            chr(0x1F4C4): "[FILE]",
            chr(0x1F4E6): "[OK]",
        }
        for source, target in replacements.items():
            text = text.replace(source, target)
        print(text)


def process_flatten_text(svg_file: Path, verbose: bool = False) -> bool:
    """Flatten text in a single SVG file (in-place modification)"""
    try:
        from svg_finalize.flatten_tspan import flatten_text_with_tspans
        from xml.etree import ElementTree as ET

        tree = ET.parse(str(svg_file))
        changed = flatten_text_with_tspans(tree)

        if changed:
            tree.write(str(svg_file), encoding='unicode', xml_declaration=False)
            if verbose:
                safe_print(f"   [OK] {svg_file.name}: 文本已展平")
        return changed
    except Exception as e:
        if verbose:
            safe_print(f"   [ERROR] {svg_file.name}: {e}")
        return False


def process_rounded_rect(svg_file: Path, verbose: bool = False) -> int:
    """Convert rounded rectangles in a single SVG file (in-place modification)"""
    try:
        from svg_finalize.svg_rect_to_path import process_svg

        with open(svg_file, 'r', encoding='utf-8') as f:
            content = f.read()

        processed, count = process_svg(content, verbose=False)

        if count > 0:
            with open(svg_file, 'w', encoding='utf-8') as f:
                f.write(processed)
            if verbose:
                safe_print(f"   [OK] {svg_file.name}: {count} 个圆角矩形")
        return count
    except Exception as e:
        if verbose:
            safe_print(f"   [ERROR] {svg_file.name}: {e}")
        return 0


def finalize_project(
    project_dir: Path,
    options: dict[str, bool],
    dry_run: bool = False,
    quiet: bool = False,
    compress: bool = False,
    max_dimension: int | None = None,
) -> bool:
    """
    Finalize SVG files in the project

    Args:
        project_dir: Project directory path
        options: Processing options dictionary
        dry_run: Preview only, do not execute
        quiet: Quiet mode, reduce output
        compress: Compress images before embedding
        max_dimension: Downscale images exceeding this dimension
    """
    svg_output = project_dir / 'svg_output'
    svg_final = project_dir / 'svg_final'
    icons_dir = Path(__file__).parent.parent / 'templates' / 'icons'

    # Check if svg_output exists
    if not svg_output.exists():
        safe_print(f"[ERROR] svg_output 目录未找到: {svg_output}")
        return False

    # Get list of SVG files
    svg_files = list(svg_output.glob('*.svg'))
    if not svg_files:
        safe_print(f"[ERROR] svg_output 中无 SVG 文件")
        return False

    if not quiet:
        print()
        safe_print(f"[DIR] 项目: {project_dir.name}")
        safe_print(f"[FILE] {len(svg_files)} 个 SVG 文件")

    if dry_run:
        safe_print("[预览] 预览模式，不执行任何操作")
        return True

    # Step 1: Copy directory
    if svg_final.exists():
        shutil.rmtree(svg_final)
    shutil.copytree(svg_output, svg_final)

    if not quiet:
        print()

    # Step 0: Repair malformed XML (must run before any XML-based step)
    if options.get('repair_xml'):
        if not quiet:
            safe_print("[0/6] 修复格式错误的 XML...")
        if not _HAS_REPAIR:
            if not quiet:
                safe_print("      [跳过] 未安装 sloppy-xml（可 pip install sloppy-xml 启用）")
        else:
            repair_count = 0
            for svg_file in svg_final.glob('*.svg'):
                report = _repair_svg_file(svg_file, dry_run=dry_run, verbose=False)
                if report.repaired:
                    repair_count += 1
                    if not quiet:
                        safe_print(f"      [已修复] {svg_file.name}: {report.summary_line}")
            if not quiet:
                if repair_count > 0:
                    safe_print(f"      共修复 {repair_count} 个文件")
                else:
                    safe_print("      无需修复")

    # Step 2: Embed icons
    if options.get('embed_icons'):
        if not quiet:
            safe_print("[1/6] 嵌入图标...")
        icons_count = 0
        for svg_file in svg_final.glob('*.svg'):
            count = embed_icons_in_file(svg_file, icons_dir, dry_run=False, verbose=False)
            icons_count += count
        if not quiet:
            if icons_count > 0:
                safe_print(f"      已嵌入 {icons_count} 个图标")
            else:
                safe_print("      无图标")

    # Step 3: Smart crop images (based on preserveAspectRatio="slice")
    if options.get('crop_images'):
        if not quiet:
            safe_print("[2/6] 智能裁剪图片...")
        crop_count = 0
        crop_errors = 0
        for svg_file in svg_final.glob('*.svg'):
            count, errors = crop_images_in_svg(str(svg_file), dry_run=False, verbose=False)
            crop_count += count
            crop_errors += errors
        if not quiet:
            if crop_count > 0:
                safe_print(f"      已裁剪 {crop_count} 张图片")
            else:
                safe_print("      无需裁剪（无 slice 属性图片）")

    # Step 4: Fix image aspect ratio (prevent stretching during PPT shape conversion)
    if options.get('fix_aspect'):
        if not quiet:
            safe_print("[3/6] 修正图片宽高比...")
        aspect_count = 0
        for svg_file in svg_final.glob('*.svg'):
            count = fix_image_aspect_in_svg(str(svg_file), dry_run=False, verbose=False)
            aspect_count += count
        if not quiet:
            if aspect_count > 0:
                safe_print(f"      已修正 {aspect_count} 张图片")
            else:
                safe_print("      无图片")

    # Step 5: Embed images
    if options.get('embed_images'):
        if not quiet:
            safe_print("[4/6] 嵌入图片...")
        images_count = 0
        for svg_file in svg_final.glob('*.svg'):
            count, _ = embed_images_in_svg(str(svg_file), dry_run=False,
                                           compress=compress,
                                           max_dimension=max_dimension)
            images_count += count
        if not quiet:
            if images_count > 0:
                safe_print(f"      已嵌入 {images_count} 张图片")
            else:
                safe_print("      无图片")

    # Step 6: Flatten text
    if options.get('flatten_text'):
        if not quiet:
            safe_print("[5/6] 展平文本...")
        flatten_count = 0
        for svg_file in svg_final.glob('*.svg'):
            if process_flatten_text(svg_file, verbose=False):
                flatten_count += 1
        if not quiet:
            if flatten_count > 0:
                safe_print(f"      已处理 {flatten_count} 个文件")
            else:
                safe_print("      无需处理")

    # Step 7: Convert rounded rects to Path
    if options.get('fix_rounded'):
        if not quiet:
            safe_print("[6/6] 将圆角矩形转为 Path...")
        rounded_count = 0
        for svg_file in svg_final.glob('*.svg'):
            count = process_rounded_rect(svg_file, verbose=False)
            rounded_count += count
        if not quiet:
            if rounded_count > 0:
                safe_print(f"      已转换 {rounded_count} 个圆角矩形")
            else:
                safe_print("      无圆角矩形")

    # Done
    if not quiet:
        print()
        safe_print("[OK] 完成！")
        print()
        print("下一步:")
        print(f"  python scripts/svg_to_pptx.py \"{project_dir}\" -s final")

    return True


def main() -> None:
    """Run the CLI entry point."""
    parser = argparse.ArgumentParser(
        description='PPT Master - SVG 后处理工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例：
  %(prog)s workspace                        # 执行所有处理（默认）
  %(prog)s workspace --only embed-icons fix-rounded
  %(prog)s workspace -q                     # 安静模式

处理选项（用于 --only）：
  repair-xml    修复格式错误的 XML（sloppy-xml）
  embed-icons   嵌入图标
  crop-images   智能裁剪图片（基于 preserveAspectRatio）
  fix-aspect    修正图片宽高比（防止 PPT 形状转换时拉伸）
  embed-images  嵌入图片
  flatten-text  展平文本
  fix-rounded   将圆角矩形转为 Path
        '''
    )

    parser.add_argument('project_dir', type=Path, help='项目目录路径')
    parser.add_argument('--only', nargs='+', metavar='OPTION',
                        choices=['repair-xml', 'embed-icons', 'crop-images', 'fix-aspect', 'embed-images', 'flatten-text', 'fix-rounded'],
                        help='仅执行指定处理步骤（默认: 全部）')
    parser.add_argument('--dry-run', '-n', action='store_true',
                        help='仅预览，不执行')
    parser.add_argument('--quiet', '-q', action='store_true',
                        help='安静模式，减少输出')
    parser.add_argument('--compress', action='store_true',
                        help='嵌入前压缩图片（JPEG quality=85，PNG 优化）')
    parser.add_argument('--max-dimension', type=int, default=None,
                        help='缩放超过此尺寸的图片（如 2560）')

    args = parser.parse_args()

    if not args.project_dir.exists():
        safe_print(f"[ERROR] 项目目录不存在: {args.project_dir}")
        sys.exit(1)

    # Determine processing options
    if args.only:
        # Execute only specified steps
        options = {
            'repair_xml': 'repair-xml' in args.only,
            'embed_icons': 'embed-icons' in args.only,
            'crop_images': 'crop-images' in args.only,
            'fix_aspect': 'fix-aspect' in args.only,
            'embed_images': 'embed-images' in args.only,
            'flatten_text': 'flatten-text' in args.only,
            'fix_rounded': 'fix-rounded' in args.only,
        }
    else:
        # Execute all by default
        options = {
            'repair_xml': True,
            'embed_icons': True,
            'crop_images': True,
            'fix_aspect': True,
            'embed_images': True,
            'flatten_text': True,
            'fix_rounded': True,
        }

    success = finalize_project(args.project_dir, options, args.dry_run, args.quiet,
                               compress=args.compress,
                               max_dimension=args.max_dimension)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
