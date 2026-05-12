#!/usr/bin/env python3
"""
SVG 预览渲染器

将 SVG 渲染为 PNG 用于视觉检查。用于 Executor 视觉检查循环：生成 SVG → 渲染 PNG → LLM 查看图片 → 修复。

渲染器优先级：PyMuPDF（通用）> CairoSVG > svglib。

用法：
    python scripts/render_svg.py

输出：
    将 workspace/svg_output/ 下的 SVG 渲染到 workspace/svg_preview/ 目录

注意：
    PyMuPDF 忠实渲染布局/文本/形状，但可能跳过外部 <image> 和 <use> 图标。
    这对视觉检查循环足够——LLM 检查布局、间距、文本换行和重叠，而非位图保真度。
"""

import sys
from pathlib import Path

# Add repo root to sys.path so imports like 'scripts.pathutil' work when script is run directly
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

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
    from scripts.pathutil import SVG_OUTPUT_DIR, WORKSPACE_DIR
    
    if _RENDERER is None:
        print("[ERROR] No renderer available. Install one of:")
        print("  pip install PyMuPDF        # recommended, works everywhere")
        print("  pip install cairosvg       # needs Cairo C library")
        print("  pip install svglib reportlab")
        sys.exit(1)

    if not SVG_OUTPUT_DIR.exists():
        print(f"[ERROR] SVG output directory not found: {SVG_OUTPUT_DIR}")
        sys.exit(1)

    output_dir = WORKSPACE_DIR / 'svg_preview'
    ok, fail = render_project(SVG_OUTPUT_DIR, output_dir, dpi=150)
    sys.exit(0 if fail == 0 else 1)


if __name__ == '__main__':
    main()
