#!/usr/bin/env python
"""PPT Master 工作区管理工具。

用法：
    python scripts/project_manager.py init
    python scripts/project_manager.py validate
    python scripts/project_manager.py info
"""

from __future__ import annotations

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
MATERIALS_DIRNAME = "materials"

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
            "exports",
            "sources",  # 项目素材目录
        ):
            (workspace_path / rel_path).mkdir(parents=True, exist_ok=True)

        canvas_info = self.CANVAS_FORMATS[normalized_format]
        readme_path = workspace_path / "README.md"
        readme_path.write_text(
            (
                "# PPT Master Workspace\n\n"
                f"- Canvas format: {normalized_format}\n\n"
                "## Directories\n\n"
                "- `sources/`: 项目素材（用户手动放入）\n"
                "- `svg_output/`: 原始 SVG 输出\n"
                "- `svg_final/`: 后处理后的 SVG 输出\n"
                "- `images/`: 最终用于 PPT 的图片\n"
                "- `notes/`: 演讲备注\n"
                "- `templates/`: 项目模板\n"
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
            print("1. 将设计规范保存到 workspace/ 根目录")
            print("2. 生成 SVG 文件到 workspace/svg_output/")
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
