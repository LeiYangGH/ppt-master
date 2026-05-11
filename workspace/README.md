# 工作区

PPT Master 的工作目录。

## 初始化工作区

```powershell
python scripts/project_manager.py init
```

## 目录结构

```
workspace/
├── README.md
├── state.md           # 状态文件（阶段进度、决策记录、错误日志、经验教训）
├── design_spec.md     # 设计规范
├── spec_lock.md       # 执行锁定
├── sources/           # 项目素材（用户手动放入）
├── images/            # 项目图片素材
├── notes/             # 工作笔记 (01_xxx.md, notes_all.md 等)
├── svg_output/        # Executor 生成的 SVG
├── svg_final/         # 后处理后的最终 SVG
├── templates/         # 项目级模板（可选）
├── exports/           # 导出的演示文稿
└── backup/            # 备份文件
```

工作区可处于不同阶段，不必包含全部目录。


## 状态文件

`workspace/state.md` 是工作区的状态文件，由 LLM 在工作流执行过程中自动读写：

| 章节 | 用途 |
|------|------|
| 当前项目 | 画布格式等基本信息 |
| 当前阶段 | 工作流进度 |
| 阶段清单 | 各阶段完成状态 |
| 当前页进度 | Executor 阶段的页码跟踪 |
| 决策记录 | 关键决策及原因 |
| 错误日志 | 错误及处理方式 |
| 经验教训 | 跨项目持久保留的经验 |
| 进度日志 | 时间戳追加式进度记录 |

- 该文件可手工编辑或删除
- 经验教训是跨项目的关键资产——LLM 在每个新项目启动时都会读取，避免重复犯错
