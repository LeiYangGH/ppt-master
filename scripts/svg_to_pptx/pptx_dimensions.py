"""Slide dimensions, format detection, EMU conversion, and constants."""

from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

# Import project utility modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    from config import CANVAS_FORMATS
except ImportError:
    CANVAS_FORMATS = {
        'ppt169': {'name': 'PPT 16:9', 'dimensions': '1280×720', 'viewbox': '0 0 1280 720'},
    }


# ── Project info helpers (migrated from project_utils.py) ─────────

def _normalize_canvas_format(format_key: str) -> str:
    """Normalize canvas format key name."""
    if not format_key:
        return ''
    return format_key.strip().lower()


def parse_project_name(dir_name: str) -> dict[str, str]:
    """Parse project information from the project directory name.

    Args:
        dir_name: Project directory name

    Returns:
        Dictionary containing name, format, date
    """
    result = {
        'name': dir_name,
        'format': 'unknown',
        'format_name': 'Unknown format',
        'date': 'unknown',
        'date_formatted': 'Unknown date',
    }

    dir_name_lower = dir_name.lower()

    # Extract date (format: _YYYYMMDD)
    date_match = re.search(r'_(\d{8})$', dir_name)
    if date_match:
        date_str = date_match.group(1)
        result['date'] = date_str
        try:
            date_obj = datetime.strptime(date_str, '%Y%m%d')
            result['date_formatted'] = date_obj.strftime('%Y-%m-%d')
        except ValueError:
            pass

    # Prefer parsing standard format: name_format_YYYYMMDD
    full_match = re.match(
        r'^(?P<name>.+)_(?P<format>[a-z0-9_-]+)_(?P<date>\d{8})$',
        dir_name_lower,
    )
    if full_match:
        raw_format = full_match.group('format')
        normalized_format = _normalize_canvas_format(raw_format)
        if normalized_format in CANVAS_FORMATS:
            result['format'] = normalized_format
            result['format_name'] = CANVAS_FORMATS[normalized_format]['name']
            result['name'] = dir_name[: len(full_match.group('name'))]
            return result

    # Fallback: only match trailing `_format`
    sorted_formats = sorted(CANVAS_FORMATS.keys(), key=len, reverse=True)
    for fmt_key in sorted_formats:
        if re.search(rf'_{re.escape(fmt_key)}(?:_\d{{8}})?$', dir_name_lower):
            result['format'] = fmt_key
            result['format_name'] = CANVAS_FORMATS[fmt_key]['name']
            break

    # Extract project name
    name = re.sub(r'_\d{8}$', '', dir_name)
    if result['format'] != 'unknown':
        name = re.sub(
            rf'_{re.escape(result["format"])}$', '', name, flags=re.IGNORECASE
        )
    result['name'] = name

    return result


def get_project_info(project_path: str) -> dict:
    """Get detailed project information.

    Args:
        project_path: Project directory path

    Returns:
        Project information dictionary
    """
    project_path = Path(project_path)
    parsed = parse_project_name(project_path.name)

    info: dict = {
        'path': str(project_path),
        'dir_name': project_path.name,
        'name': parsed['name'],
        'format': parsed['format'],
        'format_name': parsed['format_name'],
        'date': parsed['date'],
        'date_formatted': parsed['date_formatted'],
        'exists': project_path.exists(),
        'svg_count': 0,
        'has_spec': False,
        'has_readme': False,
        'has_source': False,
        'source_count': 0,
        'spec_file': None,
        'svg_files': [],
    }

    if not project_path.exists():
        return info

    info['has_readme'] = (project_path / 'README.md').exists()

    spec_lock_path = project_path / 'spec_lock.json'
    if spec_lock_path.exists():
        info['has_spec'] = True
        info['spec_file'] = 'spec_lock.json'

    sources_dir = project_path / 'sources'
    info['has_source'] = sources_dir.exists()
    if sources_dir.exists():
        info['source_count'] = len(
            [p for p in sources_dir.iterdir() if p.is_file()]
        )

    svg_output = project_path / 'svg_output'
    if svg_output.exists():
        svg_files = sorted(svg_output.glob('*.svg'))
        info['svg_count'] = len(svg_files)
        info['svg_files'] = [f.name for f in svg_files]

    if info['format'] in CANVAS_FORMATS:
        info['canvas_info'] = CANVAS_FORMATS[info['format']]

    return info

# EMU conversion constants
EMU_PER_INCH = 914400
EMU_PER_PIXEL = EMU_PER_INCH / 96

# XML namespaces
NAMESPACES = {
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
    'asvg': 'http://schemas.microsoft.com/office/drawing/2016/SVG/main',
}

# Register namespaces for ElementTree output
for prefix, uri in NAMESPACES.items():
    ET.register_namespace(prefix, uri)


def get_slide_dimensions(
    canvas_format: str,
    custom_pixels: tuple[int, int] | None = None,
) -> tuple[int, int]:
    """Get slide dimensions in EMU units.

    Args:
        canvas_format: Canvas format key (e.g. 'ppt169').
        custom_pixels: Optional custom pixel dimensions override.

    Returns:
        (width_emu, height_emu) tuple.
    """
    if custom_pixels:
        width_px, height_px = custom_pixels
    else:
        if canvas_format not in CANVAS_FORMATS:
            canvas_format = 'ppt169'

        dimensions = CANVAS_FORMATS[canvas_format]['dimensions']
        match = re.match(r'(\d+)[×x](\d+)', dimensions)
        if match:
            width_px = int(match.group(1))
            height_px = int(match.group(2))
        else:
            width_px, height_px = 1280, 720

    return int(width_px * EMU_PER_PIXEL), int(height_px * EMU_PER_PIXEL)


def get_pixel_dimensions(
    canvas_format: str,
    custom_pixels: tuple[int, int] | None = None,
) -> tuple[int, int]:
    """Get canvas pixel dimensions.

    Args:
        canvas_format: Canvas format key.
        custom_pixels: Optional custom pixel dimensions override.

    Returns:
        (width_px, height_px) tuple.
    """
    if custom_pixels:
        return custom_pixels

    if canvas_format not in CANVAS_FORMATS:
        canvas_format = 'ppt169'

    dimensions = CANVAS_FORMATS[canvas_format]['dimensions']
    match = re.match(r'(\d+)[×x](\d+)', dimensions)
    if match:
        return int(match.group(1)), int(match.group(2))
    return 1280, 720


def get_viewbox_dimensions(svg_path: Path) -> tuple[int, int] | None:
    """Extract pixel dimensions from SVG viewBox.

    Args:
        svg_path: Path to the SVG file.

    Returns:
        (width, height) as integers, or None if not found.
    """
    try:
        with open(svg_path, 'r', encoding='utf-8') as f:
            content = f.read(2000)

        match = re.search(r'viewBox="([^"]+)"', content)
        if not match:
            return None

        parts = re.split(r'[\s,]+', match.group(1).strip())
        if len(parts) < 4:
            return None

        width = float(parts[2])
        height = float(parts[3])
        if width <= 0 or height <= 0:
            return None

        return int(round(width)), int(round(height))
    except Exception:
        return None


def detect_format_from_svg(svg_path: Path) -> str | None:
    """Detect canvas format from an SVG file's viewBox.

    Args:
        svg_path: Path to the SVG file.

    Returns:
        Canvas format key (e.g. 'ppt169'), or None if not detected.
    """
    try:
        with open(svg_path, 'r', encoding='utf-8') as f:
            content = f.read(2000)

        match = re.search(r'viewBox="([^"]+)"', content)
        if match:
            viewbox = match.group(1)
            for fmt_key, fmt_info in CANVAS_FORMATS.items():
                if fmt_info['viewbox'] == viewbox:
                    return fmt_key
    except Exception:
        pass
    return None
