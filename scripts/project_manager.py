#!/usr/bin/env python
"""PPT Master 工作区管理工具。

用法：
    python scripts/project_manager.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

# Add repo root to sys.path so imports like 'scripts.pathutil' work when script is run directly
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

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

try:
    from scripts.spec_models import SpecLock
    _has_spec_models = True
except ImportError:
    _has_spec_models = False

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
            "downloads",        # web_search 暂存区（task.md §1）
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
                "- `images/`: 最终用于 PPT 的图片（仅已采纳、已重命名为描述性名称的图片）\n"
                "- `downloads/`: web_search 暂存区（哈希名原始图片与搜索快照，审阅后用 --adopt 晋升到 images/）\n"
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
        
        # 初始化 spec_lock.json 模板
        self._init_spec_lock_template(workspace_path, normalized_format)

        return str(workspace_path)

    def _init_spec_lock_template(
        self,
        workspace_path: Path,
        canvas_format: str,
    ) -> None:
        """初始化 spec_lock.json 模板文件。
        
        生成带占位符的 JSON 模板，供 Strategist 填写。
        如果文件已存在，会覆盖（与删除再创建效果一致）。
        """
        if not _has_spec_models:
            print("[跳过] spec_models 模块不可用，未生成 spec_lock.json 模板")
            return
        
        spec_path = workspace_path / "spec_lock.json"
        
        canvas_info = self.CANVAS_FORMATS.get(canvas_format, {})
        viewbox = canvas_info.get("viewbox", "0 0 1280 720")
        
        # 解析 viewbox 获取尺寸
        vb_parts = viewbox.split()
        width = int(vb_parts[2]) if len(vb_parts) >= 3 else 1280
        height = int(vb_parts[3]) if len(vb_parts) >= 4 else 720
        
        # 生成模板字典
        template = {
            "project": {
                "name": "<填写项目名称>",
                "description": "<填写项目描述>",
                "audience": "<填写目标受众>",
                "style": "<填写设计风格，如: General Versatile（视觉冲击优先）>",
                "total_pages": 13,
                "created_date": datetime.now().strftime("%Y-%m-%d"),
                "rationale": "<填写项目定位理由>"
            },
            "canvas": {
                "viewbox": viewbox,
                "format": canvas_info.get("name", "PPT 16:9"),
                "width": width,
                "height": height,
                "margin_left": 60,
                "margin_right": 60,
                "margin_top": 50,
                "margin_bottom": 50,
                "rationale": "<填写画布配置理由>"
            },
            "colors": {
                "bg": "#FFFFFF",
                "secondary_bg": "#F5F5F5",
                "primary": "<填写主色 HEX，如 #4CAF50>",
                "accent": "<填写强调色 HEX，如 #2196F3>",
                "secondary_accent": "<填写次要强调色 HEX，如 #FF9800>",
                "text": "#333333",
                "text_secondary": "#666666",
                "text_tertiary": "#999999",
                "border": "#E0E0E0",
                "warning": "#F44336",
                "rationale": "<填写配色理由>"
            },
            "typography": {
                "font_family": "\"Microsoft YaHei\", Arial, sans-serif",
                "body_family": "\"Microsoft YaHei\", \"PingFang SC\", Arial, sans-serif",
                "code_family": "Consolas, \"Courier New\", monospace",
                "body": 22,
                "title": 36,
                "subtitle": 28,
                "section_title": 48,
                "cover_title": 60,
                "annotation": 16,
                "footer": 12,
                "rationale": "<填写字体选择理由>"
            },
            "icons": {
                "library": "tabler-filled",
                "inventory": [
                    "<填写图标1，如: building>",
                    "<填写图标2，如: wind>",
                    "<填写图标3，如: droplet>"
                ],
                "rationale": "<填写图标选择理由>"
            },
            "images": {
                "items": {
                    "P01": "<填写图片文件名>",
                    "P02": "<填写图片文件名>"
                },
                "rationale": "<填写图片配置理由>"
            },
            "page_rhythm": {
                "rhythm": {
                    "P01": "structural",
                    "P02": "structural",
                    "P03": "focal",
                    "P04": "analytical",
                    "P05": "analytical"
                },
                "rationale": "<填写节奏配置理由，structural=结构页, focal=焦点页, analytical=分析页>"
            },
            "content_outline": {
                "sections": [
                    {
                        "page": "P01",
                        "title": "<填写页面标题>",
                        "layout": "<填写布局方式，如: 全屏背景图 + 居中标题>",
                        "content": [
                            "<填写内容要点1>",
                            "<填写内容要点2>"
                        ],
                        "notes_file": "<填写演讲备注文件名，如: 01_cover.md>",
                        "rationale": "<填写内容设计理由>"
                    }
                ],
                "rationale": "<填写大纲设计理由>"
            },
            "technical_constraints": {
                "forbidden_elements": [
                    "rgba()",
                    "<style>",
                    "class",
                    "<foreignObject>",
                    "textPath",
                    "@font-face",
                    "<animate*>",
                    "<script>",
                    "<iframe>",
                    "<symbol>+<use>"
                ],
                "forbidden_patterns": [
                    "<g opacity>",
                    "HTML 命名实体"
                ],
                "xml_escape_chars": ["&", "<", ">", "\"", "'"],
                "xml_escape_entities": ["&amp;", "&lt;", "&gt;", "&quot;", "&apos;"],
                "rationale": "<填写技术约束理由>"
            },
            "forbidden": [
                "混用图标库",
                "rgba()",
                "<style>, class, <foreignObject>, textPath, @font-face, <animate*>, <script>, <iframe>, <symbol>+<use>",
                "<g opacity>（在每个子元素上单独设置透明度）",
                "文本中的 HTML 命名实体（&nbsp;, &mdash; 等）——写成原始 Unicode"
            ],
            "rationale": "<填写整体设计理由>"
        }
        
        # 写入格式化 JSON
        spec_path.write_text(
            json.dumps(template, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        
        print(f"spec_lock.json 模板已生成: {spec_path}")
        print("请让 Strategist 填写模板中的 <...> 占位符")

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


def main() -> None:
    """Run the CLI entry point."""
    from scripts.pathutil import WORKSPACE_DIR
    
    # Default: init workspace
    manager = ProjectManager(str(WORKSPACE_DIR))
    canvas_format = "ppt169"
    workspace_path = manager.init_project(canvas_format=canvas_format)
    print(f"[OK] 工作区已初始化: {workspace_path}")
    print("下一步:")
    print("1. 将设计规范保存到 workspace/ 根目录")
    print("2. 生成 SVG 文件到 workspace/svg_output/")


if __name__ == "__main__":
    main()
