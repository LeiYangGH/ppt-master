# 执行锁定

> **⚠️ 策略师骨架文件——请勿逐字复制到项目中。** 生成 `<project_path>/spec_lock.md` 时，仅输出带已填写 `-` 数据行的 `##` 章节。不要携带任何 `>` 引用块指导、硬性规则说明或覆盖示例——那些是作者端指导，不是运行时数据。每行输出必须是可解析的数据。
>
> 面向机器读取的执行契约。执行器必须在生成每个 SVG 页面之前 `read_file` 此文件。此处未列出的值禁止出现在 SVG 中。设计叙事（理由、受众、风格）见 `design_spec.md`。
>
> SVG 生成开始后，此为颜色 / 字体 / 图标 / 图片值的权威来源。修改应通过 `scripts/update_spec.py` 进行，以保持此文件与生成的 SVG 同步。

## canvas
- viewBox: 0 0 1280 720
- format: PPT 16:9

> 策略师：根据所选画布填写 viewBox 和格式。常用值：`0 0 1280 720`（PPT 16:9）、`0 0 1024 768`（PPT 4:3）、`0 0 1242 1660`（小红书）、`0 0 1080 1080`（微信朋友圈）、`0 0 1080 1920`（故事）。

## colors
- bg: #FFFFFF
- primary: #......
- accent: #......
- secondary_accent: #......
- text: #......
- text_secondary: #......
- border: #......

> 策略师：仅填写实际使用的颜色。按需添加额外行；删除未使用的行，不要保留为 `#......`。

## typography
- font_family: "Microsoft YaHei", Arial, sans-serif
- title_family: Georgia, SimSun, serif
- body_family: "Microsoft YaHei", "PingFang SC", Arial, sans-serif
- emphasis_family: Georgia, SimSun, serif
- code_family: Consolas, "Courier New", monospace
- body: 22
- title: 32
- subtitle: 24
- annotation: 14

> **五个 family 行全部显式列出**，以便策略师考虑每个角色——`code_family` 和 `emphasis_family` 容易被遗漏。在真实的 `spec_lock.md` 中：
> - 保留任何与 `font_family` 真正不同的 `*_family`。
> - **省略**与 `font_family` 相同的 `*_family`——执行器对缺失角色回退到 `font_family`，因此写两次是噪音。（例外：即使相同也保留 `code_family`——等宽字体在概念上是不同的。）
>
> `font_family` 是默认回退。每个声明的 family 都是 CSS 字体栈字符串。
>
> **来源**：从 `design_spec.md §IV 字体方案` 中的*按角色的字体栈*列表逐字复制。此处栈**顺序**编码了浏览器渲染意图（拉丁优先 vs 中文优先），这是拆分表无法表达的——此处的字符串必须与之一字不差。详见 `design_spec.md §IV` 说明。
>
> 字号（`body` / `title` / 等）单位为 px，与 SVG 单位一致。`body` 是**必需的基线锚点**——其他所有字号都按它的比例推导（梯度表见 `design_spec_reference.md §IV`）。
>
> **字号槽是锚点，不是封闭菜单。** 常用槽（`title` / `subtitle` / `annotation`）覆盖常见情况。按需添加角色专属槽（例如 `cover_title: 72`、`hero_number: 48`、`chart_annotation: 13`）——封面密集型、咨询风格 hero 数字、密集页面常见。执行器可使用中间值，只要与 `body` 的比例落在角色的梯度范围内。
>
> **⚠️ PPT 安全栈规则（硬性规定）。** PPTX 每个文本段只存储一个 `typeface`，没有运行时回退。每个栈必须以跨平台预装字体结尾：`"Microsoft YaHei", sans-serif` / `SimSun, serif` / `Arial, sans-serif` / `"Times New Roman", serif` / `Consolas, "Courier New", monospace`。非预装字体（Inter / Google Fonts / 品牌字体）仅在设计规范注明字体安装或嵌入要求时才可置于栈首。
>
> **栈长度纪律。** 每栈 3-4 个字体为最佳。转换器仅将**第一个**拉丁字体和**第一个**中文字体写入 PPTX——之后的全部静默丢弃。macOS 专用字体（`Songti SC`、`Menlo`、`Monaco`、`Helvetica`）通过 `FONT_FALLBACK_WIN` 自动映射到 Windows 等价字体（见 `scripts/svg_to_pptx/drawingml_utils.py`）；同时堆叠两者是冗余的。以 Windows 预装字体开头（`Microsoft YaHei` / `SimSun` / `Arial` / `Georgia` / `Consolas`）；最多保留**一个** macOS 专属字体（通常为 `"PingFang SC"`）作为浏览器预览优化。

## icons
- library: chunk-filled
- brand_library: simple-icons
- inventory: target, bolt, shield, users, chart-bar, lightbulb

> `library` 必须是 `chunk-filled` / `tabler-filled` / `tabler-outline` / `phosphor-duotone` 之一——禁止混用。`brand_library: simple-icons` 为可选项；仅当幻灯片使用真实公司/产品品牌标识时包含，否则省略。`inventory` 列出批准的图标名称（无库前缀）；执行器只能使用此列表中的图标。
>
> **`stroke_width`（仅描边风格库）**——当 `library` 为描边型（当前为 `tabler-outline`）时必需；允许值 `1.5` / `2` / `3`。执行器必须将此值通过 `stroke-width` 应用于每个 `<use data-icon="...">` 占位符，全稿统一。非描边库（`chunk-filled` / `tabler-filled` / `phosphor-duotone`）省略——在这些库中忽略。如需更粗权重请切换库；不要超过 `3`（24×24 下描边会合并，图标失去线条感）。
>
> 描边风格库示例：
> ```
> - library: tabler-outline
> - stroke_width: 2
> - inventory: home, chart-bar, users, bulb
> ```

## images
- cover_bg: images/cover_bg.jpg

> 每个使用的图片文件一个条目。如无图片则完全删除本节。

## page_rhythm
- P01: anchor
- P02: dense
- P03: breathing
- P04: dense
- P05: dense
- P06: breathing
- P07: anchor

> 每页一个条目。键：`P<NN>`（零填充，与 `design_spec.md` 中 `§IX 内容大纲` 匹配）。值：三个节奏标签之一。执行器按页读取并应用该标签的布局纪律——打破"每页看起来都一样"的模式。
>
> **词汇表**（仅以下三个值）：
> - `anchor` — 结构页（封面 / 章节开篇 / 目录 / 结尾）。严格按模板执行。
> - `dense` — 信息密集型页面（数据、KPI、对比、多要点列表）。允许卡片网格、多列布局、表格、图表。
> - `breathing` — 低密度页面（单一概念、hero 引言、大图 + 说明、章节过渡）。避免**多卡片网格布局**（多个并行圆角容器作为主要结构）；通过裸文本、分隔线、留白或全出血图片组织。单一圆角元素（hero 图片角、标注、标签、一个强调块）可以。比例遵循信息权重——不是预设比例菜单。
>
> **节奏跟随叙事**：`breathing` 页面出现在叙事真正需要停顿的地方——章节过渡、值得独立强调的单一论点、密集序列后的刻意停顿。数据简报或咨询分析可能几乎全为 `dense`——**不要发明填充页**来凑节奏。验证：每个 `breathing` 页必须能回答"这一页在说什么独立的内容？"。
>
> **缺失或空节** → 执行器对每页回退到 `dense`（遗留的前节奏行为）。仅对遗留幻灯片删除本节；新幻灯片必须填写。

## forbidden
- 混用图标库
- rgba()
- `<style>`, `class`, `<foreignObject>`, `textPath`, `@font-face`, `<animate*>`, `<script>`, `<iframe>`, `<symbol>`+`<use>`
- `<g opacity>`（在每个子元素上单独设置透明度）
- 文本中的 HTML 命名实体（`&nbsp;`, `&mdash;`, `&copy;`, `&ndash;`, `&reg;`, `&hellip;`, `&bull;` …）——写成原始 Unicode（`—`, `©`, `→`, 不间断空格等）；XML 保留字符 `& < > " '` 必须转义为 `&amp; &lt; &gt; &quot; &apos;`。详见 shared-standards.md §1.0
