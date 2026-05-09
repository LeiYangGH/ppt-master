---
description: 使用 svg_position_calculator.py 验证图表坐标与设计规格的一致性
---

# 图表验证工作流

> 独立的后生成步骤。在包含数据图表的演示文稿完成SVG生成后、后处理与导出前运行。捕捉AI模型将数据映射到像素位置时常见的10-50px坐标误差。

本工作流**独立运行**：读取 `design_spec.md` 和已生成的SVG，然后运行计算器脚本 — 无需上游对话上下文。可在新会话中安全调用。

## 何时运行

- 演示文稿包含一个或多个数据可视化图表，类型属于**单次** `svg_position_calculator.py calc` 调用所支持的集合。支持集由计算器的CLI子命令（`bar`、`line`、`pie`、`radar`）及其单系列模型固定 — 具体 `charts_index.json` 键见步骤1。
- SVG已生成到 `<project_path>/svg_output/` 且 `svg_quality_checker.py` 已通过。
- 后处理（`finalize_svg.py`、`svg_to_pptx.py`）**尚未**运行。

复合/衍生图表类型（多系列、堆叠、正负差值、镜像、双轴、累积叠加）无法通过一次calc调用校准，超出范围。非XY数据可视化（树状图/仪表盘/漏斗图/热力图/矩阵/气泡图/箱线图）和信息图/图表/框架/地图同样超出范围。

---

## 步骤 1：从设计规格构建页面列表

读取 `<project_path>/design_spec.md` §VII 可视化参考列表（权威演示文稿计划；与§IX页面大纲交叉核对），并**严格过滤**为以下计算器支持集合。范围外的内容不要纳入列表，即使§VII将其标记为图表。

| 计算器子命令 | 范围内 `charts_index.json` 键 | 备注 |
|-------------|-------------------------------|------|
| `calc bar`  | `bar_chart`、`horizontal_bar_chart` | 后者加 `--horizontal`。仅单系列。 |
| `calc line` | `line_chart`、`area_chart`、`scatter_chart` | 面积图使用线输出作为上边界，然后闭包到 `y_max`。 |
| `calc pie`  | `pie_chart`、`donut_chart` | 环形图：传 `--inner-radius`。 |
| `calc radar`| `radar_chart` | 独立子命令 — 不在 `calc pie` 下。 |

**可通过重复调用+累积预计算验证**（见下方[堆叠配方](#堆叠配方)）：

- `stacked_bar_chart`、`stacked_area_chart` — 纳入步骤1列表，标记 `type=stacked-bar` / `type=stacked-area`，按配方验证。

**超出范围**（无单调用模型且无干净的重复调用配方 — 静默跳过）：

- 多系列/正负/配对/双轴柱线图：`grouped_bar_chart`、`butterfly_chart`、`waterfall_chart`、`bullet_chart`、`dumbbell_chart`、`pareto_chart`、`dual_axis_line_chart`
- 非XY数据可视化：`treemap_chart`、`gauge_chart`、`progress_bar_chart`、`funnel_chart`、`matrix_2x2`、`bubble_chart`、`heatmap_chart`、`box_plot_chart`、`kpi_cards`
- `charts_index.json` 中 `process` / `strategy` / `architecture` / `infographic` / `table` 类别下的所有内容

结果列表：

```
P03 03_market_share.svg  type=bar
P07 07_growth.svg        type=line
P11 11_share_split.svg   type=pie
```

如§VII缺失（遗留项目/自由结构演示文稿），跳过本工作流并报告："design_spec.md 无 §VII — 图表页面无法权威枚举，verify-charts 已跳过"。不得回退到从SVG内容猜测；那会重新引入本工作流旨在消除的静默跳过问题。

如过滤后列表为空，输出 `verify-charts: 规格未声明计算器支持的图表页面，无需验证` 并停止。

---

## 步骤 2：逐页 — 读取SVG、运行计算器、对比、更新

对步骤1列表中的每一页：

1. 读取 `<project_path>/svg_output/<page>.svg`。
2. 定位绑图区定义：
   - 首选：Executor放置的 `<!-- chart-plot-area: ... -->` 标记（见 [executor.md §4.1](../references/executor.md)）。直接读取坐标。
   - 如缺失：从SVG的轴线（矩形图表）或中心/半径元素（径向图表）推导绑图区。然后**将标记回写到SVG**，避免后续运行重复此开销。
3. 从SVG的 `<text>` 标签/值元素读取数据系列。
4. **读取轴刻度标签（仅柱状图）。** 定位数值轴上的 `<text>` 元素 — 水平柱状图为X轴标签，垂直柱状图为Y轴标签。提取首尾刻度值确定轴范围（如 `0%` 到 `120%` → 范围 `0,120`）。将此范围作为 `--value-range "0,120"` 传给计算器。如SVG无显式刻度标签（仅有数据标签，无网格线），省略 `--value-range` 让计算器自动归一化 — 但在回执中标注 `scale=auto (no ticks)`。
5. 运行对应的计算器命令：

   ```powershell
   # bar_chart / horizontal_bar_chart（后者加 --horizontal）
   # 重要：始终从轴刻度标签传递 --value-range（步骤4）
   python skills/ppt-master/scripts/svg_position_calculator.py calc bar \
     --data "Label1:Value1,Label2:Value2" --area "x_min,y_min,x_max,y_max" \
     --bar-width 120 --value-range "0,axis_max"

   # line_chart / area_chart / scatter_chart — 面积图使用线输出作为上边界，然后闭包到y_max
   python skills/ppt-master/scripts/svg_position_calculator.py calc line \
     --data "x1:y1,x2:y2,..." --area "x_min,y_min,x_max,y_max" --y-range "0,max"

   # pie_chart
   python skills/ppt-master/scripts/svg_position_calculator.py calc pie \
     --data "Slice1:Value1,Slice2:Value2" --center "cx,cy" --radius 200

   # donut_chart（带inner-radius的饼图）
   python skills/ppt-master/scripts/svg_position_calculator.py calc pie \
     --data "Slice1:Value1,Slice2:Value2" --center "cx,cy" --radius 200 --inner-radius 120

   # radar_chart（独立子命令）
   python skills/ppt-master/scripts/svg_position_calculator.py calc radar \
     --data "Dim1:Value1,Dim2:Value2,Dim3:Value3" --center "cx,cy" --radius 200
   ```

   面积图填充路径闭包到绑图区底边：

   ```svg
   M first_x,first_y ... L last_x,last_y L last_x,y_max L first_x,y_max Z
   ```

6. **感知比例的对比。** 将计算器输出与SVG现有坐标对比。在判定不匹配前，确认计算器输出头部显示 `Value scale: axis ticks (...)` 与SVG绘制的轴一致。如显示 `auto (max*1.1)` 但图表有显式轴刻度，说明计算器未使用 `--value-range` 调用 — 回到步骤4用正确范围重新运行。**不得用比例不匹配的输出更新SVG。** 仅在确认比例匹配且坐标确实不同时更新SVG属性。手动更新（不得使用正则/批量替换 — 坐标是位置敏感的，容易错位）。

更新任何页面后，重新运行质量检查器确认未引入问题：

```powershell
python skills/ppt-master/scripts/svg_quality_checker.py <project_path>
```

---

## 堆叠配方

`stacked_bar_chart` 和 `stacked_area_chart` 非单次调用，但可干净地归约为对现有图元的重复调用。操作者已计算累积值来绘制SVG — verify-charts复用它们。

**堆叠柱状图** — 对N个堆叠系列在同一x类别上，运行 `calc bar` N次。传入每个段的**高度**作为数据值，并将该类别下方所有段的像素高度之和从 `--area` 的 `y_max` 中减去。将每个段的 `(x, y, width, height)` 与SVG对比。

```powershell
# 示例：类别"Q1"处双系列堆叠，底部=30，顶部=20，绑图区y从100到500
# 运行1 — 底部段（原点 = 基线）
python skills/ppt-master/scripts/svg_position_calculator.py calc bar \
  --data "Q1:30,Q2:..." --area "x_min,100,x_max,500" \
  --bar-width 80 --value-range "0,axis_max"
# 运行2 — 顶部段（原点上移底部段的像素高度）
python skills/ppt-master/scripts/svg_position_calculator.py calc bar \
  --data "Q1:20,Q2:..." --area "x_min,100,x_max,<500 - bottom_height_px>" \
  --bar-width 80 --value-range "0,axis_max"
```

**堆叠面积图** — 对N个堆叠系列，对**累积**y值运行 `calc line` N次（系列1原始值；系列2 = 系列1+系列2；…）。每次调用得出一个条带的上边界。每个条带的SVG路径闭包到**前一个**条带的上边界（而非 `y_max`）。

如堆叠页面的段位置无法归约为此配方（如负值段、百分比堆叠但总计非100），在回执中标记 `manual-verify` 并手动检查 — 不得静默通过。

---

## 步骤 3：逐页回执

对步骤1列表中的每一页输出一行。回执数量必须等于步骤1列表长度 — 这是关卡关闭产物。

```
verify-charts: 03_market_share.svg | type=bar          | scale=0-100 (from ticks) | calc=ran | svg=updated
verify-charts: 07_growth.svg       | type=line         | scale=N/A                | calc=ran | svg=unchanged (already accurate)
verify-charts: 11_share_split.svg  | type=pie          | scale=N/A                | calc=ran | svg=updated | marker=added (was missing)
verify-charts: 14_revenue_mix.svg  | type=stacked-bar  | scale=0-200 (from ticks) | calc=ran×3 | svg=updated (per Stacked recipe)
verify-charts: 15_unit_economics.svg | type=stacked-area | scale=N/A | manual-verify | reason=percent-stacked, recipe does not apply
```

---

## 验证后

继续后处理与导出（[SKILL.md 步骤7](../SKILL.md)）：

```powershell
python skills/ppt-master/scripts/notes_all_md_split.py <project_path>
python skills/ppt-master/scripts/finalize_svg.py <project_path>
python skills/ppt-master/scripts/svg_to_pptx.py <project_path> -s final
```
