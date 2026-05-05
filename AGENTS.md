# AGENTS.md

此文件是通用 AI 智能体的项目入口。

在任何 PPT 生成任务之前，**你必须首先阅读 [`skills/ppt-master/SKILL.md`](skills/ppt-master/SKILL.md)** — 这是关于项目创建、角色切换、串行执行、质量关卡、后处理和导出的权威工作流程。

## 项目概述

PPT Master 是一个 AI 驱动的演示文稿生成系统。多角色协作（Strategist → Image_Generator → Executor）将 Markdown 源文档转换为具有真实 PowerPoint 形状（DrawingML）的原生可编辑 PPTX。

**核心流程**：`源文档 → 创建项目 → 模板选项 → Strategist 八项确认 → [Image_Generator] → Executor → 质量检查 → 后处理 → 导出 PPTX`

> 包含数据图表的幻灯片：在执行器和后处理步骤之间运行独立的 [`verify-charts`](skills/ppt-master/workflows/verify-charts.md) 工作流程以校准图表坐标。

## 执行要求

- 在开始 PPT 任务之前阅读 [`skills/ppt-master/SKILL.md`](skills/ppt-master/SKILL.md)。
- 对于独立模板创建，阅读 [`skills/ppt-master/workflows/create-template.md`](skills/ppt-master/workflows/create-template.md)。
- 角色特定规则位于 [`skills/ppt-master/references/`](skills/ppt-master/references/)。
- 技术 SVG/PPT 约束位于 [`skills/ppt-master/references/shared-standards.md`](skills/ppt-master/references/shared-standards.md)。
- 画布选择位于 [`skills/ppt-master/references/canvas-formats.md`](skills/ppt-master/references/canvas-formats.md)。
- 图标库详细信息位于 [`skills/ppt-master/templates/icons/README.md`](skills/ppt-master/templates/icons/README.md)。

## 兼容性边界

- 此仓库是一个工作流程/技能包，而不是应用程序或服务脚手架。
- 不要假设 `.worktrees/`、`tests/` 或强制分支设置等约定，除非用户明确要求。
- 与通用编码技能冲突时，优先考虑此仓库中的 [`skills/ppt-master/SKILL.md`](skills/ppt-master/SKILL.md) 和此文件。

## 命令快速参考

仅为便捷摘要 — 完整工作流程见 [`skills/ppt-master/SKILL.md`](skills/ppt-master/SKILL.md)。

```powershell
# 项目管理
python skills/ppt-master/scripts/project_manager.py init <project_name> --format ppt169
python skills/ppt-master/scripts/project_manager.py import-sources <project_path> <source_files_or_URLs...> --move
python skills/ppt-master/scripts/project_manager.py validate <project_path>

# 图像工具和 SVG 质量检查
python skills/ppt-master/scripts/analyze_images.py <project_path>/images
python skills/ppt-master/scripts/image_gen.py "prompt" --aspect_ratio 16:9 --image_size 1K -o <project_path>/images
python skills/ppt-master/scripts/svg_quality_checker.py <project_path>

# 后处理流程：按顺序运行，一次一个命令
python skills/ppt-master/scripts/total_md_split.py <project_path>
python skills/ppt-master/scripts/finalize_svg.py <project_path>
python skills/ppt-master/scripts/svg_to_pptx.py <project_path> -s final
```

### 图表校准（独立 — 按需运行，不属于主流程）

适用于包含数据图表的幻灯片。完整工作流程：[`workflows/verify-charts.md`](skills/ppt-master/workflows/verify-charts.md)。

```powershell
# 步骤 1：通过绘图区域标记枚举图表页面
Get-ChildItem -Path "<project_path>\svg_output\*.svg" | Select-String -Pattern "chart-plot-area" -List | Select-Object -ExpandProperty Path

# 步骤 2：每页运行计算器（图表类型驱动子命令）
python skills/ppt-master/scripts/svg_position_calculator.py calc bar   --data "L1:V1,L2:V2" --area "x_min,y_min,x_max,y_max" --bar-width 120 --value-range "0,axis_max"
python skills/ppt-master/scripts/svg_position_calculator.py calc line  --data "x1:y1,x2:y2" --area "x_min,y_min,x_max,y_max" --y-range "0,max"
python skills/ppt-master/scripts/svg_position_calculator.py calc pie   --data "A:35,B:25" --center "cx,cy" --radius 200 [--inner-radius 120]
python skills/ppt-master/scripts/svg_position_calculator.py calc radar --data "D1:V1,D2:V2,D3:V3" --center "cx,cy" --radius 200
```

## 核心目录

- `skills/ppt-master/SKILL.md` — 主要工作流程权威。
- `skills/ppt-master/references/` — 角色定义和技术规范。
- `skills/ppt-master/scripts/` — 可运行工具脚本。
- `skills/ppt-master/scripts/docs/` — 专题脚本文档。
- `skills/ppt-master/templates/` — 布局模板、图表模板、图标库。
- `examples/` — 示例项目。
- `projects/` — 用户项目工作区。
