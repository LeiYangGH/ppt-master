#!/usr/bin/env python
"""
结构化配置校验工具

验证 spec_lock.json 文件是否符合 schema 定义。

用法：
    python scripts/validate_spec.py workspace/spec_lock.json
    python scripts/validate_spec.py  # 默认验证 workspace/spec_lock.json
"""

import sys
import json
from pathlib import Path

# Add repo root to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.spec_models import SpecLock


def validate_spec_file(json_path: str) -> bool:
    """验证 spec_lock.json 文件
    
    Args:
        json_path: JSON 配置文件路径
    
    Returns:
        验证是否通过
    """
    path = Path(json_path)
    
    if not path.exists():
        print(f"错误: 文件不存在: {path}")
        return False
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"错误: JSON 格式无效: {e}")
        return False
    
    try:
        # 使用 Pydantic 模型验证
        spec = SpecLock(**data)
        
        print(f"✓ 配置验证成功: {path}")
        print(f"  项目名称: {spec.project.name}")
        print(f"  画布尺寸: {spec.canvas.width}x{spec.canvas.height}")
        print(f"  主色: {spec.colors.primary}")
        print(f"  正文字号: {spec.typography.body}")
        print(f"  总页数: {spec.project.total_pages}")
        
        # 检查是否为格式化输出（非紧凑格式）
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 简单检查：格式化 JSON 通常包含换行和缩进
        if '\n' not in content:
            print("警告: JSON 文件可能是紧凑格式，建议使用格式化输出 (indent=2)")
        
        return True
        
    except Exception as e:
        print(f"错误: 配置验证失败: {e}")
        
        # 尝试提供更详细的错误信息
        if hasattr(e, 'errors'):
            print("\n详细错误:")
            for error in e.errors():
                print(f"  - {error.get('loc', '未知位置')}: {error.get('msg', '未知错误')}")
        
        return False


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='验证 spec_lock.json 配置文件')
    parser.add_argument(
        'json_path',
        nargs='?',
        default='workspace/spec_lock.json',
        help='JSON 配置文件路径（默认: workspace/spec_lock.json）'
    )
    
    args = parser.parse_args()
    
    success = validate_spec_file(args.json_path)
    
    if success:
        print("\n验证通过!")
        sys.exit(0)
    else:
        print("\n验证失败!")
        sys.exit(1)


if __name__ == '__main__':
    main()
