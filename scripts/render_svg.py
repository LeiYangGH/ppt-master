#!/usr/bin/env python3
"""
PPT Master - SVG Preview Renderer

Renders SVG files to PNG for visual review. Designed for the Executor
visual-check loop: generate SVG → render PNG → LLM views image → fix if needed.

Renderer priority: PyMuPDF (works everywhere) > CairoSVG > svglib.

Usage:
    # Render a single SVG
    python scripts/render_svg.py workspace/svg_output/slide_01.svg

    # Render all SVGs in workspace/svg_output/
    python scripts/render_svg.py workspace

    # Custom output directory
    python scripts/render_svg.py workspace -o <output_dir>

Output:
    PNG files are written to workspace/svg_preview/ (default)
    or next to the SVG file when rendering a single file.

Notes:
    PyMuPDF renders SVG layout/text/shapes faithfully but may skip
    external <image> references and <use> icons. This is fine for the
    visual-check loop — the LLM reviews layout, spacing, text wrapping,
    and overlap, not bitmap fidelity.
"""

import argparse
import sys
from pathlib import Path

# ── Renderer detection ───────────────────────────────────────────────

_RENDERER: str | None = None

try:
    import fitz  # PyMuPDF — works on all platforms without C deps
    _RENDERER = 'pymupdf'
except ImportError:
    pass

if _RENDERER is None:
    try:
        import cairosvg  # needs Cairo C lib
        _RENDERER = 'cairosvg'
    except (ImportError, OSError):
        pass

if _RENDERER is None:
    try:
        from svglib.svglib import svg2rlg
        from reportlab.graphics import renderPM
        _RENDERER = 'svglib'
    except (ImportError, OSError):
        pass


# ── Core render function ─────────────────────────────────────────────

def _render_pymupdf(svg_path: Path, png_path: Path, dpi: int = 150) -> bool:
    """Render SVG to PNG via PyMuPDF (fitz)."""
    doc = fitz.open(str(svg_path))
    if len(doc) == 0:
        return False
    page = doc[0]
    pix = page.get_pixmap(dpi=dpi)
    pix.save(str(png_path))
    doc.close()
    return True


def _render_cairosvg(svg_path: Path, png_path: Path, width: int = 1920) -> bool:
    """Render SVG to PNG via CairoSVG."""
    cairosvg.svg2png(url=str(svg_path), write_to=str(png_path), output_width=width)
    return True


def _render_svglib(svg_path: Path, png_path: Path) -> bool:
    """Render SVG to PNG via svglib + reportlab."""
    drawing = svg2rlg(str(svg_path))
    if drawing is None:
        return False
    renderPM.drawToFile(drawing, str(png_path), fmt="PNG")
    return True


def render_file(svg_path: Path, png_path: Path, *, dpi: int = 150, verbose: bool = True) -> bool:
    """Render a single SVG to PNG. Returns True on success."""
    try:
        if _RENDERER == 'pymupdf':
            ok = _render_pymupdf(svg_path, png_path, dpi=dpi)
        elif _RENDERER == 'cairosvg':
            ok = _render_cairosvg(svg_path, png_path)
        elif _RENDERER == 'svglib':
            ok = _render_svglib(svg_path, png_path)
        else:
            ok = False

        if ok and verbose:
            print(f"  [OK] {svg_path.name} -> {png_path.name}")
        elif not ok and verbose:
            print(f"  [FAIL] {svg_path.name}: renderer returned failure")
        return ok
    except Exception as e:
        if verbose:
            print(f"  [FAIL] {svg_path.name}: {e}")
        return False


# ── Project-level rendering ──────────────────────────────────────────

def render_project(
    project_dir: Path,
    output_dir: Path | None = None,
    *,
    dpi: int = 150,
    verbose: bool = True,
) -> tuple[int, int]:
    """Render all SVGs in svg_output/ to PNG.

    Returns (success_count, fail_count).
    """
    svg_dir = project_dir / 'svg_output'
    if not svg_dir.is_dir():
        print(f"[ERROR] svg_output/ not found in {project_dir}")
        return 0, 0

    if output_dir is None:
        output_dir = project_dir / 'svg_preview'
    output_dir.mkdir(parents=True, exist_ok=True)

    svg_files = sorted(svg_dir.glob('*.svg'))
    if not svg_files:
        print(f"[ERROR] No SVG files in {svg_dir}")
        return 0, 0

    if verbose:
        print(f"[DIR] Rendering {len(svg_files)} SVG(s) -> {output_dir.name}/  (renderer: {_RENDERER})")

    ok = fail = 0
    for svg_path in svg_files:
        png_path = output_dir / (svg_path.stem + '.png')
        if render_file(svg_path, png_path, dpi=dpi, verbose=verbose):
            ok += 1
        else:
            fail += 1

    if verbose:
        print(f"\n[SUMMARY] {ok} rendered, {fail} failed")
    return ok, fail


# ── CLI ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='PPT Master - SVG Preview Renderer',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='Renderer priority: PyMuPDF > CairoSVG > svglib.',
    )
    parser.add_argument('path', type=Path, help='SVG file or project directory')
    parser.add_argument('-o', '--output', type=Path, default=None,
                        help='Output directory (default: svg_preview/ under project)')
    parser.add_argument('--dpi', type=int, default=150,
                        help='Render DPI (default: 150, PyMuPDF only)')
    args = parser.parse_args()

    if _RENDERER is None:
        print("[ERROR] No renderer available. Install one of:")
        print("  pip install PyMuPDF        # recommended, works everywhere")
        print("  pip install cairosvg       # needs Cairo C library")
        print("  pip install svglib reportlab")
        sys.exit(1)

    target = args.path

    if target.is_file() and target.suffix == '.svg':
        if args.output and args.output.is_dir():
            png_path = args.output / (target.stem + '.png')
        else:
            png_path = target.with_suffix('.png')
        success = render_file(target, png_path, dpi=args.dpi)
        sys.exit(0 if success else 1)

    elif target.is_dir():
        ok, fail = render_project(target, args.output, dpi=args.dpi)
        sys.exit(0 if fail == 0 else 1)

    else:
        print(f"[ERROR] Not found: {target}")
        sys.exit(1)


if __name__ == '__main__':
    main()
