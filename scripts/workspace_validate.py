#!/usr/bin/env python
"""
工作区结构完整性校验工具

在 S5 后处理完成后、S6 导出之前运行，作为流程完整性兜底检查。

用法：
    python scripts/workspace_validate.py
    python scripts/workspace_validate.py --strict   # warning 也视为失败
"""

import json
import sys
from pathlib import Path
from typing import List, Tuple


WORKSPACE = Path("workspace")


class WorkspaceValidator:
    """工作区结构完整性校验"""

    def __init__(self, strict: bool = False):
        self.strict = strict
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.spec: dict | None = None

    def validate(self) -> bool:
        """运行全部校验，返回是否通过。"""
        self._check_directory_structure()
        self._check_spec_lock()
        self._check_svg_output()
        self._check_notes()
        self._check_svg_final()
        self._check_exports()
        self._print_report()
        return len(self.errors) == 0 and (not self.strict or len(self.warnings) == 0)

    # ── 目录结构 ──────────────────────────────────────────────

    def _check_directory_structure(self) -> None:
        required_dirs = [
            WORKSPACE,
            WORKSPACE / "svg_output",
            WORKSPACE / "notes",
        ]
        for d in required_dirs:
            if not d.is_dir():
                self.errors.append(f"缺少目录: {d}")

    # ── spec_lock.json ────────────────────────────────────────

    def _check_spec_lock(self) -> None:
        spec_path = WORKSPACE / "spec_lock.json"
        if not spec_path.is_file():
            self.errors.append("缺少 workspace/spec_lock.json（S3 未完成）")
            return
        try:
            with open(spec_path, "r", encoding="utf-8") as f:
                self.spec = json.load(f)
        except json.JSONDecodeError as e:
            self.errors.append(f"spec_lock.json JSON 格式错误: {e}")
            self.spec = None
            return

        # 必须字段检查
        for key in ("project", "canvas", "colors", "typography"):
            if key not in self.spec:
                self.errors.append(f"spec_lock.json 缺少字段: {key}")

    # ── SVG 输出 ──────────────────────────────────────────────

    def _check_svg_output(self) -> None:
        svg_dir = WORKSPACE / "svg_output"
        if not svg_dir.is_dir():
            return  # 已在 _check_directory_structure 报错

        svg_files = sorted(svg_dir.glob("*.svg"))
        if not svg_files:
            self.errors.append("svg_output/ 下无 SVG 文件")
            return

        # 与 spec 中的 total_pages 比对
        if self.spec:
            total_pages = self.spec.get("project", {}).get("total_pages")
            if total_pages and len(svg_files) != total_pages:
                self.errors.append(
                    f"SVG 文件数 ({len(svg_files)}) 与 spec 声明页数 ({total_pages}) 不一致"
                )

    # ── 演讲备注 ──────────────────────────────────────────────

    def _check_notes(self) -> None:
        notes_dir = WORKSPACE / "notes"
        if not notes_dir.is_dir():
            return  # 已在 _check_directory_structure 报错

        notes_all = notes_dir / "notes_all.md"
        split_files = sorted(notes_dir.glob("P*.md"))

        if not notes_all.is_file() and not split_files:
            self.errors.append("notes/ 下既无 notes_all.md 也无拆分备注文件（S4 未完成）")
        elif notes_all.is_file() and not split_files:
            self.warnings.append("notes_all.md 存在但未拆分（S5.1 未运行）")

    # ── SVG 最终版 ────────────────────────────────────────────

    def _check_svg_final(self) -> None:
        final_dir = WORKSPACE / "svg_final"
        svg_dir = WORKSPACE / "svg_output"

        if not final_dir.is_dir():
            self.warnings.append("svg_final/ 目录不存在（S5.2 未运行）")
            return

        final_files = list(final_dir.glob("*.svg"))
        svg_files = list(svg_dir.glob("*.svg")) if svg_dir.is_dir() else []

        if svg_files and len(final_files) != len(svg_files):
            self.errors.append(
                f"svg_final 文件数 ({len(final_files)}) 与 svg_output ({len(svg_files)}) 不一致"
            )

    # ── 导出目录 ──────────────────────────────────────────────

    def _check_exports(self) -> None:
        exports_dir = WORKSPACE / "exports"
        if not exports_dir.is_dir():
            self.warnings.append("exports/ 目录不存在（S6 未运行）")
            return

        pptx_files = list(exports_dir.glob("*.pptx"))
        if not pptx_files:
            self.warnings.append("exports/ 下无 .pptx 文件")

    # ── 报告输出 ──────────────────────────────────────────────

    def _print_report(self) -> None:
        print("=" * 60)
        print("工作区结构校验报告")
        print("=" * 60)

        if self.errors:
            print(f"\n[ERROR] 错误 ({len(self.errors)}):")
            for e in self.errors:
                print(f"  - {e}")

        if self.warnings:
            print(f"\n[WARN] 警告 ({len(self.warnings)}):")
            for w in self.warnings:
                print(f"  - {w}")

        if not self.errors and not self.warnings:
            print("\n[OK] 工作区结构完整，所有检查通过。")
        elif not self.errors:
            print(f"\n[OK] 无错误，有 {len(self.warnings)} 个警告。")
        else:
            print(f"\n[FAIL] {len(self.errors)} 个错误，{len(self.warnings)} 个警告。")


def main() -> None:
    strict = "--strict" in sys.argv
    validator = WorkspaceValidator(strict=strict)
    ok = validator.validate()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
