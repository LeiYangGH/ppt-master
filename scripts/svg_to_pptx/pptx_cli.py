"""svg_to_pptx 命令行入口。"""

from __future__ import annotations

import sys
import shutil
import argparse
from datetime import datetime
from pathlib import Path

from .pptx_dimensions import CANVAS_FORMATS, get_project_info
from .pptx_discovery import find_svg_files, find_notes_files
from .pptx_builder import create_pptx_with_native_svg
from .pptx_slide_xml import TRANSITIONS

try:
    from pptx_animations import ANIMATIONS as _ANIMATIONS
except ImportError:
    _ANIMATIONS = {}


def main() -> None:
    """CLI entry point for the SVG to PPTX conversion tool."""
    transition_choices = (
        ['none'] + (list(TRANSITIONS.keys()) if TRANSITIONS
                    else ['fade', 'push', 'wipe', 'split', 'strips', 'cover', 'random'])
    )

    animation_choices = (
        ['none'] + (list(_ANIMATIONS.keys()) if _ANIMATIONS
                    else ['fade', 'fly', 'zoom', 'appear'])
        + ['mixed', 'random']
    )

    parser = argparse.ArgumentParser(
        description='SVG 转 PPTX 工具（Office 兼容模式）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f'''
示例：
    %(prog)s examples/ppt169_demo -s final    # 默认: 主 pptx -> exports/，SVG 快照 + svg_output -> backup/<ts>/
    %(prog)s examples/ppt169_demo --only native   # 仅生成原生形状版
    %(prog)s examples/ppt169_demo --only legacy   # 仅生成 SVG 图片版
    %(prog)s examples/ppt169_demo -o out.pptx     # 指定路径（SVG 参考 -> out_svg.pptx）

    # 禁用/切换页面转场效果
    %(prog)s examples/ppt169_demo -t none
    %(prog)s examples/ppt169_demo -t push --transition-duration 1.0

SVG 源目录 (-s)：
    output   - svg_output（原始版本）
    final    - svg_final（后处理版本，推荐）
    <任意>    - 直接指定子目录名

页面转场效果 (-t/--transition)：
    {', '.join(transition_choices)}

元素入场动画 (-a/--animation，原生形状模式)：
    {', '.join(animation_choices)}
    说明：作用于顶层 <g id="..."> SVG 组，按 z 轴顺序执行。默认为
         "mixed"（自动为每个组变换效果）。启动模式由
         --animation-trigger 设置，对应 PowerPoint 的"开始"下拉框：
           on-click              每个组一次点击
           with-previous         幻灯片进入时所有组同时启动
           after-previous (默认)  幻灯片进入时级联启动；
                                 间隔 = --animation-stagger 秒
         mixed 使用精选可见效果序列；random 从同一效果池随机采样。
         使用 "-a none" 禁用。

兼容模式（默认启用）：
    - 自动生成 PNG 回退图片，SVG 作为扩展嵌入
    - 兼容所有 Office 版本（包括 Office LTSC 2021）
    - 较新 Office 显示 SVG（可编辑），较旧版本显示 PNG
    - 需要 svglib: pip install svglib reportlab
    - 使用 --no-compat 禁用（仅支持 Office 2019+）

演讲备注（默认启用）：
    - 自动从 notes/ 目录读取 Markdown 备注文件
    - 支持两种命名方式：
      1. 按文件名匹配（推荐）: 01_cover.md 对应 01_cover.svg
      2. 按序号匹配: slide01.md 对应第 1 个 SVG（向后兼容）
    - 使用 --no-notes 禁用
''',
    )

    parser.add_argument('project_path', type=str, help='项目目录路径')
    parser.add_argument('-o', '--output', type=str, default=None, help='输出文件路径')
    parser.add_argument('-s', '--source', type=str, default='output',
                        help='SVG 源: output/final 或任意子目录名（推荐: final）')
    parser.add_argument('-f', '--format', type=str,
                        choices=list(CANVAS_FORMATS.keys()), default=None,
                        help='指定画布格式')
    parser.add_argument('-q', '--quiet', action='store_true', help='安静模式')

    parser.add_argument('--no-compat', action='store_true',
                        help='禁用 Office 兼容模式（纯 SVG，需要 Office 2019+）')

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument('--only', type=str, choices=['native', 'legacy'], default=None,
                            help='仅生成一个版本: native（可编辑形状）或 legacy（SVG 图片）')
    mode_group.add_argument('--native', action='store_true', default=False,
                            help='（已弃用，现为默认）将 SVG 转为原生 DrawingML 形状')

    parser.add_argument('-t', '--transition', type=str, choices=transition_choices, default='fade',
                        help='页面转场效果（默认: fade，使用 "none" 禁用）')
    parser.add_argument('--transition-duration', type=float, default=0.4,
                        help='转场时长（秒，默认: 0.4）')
    parser.add_argument('--auto-advance', type=float, default=None,
                        help='自动翻页间隔（秒，默认: 手动翻页）')

    parser.add_argument('-a', '--animation', type=str, choices=animation_choices,
                        default='mixed',
                        help='元素入场动画（仅原生形状模式）。'
                             '选择单一效果、"mixed"（自动变换，默认）、'
                             '"random" 或 "none" 禁用。')
    parser.add_argument('--animation-duration', type=float, default=0.3,
                        help='元素入场时长（秒，默认: 0.3）')
    parser.add_argument('--animation-trigger', type=str,
                        choices=['on-click', 'with-previous', 'after-previous'],
                        default='after-previous',
                        help='元素启动模式（对应 PowerPoint "开始"下拉框）：'
                             '"on-click"（每元素一次点击），'
                             '"with-previous"（幻灯片进入时同时启动），'
                             '"after-previous"（默认，级联启动）。')
    parser.add_argument('--animation-stagger', type=float, default=0.4,
                        help='after-previous 模式下元素间延迟'
                             '（秒，默认 0.4）。其他模式忽略。')

    parser.add_argument('--no-notes', action='store_true',
                        help='禁用演讲备注嵌入（默认启用）')

    args = parser.parse_args()

    project_path = Path(args.project_path)
    if not project_path.exists():
        print(f"错误: 路径不存在: {project_path}")
        sys.exit(1)

    try:
        project_info = get_project_info(str(project_path))
        project_name = project_info.get('name', project_path.name)
        detected_format = project_info.get('format')
    except Exception:
        project_name = project_path.name
        detected_format = None

    canvas_format = args.format
    if canvas_format is None and detected_format and detected_format != 'unknown':
        canvas_format = detected_format

    svg_files, source_dir_name = find_svg_files(project_path, args.source)

    if not svg_files:
        print("错误: 未找到 SVG 文件")
        sys.exit(1)

    # Determine which versions to generate
    only_mode = args.only
    gen_native = only_mode in (None, 'native')
    gen_legacy = only_mode in (None, 'legacy')

    # --native flag (deprecated) maps to --only native
    if args.native and only_mode is None:
        gen_legacy = False

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    backup_dir: Path | None = None
    if args.output:
        output_base = Path(args.output)
        native_path = output_base
        stem = output_base.stem
        legacy_path = output_base.parent / f"{stem}_svg{output_base.suffix}"
    else:
        exports_dir = project_path / "exports"
        exports_dir.mkdir(parents=True, exist_ok=True)
        native_path = exports_dir / f"{project_name}_{timestamp}.pptx"

        backup_dir = project_path / "backup" / timestamp
        backup_dir.mkdir(parents=True, exist_ok=True)
        legacy_path = backup_dir / f"{project_name}_svg.pptx"

    native_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_path.parent.mkdir(parents=True, exist_ok=True)

    verbose = not args.quiet

    enable_notes = not args.no_notes
    notes: dict[str, str] = {}
    if enable_notes:
        notes = find_notes_files(project_path, svg_files)

    transition = args.transition if args.transition != 'none' else None
    animation = args.animation if args.animation != 'none' else None

    shared_kwargs = dict(
        svg_files=svg_files,
        canvas_format=canvas_format,
        verbose=verbose,
        transition=transition,
        transition_duration=args.transition_duration,
        auto_advance=args.auto_advance,
        use_compat_mode=not args.no_compat,
        notes=notes,
        enable_notes=enable_notes,
        animation=animation,
        animation_duration=args.animation_duration,
        animation_stagger=args.animation_stagger,
        animation_trigger=args.animation_trigger,
    )

    success = True

    # --- Native shapes version (primary) ---
    if gen_native:
        if verbose:
            print("SVG 转 PPTX 工具")
            print("=" * 50)
            print(f"  项目路径: {project_path}")
            print(f"  SVG 目录: {source_dir_name}")
            print(f"  输出文件: {native_path}")
            print()

        ok = create_pptx_with_native_svg(
            output_path=native_path,
            use_native_shapes=True,
            **shared_kwargs,
        )
        success = success and ok

    # --- SVG image reference version ---
    if gen_legacy:
        if verbose:
            if gen_native:
                print()
                print("-" * 50)
            print("SVG 转 PPTX 工具（SVG 参考）")
            print("=" * 50)
            print(f"  项目路径: {project_path}")
            print(f"  SVG 目录: {source_dir_name}")
            print(f"  输出文件: {legacy_path}")
            print()

        ok = create_pptx_with_native_svg(
            output_path=legacy_path,
            use_native_shapes=False,
            **shared_kwargs,
        )
        success = success and ok

        if ok and backup_dir is not None:
            svg_output_src = project_path / "svg_output"
            if svg_output_src.is_dir():
                svg_output_dst = backup_dir / "svg_output"
                try:
                    shutil.copytree(svg_output_src, svg_output_dst)
                    if verbose:
                        print(f"  svg_output 备份: {svg_output_dst}")
                except Exception as exc:
                    if verbose:
                        print(f"  [警告] svg_output 备份跳过: {exc}")
            elif verbose:
                print(f"  [信息] svg_output/ 未找到，跳过备份")

    sys.exit(0 if success else 1)
