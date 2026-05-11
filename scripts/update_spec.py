#!/usr/bin/env python
"""将 spec_lock.md 的值变更同步到锁文件和 svg_output/*.svg。

用法：
    python scripts/update_spec.py colors.primary=#0066AA
    python scripts/update_spec.py typography.font_family='"PingFang SC", sans-serif'

v2 支持范围：
- `colors.*` — 在 svg_output/*.svg 中替换 HEX 值（不区分大小写）。
- `typography.font_family` — 替换每个 `font-family="..."` / `font-family='...'` 属性的内部值。
  这是全局替换：所有文本元素统一使用新字体，不论角色。

省略点的裸 `key=value` 视为 `colors.key=value`，保持向后兼容。

其他键（字号、角色级 `typography.*_family` 覆盖、图标、图片、画布、禁用项）
故意不支持——它们涉及属性级或语义级替换，批量传播的风险收益不成比例。
如需角色级字体变更，请编辑 spec_lock.md 并重新生成受影响页面。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HEX_RE = re.compile(r"^#(?:[0-9A-Fa-f]{3,4}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$")
FONT_FAMILY_RE = re.compile(r"""(font-family\s*=\s*)(["'])(.*?)\2""")


def parse_lock(lock_path: Path) -> dict[str, dict[str, str]]:
    """Return {section_name: {key: value}} parsed from spec_lock.md.

    The format is:
        ## section
        - key: value
    """
    sections: dict[str, dict[str, str]] = {}
    current: str | None = None
    for raw in lock_path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if line.startswith("## "):
            current = line[3:].strip()
            sections.setdefault(current, {})
            continue
        if current is None:
            continue
        m = re.match(r"^-\s+([A-Za-z0-9_]+)\s*:\s*(.+?)\s*$", line)
        if m:
            sections[current][m.group(1)] = m.group(2)
    return sections


def rewrite_lock(lock_path: Path, section: str, key: str, new_value: str) -> None:
    """Rewrite the single `- key: old_value` line under `## section`."""
    lines = lock_path.read_text(encoding="utf-8").splitlines(keepends=True)
    in_section = False
    for i, raw in enumerate(lines):
        stripped = raw.rstrip("\n")
        if stripped.startswith("## "):
            in_section = stripped[3:].strip() == section
            continue
        if not in_section:
            continue
        m = re.match(r"^(-\s+)([A-Za-z0-9_]+)(\s*:\s*)(.+?)(\s*)$", stripped)
        if m and m.group(2) == key:
            lines[i] = f"{m.group(1)}{m.group(2)}{m.group(3)}{new_value}{m.group(5)}\n"
            lock_path.write_text("".join(lines), encoding="utf-8")
            return
    raise KeyError(f"key {key!r} not found under section {section!r} in {lock_path}")


def replace_color_in_svgs(
    svg_dir: Path, old_hex: str, new_hex: str, *, dry_run: bool = False
) -> list[tuple[Path, int]]:
    """Replace old_hex with new_hex in every .svg under svg_dir.

    Returns a list of (path, replacement_count) for each changed file. The
    count comes straight from re.subn so callers can spot anomalies —
    e.g. one file with 50 hits when the rest have 4-8 is likely a stray
    HEX literal inside <text> content rather than a styling attribute.

    Two-phase: plan all file updates in memory, then write to disk. If any
    exception is raised during planning (e.g. bad HEX, read failure), no files
    are touched. This keeps svg_output/ and the caller's spec_lock.md write
    in a consistent pair: either everything is applied or nothing is.

    When dry_run=True, the planning phase still runs (so bad HEX still raises
    and callers see which files would change), but no disk writes happen. The
    returned list describes the would-change files.
    """
    if not HEX_RE.match(old_hex) or not HEX_RE.match(new_hex):
        raise ValueError(f"not a HEX color: old={old_hex!r} new={new_hex!r}")
    pattern = re.compile(re.escape(old_hex), re.IGNORECASE)
    planned: list[tuple[Path, str, int]] = []
    for svg in sorted(svg_dir.glob("*.svg")):
        text = svg.read_text(encoding="utf-8")
        new_text, n = pattern.subn(new_hex, text)
        if n > 0:
            planned.append((svg, new_text, n))
    if not dry_run:
        for svg, new_text, _ in planned:
            svg.write_text(new_text, encoding="utf-8")
    return [(p, n) for p, _, n in planned]


def replace_font_family_in_svgs(
    svg_dir: Path, new_value: str, *, dry_run: bool = False
) -> list[tuple[Path, int]]:
    """Replace the inner value of every `font-family="..."` / `font-family='...'`
    attribute in every .svg under svg_dir.

    Returns a list of (path, replacement_count) for each changed file.

    Preserves the outer quote character when possible; if the new value contains
    that same quote type, switches the outer quote to the other kind.

    Two-phase: plan all file updates in memory, then write to disk. The inner
    `_sub` may raise ValueError when the new value contains both quote kinds —
    when that happens in the planning phase, no files have been touched yet.

    When dry_run=True, the planning phase still runs (so the ValueError still
    fires and callers see which files would change), but no disk writes happen.
    The returned list describes the would-change files.
    """
    def _sub(m: re.Match[str]) -> str:
        prefix, quote, _inner = m.group(1), m.group(2), m.group(3)
        outer = quote
        if outer in new_value:
            outer = "'" if quote == '"' else '"'
            if outer in new_value:
                raise ValueError(
                    f"new font_family value contains both ' and \" — cannot embed: {new_value!r}"
                )
        return f"{prefix}{outer}{new_value}{outer}"

    planned: list[tuple[Path, str, int]] = []
    for svg in sorted(svg_dir.glob("*.svg")):
        text = svg.read_text(encoding="utf-8")
        new_text, n = FONT_FAMILY_RE.subn(_sub, text)
        if n > 0 and new_text != text:
            planned.append((svg, new_text, n))
    if not dry_run:
        for svg, new_text, _ in planned:
            svg.write_text(new_text, encoding="utf-8")
    return [(p, n) for p, _, n in planned]


def main() -> int:
    from scripts.pathutil import WORKSPACE_DIR, SPEC_LOCK_FILE, SVG_OUTPUT_DIR
    
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "assignment",
        help="section.key=value（如 colors.primary=#0066AA, typography.font_family='\"Inter\", Arial, sans-serif'）。"
        "裸 key=value 视为 colors.key=value。",
    )
    ap.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="预览哪些 SVG 会变更；不写入磁盘。",
    )
    args = ap.parse_args()

    project = WORKSPACE_DIR
    lock = SPEC_LOCK_FILE
    svg_dir = SVG_OUTPUT_DIR

    if not lock.exists():
        print(f"错误: spec_lock.md 未找到: {lock}", file=sys.stderr)
        return 2
    if not svg_dir.exists():
        print(f"错误: svg_output/ 未找到: {svg_dir}", file=sys.stderr)
        return 2

    if "=" not in args.assignment:
        print("错误: 赋值格式必须为 [section.]key=value", file=sys.stderr)
        return 2
    lhs, new_value = args.assignment.split("=", 1)
    lhs = lhs.strip()
    new_value = new_value.strip()
    if "." in lhs:
        section, key = lhs.split(".", 1)
        section = section.strip()
        key = key.strip()
    else:
        section, key = "colors", lhs

    sections = parse_lock(lock)
    section_map = sections.get(section, {})
    if key not in section_map:
        known = {s: sorted(v) for s, v in sections.items()}
        print(
            f"错误: {key!r} 在 spec_lock.md 的 `## {section}` 下未找到。\n"
            f"已知键: {known}",
            file=sys.stderr,
        )
        return 2

    old_value = section_map[key]

    if section == "colors":
        if not HEX_RE.match(new_value):
            print(f"错误: colors.{key} 的新值必须是 HEX 颜色（得到 {new_value!r}）", file=sys.stderr)
            return 2
        if old_value == new_value:
            print(f"无变更: colors.{key} 已为 {new_value}")
            return 0
        # SVGs first (may raise on bad HEX), then lock. Writing lock last
        # avoids a state where lock claims new_value but SVGs still hold
        # old_value — that state silences re-runs (parse_lock would then
        # see new_value == old_value and exit early).
        changed = replace_color_in_svgs(svg_dir, old_value, new_value, dry_run=args.dry_run)
        if not args.dry_run:
            rewrite_lock(lock, "colors", key, new_value)
    elif section == "typography" and key == "font_family":
        if old_value == new_value:
            print(f"无变更: typography.font_family 已为 {new_value}")
            return 0
        try:
            changed = replace_font_family_in_svgs(svg_dir, new_value, dry_run=args.dry_run)
        except ValueError as e:
            print(f"错误: {e}", file=sys.stderr)
            return 2
        if not args.dry_run:
            rewrite_lock(lock, "typography", key, new_value)
    else:
        print(
            f"错误: {section}.{key} 不被 update_spec.py 支持。\n"
            f"v2 支持: colors.* (HEX), typography.font_family。\n"
            f"其他变更请手动编辑 spec_lock.md 和受影响 SVG。",
            file=sys.stderr,
        )
        return 2

    if args.dry_run:
        print(f"[预览] spec_lock.md: {section}.{key}  {old_value} → {new_value}")
        print(f"[预览] svg_output/:  {len(changed)} 个文件将更新")
    else:
        print(f"spec_lock.md: {section}.{key}  {old_value} → {new_value}")
        print(f"svg_output/:  {len(changed)} 个文件已更新")
    for p, n in changed:
        suffix = "处替换" if n == 1 else "处替换"
        print(f"  - {p.name} ({n} {suffix})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
