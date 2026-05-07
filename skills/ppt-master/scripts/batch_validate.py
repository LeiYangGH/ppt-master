#!/usr/bin/env python
"""
PPT Master - 批量项目校验工具

一次性检查多个项目的结构完整性和合规性。

用法：
    python scripts/batch_validate.py examples
    python scripts/batch_validate.py projects
    python scripts/batch_validate.py --all
    python scripts/batch_validate.py examples projects
"""

import sys
from collections import defaultdict
from pathlib import Path

try:
    from project_utils import (
        find_all_projects,
        get_project_info,
        validate_project_structure,
        validate_svg_viewbox,
        CANVAS_FORMATS
    )
except ImportError:
    print("错误: 无法导入 project_utils 模块")
    print("请确保 project_utils.py 在同一目录下")
    sys.exit(1)


class BatchValidator:
    """Batch validator"""

    def __init__(self):
        self.results: list[dict[str, object]] = []
        self.summary = {
            'total': 0,
            'valid': 0,
            'has_errors': 0,
            'has_warnings': 0,
            'missing_readme': 0,
            'missing_spec': 0,
            'svg_issues': 0
        }

    def validate_directory(self, directory: str, recursive: bool = False) -> list[dict[str, object]]:
        """
        Validate all projects in a directory

        Args:
            directory: Directory path
            recursive: Whether to recursively search subdirectories

        Returns:
            List of validation results
        """
        dir_path = Path(directory)
        if not dir_path.exists():
            print(f"[ERROR] 目录不存在: {directory}")
            return []

        print(f"\n[扫描] 正在扫描目录: {directory}")
        print("=" * 80)

        projects = find_all_projects(directory)

        if not projects:
            print(f"[WARN] 未找到项目")
            return []

        print(f"找到 {len(projects)} 个项目\n")

        for project_path in projects:
            self.validate_project(str(project_path))

        return self.results

    def validate_project(self, project_path: str) -> dict[str, object]:
        """
        Validate a single project

        Args:
            project_path: Project path

        Returns:
            Validation result dictionary
        """
        self.summary['total'] += 1

        # Get project info
        info = get_project_info(project_path)

        # Validate project structure
        is_valid, errors, warnings = validate_project_structure(project_path)

        # Validate SVG viewBox
        svg_warnings = []
        if info['svg_files']:
            project_path_obj = Path(project_path)
            svg_files = [project_path_obj / 'svg_output' /
                         f for f in info['svg_files']]
            svg_warnings = validate_svg_viewbox(svg_files, info['format'])

        # Aggregate results
        result = {
            'path': project_path,
            'name': info['name'],
            'format': info['format_name'],
            'date': info['date_formatted'],
            'svg_count': info['svg_count'],
            'is_valid': is_valid,
            'errors': errors,
            'warnings': warnings + svg_warnings,
            'has_readme': info['has_readme'],
            'has_spec': info['has_spec']
        }

        self.results.append(result)

        # Update statistics
        if is_valid and not warnings and not svg_warnings:
            self.summary['valid'] += 1
            status = "[OK]"
        elif errors:
            self.summary['has_errors'] += 1
            status = "[ERROR]"
        else:
            self.summary['has_warnings'] += 1
            status = "[WARN]"

        if not info['has_readme']:
            self.summary['missing_readme'] += 1
        if not info['has_spec']:
            self.summary['missing_spec'] += 1
        if svg_warnings:
            self.summary['svg_issues'] += 1

        # Print result
        print(f"{status} {info['name']}")
        print(f"   路径: {project_path}")
        print(
            f"   格式: {info['format_name']} | SVG: {info['svg_count']} 个文件 | 日期: {info['date_formatted']}")

        if errors:
            print(f"   [ERROR] 错误 ({len(errors)}):")
            for error in errors:
                print(f"      - {error}")

        if warnings or svg_warnings:
            all_warnings = warnings + svg_warnings
            print(f"   [WARN] 警告 ({len(all_warnings)}):")
            for warning in all_warnings[:3]:  # Only show first 3 warnings
                print(f"      - {warning}")
            if len(all_warnings) > 3:
                print(f"      ... 等 {len(all_warnings) - 3} 个更多警告")

        print()

        return result

    def print_summary(self) -> None:
        """Print a summary of validation results."""
        print("\n" + "=" * 80)
        print("[汇总] 校验汇总")
        print("=" * 80)

        print(f"\n项目总数: {self.summary['total']}")
        print(
            f"  [OK] 完全有效: {self.summary['valid']} ({self._percentage(self.summary['valid'])}%)")
        print(
            f"  [WARN] 有警告: {self.summary['has_warnings']} ({self._percentage(self.summary['has_warnings'])}%)")
        print(
            f"  [ERROR] 有错误: {self.summary['has_errors']} ({self._percentage(self.summary['has_errors'])}%)")

        print(f"\n常见问题:")
        print(f"  缺少 README.md: {self.summary['missing_readme']} 个项目")
        print(f"  缺少设计规范: {self.summary['missing_spec']} 个项目")
        print(f"  SVG 格式问题: {self.summary['svg_issues']} 个项目")

        # Group statistics by format
        format_stats = defaultdict(int)
        for result in self.results:
            format_stats[result['format']] += 1

        if format_stats:
            print(f"\n画布格式分布:")
            for fmt, count in sorted(format_stats.items(), key=lambda x: x[1], reverse=True):
                print(f"  {fmt}: {count} 个项目")

        # Provide fix suggestions
        if self.summary['has_errors'] > 0 or self.summary['has_warnings'] > 0:
            print(f"\n[建议] 修复建议:")

            if self.summary['missing_readme'] > 0:
                print(f"  1. 为缺少 README 的项目创建文档")
                print(
                    f"     参考: examples/google_annual_report_ppt169_20251116/README.md")

            if self.summary['svg_issues'] > 0:
                print(f"  2. 检查并修正 SVG viewBox 设置")
                print(f"     确保与画布格式一致")

            if self.summary['missing_spec'] > 0:
                print(f"  3. 添加设计规范文件")

    def _percentage(self, count: int) -> int:
        """Calculate percentage"""
        if self.summary['total'] == 0:
            return 0
        return int(count / self.summary['total'] * 100)

    def export_report(self, output_file: str = 'validation_report.txt') -> None:
        """
        Export validation report to file

        Args:
            output_file: Output file path
        """
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("PPT Master 项目校验报告\n")
            f.write("=" * 80 + "\n\n")

            for result in self.results:
                status = "[OK] 有效" if result['is_valid'] and not result['warnings'] else \
                    "[ERROR] 错误" if result['errors'] else "[WARN] 警告"

                f.write(f"{status} - {result['name']}\n")
                f.write(f"路径: {result['path']}\n")
                f.write(
                    f"格式: {result['format']} | SVG: {result['svg_count']} 个文件\n")

                if result['errors']:
                    f.write(f"\n错误:\n")
                    for error in result['errors']:
                        f.write(f"  - {error}\n")

                if result['warnings']:
                    f.write(f"\n警告:\n")
                    for warning in result['warnings']:
                        f.write(f"  - {warning}\n")

                f.write("\n" + "-" * 80 + "\n\n")

            # Write summary
            f.write("\n" + "=" * 80 + "\n")
            f.write("校验汇总\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"项目总数: {self.summary['total']}\n")
            f.write(f"完全有效: {self.summary['valid']}\n")
            f.write(f"有警告: {self.summary['has_warnings']}\n")
            f.write(f"有错误: {self.summary['has_errors']}\n")

        print(f"\n[报告] 校验报告已导出: {output_file}")


def main() -> None:
    """Run the CLI entry point."""
    if len(sys.argv) < 2:
        print("PPT Master - 批量项目校验工具\n")
        print("用法:")
        print("  python scripts/batch_validate.py <目录>")
        print("  python scripts/batch_validate.py <目录1> <目录2> ...")
        print("  python scripts/batch_validate.py --all")
        print("\n示例:")
        print("  python scripts/batch_validate.py examples")
        print("  python scripts/batch_validate.py projects")
        print("  python scripts/batch_validate.py examples projects")
        print("  python scripts/batch_validate.py --all")
        sys.exit(0)

    validator = BatchValidator()

    # Process arguments
    if '--all' in sys.argv:
        directories = ['examples', 'projects']
    else:
        directories = [arg for arg in sys.argv[1:] if not arg.startswith('--')]

    # Validate each directory
    for directory in directories:
        if Path(directory).exists():
            validator.validate_directory(directory)
        else:
            print(f"[WARN] 跳过不存在的目录: {directory}\n")

    # Print summary
    validator.print_summary()

    # Export report (if specified)
    if '--export' in sys.argv:
        output_file = 'validation_report.txt'
        if '--output' in sys.argv:
            idx = sys.argv.index('--output')
            if idx + 1 < len(sys.argv):
                output_file = sys.argv[idx + 1]
        validator.export_report(output_file)

    # Return exit code
    if validator.summary['has_errors'] > 0:
        sys.exit(1)
    elif validator.summary['has_warnings'] > 0:
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()
