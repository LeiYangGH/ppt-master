# 用户项目工作区

存放进行中的项目。

## 新建项目

```powershell
python /scripts/project_manager.py init my_project --format ppt169
```

## 目录结构

```
project_name_format_YYYYMMDD/
├── README.md
├── design_spec.md
├── sources/          # 原始文件 / URL 存档 / 转换后的 Markdown 及其附件
├── images/           # 项目图片素材
├── notes/            # 工作笔记 (01_xxx.md, notes_all.md 等)
├── svg_output/       # Executor 生成的 SVG
├── svg_final/        # 后处理后的最终 SVG
├── templates/        # 项目级模板（可选）
├── *.pptx            # 导出的演示文稿
└── image_analysis.csv  # 图片扫描结果（可选）
```

项目可处于不同阶段，不必包含全部目录。

## 注意事项

- 本目录内容已被 `.gitignore` 排除
- 完成的项目可移至 `examples/` 分享
- 工作区外文件默认复制，工作区内文件直接移入 `sources/`

## 共享状态文件

`projects/` 根目录下有三个共享状态文件（三件套），由 LLM 在工作流执行过程中自动读写：

| 文件 | 用途 | 生命周期 |
|------|------|----------|
| `task_plan.md` | 当前项目、阶段进度、决策与错误日志 | 新项目 init 时重置 |
| `findings.md` | 当前项目发现 + 跨项目经验教训 | 经验教训持久保留 |
| `progress.md` | 时间戳追加式进度日志 | 持续追加 |

- 这些文件可手工编辑或删除。例如新项目开始时，可保留 `findings.md` 中的经验教训部分，清空其他内容。
- `findings.md` 的经验教训是跨项目的关键资产——LLM 在每个新项目启动时都会读取，避免重复犯错。
