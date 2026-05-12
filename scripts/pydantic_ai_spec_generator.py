#!/usr/bin/env python
"""
Pydantic-AI 结构化配置生成示例

本脚本是 spec_lock.json 生成的备用方案/示例代码，主要用于：
1. 展示如何使用 Pydantic-AI 生成结构化配置
2. 作为脱离 AI IDE 环境时的备用生成工具
3. 未来完全 agent 应用开发的参考实现

当前推荐方案：
  在 AI IDE 环境中，由 Strategist 直接输出 spec_lock.json，
  然后使用 validate_spec.py 进行校验。这样可以保持上下文连贯性。

本脚本的局限性：
  - 调用外部 LLM 时无法获取 AI IDE 的完整上下文
  - 无法注入项目状态、设计理由等隐性信息
  - 生成质量依赖于提示词的完整性

用法：
    # 验证现有配置
    python scripts/pydantic_ai_spec_generator.py --validate workspace/spec_lock.json
    
    # 生成配置（需要配置 LLM API）
    python scripts/pydantic_ai_spec_generator.py --generate "项目描述..."
"""

import os
import json
import sys
from pathlib import Path

# Add repo root to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pydantic_ai import Agent
from scripts.spec_models import SpecLock


def create_spec_generator_agent():
    """创建用于生成结构化配置的 Pydantic-AI Agent"""
    
    # 定义系统提示
    system_prompt = """你是一个专业的 PPT 设计规范生成器。

你的任务是根据用户提供的项目描述，生成一个完整的、结构化的 PPT 设计规范配置。

配置必须包含以下部分：
1. project: 项目信息（名称、描述、受众、风格等）
2. canvas: 画布配置（尺寸、格式等）
3. colors: 颜色配置（主色、强调色、文字色等）
4. typography: 字体配置（字体族、字号等）
5. icons: 图标配置（图标库、可用图标等）
6. images: 图片配置（图片映射）
7. page_rhythm: 页面节奏配置
8. content_outline: 内容大纲
9. technical_constraints: 技术约束
10. forbidden: 禁止项列表

要求：
- 所有颜色必须使用 HEX 格式（如 #FFFFFF）
- 字号必须在 8-120 范围内
- viewBox 格式必须为 "0 0 width height"
- 配置必须符合 Pydantic 模型定义的约束
- 输出格式化的 JSON（indent=2）

请根据用户提供的项目描述，生成完整的设计规范配置。"""
    
    # 创建 Agent
    agent = Agent(
        'openai:gpt-4o',  # 或其他支持的模型
        output_type=SpecLock,
        system_prompt=system_prompt
    )
    
    return agent


def generate_spec_from_description(description: str, output_path: str = None):
    """根据项目描述生成结构化配置
    
    Args:
        description: 项目描述
        output_path: 输出文件路径（可选）
    
    Returns:
        生成的 SpecLock 对象
    """
    
    agent = create_spec_generator_agent()
    
    # 生成配置
    prompt = f"""请根据以下项目描述生成完整的 PPT 设计规范配置：

{description}

要求：
1. 配置必须完整，包含所有必要的部分
2. 颜色使用 HEX 格式
3. 字号合理（标题 > 正文 > 注释）
4. 内容大纲详细，包含每页的布局和内容
5. 技术约束完整
"""
    
    result = agent.run_sync(prompt)
    spec = result.output
    
    # 如果指定了输出路径，保存到文件
    if output_path:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 使用格式化 JSON 输出
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(spec.to_json(indent=2))
        
        print(f"配置已保存到: {output_file}")
    
    return spec


def load_and_validate_spec(json_path: str) -> SpecLock:
    """加载并验证配置文件
    
    Args:
        json_path: JSON 配置文件路径
    
    Returns:
        验证后的 SpecLock 对象
    """
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 使用 Pydantic 模型验证
    spec = SpecLock(**data)
    
    print(f"配置验证成功: {json_path}")
    print(f"  项目名称: {spec.project.name}")
    print(f"  画布尺寸: {spec.canvas.width}x{spec.canvas.height}")
    print(f"  主色: {spec.colors.primary}")
    print(f"  正文字号: {spec.typography.body}")
    
    return spec


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='使用 Pydantic-AI 生成结构化配置')
    parser.add_argument('--generate', '-g', help='根据描述生成配置')
    parser.add_argument('--validate', '-v', help='验证配置文件')
    parser.add_argument('--output', '-o', help='输出文件路径')
    
    args = parser.parse_args()
    
    if args.validate:
        # 验证配置文件
        spec = load_and_validate_spec(args.validate)
        print("\n配置内容预览:")
        print(spec.to_json(indent=2)[:500] + "...")
    
    elif args.generate:
        # 生成配置
        output_path = args.output or 'workspace/spec_lock.json'
        spec = generate_spec_from_description(args.generate, output_path)
        print("\n生成的配置:")
        print(spec.to_json(indent=2)[:500] + "...")
    
    else:
        # 默认：验证现有配置
        default_path = 'workspace/spec_lock.json'
        if Path(default_path).exists():
            print(f"验证默认配置: {default_path}")
            spec = load_and_validate_spec(default_path)
            print("\n配置验证通过!")
        else:
            print(f"未找到默认配置文件: {default_path}")
            print("请使用 --generate 生成配置，或 --validate 验证指定文件")


if __name__ == '__main__':
    main()
