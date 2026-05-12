# Executor 通用指南

> 风格专属内容见对应的 `executor-{style}.md`。技术约束见 `shared-standards.md`。

---

## 1. 模板遵循规则

如果项目中存在 `templates/`，则按模板结构执行：

| 页面类型 | 对应模板 | 遵循规则 |
|-----------|----------------------|-----------------|
| 封面 | `01_cover.svg` | 继承背景、装饰元素和版式结构；替换占位内容 |
| 章节页 | `02_chapter.svg` | 继承编号样式、标题位置和装饰元素 |
| 内容页 | `03_content.svg` | 继承页眉/页脚样式；**内容区可自由布局** |
| 结束页 | `04_ending.svg` | 继承背景、感谢语位置和联系方式布局 |
| 目录页 | `02_toc.svg` | **可选**：继承目录标题和列表样式 |

### 页面-模板映射声明（必填输出）

每生成一页前，都要输出该页使用的模板：

```
📝 **Template mapping**: `templates/01_cover.svg`（或 "None (free design)"）
🎯 **Adherence rules / layout strategy**: [具体说明]
```

- **内容页**：模板只定义页眉/页脚，内容区自由
- **无模板**：完全按 Design Spec 生成

---

## 2. 设计参数确认（必做）

在生成第一张 SVG 页面前，先输出一份确认清单：画布尺寸、正文字号、配色方案（primary/secondary/accent HEX）、字体方案。这样可防止规范与执行漂移。

### 2.1 每页重读 `spec_lock.json`

> 长文档在中后段容易因上下文压缩而偏离已声明的配色和图标。`spec_lock.json` 是执行时的唯一基准，每页都要重读。

**硬规则**：生成**每一页** SVG 前，都必须执行 `read_file <project_path>/spec_lock.json`。只能使用文件中的值，不能凭记忆。

**经验教训（强制读取）**：首次进入 Executor 阶段时，`read_file workspace/state.md` 中的经验教训章节，避免重复犯已记录的错误（如 tspan 语法、spec_lock 漂移模式等）。

**如果 `spec_lock.json` 缺失**：输出一次 `warning: spec_lock.json missing — generating without execution lock`，然后停止。新项目**必须**有这个文件（见 strategist.md §6 step 4）。

**禁止使用 lock 外的值**：

- 颜色（`fill` / `stroke` / `stop-color`）必须来自 `colors`
- 图标必须来自 `icons.inventory`，且图标库必须等于 `icons.library`
- 字体来自 `typography`：若声明了 `title_family` / `body_family` / `emphasis_family` / `code_family`，则优先使用；否则回退到 `font_family`
- 字号遵循以 `typography.body` 为锚点的**比例梯度**，不是固定菜单。允许中间值（如 40px 大数字、13px 注释），前提是其与 `body` 的比例落在该角色允许区间内（见 `spec_lock.json typography`）。超出所有区间时，必须先扩展 lock。
- 图片只能引用 `images` 中列出的文件，禁止自造文件名

如果某页需要的值不在 `spec_lock.json` 中，必须明确提出，不能默默编造。

**逐页布局节奏：`page_rhythm` 段**

每页绘制前，先查 `page_rhythm` 中该页对应的项（key 格式为 `P<NN>`），并套用对应布局纪律：

| 标签 | 布局纪律 |
|-----|-------------------|
| `structural` | 结构页（封面 / 章节 / 目录 / 结束页）。严格按对应模板执行 |
| `analytical` | 信息密集页。允许卡片网格、多列布局、KPI 仪表盘、表格和图表。这是默认模式 |
| `focal` | 低密度冲击页。避免**多卡片网格布局**，不要把内容做成多个并列圆角容器（如三卡、四卡 KPI、2×2 卡片矩阵）。应改用裸文本块、分隔线、留白或全幅图片。单个圆角元素（如主图圆角、标签、强调块）可以保留；限制的是网格结构，不是 `rx` 属性。比例由信息权重决定，不套固定比例。典型形式：大引语、单个大数字 + 一句解释、全幅图片 + 浮动说明、章节过渡页 |

> 如果没有节奏变化，页面很容易全部退化为卡片网格，产生“AI 生成感”。`page_rhythm` 是少数能穿越上下文压缩保留下来的叙事杠杆。

**缺少 `page_rhythm` 段** → 输出一次 `warning: spec_lock.json missing page_rhythm — defaulting all pages to analytical`，并将所有页面回退为 `analytical`。

**当前页找不到标签** → 静默回退为 `analytical`，不要自造标签。

---

## 3. 执行规范

- **接近原则**：相关元素紧凑摆放；无关元素拉开距离
- **遵循规范**：严格按 spec 中的颜色、布局、画布格式和字体执行
- **模板继承**：若模板存在，则继承其视觉框架
- **主代理负责**：SVG 生成必须由主代理执行，不能交给子代理；这样才能保持跨页视觉连续性
- **生成节奏**：先锁定全局设计上下文，再在同一连续上下文中按页顺序生成；不要分批次（例如每次 5 页）
- **极简改动**：不为一次性场景创建抽象；不为"以防万一"添加未要求的装饰、动画占位或额外颜色。如果 50 行 SVG 能解决的问题不要用 200 行。每一处改动都必须能溯源到 spec_lock 或用户请求。
- **手术刀修复**：修复错误时只动目标页/目标元素，不连带改写无关内容。例如：quality_checker 报 P05 漂移只重生成 P05，不要"顺便"修改 P04/P06；修一个颜色漂移只替换该颜色值，不要"统一"相邻页面的间距。修改产生的孤儿代码（如删除图片引用后的 `<clipPath>`）必须清理，但预先存在的死代码不要删。
- **分阶段批处理**（推荐）：
  1. **视觉构建阶段**：按顺序生成全部 SVG 页面，以保证视觉一致性。图表初稿阶段可先按布局判断绘制，但**每个图表页都必须嵌入 plot-area marker**（见下文 §3.1）；坐标校准是生成后的独立步骤，依赖这些标记。每完成一页后更新 `workspace/state.md` 的"当前页进度"字段（如 P05/12），以便会话中断后可从该页恢复。
  2. **质量检查关卡**：对 `svg_output/` 运行 `python scripts/svg_quality_checker.py workspace`。任何 `error`（禁用特性、viewBox 不匹配、spec_lock 漂移、PPT 不安全字体等）都必须在继续前修复并复检。`warning` 在容易修时也应处理。不要推迟到 `finalize_svg.py` 之后，因为后处理会重写 SVG，掩盖部分问题。
  3. **逻辑构建阶段**：SVG 全部通过质量检查后，再批量生成演讲备注，以保持叙事连续性。

### 3.1 图表绘图区标记（每个图表页强制）

> [`verify-charts`](../optional-optional-workflows/verify-charts.md) 工作流会根据 `spec_lock.json content_outline` 找出图表页，再读取各页的 plot-area marker，并把它交给 `svg_position_calculator.py`。如果缺少标记，就只能每次重新从坐标轴反推绘图区。

每个包含数据图表的 SVG 页面，都必须在 `<g id="chartArea">` 中加入绘图区标记，位置应放在**坐标轴之后**、**第一个数据元素之前**。

**矩形绘图区**（bar / horizontal_bar / grouped_bar / stacked_bar / line / area / stacked_area / scatter / waterfall / pareto / butterfly）：

```xml
<!-- chart-plot-area: x_min,y_min,x_max,y_max -->
```

**径向图表**（pie / donut / radar）：

```xml
<!-- chart-plot-area: pie | center: cx,cy | radius: r -->
<!-- chart-plot-area: donut | center: cx,cy | outer-radius: r1 | inner-radius: r2 -->
<!-- chart-plot-area: radar | center: cx,cy | radius: r -->
```

**坐标值确定方法**：

| 值 | 来源 |
|-------|------------|
| `x_min` | Y 轴线的 X 坐标（数据区左边界） |
| `y_min` | 最上方网格线的 Y 坐标（数据区上边界） |
| `x_max` | 最右侧坐标轴端点或网格线的 X 坐标 |
| `y_max` | X 轴基线的 Y 坐标 |
| `cx, cy` | 饼图 / 环图 / 雷达图中心点（需考虑 `transform="translate()"`） |
| `r` | 图表外半径 |

**逐页验证**：每次写完图表 SVG 后，确认标记存在：

```powershell
grep "chart-plot-area" <project_path>/svg_output/<current_page>.svg
```

> `templates/charts/` 中所有图表模板都带这个标记作为参考。你在画图表却没有它，就说明有 bug。

### 3.2 逐页视觉复检（推荐）

> LLM 在“盲写” SVG——它看不到渲染后的结果。常见缺陷（文字溢出、元素重叠、间距不均、短文本被强制换行）在代码层面难发现，但截图里一眼即见。这个可选回路能提前捕获这些问题。

**每写完一页 SVG 后**，渲染并视觉检查：

```bash
python3 scripts/render_svg.py <project_path>/svg_output/<current_page>.svg
```

这会在 SVG 旁生成 `<current_page>.png`。然后 `read_file` 该 PNG 并检查：

| 缺陷 | 查找内容 |
|------|------|
| **文字溢出** | 文字被页面边缘裁剪或延伸出容器 |
| **元素重叠** | 形状 / 文字块非预期地互相遮挡 |
| **强制换行** | 短文本（< 15 字）被拆到多行 |
| **间距不均** | 卡片网格间距可见地不一致；元素偏集一侧 |
| **编码伪影** | 乱码字符；`&amp;` / `&lt;` 以字面形式可见 |

**决策**：
- **无明显问题** → 进入下一页。
- **发现问题** → 编辑 SVG 修复、重新渲染、重新检查。**每页最多 2 轮修复**以避免无限循环——若 2 轮后仍未完美，继续前行并向用户报告。

**何时跳过**：若渲染工具不可用（未安装 PyMuPDF / CairoSVG），静默跳过，依靠代码层的质量检查器。

> 注：PyMuPDF 渲染时可能无法解析外部 `<image>` 引用或 `<use data-icon>` 占位符——这是预期的。请在预览中关注布局、文字和间距。

- **技术规范**：SVG / PPT 约束见 shared-standards.md
- **视觉层次要克制**：层次主要来自节奏（平 vs 浮、密 vs 疏），不是到处加阴影。每页最多只给 2-3 个真正浮起的元素加阴影（如照片上的卡片、主 CTA、覆盖层）；同级卡片网格、分隔线、正文容器应保持平面。优先用字重、留白、强调条和轻底色，而不是阴影。完整规则见 `shared-standards.md §6`。

### SVG 文件命名规范

格式：`<NN>_<page_name>.svg`（两位序号，从 01 开始；文件名语言需与整套 deck 一致，并与 Design Spec 中的页标题匹配）。

示例：`01_封面.svg` / `02_目录.svg` / `03_核心优势.svg`；`01_cover.svg` / `02_agenda.svg` / `03_key_benefits.svg`。

---

## 4. 图标使用

Strategist 负责选择图标库和清单；Executor 只负责实现。图标库细节与“单 deck 单图标库”规则见 `../templates/icons/README.md`。本节只定义占位语法。

**内置图标——占位符方式（推荐）**：

```xml
<!-- chunk-filled（直线几何、锐角、结构感强） -->
<use data-icon="chunk-filled/home" x="100" y="200" width="48" height="48" fill="#005587"/>

<!-- tabler-filled（曲线造型，更圆润） -->
<use data-icon="tabler-filled/home" x="100" y="200" width="48" height="48" fill="#005587"/>

<!-- tabler-outline（轻量线稿风，仅适合屏幕型 deck） -->
<use data-icon="tabler-outline/home" x="100" y="200" width="48" height="48" fill="#005587"/>

<!-- phosphor-duotone（单色 + 20% 背板，柔和但不厚重） -->
<use data-icon="phosphor-duotone/house" x="100" y="200" width="48" height="48" fill="#005587"/>

<!-- simple-icons（品牌 logo，仅用于真实公司/产品标识） -->
<use data-icon="simple-icons/github" x="100" y="200" width="48" height="48" fill="#181717"/>

<!-- tabler-outline 可设置细/粗描边（仅线稿库） -->
<use data-icon="tabler-outline/home" x="100" y="200" width="48" height="48" fill="#005587" stroke-width="1.5"/>
<use data-icon="tabler-outline/home" x="100" y="200" width="48" height="48" fill="#005587" stroke-width="3"/>
```

> ⚠️ **颜色**：`<use data-icon="...">` 一律使用 `fill="#HEX"`。即使是线稿库，也**不要**用 `stroke` 或 `fill="none"`。
>
> **stroke-width**（仅线稿库，目前为 `tabler-outline`）：允许值 `{1.5, 2, 3}`。如果 `spec_lock.json icons.stroke_width` 已声明，则整套 deck 必须统一使用该值；未声明时默认 `2`（兼容旧项目）。非线稿库忽略该属性。
>
> 图标会由 `finalize_svg.py` 自动嵌入，无需手动运行 `embed_icons.py`。

**查找图标**——建议用终端，零 token 成本：
```powershell
Get-ChildItem templates\icons\chunk-filled\*home*
Get-ChildItem templates\icons	abler-filled\*home*
Get-ChildItem templates\icons	abler-outline\*chart*
ls templates/icons/phosphor-duotone/ | grep house
ls templates/icons/simple-icons/ | grep github
```

**抽象概念 → 图标名**（`chunk-filled` 命名；tabler 系列请用其对应名并自行 `ls | grep` 验证）：

| 概念 | chunk-filled | tabler-filled / tabler-outline |
|---------|-------|-------------------------------|
| 增长 / 上升 | `arrow-trend-up` | same |
| 下滑 / 下降 | `arrow-trend-down` | same |
| 成功 / 完成 | `circle-checkmark` | `circle-check` |
| 警告 / 风险 | `triangle-exclamation` | `alert-triangle` |
| 创新 / 想法 | `lightbulb` | `bulb` |
| 战略 / 目标 | `target` | same |
| 效率 / 速度 | `bolt` | same |
| 协作 / 团队 | `users` | same |
| 设置 / 配置 | `cog` | `settings` |
| 安全 / 信任 | `shield` | same |
| 金钱 / 财务 | `dollar` | `currency-dollar` |
| 时间 / 截止 | `clock` | same |
| 地点 / 区域 | `map-pin` | same |
| 沟通 | `comment` | `message` |
| 分析 / 数据 | `chart-bar` | same |
| 流程 / 流转 | `arrows-rotate-clockwise` | `refresh` |
| 全球 / 世界 | `globe` | `world` |
| 卓越 / 奖项 | `star` | same |
| 扩张 / 扩展 | `maximize` | same |
| 问题 / 缺陷 | `bug` | same |

> 对于 `home`、`user`、`file`、`search`、`arrow` 这类直观名称，直接 `grep` 图标目录即可，不必查表。

> ⚠️ **图标校验**：只能使用 Design Spec 批准清单中的图标。每个图标使用前都要通过 `ls | grep` 验证。**同一 deck 混用多个图标库是禁止的。**

---

## 5. 可视化参考

如果 Design Spec 中包含 **VII. Visualization Reference List**，则在绘制对应页面前，先读取 `templates/charts/` 中指定的模板。

**必须读取，但不能照抄。** 每种在 §VII 中首次出现的图表类型，第一次使用前都要读取 `templates/charts/<chart_name>.svg`。它只用于参考布局、结构、间距和视觉逻辑；实际绘制时要替换为项目自己的配色、字体和内容。不要凭记忆发挥，也不要逐字复制。

> 只有在图表类型变化时才需要重新读取；同类型后续页面可复用理解。

**适配规则**：
- **必须保留**：图表类型（柱图 / 折线 / 饼图 / 时间线 / 流程 / 框架等）
- **需要适配**：数据、标签、颜色（项目配色）、尺寸
- **可自由调整**：构图、坐标范围、网格、图例、间距、装饰，只要图表仍准确且可读
- **禁止**：没有规范依据就更换图表类型；删除提纲中的数据点或结构元素

> 模板目录：`templates/charts/`（70 种）。索引：`templates/charts/charts_index.json`

### 5.1 图表坐标校准

坐标校准是**独立的生成后工作流**，不属于 executor 主流程。SVG 全部生成后，如果 deck 中含数据图表，应在后处理前运行 [`optional-workflows/verify-charts.md`](../optional-workflows/verify-charts.md)。

Executor 在这里唯一的上游义务，是在初稿阶段就为每个图表页嵌入 `<!-- chart-plot-area ... -->` 标记（见 §3.1）。`verify-charts` 会根据 `spec_lock.json content_outline` 找到图表页，并用该标记驱动 `svg_position_calculator.py`。

> 不要在初稿阶段运行 `svg_position_calculator.py`。该工具用于校准**已生成好的** SVG，如果 SVG 还不存在，就无从比较。

---

## 6. 图片处理

按 Design Spec 中图片资源清单处理图片。图片均由用户提供，状态为 **Existing**，直接从 `../images/` 引用。

**引用语法**：见 `svg-image-embedding.md`

**占位方式**：虚线边框 `<rect stroke-dasharray="8,4" .../>` + 描述文本

---

## 7. 字体使用

唯一依据：`spec_lock.json typography`。默认使用 `font_family`；如果声明了 `title_family` / `body_family` / `emphasis_family` / `code_family`，则按角色覆盖。

如果 `spec_lock.json` 缺失，**不要自己编造字体栈**。

**硬规则**：每个 SVG 的 `font-family` 栈都必须以一个系统已预装字体结尾，例如：`Microsoft YaHei / SimHei / SimSun / Arial / Calibri / Segoe UI / Times New Roman / Georgia / Consolas / Courier New / Impact / Arial Black`。PPTX 没有运行时字体回退；缺字时通常会退化成 Calibri。

---

## 8. 演讲备注生成框架

### 任务 1：生成完整备注文档

所有 SVG 页面完成后，进入逻辑构建阶段，把完整备注写入 `notes/notes_all.md`。备注应**整批生成**，不要逐页零散写，这样过渡语才会连贯。

**语言规则（先看）**：当前场景只使用中文。所有结构标签和舞台提示标记都必须使用中文，不要混入英文标签。

**每页结构**：

- 标题格式：`# <number>_<page_title>`
- 页面之间用 `---` 分隔
- 每页包含：
  - 2–5 句讲稿，语气自然，聚焦本页核心信息
  - 一行 `要点：`，列出 1–3 个具体要点，使用 ①②③ 编号；必须填真实内容，不能只留圈号
  - 一行 `时长：`，写一个明确数字（如 `2分钟`），不能写区间，也不能写 `X`
  - 第一页之外的每页，都必须以独立的 `[过渡]` 开头，承接上一页

**示例**

```
# 02_市场格局

[过渡] 在明确了行业背景之后，我们来看具体的市场格局。
当前线上零售集中度持续上升，前三大平台合计份额已达 68%。腰部玩家正在被快速挤压，留给新进入者的窗口期不超过 18 个月。这意味着我们的策略必须聚焦，而不是铺开。

要点：① 集中度 68% 的事实 ② 18 个月窗口期 ③ 聚焦优于铺开
时长：2分钟
```

**常见错误**：
- 直接写 `① ② ③`，却不填真实内容
- 写成 `时长：1-2分钟` 这种区间，而不是一个明确数值
- 正文是中文，却把 `[过渡]`、`要点：`、`时长：` 写成英文

### 任务 2：拆分为逐页备注文件

把 `notes/notes_all.md` 自动拆分为 `notes/` 目录下的逐页文件。

**命名规则**：与 SVG 文件名对应，如：`01_cover.svg` → `notes/01_cover.md`；也兼容旧格式 `slide01.md`。

---

## 9. 完成后的下一步

> **自动续跑**：当视觉构建阶段（全部 SVG）和逻辑构建阶段（全部备注）完成后，Executor 直接进入后处理流程。

**后处理**（与 [shared-standards.md §5](shared-standards.md) 相同）：

```powershell
# 1. 拆分备注
python scripts/notes_all_md_split.py <project_path>

# 2. SVG 后处理（自动嵌入图标、图片等）
python scripts/finalize_svg.py <project_path>

# 3. 用户手动导出 PPTX
# python scripts/svg_to_pptx.py <project_path> -s final
# 输出：
#   exports/<project_name>_<timestamp>.pptx           ← 主原生 pptx
#   backup/<timestamp>/<project_name>_svg.pptx        ← SVG 快照备份
#   backup/<timestamp>/svg_output/                    ← Executor SVG 源文件备份
```
