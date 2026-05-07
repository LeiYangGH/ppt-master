# SVG 流水线工具

涵盖后处理、SVG 校验、演讲者备注和 PPTX 导出。

## 推荐流水线

按顺序执行以下步骤：

```bash
python scripts/total_md_split.py <project_path>
python scripts/finalize_svg.py <project_path>
python scripts/svg_to_pptx.py <project_path> -s final
```

## `finalize_svg.py`

统一后处理入口。这是运行 SVG 清理的首选方式。

它聚合了：
- `embed_icons.py`
- `crop_images.py`
- `fix_image_aspect.py`
- `embed_images.py`
- `flatten_tspan.py`
- `svg_rect_to_path.py`

## `svg_to_pptx.py`

将项目 SVG 转换为 PPTX。

```bash
python scripts/svg_to_pptx.py <project_path> -s final
python scripts/svg_to_pptx.py <project_path> -s final --only native
python scripts/svg_to_pptx.py <project_path> -s final --only legacy
python scripts/svg_to_pptx.py <project_path> -s final --no-notes
python scripts/svg_to_pptx.py <project_path> -t none
python scripts/svg_to_pptx.py <project_path> -s final --auto-advance 3
python scripts/svg_to_pptx.py <project_path> -s final --animation mixed --animation-duration 0.8
```

行为说明：
- 默认输出：
  - `exports/<project_name>_<timestamp>.pptx` — 主文件，原生可编辑 PPTX
  - `backup/<timestamp>/<project_name>_svg.pptx` — SVG 快照，用于视觉参考
  - `backup/<timestamp>/svg_output/` — Executor SVG 源码副本，不重新运行 LLM 也能通过 `finalize_svg → svg_to_pptx` 重建 PPTX
- 显式指定 `-o/--output` 会在目标路径旁保留传统并排 `_svg.pptx`，并跳过 `backup/`
- 推荐源目录：`svg_final/`
- 演讲者备注默认自动嵌入，加 `--no-notes` 可禁用
- 页面切换由 `-t/--transition` 控制；元素入场动画由 `-a/--animation` 控制
- 元素动画作用于顶层 SVG `<g id="...">` 组，按 z 轴顺序执行；建议每页 3–8 个内容组。页面装饰（背景 / 页眉 / 页脚 / 装饰 / 水印 / 页码，按 id 标识）自动跳过
- 启动模式由 `--animation-trigger` 设置，对应 PowerPoint 的"开始"下拉框：`after-previous`（默认，幻灯片进入时按 `--animation-stagger` 间隔级联）、`on-click`（点击触发）、`with-previous`（幻灯片进入时同时启动）
- 无顶层分组的扁平 SVG 根节点最多回退到 8 个可见图元；超过此数量则跳过该页动画
- `mixed` 为确定性模式：每页第一个动画组使用 `fade`，后续组在整个演示文稿中循环使用精选可见效果池；`random` 从同一池中随机采样
- `--animation-duration` 控制单个元素入场时长；`--animation-stagger` 在 `after-previous` 模式下增加元素间间隔

依赖：

```bash
pip install python-pptx
```

## `total_md_split.py`

将 `total.md` 拆分为每页讲稿文件。

```bash
python scripts/total_md_split.py <project_path>
python scripts/total_md_split.py <project_path> -o <output_directory>
python scripts/total_md_split.py <project_path> -q
```

要求：
- 每节以 `# ` 开头
- 标题文字与 SVG 文件名匹配
- 节之间以 `---` 分隔

## `svg_quality_checker.py`

校验 SVG 技术合规性。

```bash
python scripts/svg_quality_checker.py examples/project/svg_output/01_cover.svg
python scripts/svg_quality_checker.py examples/project/svg_output
python scripts/svg_quality_checker.py examples/project
python scripts/svg_quality_checker.py examples/project --format ppt169
python scripts/svg_quality_checker.py --all examples
python scripts/svg_quality_checker.py examples/project --export
```

检查项：
- `viewBox`
- 禁用元素
- width/height 一致性
- 换行结构

## `svg_position_calculator.py`

SVG 生成后，分析并复核支持的图表坐标。

在 `svg_quality_checker.py` 通过后使用，且仅支持以下图表类型：`bar`、`pie` / `donut`、`radar`、`line` / `area` / `scatter`、`grid`。面积图无独立计算模式：先用 `calc line` 算出上边界点，再在 SVG 中将填充区域闭合到绘图区底部基线（`y_max`）。

### 计算预期坐标

```bash
python scripts/svg_position_calculator.py calc bar --data "A:185,B:142" --area "130,155,1200,480" --bar-width 120
python scripts/svg_position_calculator.py calc line --data "0:50,10:80,20:120" --area "120,120,1200,600" --y-range "0,150"
python scripts/svg_position_calculator.py calc pie --data "A:35,B:25,C:20" --center "420,400" --radius 200
python scripts/svg_position_calculator.py calc grid --rows 2 --cols 3 --area "50,150,1230,670"
```

面积图使用 line 输出作为上边界：

```svg
M first_x,first_y ... L last_x,last_y L last_x,y_max L first_x,y_max Z
```

手动将计算器输出与生成 SVG 中已有坐标对比。若不一致，按 `calc` 输出更新 SVG，重新运行 `svg_quality_checker.py`，再重复坐标复核。该工具故意不自动改写 SVG 文件。

### 分析（检查已有 SVG）

```bash
python scripts/svg_position_calculator.py analyze <svg_file>
```

SVG 生成后，当手动对比需要更多上下文时，用此命令检查已有 SVG 几何结构。

## 高级独立工具

### `flatten_tspan.py`

```bash
python scripts/svg_finalize/flatten_tspan.py examples/<project>/svg_output
python scripts/svg_finalize/flatten_tspan.py path/to/input.svg path/to/output.svg
```

### `svg_rect_to_path.py`

```bash
python scripts/svg_finalize/svg_rect_to_path.py <project_path>
python scripts/svg_finalize/svg_rect_to_path.py <project_path> -s final
python scripts/svg_finalize/svg_rect_to_path.py path/to/file.svg
```

圆角需要保留到 PowerPoint 形状转换时使用。

### `fix_image_aspect.py`

```bash
python scripts/svg_finalize/fix_image_aspect.py path/to/slide.svg
python scripts/svg_finalize/fix_image_aspect.py 01_cover.svg 02_toc.svg
python scripts/svg_finalize/fix_image_aspect.py --dry-run path/to/slide.svg
```

嵌入图像在 PowerPoint 形状转换后拉伸时使用。

### `embed_icons.py`

```bash
python scripts/svg_finalize/embed_icons.py output.svg
python scripts/svg_finalize/embed_icons.py svg_output/*.svg
python scripts/svg_finalize/embed_icons.py --dry-run svg_output/*.svg
```

将 `<use data-icon="chunk-filled/name" .../>`、`<use data-icon="tabler-filled/name" .../>` 和 `<use data-icon="tabler-outline/name" .../>` 占位符替换为实际 SVG path 元素。用于 `finalize_svg.py` 之外的手动图标嵌入检查。

## PPT 兼容性规则

使用 PowerPoint 安全的透明度语法：

| 避免使用 | 改用 |
|------|-------------|
| `fill=\"rgba(...)\"` | `fill=\"#hex\"` + `fill-opacity` |
| `<g opacity=\"...\">` | 在每个子元素上设置 opacity |
| `<image opacity=\"...\">` | 叠加遮罩层 |

PowerPoint 同样不兼容：
- 基于 marker 的箭头
- 不支持的滤镜
- 未映射到 DrawingML 的原生 SVG 特性
