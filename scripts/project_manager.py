#!/usr/bin/env python
"""PPT Master 工作区管理工具。

用法：
    python scripts/project_manager.py init
    python scripts/project_manager.py import-sources <源文件1> [<源文件2> ...] [--move | --copy]
    python scripts/project_manager.py validate
    python scripts/project_manager.py info
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

try:
    from project_utils import (
        CANVAS_FORMATS,
        get_project_info as get_project_info_common,
        normalize_canvas_format,
        validate_project_structure,
        validate_svg_viewbox,
    )
except ImportError:
    tools_dir = Path(__file__).resolve().parent
    if str(tools_dir) not in sys.path:
        sys.path.insert(0, str(tools_dir))
    from project_utils import (  # type: ignore
        CANVAS_FORMATS,
        get_project_info as get_project_info_common,
        normalize_canvas_format,
        validate_project_structure,
        validate_svg_viewbox,
    )

TOOLS_DIR = Path(__file__).resolve().parent
SKILL_DIR = TOOLS_DIR.parent
REPO_ROOT = SKILL_DIR
SOURCE_DIRNAME = "sources"
TEXT_SOURCE_SUFFIXES = {".md", ".markdown", ".txt"}


def sanitize_name(value: str) -> str:
    """Sanitize a user-facing name into a filesystem-safe token."""
    safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in value.strip())
    safe = safe.strip("._")
    while "__" in safe:
        safe = safe.replace("__", "_")
    return safe[:120] or "source"


def is_within_path(path: Path, parent: Path) -> bool:
    """Return whether `path` resolves inside `parent`."""
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


class ProjectManager:
    """Create, inspect, validate, and populate workspace."""

    CANVAS_FORMATS = CANVAS_FORMATS

    def __init__(self, workspace_dir: str = "workspace") -> None:
        self.workspace_dir = Path(workspace_dir)

    def init_project(
        self,
        canvas_format: str = "ppt169",
    ) -> str:
        normalized_format = normalize_canvas_format(canvas_format)
        if normalized_format not in self.CANVAS_FORMATS:
            available = ", ".join(sorted(self.CANVAS_FORMATS.keys()))
            raise ValueError(
                f"不支持的画布格式: {canvas_format} "
                f"(可用: {available})"
            )

        workspace_path = self.workspace_dir
        workspace_path.mkdir(parents=True, exist_ok=True)

        for rel_path in (
            "svg_output",
            "svg_final",
            "images",
            "notes",
            "templates",
            SOURCE_DIRNAME,
            "exports",
        ):
            (workspace_path / rel_path).mkdir(parents=True, exist_ok=True)

        canvas_info = self.CANVAS_FORMATS[normalized_format]
        readme_path = workspace_path / "README.md"
        readme_path.write_text(
            (
                "# PPT Master Workspace\n\n"
                f"- Canvas format: {normalized_format}\n\n"
                "## Directories\n\n"
                "- `svg_output/`: 原始 SVG 输出\n"
                "- `svg_final/`: 后处理后的 SVG 输出\n"
                "- `images/`: 演示素材\n"
                "- `notes/`: 演讲备注\n"
                "- `templates/`: 项目模板\n"
                "- `sources/`: 源材料与规范化 Markdown\n"
                "- `exports/`: 原生 PPTX 导出（带时间戳）\n"
                "- `backup/<timestamp>/`: SVG 快照 + svg_output/ 归档（导出时自动创建，旧时间戳可安全删除）\n"
            ),
            encoding="utf-8",
        )

        print(f"工作区已创建: {workspace_path}")
        print(f"画布: {canvas_info['name']} ({canvas_info['dimensions']})")

        # 初始化状态文件
        self._init_state(workspace_path, normalized_format)

        return str(workspace_path)

    def _init_state(
        self,
        workspace_path: Path,
        canvas_format: str,
    ) -> None:
        """初始化 workspace/state.md 状态文件。"""
        state_path = workspace_path / "state.md"
        template_path = SKILL_DIR / "templates" / "state" / "state.md"

        if template_path.exists():
            content = template_path.read_text(encoding="utf-8")
            content = content.replace("{canvas_format}", canvas_format)
            state_path.write_text(content, encoding="utf-8")
        else:
            # 模板不存在时生成最小版本
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
            state_path.write_text(
                f"# 工作区状态\n\n"
                f"## 当前项目\n画布格式: {canvas_format}\n\n"
                f"## 当前阶段\nS0 项目初始化 — 进行中\n\n"
                f"## 阶段清单\n"
                f"- [/] S0 项目初始化\n"
                f"- [ ] S1 源内容处理\n"
                f"- [ ] S2 模板选项\n"
                f"- [ ] S3 Strategist（八项确认 ⛔）\n"
                f"- [ ] S4 Executor（逐页生成）\n"
                f"- [ ] S5 后处理 + 导出\n\n"
                f"## 当前页进度\n_（Executor 阶段填写）_\n\n"
                f"## 决策记录\n| # | 决策 | 原因 |\n|---|------|------|\n\n"
                f"## 错误日志\n| 错误 | 阶段 | 处理 |\n|------|------|------|\n\n"
                f"## 经验教训\n_（跨项目持久保留）_\n\n"
                f"## 进度日志\n| 时间 | 动作 | 结果 |\n|------|------|------|\n"
                f"| {now_str} | 工作区初始化 | 成功 |\n",
                encoding="utf-8",
            )

    def _source_dir(self, workspace_path: Path) -> Path:
        sources_dir = workspace_path / SOURCE_DIRNAME
        sources_dir.mkdir(parents=True, exist_ok=True)
        return sources_dir

    def _ensure_unique_path(self, path: Path) -> Path:
        if not path.exists():
            return path

        suffix = path.suffix
        stem = path.stem
        counter = 2
        while True:
            candidate = path.with_name(f"{stem}_{counter}{suffix}")
            if not candidate.exists():
                return candidate
            counter += 1

    def _copy_or_move_file(self, source: Path, destination: Path, move: bool) -> Path:
        try:
            if source.resolve() == destination.resolve():
                return destination
        except FileNotFoundError:
            pass

        destination = self._ensure_unique_path(destination)
        if move:
            shutil.move(str(source), str(destination))
        else:
            shutil.copy2(source, destination)
        return destination

    def _copy_or_move_tree(self, source: Path, destination: Path, move: bool) -> Path:
        try:
            if source.resolve() == destination.resolve():
                return destination
        except FileNotFoundError:
            pass

        destination = self._ensure_unique_path(destination)
        if move:
            shutil.move(str(source), str(destination))
        else:
            shutil.copytree(source, destination)
        return destination

    def _run_tool(self, args: list[str]) -> None:
        try:
            result = subprocess.run(
                args,
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except FileNotFoundError as exc:
            raise RuntimeError(f"可执行文件未找到: {args[0]}") from exc
        except subprocess.CalledProcessError as exc:
            details = (exc.stderr or exc.stdout or "").strip()
            raise RuntimeError(details or "工具执行失败") from exc

        if result.stdout.strip():
            print(result.stdout.strip())

    def _normalize_text_source(self, source_path: Path, sources_dir: Path) -> Path:
        target = self._ensure_unique_path(sources_dir / f"{source_path.stem}.md")
        content = source_path.read_text(encoding="utf-8", errors="replace")
        target.write_text(content, encoding="utf-8")
        return target

    def _canonicalize_markdown_content(self, content: str) -> str:
        canonical = content.replace("\r\n", "\n")
        canonical = re.sub(r"(?m)^(\s*Crawled:\s+).*$", r"\1__IGNORED__", canonical)
        canonical = re.sub(r"(?m)^(\s*Imported:\s+).*$", r"\1__IGNORED__", canonical)
        canonical = re.sub(r"([^\s\]()/]+_files)/", "__ASSET_DIR__/", canonical)
        return canonical.strip()

    def _find_equivalent_markdown(self, source_path: Path, sources_dir: Path) -> Path | None:
        source_content = source_path.read_text(encoding="utf-8", errors="replace")
        canonical_source = self._canonicalize_markdown_content(source_content)

        for existing in sorted(sources_dir.iterdir()):
            if existing.suffix.lower() not in {".md", ".markdown"}:
                continue
            try:
                if existing.resolve() == source_path.resolve():
                    continue
            except FileNotFoundError:
                pass

            existing_content = existing.read_text(encoding="utf-8", errors="replace")
            if self._canonicalize_markdown_content(existing_content) == canonical_source:
                return existing

        return None

    def _companion_asset_dir(self, source_path: Path) -> Path | None:
        candidate = source_path.with_name(f"{source_path.stem}_files")
        if candidate.exists() and candidate.is_dir():
            return candidate
        return None

    def _rewrite_markdown_asset_refs(
        self,
        markdown_path: Path,
        original_asset_dirname: str,
        imported_asset_dirname: str,
    ) -> None:
        if original_asset_dirname == imported_asset_dirname:
            return

        content = markdown_path.read_text(encoding="utf-8", errors="replace")
        updated = content.replace(f"{original_asset_dirname}/", f"{imported_asset_dirname}/")
        if updated != content:
            markdown_path.write_text(updated, encoding="utf-8")

    def _import_markdown_with_assets(
        self,
        source_path: Path,
        sources_dir: Path,
        move: bool,
    ) -> tuple[Path, Path | None, str | None]:
        archived_markdown = self._copy_or_move_file(
            source_path,
            sources_dir / source_path.name,
            move=move,
        )

        asset_dir = self._companion_asset_dir(source_path)
        if asset_dir is None:
            return archived_markdown, None, None

        imported_asset_dir = self._copy_or_move_tree(
            asset_dir,
            sources_dir / f"{archived_markdown.stem}_files",
            move=move,
        )
        self._rewrite_markdown_asset_refs(
            archived_markdown,
            original_asset_dirname=asset_dir.name,
            imported_asset_dirname=imported_asset_dir.name,
        )

        note = None
        if archived_markdown.stem != source_path.stem:
            note = (
                f"{source_path}: 导入的 Markdown 已重命名为 {archived_markdown.name}，"
                f"资源引用已改写为 {imported_asset_dir.name}/"
            )
        return archived_markdown, imported_asset_dir, note

    def import_sources(
        self,
        source_items: list[str],
        move: bool = False,
        copy: bool = False,
    ) -> dict[str, list[str]]:
        if move and copy:
            raise ValueError("--move 和 --copy 互斥")
        workspace_path = self.workspace_dir
        if not workspace_path.exists() or not workspace_path.is_dir():
            raise FileNotFoundError(f"工作区目录未找到: {workspace_path}")
        if not source_items:
            raise ValueError("至少需要一个源文件路径")

        sources_dir = self._source_dir(workspace_path)
        summary: dict[str, list[str]] = {
            "archived": [],
            "markdown": [],
            "assets": [],
            "notes": [],
            "skipped": [],
        }

        for item in source_items:
            source_path = Path(item)
            if not source_path.exists():
                summary["skipped"].append(f"{item}: 路径未找到")
                continue
            if source_path.is_dir():
                summary["skipped"].append(f"{item}: 不支持目录")
                continue

            if copy:
                effective_move = False
            elif move:
                effective_move = True
            elif is_within_path(source_path, REPO_ROOT):
                effective_move = True
                print(
                    f"注意: {source_path} 位于 ppt-master 仓库内，已移动（非复制）以避免误提交。"
                    f"使用 --copy 可覆盖此行为。",
                    file=sys.stderr,
                )
            else:
                effective_move = False
            suffix = source_path.suffix.lower()

            if suffix in {".md", ".markdown"}:
                duplicate_markdown = self._find_equivalent_markdown(source_path, sources_dir)
                if duplicate_markdown is not None:
                    summary["markdown"].append(str(duplicate_markdown))
                    summary["notes"].append(
                        f"{item}: 跳过重复 Markdown 导入，等效内容已存在: {duplicate_markdown.name}"
                    )
                    continue

                archived_markdown, asset_dir, note = self._import_markdown_with_assets(
                    source_path,
                    sources_dir,
                    move=effective_move,
                )
                summary["archived"].append(str(archived_markdown))
                summary["markdown"].append(str(archived_markdown))
                if asset_dir is not None:
                    summary["assets"].append(str(asset_dir))
                if note:
                    summary["notes"].append(note)
                continue

            archived_path = self._copy_or_move_file(
                source_path,
                sources_dir / source_path.name,
                move=effective_move,
            )
            summary["archived"].append(str(archived_path))

            if suffix == ".txt":
                markdown_path = self._normalize_text_source(archived_path, sources_dir)
                summary["markdown"].append(str(markdown_path))
            else:
                summary["notes"].append(f"{item}: 已归档（未转换）")

        return summary

    def validate_project(self) -> tuple[bool, list[str], list[str]]:
        workspace_path = self.workspace_dir
        is_valid, errors, warnings = validate_project_structure(str(workspace_path))

        if workspace_path.exists() and workspace_path.is_dir():
            info = get_project_info_common(str(workspace_path))
            if info.get("svg_files"):
                svg_files = [workspace_path / "svg_output" / name for name in info["svg_files"]]
                expected_format = info.get("format")
                if expected_format == "unknown":
                    expected_format = None
                warnings.extend(validate_svg_viewbox(svg_files, expected_format))

        return is_valid, errors, warnings

    def get_project_info(self) -> dict[str, object]:
        workspace_path = str(self.workspace_dir)
        shared = get_project_info_common(workspace_path)
        return {
            "name": shared.get("name", "workspace"),
            "path": shared.get("path", workspace_path),
            "exists": shared.get("exists", False),
            "svg_count": shared.get("svg_count", 0),
            "has_spec": shared.get("has_spec", False),
            "has_source": shared.get("has_source", False),
            "source_count": shared.get("source_count", 0),
            "canvas_format": shared.get("format_name", "Unknown"),
            "create_date": shared.get("date_formatted", "Unknown"),
        }


def print_usage() -> None:
    """Print CLI usage information from the module docstring."""
    print(__doc__)


def parse_init_args(argv: list[str]) -> str:
    """Parse arguments for the `init` subcommand."""
    canvas_format = "ppt169"

    i = 2
    while i < len(argv):
        if argv[i] == "--format" and i + 1 < len(argv):
            canvas_format = argv[i + 1]
            i += 2
        else:
            i += 1

    return canvas_format


def parse_import_args(argv: list[str]) -> tuple[list[str], bool, bool]:
    """Parse arguments for the `import-sources` subcommand."""
    if len(argv) < 3:
        raise ValueError("至少一个源文件为必填项")

    move = False
    copy = False
    sources: list[str] = []

    for arg in argv[2:]:
        if arg == "--move":
            move = True
        elif arg == "--copy":
            copy = True
        else:
            sources.append(arg)

    if move and copy:
        raise ValueError("--move 和 --copy 互斥")

    return sources, move, copy


def main() -> None:
    """Run the CLI entry point."""
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    command = sys.argv[1]
    manager = ProjectManager()

    try:
        if command == "init":
            canvas_format = parse_init_args(sys.argv)
            workspace_path = manager.init_project(canvas_format=canvas_format)
            print(f"[OK] 工作区已初始化: {workspace_path}")
            print("下一步:")
            print("1. 将源文件放入 workspace/sources/（或使用 import-sources）")
            print("2. 将设计规范保存到 workspace/ 根目录")
            print("3. 生成 SVG 文件到 workspace/svg_output/")
            return

        if command == "import-sources":
            sources, move, copy = parse_import_args(sys.argv)
            summary = manager.import_sources(sources, move=move, copy=copy)
            print(f"[OK] 源文件已导入: {manager.workspace_dir}")
            if summary["archived"]:
                print("\n归档的原始文件 / URL 记录:")
                for item in summary["archived"]:
                    print(f"  - {item}")
            if summary["markdown"]:
                print("\n规范化 Markdown:")
                for item in summary["markdown"]:
                    print(f"  - {item}")
            if summary["assets"]:
                print("\n导入的资源目录:")
                for item in summary["assets"]:
                    print(f"  - {item}")
            if summary["notes"]:
                print("\n备注:")
                for item in summary["notes"]:
                    print(f"  - {item}")
            if summary["skipped"]:
                print("\n跳过:")
                for item in summary["skipped"]:
                    print(f"  - {item}")
            return

        if command == "validate":
            is_valid, errors, warnings = manager.validate_project()

            print(f"\n工作区校验: {manager.workspace_dir}")
            print("=" * 60)

            if errors:
                print("\n[ERROR]")
                for error in errors:
                    print(f"  - {error}")

            if warnings:
                print("\n[WARN]")
                for warning in warnings:
                    print(f"  - {warning}")

            if is_valid and not warnings:
                print("\n[OK] 工作区结构完整。")
            elif is_valid:
                print("\n[OK] 工作区结构有效，但有警告。")
            else:
                print("\n[ERROR] 工作区结构无效。")
                sys.exit(1)
            return

        if command == "info":
            info = manager.get_project_info()

            print(f"\n工作区信息: {info['name']}")
            print("=" * 60)
            print(f"路径: {info['path']}")
            print(f"存在: {'是' if info['exists'] else '否'}")
            print(f"SVG 文件数: {info['svg_count']}")
            print(f"设计规范: {'有' if info['has_spec'] else '无'}")
            print(f"源材料: {'有' if info['has_source'] else '无'}")
            print(f"源文件数: {info['source_count']}")
            print(f"画布格式: {info['canvas_format']}")
            print(f"创建日期: {info['create_date']}")
            return

        raise ValueError(f"未知命令: {command}")
    except Exception as exc:
        print(f"[ERROR] {exc}")
        print_usage()
        sys.exit(1)


if __name__ == "__main__":
    main()
