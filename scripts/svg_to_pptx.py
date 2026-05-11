#!/usr/bin/env python
"""SVG to PPTX Tool (thin wrapper).

Delegates to the svg_to_pptx package with default parameters:
    python scripts/svg_to_pptx.py
"""

import sys
from pathlib import Path

# Ensure the scripts directory is on sys.path so the package can be found
sys.path.insert(0, str(Path(__file__).resolve().parent))

from svg_to_pptx.pptx_cli import main as _main

def main() -> None:
    """CLI entry point with default parameters."""
    # Set default parameters: workspace, source=final
    sys.argv = [
        sys.argv[0],  # script name
        'workspace',  # project_path
        '-s', 'final'  # source directory
    ]
    _main()

if __name__ == '__main__':
    main()
