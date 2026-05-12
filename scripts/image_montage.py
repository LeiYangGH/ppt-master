#!/usr/bin/env python3
"""Build contact-sheet montages from a directory of images.

LLM-oriented batch triage: instead of opening each of the N freshly
downloaded search images and judging them one by one, tile them into
M = ceil(N / 20) montage images (``montage_01_of_M.jpg`` ...), each
containing up to 20 thumbnails with the original filename stamped under
every cell.  The LLM then only needs to vision-read M montages to
produce a keep/rename/delete decision for every source image.

用法：
    python scripts/image_montage.py

LLM usage notes
---------------
  * One montage \u2248 20 images, laid out 4 columns \u00d7 5 rows.
  * Each cell's original filename is rendered at the bottom in a
    dark-band label; truncated from the middle with an ellipsis when
    it is too long to fit the cell width.
  * Output lands in ``<images_dir>/_montage/``.  That subdirectory is
    always ignored on subsequent runs so re-running the script never
    folds old montages back in.
  * ``montage_manifest.json`` next to the montages records the exact
    mapping from montage -> list of cell filenames, so the LLM can
    reference filenames directly when instructing the user (or the
    follow-up pipeline step) to delete / rename specific images.
"""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError

# --- Path bootstrap: allow reusing web_search's project resolver --------
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from web_search import resolve_project_images_dir  # type: ignore
except Exception:  # pragma: no cover - defensive fallback
    def resolve_project_images_dir(hint: Optional[str] = None) -> Optional[Path]:
        if hint:
            p = Path(hint)
            if p.name != "images":
                p = p / "images"
            return p
        env = os.environ.get("PPT_PROJECT_DIR") or os.environ.get("PPT_CURRENT_PROJECT")
        if env:
            p = Path(env)
            if p.name != "images":
                p = p / "images"
            return p
        return None


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}

# Grid & cell geometry tuned so the whole montage stays <= 1440 on its
# long side (comfortable for current-generation vision models) while
# each thumbnail is still large enough to judge subject matter.
_DEFAULT_COLS         = 4
_DEFAULT_ROWS         = 5     # -> 20 cells per montage
_DEFAULT_CELL_W       = 320
_DEFAULT_CELL_H       = 240
_DEFAULT_LABEL_H      = 44
_DEFAULT_MARGIN       = 8
_DEFAULT_GUTTER       = 4
_DEFAULT_QUALITY      = 85
_DEFAULT_OUTPUT_NAME  = "_montage"
_DEFAULT_FORMAT       = "jpg"

_BG_COLOR      = (28, 28, 32)      # overall background
_CELL_BG       = (48, 48, 52)      # cell padding area (visible when thumb doesn't fill)
_LABEL_BG      = (16, 16, 18)      # label strip
_LABEL_FG      = (230, 230, 230)   # label text
_INDEX_BG      = (228, 168, 48)    # small corner badge with cell index
_INDEX_FG      = (20, 20, 20)

# Font search order (Win -> Linux -> macOS); first existing file wins.
_FONT_CANDIDATES = [
    # Windows
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\simsun.ttc",
    # Linux
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    # macOS
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_font(size: int, override: Optional[str] = None) -> ImageFont.ImageFont:
    candidates = [override] if override else []
    candidates.extend(_FONT_CANDIDATES)
    for path in candidates:
        if not path:
            continue
        try:
            return ImageFont.truetype(path, size=size)
        except (OSError, ValueError):
            continue
    print("  [montage] warn: no CJK font found; non-ASCII filenames may show as boxes",
          file=sys.stderr)
    return ImageFont.load_default()


def _text_width(draw: ImageDraw.ImageDraw, text: str,
                font: ImageFont.ImageFont) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def _truncate_middle(draw: ImageDraw.ImageDraw, text: str,
                     font: ImageFont.ImageFont, max_width: int) -> str:
    """Shrink *text* to fit *max_width* by eating the middle."""
    if _text_width(draw, text, font) <= max_width:
        return text
    ellipsis = "\u2026"  # single-char ellipsis
    # Binary-ish shrink: keep head=4, eat from the tail first (last part of a
    # hashed filename is usually the discriminator and suffix).
    for keep_tail in range(len(text) - 1, 4, -1):
        candidate = text[:6] + ellipsis + text[-keep_tail:]
        if _text_width(draw, candidate, font) <= max_width:
            return candidate
    # Fallback: hard-truncate
    out = text
    while out and _text_width(draw, out + ellipsis, font) > max_width:
        out = out[:-1]
    return out + ellipsis


def _collect_images(root: Path, output_dir: Path, recursive: bool) -> list[Path]:
    """Enumerate images under *root*, skipping the montage output directory."""
    iterator = root.rglob("*") if recursive else root.iterdir()
    found: list[Path] = []
    out_resolved = output_dir.resolve()
    for p in iterator:
        if not p.is_file():
            continue
        if p.suffix.lower() not in _IMAGE_EXTENSIONS:
            continue
        # Skip anything inside the output directory (even if recursive)
        try:
            p.resolve().relative_to(out_resolved)
            continue  # p is inside output_dir -> skip
        except ValueError:
            pass
        # Skip Pillow's default `.part`-like artefacts just in case
        if p.name.endswith(".part"):
            continue
        found.append(p)
    found.sort(key=lambda q: q.name.lower())
    return found


def _thumb_for_cell(src: Path, target_w: int, target_h: int) -> Image.Image:
    """Return a ``target_w`` x ``target_h`` RGB image with *src* centred inside,
    preserving aspect ratio (letterbox on the shorter axis)."""
    cell = Image.new("RGB", (target_w, target_h), _CELL_BG)
    try:
        with Image.open(src) as im:
            im = im.convert("RGB")
            im.thumbnail((target_w, target_h), Image.LANCZOS)
            ox = (target_w - im.width) // 2
            oy = (target_h - im.height) // 2
            cell.paste(im, (ox, oy))
    except (OSError, UnidentifiedImageError, ValueError) as exc:
        # Render an error placeholder so the cell still carries the filename
        draw = ImageDraw.Draw(cell)
        msg = f"[broken]\n{type(exc).__name__}"
        font = _load_font(14)
        draw.multiline_text((8, 8), msg, fill=(255, 120, 120), font=font)
    return cell


def _render_cell(src: Path, global_index: int,
                 cell_w: int, cell_h: int, label_h: int,
                 label_font: ImageFont.ImageFont,
                 index_font: ImageFont.ImageFont) -> Image.Image:
    """Render a single cell = thumbnail + bottom label strip + index badge."""
    total_h = cell_h + label_h
    cell = Image.new("RGB", (cell_w, total_h), _LABEL_BG)

    # Thumbnail area
    thumb = _thumb_for_cell(src, cell_w, cell_h)
    cell.paste(thumb, (0, 0))

    draw = ImageDraw.Draw(cell)

    # Small corner badge with 1-based cell index (matches manifest order)
    badge_text = str(global_index)
    bw = _text_width(draw, badge_text, index_font) + 10
    bh = 20
    draw.rectangle([(0, 0), (bw, bh)], fill=_INDEX_BG)
    draw.text((5, 1), badge_text, fill=_INDEX_FG, font=index_font)

    # Filename label
    label_top = cell_h
    draw.rectangle([(0, label_top), (cell_w, total_h)], fill=_LABEL_BG)
    label_text = _truncate_middle(draw, src.name, label_font, max_width=cell_w - 10)
    tw = _text_width(draw, label_text, label_font)
    tx = (cell_w - tw) // 2
    ty = label_top + (label_h - _text_height(draw, label_text, label_font)) // 2
    draw.text((tx, ty), label_text, fill=_LABEL_FG, font=label_font)
    return cell


def _text_height(draw: ImageDraw.ImageDraw, text: str,
                 font: ImageFont.ImageFont) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[3] - bbox[1]


def _compose_montage(cells: list[Image.Image], cols: int, rows: int,
                     cell_w: int, cell_h: int, label_h: int,
                     margin: int, gutter: int,
                     header: str,
                     header_font: ImageFont.ImageFont) -> Image.Image:
    """Arrange up to cols*rows *cells* into a single montage image."""
    header_h = 32 if header else 0
    inner_w = cols * cell_w + (cols - 1) * gutter
    inner_h = rows * (cell_h + label_h) + (rows - 1) * gutter
    total_w = inner_w + 2 * margin
    total_h = inner_h + 2 * margin + header_h

    canvas = Image.new("RGB", (total_w, total_h), _BG_COLOR)
    draw = ImageDraw.Draw(canvas)

    if header:
        draw.text((margin + 2, margin + 4), header,
                  fill=(240, 240, 240), font=header_font)

    origin_y = margin + header_h
    for idx, cell in enumerate(cells):
        r, c = divmod(idx, cols)
        x = margin + c * (cell_w + gutter)
        y = origin_y + r * (cell_h + label_h + gutter)
        canvas.paste(cell, (x, y))

    return canvas


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------

def build_montages(
    images_dir: Path,
    *,
    output_dir: Optional[Path] = None,
    cols: int = _DEFAULT_COLS,
    rows: int = _DEFAULT_ROWS,
    cell_w: int = _DEFAULT_CELL_W,
    cell_h: int = _DEFAULT_CELL_H,
    label_h: int = _DEFAULT_LABEL_H,
    margin: int = _DEFAULT_MARGIN,
    gutter: int = _DEFAULT_GUTTER,
    quality: int = _DEFAULT_QUALITY,
    fmt: str = _DEFAULT_FORMAT,
    recursive: bool = False,
    font_override: Optional[str] = None,
) -> dict:
    """Produce one or more montage images covering every image in *images_dir*."""
    if not images_dir.exists() or not images_dir.is_dir():
        raise FileNotFoundError(f"images directory not found: {images_dir}")

    output_dir = output_dir or (images_dir / _DEFAULT_OUTPUT_NAME)
    output_dir.mkdir(parents=True, exist_ok=True)

    images = _collect_images(images_dir, output_dir, recursive)
    if not images:
        return {
            "images_dir":     str(images_dir),
            "output_dir":     str(output_dir),
            "total_images":   0,
            "total_montages": 0,
            "montages":       [],
        }

    per_montage = cols * rows
    total_montages = math.ceil(len(images) / per_montage)

    label_font  = _load_font(15, font_override)
    index_font  = _load_font(14, font_override)
    header_font = _load_font(16, font_override)

    ext = fmt.lower().lstrip(".")
    if ext not in ("jpg", "jpeg", "png"):
        raise ValueError(f"unsupported format: {fmt}")
    if ext == "jpeg":
        ext = "jpg"

    manifest_entries: list[dict] = []
    pad = len(str(total_montages))

    for bi in range(total_montages):
        batch = images[bi * per_montage:(bi + 1) * per_montage]
        cells = []
        for local_i, src in enumerate(batch):
            global_index = bi * per_montage + local_i + 1
            cells.append(_render_cell(src, global_index,
                                      cell_w, cell_h, label_h,
                                      label_font, index_font))

        header = (f"montage {bi + 1}/{total_montages}   "
                  f"cells {bi * per_montage + 1}\u2013"
                  f"{bi * per_montage + len(batch)} of {len(images)}   "
                  f"({images_dir.name})")
        page = _compose_montage(cells, cols, rows,
                                cell_w, cell_h, label_h,
                                margin, gutter, header, header_font)

        fname = f"montage_{bi + 1:0{pad}d}_of_{total_montages:0{pad}d}.{ext}"
        out_path = output_dir / fname
        save_kwargs: dict = {}
        if ext == "jpg":
            save_kwargs.update(format="JPEG", quality=quality, optimize=True)
        else:
            save_kwargs.update(format="PNG", optimize=True)
        page.save(out_path, **save_kwargs)

        manifest_entries.append({
            "file":   fname,
            "path":   str(out_path),
            "start":  bi * per_montage + 1,
            "count":  len(batch),
            "cells":  [p.name for p in batch],
        })

    manifest = {
        "images_dir":       str(images_dir),
        "output_dir":       str(output_dir),
        "total_images":     len(images),
        "total_montages":   total_montages,
        "cells_per_montage": per_montage,
        "grid":             {"cols": cols, "rows": rows,
                             "cell": [cell_w, cell_h], "label_h": label_h},
        "montages":         manifest_entries,
    }

    (output_dir / "montage_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[list[str]] = None) -> int:
    from scripts.pathutil import IMAGES_DIR
    
    images_dir = IMAGES_DIR
    if not images_dir.exists():
        print(f"error: images directory does not exist: {images_dir}", file=sys.stderr)
        return 2

    # Use default parameters
    output_dir = None
    cols = 4
    rows = 5
    cell_w = None
    cell_h = None
    label_h = None
    quality = 85
    fmt = 'jpg'
    recursive = False
    font_override = None
    json_output = False

    manifest = build_montages(
        images_dir,
        output_dir=output_dir,
        cols=cols,
        rows=rows,
        cell_w=cell_w,
        cell_h=cell_h,
        label_h=label_h,
        quality=quality,
        fmt=fmt,
        recursive=recursive,
        font_override=font_override,
    )

    if json_output:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0

    # Human summary
    print(f"  images_dir     : {manifest['images_dir']}")
    print(f"  output_dir     : {manifest['output_dir']}")
    print(f"  total images   : {manifest['total_images']}")
    print(f"  total montages : {manifest['total_montages']}  "
          f"({manifest.get('cells_per_montage', 0)} per montage)")
    for m in manifest["montages"]:
        print(f"   - {m['file']}  ({m['count']} cells: "
              f"#{m['start']}..#{m['start'] + m['count'] - 1})")
    if manifest["total_montages"]:
        print(f"  manifest JSON  : "
              f"{Path(manifest['output_dir']) / 'montage_manifest.json'}")
    return 0 if manifest["total_images"] > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
