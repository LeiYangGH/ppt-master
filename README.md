# PPT Master — 中文本地化分支

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)

本项目是 [hugohe3/ppt-master](https://github.com/hugohe3/ppt-master) 的 fork，针对中文场景与本地 LLM 的使用做了简化和适配。

## 与上游的主要差异

| 维度 | 上游 | 本分支 |
|------|------|--------|
| 提示词语言 | 英文 | **中文优先**——角色定义、交互文案、spec_lock 字段说明等均中文化；SVG/DrawingML 等技术词汇保留英文 |
| LLM 依赖 | 依赖云端商业模型 API | **本地 LLM 优先**——工作流不绑定特定模型 API，支持本地部署的模型 |
| 运行环境 | 跨平台 Shell | **Windows PowerShell**——终端操作默认使用 PowerShell 命令 |
| 执行纪律 | 原版串行流程 | 在原版基础上强化了虚拟环境使用、文件直读直写等约束 |

> 完整的工作流、架构设计与脚本用法，请参阅 [`skills/ppt-master/SKILL.md`](skills/ppt-master/SKILL.md) 与 [`arch-design.md`](arch-design.md)。
