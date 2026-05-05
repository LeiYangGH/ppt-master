# 用户项目工作区

存放进行中的项目。

## 新建项目

```bash
python skills/ppt-master/scripts/project_manager.py init my_project --format ppt169
```

## 目录结构

```
project_name_format_YYYYMMDD/
├── README.md
├── design_spec.md
├── sources/          # 原始文件 / URL 存档 / 转换后的 Markdown 及其附件
├── images/           # 项目图片素材
├── notes/            # 工作笔记 (01_xxx.md, total.md 等)
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
