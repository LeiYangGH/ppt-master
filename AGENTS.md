# AGENTS.md

PPT Master — AI 驱动的多角色协作演示文稿生成系统。

> **本文件仅为入口指引，不包含任何工作流规范。** 所有 PPT 生成任务的权威规则、角色定义、串行步骤、质量关卡和导出流程均位于下方的 SKILL.md 中。

## 必读

**在任何 PPT 任务之前，你必须首先完整阅读 `skills/ppt-master/SKILL.md`** — 它是项目创建、角色切换、串行执行、质量关卡、后处理和导出的唯一权威来源。

- 独立模板创建：[`workflows/create-template.md`](skills/ppt-master/workflows/create-template.md)
- 图表坐标校准：[`workflows/verify-charts.md`](skills/ppt-master/workflows/verify-charts.md)

## 核心目录

| 目录 | 用途 |
|------|------|
| `skills/ppt-master/` | 技能包根目录（SKILL.md、脚本、模板、参考规范） |
| `skills/ppt-master/references/` | 角色定义（Strategist / Image_Generator / Executor）和技术约束 |
| `skills/ppt-master/scripts/` | 可运行工具脚本（项目管理、图片生成、SVG 质检、导出等） |
| `skills/ppt-master/templates/` | 布局模板、图表模板、图标库 |
| `examples/` | 已完成的示例项目（可供参考风格和结构） |
| `projects/` | 用户项目工作区（运行时产出目录） |

## 补充约束

以下规则在 SKILL.md 之外，作为 AI 智能体的入口级提醒：

- **AGENTS.md 不是规范副本** — 若本文件内容与 SKILL.md 冲突，以 SKILL.md 为准。不要将本文件中的摘要视为完整规则。
- **项目性质** — 此仓库是工作流/技能包，不是应用程序或服务脚手架。不要默认创建 `tests/`、CI/CD 等通用工程结构，除非用户明确要求。
- **参考示例** — 需要理解风格或结构时，可浏览 `examples/` 下的已完成项目，但不要将示例内容直接复制到用户项目中。
