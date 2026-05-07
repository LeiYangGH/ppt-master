# PPT Master Toolset

This directory contains user-facing scripts for conversion, project setup, SVG processing, export, and image generation.

## Directory Layout

- Top-level `scripts/`: runnable entry scripts
- `scripts/image_backends/`: internal provider implementations used by `image_gen.py`
- `scripts/template_import/`: internal PPTX reference-preparation helpers used by `pptx_template_import.py`
- `scripts/svg_finalize/`: internal post-processing helpers used by `finalize_svg.py`
- `scripts/docs/`: topic-focused script documentation
- `scripts/assets/`: static assets consumed by scripts

## Quick Start

Typical end-to-end workflow:

```powershell
python scripts/project_manager.py init <project_name> --format ppt169
python scripts/project_manager.py import-sources <project_path> <source_files...> --move
python scripts/total_md_split.py <project_path>
python scripts/finalize_svg.py <project_path>
python scripts/svg_to_pptx.py <project_path> -s final
```

Repository update:

```powershell
python scripts/update_repo.py
```

## Script Index

| Area | Primary scripts | Documentation |
|------|-----------------|---------------|
| Project management | `project_manager.py`, `batch_validate.py`, `generate_examples_index.py`, `error_helper.py`, `pptx_template_import.py` | [docs/project.md](./docs/project.md) |
| SVG pipeline | `finalize_svg.py`, `svg_to_pptx.py`, `total_md_split.py`, `svg_quality_checker.py` | [docs/svg-pipeline.md](./docs/svg-pipeline.md) |
| Spec maintenance | `update_spec.py` | [docs/update_spec.md](./docs/update_spec.md) |
| Image tools | `image_gen.py`, `analyze_images.py`, `gemini_watermark_remover.py` | [docs/image.md](./docs/image.md) |
| Repo maintenance | `update_repo.py` | README install/update section |
| Troubleshooting | validation, preview, export, dependency issues | [docs/troubleshooting.md](./docs/troubleshooting.md) |

## High-Frequency Commands

Project setup:

```powershell
python scripts/project_manager.py init <project_name> --format ppt169
python scripts/project_manager.py import-sources <project_path> <source_files...> --move
python scripts/project_manager.py validate <project_path>
```

Template source import:

```powershell
python scripts/pptx_template_import.py <template.pptx>
python scripts/pptx_template_import.py <template.pptx> --manifest-only
```

Post-processing and export:

```powershell
python scripts/total_md_split.py <project_path>
python scripts/finalize_svg.py <project_path>
python scripts/svg_to_pptx.py <project_path> -s final
```

Image generation:

```powershell
python scripts/image_gen.py "A modern futuristic workspace"
python scripts/image_gen.py --list-backends
python scripts/analyze_images.py <project_path>/images
```

Repository update:

```powershell
python scripts/update_repo.py
python scripts/update_repo.py --skip-pip
```

## Recommendations

- Keep one user-facing entry point per workflow at the top level of `scripts/`
- Move provider-specific or helper internals into subdirectories
- Prefer the unified entry points `project_manager.py`, `finalize_svg.py`, and `image_gen.py`
- Prefer `svg_final/` over `svg_output/` when exporting

## Related Docs

- [Project Tools](./docs/project.md)
- [SVG Pipeline Tools](./docs/svg-pipeline.md)
- [Image Tools](./docs/image.md)
- [Troubleshooting](./docs/troubleshooting.md)
- [Skill Entry](../SKILL.md)

_Last updated: 2026-04-09_
