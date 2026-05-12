# PPT Master Workspace

- Canvas format: ppt169

## Directories

- `sources/`: 项目素材（用户手动放入）
- `svg_output/`: 原始 SVG 输出
- `svg_final/`: 后处理后的 SVG 输出
- `images/`: 最终用于 PPT 的图片（仅已采纳、已重命名为描述性名称的图片）
- `downloads/`: web_search 暂存区（哈希名原始图片与搜索快照，审阅后用 --adopt 晋升到 images/）
- `notes/`: 演讲备注
- `templates/`: 项目模板
- `exports/`: 原生 PPTX 导出（带时间戳）
- `backup/<timestamp>/`: SVG 快照 + svg_output/ 归档（导出时自动创建，旧时间戳可安全删除）
