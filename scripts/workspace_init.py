#!/usr/bin/env python
"""PPT Master 工作区初始化工具。

用法：
    python scripts/workspace_init.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add repo root to sys.path so imports like 'scripts.pathutil' work when script is run directly
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from config import (
        CANVAS_FORMATS,
        normalize_canvas_format,
    )
except ImportError:
    tools_dir = Path(__file__).resolve().parent
    if str(tools_dir) not in sys.path:
        sys.path.insert(0, str(tools_dir))
    from config import (  # type: ignore
        CANVAS_FORMATS,
        normalize_canvas_format,
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


# ============================================================
# .env Loader
# ============================================================

def _load_dotenv() -> int:
    """从 REPO_ROOT/.env 加载环境变量。

    仅设置尚未存在的变量（os.environ.setdefault），不覆盖已有的系统环境变量。
    支持：export 前缀、单/双引号包裹值、# 注释、空行跳过。

    返回加载的变量数量。
    """
    dotenv_path = REPO_ROOT / ".env"
    if not dotenv_path.exists():
        return 0

    loaded = 0
    try:
        for raw in dotenv_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.lower().startswith("export "):
                line = line[7:].lstrip()
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if not key:
                continue
            os.environ.setdefault(key, value)
            loaded += 1
    except OSError:
        pass
    return loaded


# ============================================================
# Environment Check
# ============================================================

class EnvironmentCheckResult:
    """环境检查结果。"""
    def __init__(self):
        self.errors: list[str] = []      # 必须修复的错误
        self.warnings: list[str] = []    # 可选的警告
        self.info: list[str] = []        # 信息

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0


def _check_environment() -> EnvironmentCheckResult:
    """检查运行环境，确保所有依赖可用。

    返回 EnvironmentCheckResult；若 result.ok 为 False，脚本应终止。
    """
    result = EnvironmentCheckResult()

    # ── 1. Python 版本 ──────────────────────────────────────
    if sys.version_info < (3, 10):
        result.errors.append(
            f"Python >= 3.10 required, got {sys.version_info.major}.{sys.version_info.minor}"
        )

    # ── 2. 虚拟环境 ────────────────────────────────────────
    in_venv = sys.prefix != sys.base_prefix
    if in_venv:
        result.info.append(f"[OK] 虚拟环境已激活: {sys.prefix}")
    else:
        # 检查项目目录下是否存在 venv 目录
        venv_candidates = [".venv", "venv"]
        found_venv_dir = None
        for name in venv_candidates:
            if (REPO_ROOT / name).is_dir():
                found_venv_dir = name
                break
        if found_venv_dir:
            result.warnings.append(
                f"检测到 {found_venv_dir}/ 目录但虚拟环境未激活\n"
                f"  激活方式: {found_venv_dir}\\Scripts\\activate  (Windows)\n"
                f"  激活方式: source {found_venv_dir}/bin/activate  (Linux/macOS)"
            )
        else:
            result.warnings.append(
                "未检测到虚拟环境 — 强烈建议使用 venv 隔离依赖\n"
                "  创建: python -m venv .venv\n"
                "  激活: .venv\\Scripts\\activate  (Windows)"
            )

    # ── 3. 必需的 Python 包 ─────────────────────────────────
    required_packages = [
        ("pydantic_ai", "pydantic-ai", "LLM 图片审核 (llm_process_image.py)"),
        ("pydantic", "pydantic", "pydantic-ai 的依赖"),
        ("httpx", "httpx", "LLM API 调用 (llm_process_image.py)"),
        ("requests", "requests", "HTTP 请求 (web_search.py)"),
        ("urllib3", "urllib3", "HTTP 连接池 (web_search.py)"),
        ("PIL", "Pillow", "图片分析 (analyze_images.py, image_montage.py)"),
        ("sloppy_xml", "sloppy-xml", "SVG XML 修复 (svg_repair.py)"),
        ("pptx", "python-pptx", "PPTX 导出 (svg_to_pptx.py)"),
    ]
    for module_name, pip_name, usage in required_packages:
        try:
            __import__(module_name)
            result.info.append(f"[OK] {pip_name} ({usage})")
        except ImportError:
            result.errors.append(
                f"缺少包: {pip_name} — {usage}\n"
                f"  修复: pip install {pip_name}"
            )

    # ── 4. 渲染器（至少一个） ───────────────────────────────
    renderer_found = False
    renderer_details = []
    try:
        import fitz  # noqa: F401
        renderer_found = True
        renderer_details.append("PyMuPDF (fitz)")
    except (ImportError, OSError):
        pass
    if not renderer_found:
        try:
            import cairosvg  # noqa: F401
            renderer_found = True
            renderer_details.append("cairosvg")
        except (ImportError, OSError):
            pass
    if not renderer_found:
        try:
            from svglib.svglib import svg2rlg  # noqa: F401
            from reportlab.graphics import renderPM  # noqa: F401
            renderer_found = True
            renderer_details.append("svglib + reportlab")
        except (ImportError, OSError):
            pass
    if renderer_found:
        result.info.append(f"[OK] SVG 渲染器: {', '.join(renderer_details)}")
    else:
        result.warnings.append(
            "未找到 SVG 渲染器 — render_svg.py 将不可用\n"
            "  可选: pip install PyMuPDF  (推荐) | cairosvg | svglib reportlab"
        )

    # ── 5. 内部模块可导入性 ────────────────────────────────
    internal_modules = [
        ("config", "CANVAS_FORMATS / normalize_canvas_format"),
        ("scripts.pathutil", "WORKSPACE_DIR 路径定义"),
    ]
    for module_name, usage in internal_modules:
        try:
            __import__(module_name)
            result.info.append(f"[OK] 内部模块: {module_name} ({usage})")
        except ImportError as e:
            result.errors.append(
                f"内部模块导入失败: {module_name} — {usage}\n"
                f"  错误: {e}\n"
                f"  修复: 确保在项目根目录运行，且 scripts/ 目录完整"
            )

    # spec_models（部分功能需要，不阻塞）
    if _has_spec_models:
        result.info.append("[OK] 内部模块: scripts.spec_models (SpecLock schema)")
    else:
        result.warnings.append(
            "scripts.spec_models 不可用 — spec_lock.json 模板生成功能将被跳过\n"
            "  可能原因: pydantic 未安装或版本不兼容"
        )

    # svg_finalize 子模块（finalize_svg.py 需要）
    _svg_finalize_submodules = [
        "svg_finalize.crop_images",
        "svg_finalize.embed_icons",
        "svg_finalize.embed_images",
        "svg_finalize.fix_image_aspect",
    ]
    _svg_finalize_ok = True
    for sub_mod in _svg_finalize_submodules:
        try:
            __import__(sub_mod)
        except ImportError as e:
            result.errors.append(
                f"SVG 后处理模块导入失败: {sub_mod}\n"
                f"  错误: {e}\n"
                f"  修复: 确保 scripts/svg_finalize/ 目录完整"
            )
            _svg_finalize_ok = False
    if _svg_finalize_ok:
        result.info.append("[OK] 内部模块: svg_finalize.* (SVG 后处理)")

    # ── 6. 模板目录完整性 ──────────────────────────────────
    template_files = [
        ("templates/state.md", "状态文件模板 (_init_state)"),
        ("templates/layouts/layouts_index.json", "布局模板索引"),
        ("templates/charts/charts_index.json", "可视化模板索引"),
    ]
    for rel_path, usage in template_files:
        full_path = REPO_ROOT / rel_path
        if full_path.exists():
            result.info.append(f"[OK] 模板文件: {rel_path}")
        else:
            result.warnings.append(
                f"模板文件缺失: {rel_path} — {usage}\n"
                f"  影响: 对应功能将降级或跳过"
            )

    # ── 7. .env 文件加载 ───────────────────────────────────
    dotenv_count = _load_dotenv()
    if dotenv_count > 0:
        result.info.append(f"[OK] .env 文件已加载 ({dotenv_count} 个变量)")
    else:
        dotenv_path = REPO_ROOT / ".env"
        if dotenv_path.exists():
            result.warnings.append(
                ".env 文件存在但未解析到有效变量 — 请检查文件格式"
            )
        # .env 不存在不算错误，用户可能用系统环境变量

    # ── 8. LLM 完整配置验证 ────────────────────────────────
    # 先检查 API Key 存在性
    llm_key_env = "LLM_IMAGE_PROCESS_MIMOV25_API_KEY"
    llm_key_value = os.environ.get(llm_key_env, "").strip()

    detected_model_keys = []
    for k, v in os.environ.items():
        if k.startswith("LLM_IMAGE_PROCESS_") and k.endswith("_API_KEY") and v.strip():
            detected_model_keys.append(k)

    if llm_key_value:
        result.info.append(f"[OK] {llm_key_env} 已设置")
    elif detected_model_keys:
        result.info.append(
            f"[OK] 检测到 LLM API Key: {', '.join(detected_model_keys)}"
        )
    else:
        result.errors.append(
            f"未设置 LLM API Key — llm_process_image.py 需要以下任一环境变量:\n"
            f"  {llm_key_env}\n"
            f"  LLM_IMAGE_PROCESS_<MODEL_NAME>_API_KEY\n"
            f"  设置方式: 在 .env 文件或系统环境变量中配置"
        )

    # 验证完整 LLM 配置能否加载（仅在 pydantic-ai 可用时尝试）
    try:
        from llm_process_image import _load_llm_config  # noqa: F401
        try:
            _cfg = _load_llm_config()
            result.info.append(
                f"[OK] LLM 配置加载成功: model={_cfg.model_name}, base_url={_cfg.base_url}"
            )
        except RuntimeError as e:
            # _load_llm_config 在 api_key 为空时抛 RuntimeError
            result.errors.append(
                f"LLM 配置加载失败: {e}\n"
                f"  修复: 确保 LLM_IMAGE_PROCESS_*_API_KEY 环境变量已设置"
            )
        except Exception as e:
            result.warnings.append(f"LLM 配置加载时出现意外错误: {e}")
    except ImportError:
        # pydantic-ai 不可用时跳过，前面已有包检查报错
        pass

    # ── 9. 搜索引擎 API Key ────────────────────────────────
    tavily_key = os.environ.get("TAVILY_API_KEY", "").strip()
    baidu_key = os.environ.get("BAIDU_API_KEY", "").strip()

    if tavily_key:
        result.info.append("[OK] TAVILY_API_KEY 已设置")
    if baidu_key:
        result.info.append("[OK] BAIDU_API_KEY 已设置")
    if not tavily_key and not baidu_key:
        result.errors.append(
            "未设置搜索引擎 API Key — web_search.py 需要至少一个:\n"
            "  TAVILY_API_KEY  (推荐，月 1000 次)\n"
            "  BAIDU_API_KEY   (备选，月 1500 次)\n"
            "  设置方式: 在 .env 文件或系统环境变量中配置"
        )

    # ── 10. pydantic-ai subagent 初始化 ─────────────────────
    try:
        from pydantic_ai import Agent  # noqa: F401
        from pydantic_ai.models.openai import OpenAIChatModel  # noqa: F401
        from pydantic_ai.providers.openai import OpenAIProvider  # noqa: F401
        result.info.append("[OK] pydantic-ai subagent (Agent + OpenAI provider) 可初始化")
    except ImportError as e:
        result.errors.append(
            f"pydantic-ai subagent 初始化失败: {e}\n"
            f"  可能原因: pydantic-ai 版本过旧\n"
            f"  修复: pip install --upgrade pydantic-ai"
        )

    # ── 11. 可选依赖检查 ───────────────────────────────────
    try:
        import numpy  # noqa: F401
        result.info.append("[OK] numpy")
    except ImportError:
        result.warnings.append("未安装 numpy（非必须，但某些场景可能需要）")

    return result


def _print_check_report(result: EnvironmentCheckResult) -> None:
    """打印环境检查报告。"""
    total_checks = len(result.info) + len(result.warnings) + len(result.errors)
    print("\n" + "=" * 60)
    print(f"环境检查报告 ({total_checks} 项检查)")
    print("=" * 60)

    if result.info:
        print(f"\n[通过] ({len(result.info)}):")
        for msg in result.info:
            print(f"  {msg}")

    if result.warnings:
        print(f"\n[警告] ({len(result.warnings)}) — 建议修复:")
        for msg in result.warnings:
            for line in msg.splitlines():
                print(f"  {line}")

    if result.errors:
        print(f"\n[错误] ({len(result.errors)}) — 必须修复:")
        for msg in result.errors:
            for line in msg.splitlines():
                print(f"  {line}")

    print("=" * 60)
    if result.ok:
        print("[OK] 环境检查通过")
    else:
        print("[FAIL] 环境检查未通过，请修复上述错误后重试")
    print()


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
        template_path = SKILL_DIR / "templates" / "state.md"

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

def main() -> None:
    """Run the CLI entry point."""
    from scripts.pathutil import WORKSPACE_DIR

    # Step 0: 环境检查
    check_result = _check_environment()
    _print_check_report(check_result)
    if not check_result.ok:
        sys.exit(1)

    # Step 1: init workspace
    manager = ProjectManager(str(WORKSPACE_DIR))
    canvas_format = "ppt169"
    workspace_path = manager.init_project(canvas_format=canvas_format)
    print(f"[OK] 工作区已初始化: {workspace_path}")
    print("下一步:")
    print("1. 将设计规范保存到 workspace/ 根目录")
    print("2. 生成 SVG 文件到 workspace/svg_output/")


if __name__ == "__main__":
    main()
