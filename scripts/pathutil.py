"""
Path utilities for PPT Master scripts.
Centralizes path definitions based on the repository root.
"""

import sys
from pathlib import Path

# Repository root (parent of the scripts directory)
REPO_ROOT = Path(__file__).resolve().parent.parent

# Core workspace paths
WORKSPACE_DIR = REPO_ROOT / 'workspace'
SOURCES_DIR = WORKSPACE_DIR / 'sources'
IMAGES_DIR = WORKSPACE_DIR / 'images'
SVG_OUTPUT_DIR = WORKSPACE_DIR / 'svg_output'
SVG_FINAL_DIR = WORKSPACE_DIR / 'svg_final'
NOTES_DIR = WORKSPACE_DIR / 'notes'
EXPORTS_DIR = WORKSPACE_DIR / 'exports'

# Specific key files
STATE_FILE = WORKSPACE_DIR / 'state.md'
SPEC_LOCK_FILE = WORKSPACE_DIR / 'spec_lock.md'
DESIGN_SPEC_FILE = WORKSPACE_DIR / 'design_spec.md'
NOTES_ALL_FILE = NOTES_DIR / 'notes_all.md'

# Repo templates
TEMPLATES_DIR = REPO_ROOT / 'templates'

# Add repo root to Python path so scripts can import modules relative to repo
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
