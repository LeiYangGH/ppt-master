# 故障排查

## 验证失败

1. 运行：

```powershell
python scripts/project_manager.py validate <project_path>
```

2. 修复验证器报告的文件缺失或目录无效问题。
3. 后处理或导出前重新验证。

## 演讲者备注未拆分

检查 `notes_all.md`：
- 标题必须以 `# ` 开头
- 标题文字须与 SVG 文件名匹配
- 节之间须以 `---` 分隔

然后重新运行：

```powershell
python scripts/notes_all_md_split.py <project_path>
```

## PPT 导出质量异常

推荐顺序：

```powershell
python scripts/notes_all_md_split.py <project_path>
python scripts/finalize_svg.py <project_path>
python scripts/svg_to_pptx.py <project_path> -s final
```

存在 `svg_final/` 时，不要直接从 `svg_output/` 导出。

