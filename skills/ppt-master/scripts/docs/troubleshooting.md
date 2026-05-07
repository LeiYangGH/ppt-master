# 故障排查

## 验证失败

1. 运行：

```powershell
python scripts/project_manager.py validate <project_path>
```

2. 修复验证器报告的文件缺失或目录无效问题。
3. 后处理或导出前重新验证。

## SVG 预览异常

1. 检查文件路径和文件名。
2. 确认命名规范一致。
3. 若浏览器直接打开文件不一致，通过本地服务器预览：

```powershell
python -m http.server --directory <svg_output_path> 8000
```

## 演讲者备注未拆分

检查 `total.md`：
- 标题必须以 `# ` 开头
- 标题文字须与 SVG 文件名匹配
- 节之间须以 `---` 分隔

然后重新运行：

```powershell
python scripts/total_md_split.py <project_path>
```

## PPT 导出质量异常

推荐顺序：

```powershell
python scripts/total_md_split.py <project_path>
python scripts/finalize_svg.py <project_path>
python scripts/svg_to_pptx.py <project_path> -s final
```

存在 `svg_final/` 时，不要直接从 `svg_output/` 导出。

## 依赖清单

大部分工具仅使用标准库。按需安装额外依赖：

```powershell
pip install -r requirements.txt
```

常用可选包：
- `python-pptx` — PPTX 导出
- `Pillow` — 图像处理
- `numpy` — 水印去除
- `PyMuPDF` — PDF 转换
- `google-genai` / `openai` — 图像生成后端
