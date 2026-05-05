# 通用技术规范

PPT Master 的通用技术约束，用于消除各角色文件中的重复内容。

---

## 1. SVG 禁用特性黑名单

以下内容在生成的 SVG 中**禁止使用**，否则 PPT 导出会出问题：

### 1.0 文本字符：必须是合法 XML

SVG 是严格的 XML。所有文本和属性值都必须遵守以下两条规则：

| 字符类别 | 必须写法 | 禁止写法 |
|---|---|---|
| 排版字符与符号（长破折号、短破折号、©、®、→、·、NBSP、全角标点、emoji…） | **直接写 Unicode 原字符**——如直接写 `—` `–` `©` `®` `→` | HTML 命名实体——如 `&mdash;` `&ndash;` `&copy;` `&reg;` `&rarr;` `&middot;` `&nbsp;` `&hellip;` `&bull;` 等 |
| XML 保留字符（`&`、`<`、`>`、`"`、`'`） | **只能用 XML 实体**——如 `&amp;` `&lt;` `&gt;` `&quot;` `&apos;`（例如 `R&amp;D`、`error &lt; 5%`） | 裸写 `&` `<` `>`（例如 `R&D`、`error < 5%`） |

只要有一个非法字符，整个文件就会失效，导出也会中断。数字实体（如 `&#160;` / `&#xa0;`）虽然合法，但不推荐。

**结构黑名单**（除上面的字符规则外）：

| 禁用特性 | 说明 |
|----------------|-------------|
| `mask` | 蒙版 |
| `<style>` | 内嵌样式表 |
| `class` | CSS 选择器属性（`<defs>` 内的 `id` 是合法引用，不在禁用之列） |
| External CSS | 外部样式表链接 |
| `<foreignObject>` | 嵌入外部内容 |
| `<symbol>` + `<use>` | symbol 引用复用 |
| `textPath` | 路径文字 |
| `@font-face` | 自定义字体声明 |
| `<animate*>` / `<set>` | SVG 动画 |
| `<script>` / event attributes | 脚本与交互事件 |
| `<iframe>` | 嵌入式框架 |

> **`marker-start` / `marker-end` 在满足条件时允许使用**——约束见 §1.1。转换器会把符合条件的 marker 转为原生 DrawingML `<a:headEnd>` / `<a:tailEnd>`。
>
> **`<image>` 上的 `clipPath` 在满足条件时允许使用**——约束见 §1.2。转换器会把符合条件的裁切形状转为原生 DrawingML 图片几何（`<a:prstGeom>` 或 `<a:custGeom>`）。
>
> **替代 `<mask>` 效果的方法**——DrawingML 不支持逐像素 alpha。请按效果类型改写：
> - 图片渐变蒙层（暗角 / 渐隐 / 染色）→ 叠加 `<rect>` + `<linearGradient>` / `<radialGradient>`（见 §6 图片覆盖层）
> - 非矩形图片裁切（圆形 / 圆角 / 六边形）→ 在 `<image>` 上使用 `clipPath`（见 §1.2）
> - 内发光 / 柔边 → 使用 `<filter>` + `<feGaussianBlur>`（见 §6 Glow）
> - 投影 → 使用滤镜阴影或叠层矩形（见 §6 Shadow）
>
> 像素级 alpha 效果（如文字镂空图片填充、任意 alpha 合成）在 PPT 中没有可靠路径，应在 Image_Generator 阶段直接烘焙进源图。

---

### 1.1 线端标记（条件允许）

`<line>` 和 `<path>` 上的 `marker-start` / `marker-end` **仅在**所引用的 `<marker>` 满足以下全部条件时允许使用：

| 要求 | 原因 |
|-------------|--------|
| `<marker>` 必须定义在 `<defs>` 中 | 转换器通过 id 索引查找 marker 定义 |
| `orient="auto"` | DrawingML 箭头会沿切线方向自动旋转，其他 orient 值无法可靠往返 |
| Marker 形状必须是以下之一：闭合 3 点 path/polygon（三角形）、闭合 4 点 path/polygon（菱形）、`<circle>` / `<ellipse>`（椭圆） | 只有这三类能稳定映射为 DrawingML 的 `triangle` / `diamond` / `oval`；其他形状会被静默丢弃，并附带 warning |
| Marker 子元素的 `fill` **必须与**父线条的 `stroke` 颜色一致 | DrawingML 中箭头头部继承线条颜色；若不一致，导出后效果会错 |
| `markerWidth` / `markerHeight` 大致落在 `3–15` 范围 | 会映射为 `sm`（<6）/ `med`（6–12）/ `lg`（>12） |

**使用边界**：

- `marker-start` / `marker-end`：只用于“线条本体是主体”的连接箭头
- 如果箭头本体是块状 / 实心 / 粗箭头，请直接使用独立闭合的 `<path>` / `<polygon>`；可参考 `templates/charts/chevron_process.svg` 或 `templates/charts/process_flow.svg`

**支持的 DrawingML 映射**：

| SVG marker 形状 | DrawingML 输出 |
|------------------|------------------|
| `<path d="M0,0 L10,5 L0,10 Z"/>`（triangle） | `<a:tailEnd type="triangle" w="med" len="med"/>` |
| `<polygon points="0,0 10,5 0,10"/>` | `<a:tailEnd type="triangle" w="med" len="med"/>` |
| 4-vertex closed path/polygon | `<a:tailEnd type="diamond" .../>` |
| `<circle cx="5" cy="5" r="4"/>` | `<a:tailEnd type="oval" .../>` |

**推荐模板**——可直接复用的标准箭头定义：

```xml
<defs>
  <marker id="arrowHead" markerWidth="10" markerHeight="10" refX="9" refY="5"
          orient="auto" markerUnits="strokeWidth">
    <path d="M0,0 L10,5 L0,10 Z" fill="#1976D2"/>
  </marker>
</defs>
<line x1="100" y1="200" x2="400" y2="200" stroke="#1976D2" stroke-width="3"
      marker-end="url(#arrowHead)"/>
```

> ⚠️ 无法归类的 marker 形状（曲线路径、多段路径、顶点数 > 4）会被静默丢弃，最终只剩线条、没有箭头。特殊箭头请直接手动画 `<polygon>`。

---

### 1.2 图片裁切（条件允许）

`<image>` 元素上的 `clip-path` 在其引用的 `<clipPath>` 满足以下条件时允许使用：

| 要求 | 原因 |
|-------------|--------|
| `<clipPath>` 必须定义在 `<defs>` 中 | 转换器通过 id 索引查找裁切定义 |
| 只能包含**一个**图形子元素 | 只会读取第一个子元素；多个子元素不会合成 |
| 形状必须是：`<circle>`、`<ellipse>`、`<rect>`（可带 rx/ry）、`<path>`、`<polygon>` | 这些可以映射到 DrawingML 预设或自定义几何 |
| **只能用于 `<image>` 元素** | 非图片元素使用 clip-path **禁止** |

**使用边界**：

- 只用于 `<image>` 的非矩形裁切（如圆形头像、圆角相框、六边形图片）
- **不能**用于形状元素（`<rect>` / `<circle>` / `<path>` / `<g>` / `<text>`）——目标形状应直接画出来。比如把一个矩形裁成圆，本质上就该直接画圆。
- PowerPoint 自带 SVG 渲染器并不处理 `clipPath`；只有原生 PPTX 转换链路会处理。

**支持的 DrawingML 映射**：

| SVG 裁切形状 | DrawingML 输出 | 用途 |
|----------------|------------------|----------|
| `<circle>` / `<ellipse>` | `<a:prstGeom prst="ellipse"/>` | 圆形头像、椭圆相框 |
| `<rect rx="..."/>` | `<a:prstGeom prst="roundRect"/>` with adj value | 圆角矩形照片框 |
| `<path>` / `<polygon>` | `<a:custGeom>` with path commands | 六边形、菱形、自定义图形 |

**推荐模板**——圆形图片裁切：

```xml
<defs>
  <clipPath id="avatarClip">
    <circle cx="200" cy="200" r="100"/>
  </clipPath>
</defs>
<image href="../images/photo.jpg" x="100" y="100" width="200" height="200"
       clip-path="url(#avatarClip)" preserveAspectRatio="xMidYMid slice"/>
```

**圆角矩形裁切**——适用于卡片式图片框：

```xml
<defs>
  <clipPath id="cardClip">
    <rect x="60" y="120" width="400" height="250" rx="16"/>
  </clipPath>
</defs>
<image href="../images/banner.jpg" x="60" y="120" width="400" height="250"
       clip-path="url(#cardClip)" preserveAspectRatio="xMidYMid slice"/>
```

> ⚠️ 在非图片元素上使用 `clip-path` 是**禁止**的，质量检查器会直接报错。目标几何请直接绘制。

---

## 2. PPT 兼容替代写法

| 禁用写法 | 正确替代 |
|---------------|---------------------|
| `fill="rgba(255,255,255,0.1)"` | `fill="#FFFFFF" fill-opacity="0.1"` |
| `<g opacity="0.2">...</g>` | 把 `fill-opacity` / `stroke-opacity` 分别写到每个子元素上 |
| `<image opacity="0.3"/>` | 在图片上方叠加一个 `<rect fill="background-color" opacity="0.7"/>` 作为遮罩层 |

**记忆口诀**：PPT 不识别 rgba、不识别 group opacity，也不识别 image opacity。

> 箭头建议：连接线优先使用 `marker-end`（见 §1.1），转换器会输出原生自动旋转箭头。块状 / 实心箭头请使用独立闭合形状，参考 `templates/charts/chevron_process.svg` 和 `templates/charts/process_flow.svg`。

---

## 3. 画布格式速查

> 完整格式表（演示 / 社交 / 营销）及格式选择决策树见 [`canvas-formats.md`](canvas-formats.md)。

---

## 4. 基础 SVG 规则

- **viewBox** 必须与画布尺寸一致（`width` / `height` 必须和 `viewBox` 对应）
- **背景**：使用 `<rect>` 定义页面背景色
- **`<tspan>`** 有两种用途：1）手动换行（用 `dy` 或显式 `y`）；2）同一行内做局部格式变化（颜色 / 字重 / 字号）。`<foreignObject>` **禁止**。详见下方“单逻辑行”规则。
- **字体**：每个 `font-family` 栈都**必须**以系统预装字体结尾（如 Microsoft YaHei / SimSun / Arial / Times New Roman / Consolas 等）；`@font-face` **禁止**。完整规则见 [`strategist.md §g`](strategist.md)。
- **样式**：只能写行内样式（如 `fill=""`、`font-size=""`）；`<style>` / `class` **禁止**（`<defs>` 内的 `id` 合法）
- **颜色**：只用 HEX；透明度通过 `fill-opacity` / `stroke-opacity`
- **图片**：`<image href="../images/xxx.png" preserveAspectRatio="xMidYMid slice"/>`
- **图标**：`<use data-icon="<library>/<name>" x="" y="" width="48" height="48" fill="#HEX"/>`（后处理自动嵌入）。必须始终带图标库前缀。每套 deck 只能用一种风格库（`chunk-filled` / `tabler-filled` / `tabler-outline` / `phosphor-duotone`）；`simple-icons` 只用于真实品牌标识。详见 [`../templates/icons/README.md`](../templates/icons/README.md)。

### 行内文字分段（单个逻辑行 = 单个 `<text>`）

一个逻辑上的单行文本——即使包含不同颜色 / 字重 / 字号——也**必须**写成一个 `<text>`，内部用 `<tspan>` 做行内分段。不要把同一行拆成多个相邻 `<text>`。转换器会把每个 `<tspan>` 映射为同一个 PPT 文本框中的 `<a:r>` run，从而保证整行仍是一个可编辑对象。

✅ **推荐**——一个 `<text>` 对应一个文本框，内部三个 run：

```xml
<text x="100" y="200" font-size="24" fill="#333333">
  实现<tspan fill="#1A73E8" font-weight="bold">10倍</tspan>效率提升
</text>
```

❌ **不要这样做**——三个并排 `<text>` 会在 PPT 中变成三个独立文本框（无法作为一行整体编辑，还容易对齐漂移、间距脆弱）：

```xml
<text x="100" y="200" font-size="24" fill="#333333">实现</text>
<text x="160" y="200" font-size="24" fill="#1A73E8" font-weight="bold">10倍</text>
<text x="240" y="200" font-size="24" fill="#333333">效率提升</text>
```

**⚠️ 行内 tspan 不能带 `x` / `y` / `dy`**——这些属性代表新起一行，`flatten_tspan` 会把它拆成独立文本框。`dx` 是安全的（用于字距调整，仍保持行内）。只有真正开始新行时，才应给 tspan 设置 `x` / `y` / `dy`。

**带逐行强调的多行 `<text>` 是允许的**：外层换行 tspan（带 `x` + `dy` 或 `y`）内部，可以再嵌套行内 tspan 来控制颜色 / 字重 / 字号——转换器会递归解析，并为每个样式片段生成一个 run：

```xml
<text x="80" y="190" font-size="18" fill="#333333">
  <tspan x="80" dy="0">完成率<tspan fill="#4CAF50" font-weight="bold">98%</tspan>超预期</tspan>
  <tspan x="80" dy="35">成本降低<tspan fill="#F44336" font-weight="bold">¥120万</tspan></tspan>
</text>
```

❌ **不要这样做**——同一行内通过 `<tspan x="...">` 强行跳列：

```xml
<text x="100" y="200" font-size="18" fill="#333333">
  <tspan x="100">左列</tspan><tspan x="600" font-weight="bold">右列</tspan>
</text>
```

在 tspan 上写 `x` 会被视为新起一行，从而拆成两个独立文本框。若要做双列，请直接写两个 `<text>`。

**默认原则——主动抬升关键信息。** 整段文字都用统一样式会变成“文字墙”。以下内容应使用 `<tspan fill="..." font-weight="bold">` 强调：

- **数字结果**——百分比、倍数（如 `10x`）、绝对金额（如 `¥120万`）
- **对比项**——得失、前后、目标 / 实际
- **每句中 1-2 个承重名词**——真正承载洞察的术语

不要强调：连接词、普通动词、所有名词、装饰性形容词，以及结构性文字（页脚 / 坐标轴 / 图例 / 页码 / 标签）。

颜色建议：强调优先使用 deck 的主品牌色。绿色 / 红色只留给真实的正负语义。

❌ **不要这样做**——整段统一样式会埋没洞察：

```xml
<text x="80" y="200" font-size="20" fill="#333333">
  2024年公司营收同比增长35%达到12亿元创历史新高
</text>
```

✅ **推荐**——同一行中主动抬升关键数据：

```xml
<text x="80" y="200" font-size="20" fill="#333333">
  2024年公司营收同比<tspan fill="#1A73E8" font-weight="bold">增长35%</tspan>达到<tspan fill="#1A73E8" font-weight="bold">12亿元</tspan>创历史新高
</text>
```

### 元素分组（强制）

逻辑相关的元素必须包进顶层 `<g id="...">` 分组中。这样导出到 PPTX 后会形成 PowerPoint 分组，便于选中 / 移动 / 编辑，同时也为可选的逐元素入场动画提供稳定锚点。

> ⚠️ 被禁用的只有 `<g opacity="...">`（见 §2）。普通的 `<g>` 分组不仅允许，而且是必需的。

**面向动画的规则**：`<svg>` 的直接子元素应该是语义分组，而不是零散绘图原子。建议**每页有 3–8 个顶层内容 `<g id>` 分组**（这个 3–8 不包含页面 chrome，见下文）；在 `--animation-trigger` 的不同模式下，每个内容组会成为一个入场步骤（`on-click` 为一次点击，`after-previous` 为一个串联槽位，`with-previous` 为并行播放）。

**Chrome 分组会被自动排除。** 导出器会把顶层 id 中包含 chrome 关键词的分组视为页面装饰层，并跳过动画序列——它们会和整页一起出现。匹配关键词（id 按 `-` / `_` 拆分后匹配）：`background`、`bg`、`decoration` / `decorations` / `decor`、`header`、`footer`、`chrome`、`watermark`、`pagenumber` / `pagenum` / `page-number`。因此 `<g id="bg-texture">`、`<g id="cover-footer">`、`<g id="p03-header">`、`<g id="bottom-decor">` 都会跳过动画，但仍保留 `<g>` 以便编辑和分组。页面 chrome 应统一使用这套命名，不要移除 `<g>` 包装。

**应该分组的对象**：

| 分组单元 | 包含内容 |
|---------------|----------|
| 卡片 / 面板 | 背景矩形 +（仅当卡片浮在照片 / 色块上方时才加可选阴影，见 §6）+ 图标 + 标题 + 正文 |
| 流程步骤 | 编号圆点 + 图标 + 标签 + 描述 |
| 列表项 | 项目符号 / 编号 + 图标 + 标题 + 描述 |
| 图标 + 文本组合 | 图标元素 + 相邻标签 |
| 页眉 | 标题 + 副标题 + 强调装饰 |
| 页脚 | 页码 + 品牌标识 |
| 装饰簇 | 一组相关装饰元素（圆环、光点、圆球等） |

**不要这样做**：

- 不要把整页都塞进一个巨大的 `<g>`，否则只剩一个动画步骤。
- 不要让大量顶层 `<rect>` / `<text>` / `<path>` 裸露不分组；回退动画最多只取 8 个 primitive，密集页面还可能直接跳过动画。
- 不要把每个图标、每行文字、每个装饰点都拆成独立顶层组，否则点击步骤会爆炸。
- 不要使用匿名顶层组。每个顶层语义组都必须有可读的 `id`。

**示例**：

```xml
<g id="card-benefits-1">
  <!-- 这张卡片浮在色块面板上方，因此适合加阴影；若是纯白平面画布，则应去掉滤镜。 -->
  <rect x="60" y="115" width="565" height="260" rx="20" fill="#FFFFFF" filter="url(#shadow)"/>
  <use data-icon="chunk-filled/bolt" x="108" y="163" width="44" height="44" fill="#0071E3"/>
  <text x="105" y="270" font-size="56" font-weight="bold" fill="#0071E3">10×</text>
  <text x="250" y="270" font-size="30" font-weight="bold" fill="#1D1D1F">更快</text>
  <text x="105" y="310" font-size="18" fill="#6E6E73">将生产周期从数天缩短到数小时。</text>
</g>
```

**命名要求**：顶层 `<g>` 的描述性 `id` 是**强制**的（如 `card-1`、`step-discover`、`header`、`footer`）。每个顶层 `<g id>` 都会成为 PPTX 导出时逐元素动画的锚点；如果没有，导出器只能退回到最多 8 个顶层 primitive，或在密集页面中直接跳过动画。

---

## 5. 后处理流程（3 步）

必须按顺序执行——禁止跳步，也禁止额外乱加参数：

```bash
# 1. 将总备注拆分为逐页备注文件
python scripts/total_md_split.py <project_path>

# 2. SVG 后处理（嵌入图标、裁切/嵌入图片、文字扁平化、圆角矩形转 path）
python scripts/finalize_svg.py <project_path>

# 3. 导出 PPTX（从 svg_final/ 导出，默认嵌入演讲备注）
python scripts/svg_to_pptx.py <project_path> -s final
# 输出：
#   exports/<project_name>_<timestamp>.pptx           ← 主原生 pptx
#   backup/<timestamp>/<project_name>_svg.pptx        ← SVG 快照
#   backup/<timestamp>/svg_output/                    ← Executor SVG 源文件备份
```

**可选动画参数**（仅当用户明确要求时）：
- `-t <effect>` —— 页面切换效果（`fade` / `push` / `wipe` / `split` / `strips` / `cover` / `random` / `none`；默认 `fade`）
- `-a <effect>` —— 逐元素入场动画（`fade` / `mixed` / `random` / 22 种命名效果之一 / `none`；默认 `mixed`）。锚点是顶层 `<g id="...">` 分组。
- `--animation-trigger {on-click,with-previous,after-previous}` —— 对应 PowerPoint 动画面板里的 Start 模式。默认 `after-previous`（页面进入后自动串联播放，节奏由 `--animation-stagger <seconds>` 控制）；`on-click` 逐次点击推进；`with-previous` 为全部组同时播放。
- `--auto-advance <seconds>` —— 展台 / 轮播式自动播放

完整说明见 [`animations.md`](animations.md)。

**禁止事项**：
- 绝对不要用 `cp` 替代 `finalize_svg.py`
- 绝对不要直接从 `svg_output/` 导出——**必须**从 `svg_final/` 导出（使用 `-s final`）
- 绝对不要使用 `--only`（它会抑制两种输出中的一种）

**重跑规则**：后处理之后，只要 `svg_output/` 再次发生变化，就必须重新执行第 2-3 步。第 1 步只在 `notes/total.md` 发生变化时才需要重跑。

---

## 6. 阴影与覆盖层技巧

> `<mask>` 元素和 `<image opacity="...">` 都是禁用的。请始终改用叠加 `<rect>` 或渐变覆盖层（见 §2）。

### Shadow

> **阴影应克制使用，而不是默认就上。** “设计感”往往来自节制，而不是堆叠。

#### 何时使用

只有当元素确实“浮”在另一层之上时才使用：
- 浮在照片或色块上的卡片 / 引语框 / 注释框
- 一页中唯一的主 CTA，或需要从同级对象中被挑出来的“推荐项”
- 覆盖层（callout、tooltip、弹层强调）
- 浮在纹理背景上的图片卡片

#### 何时不要用

- 背景面板 / 分隔条 / 装饰条——它们是“地板层”
- 2 / 3 / 4 列的同级卡片网格——应全部保持平面
- 已经有明显边框、渐变填充或强底色的容器——再加阴影会重复
- 正文段落容器——会破坏阅读节奏
- 装饰线 / 分隔线 / 图标——它们是符号，不是物体
- 页面只有一个内容容器——没有第二层可供“抬起”
- 深色背景页面——黑色阴影会消失；应改用 1px 低透明白描边或外发光

**每页预算**：最多 2-3 个带阴影元素。想加第 4 个前，先删掉一个。

#### 每页单一光源

同一页内，所有 `feOffset` 必须保持相同的 `dx` / `dy` 方向。默认值可用：`dx="0"`，`dy="4"` 到 `dy="8"`（相当于光从上前方打下）。

#### 以克制代替“看得见”

标准原则是：“阴影应该被感受到，而不是被看见。” 如果用户一眼看到阴影本身，通常就太重了。
- 静止层卡片：`flood-opacity` 0.06-0.12
- 抬升层元素（CTA、覆盖层）：最大 `flood-opacity` 0.20
- 超过 0.20 会很容易变成 Office 2007 式硬阴影
- 颜色建议：低透明近黑色，或背景色的更深一档。品牌色阴影只应用于同色系强调元素。

#### 抬升层最多两级

一页中最多只允许两个“非地板层”层级。

| 层级 | 使用场景 | dy | stdDeviation | flood-opacity |
|------|------|----|--------------|---------------|
| 地板层（无阴影） | 背景、同级卡片网格、分隔线、正文容器 | — | — | — |
| 静止层 | 浮在照片/面板上的卡片、次级提示框 | 2-4 | 4-8 | 0.06-0.10 |
| 抬升层 | 主 CTA、重点 / 推荐卡片、覆盖层 | 6-10 | 10-16 | 0.12-0.20 |

#### 不要叠加“视觉重量工具”

每个容器只选**一种**：阴影、边框、渐变填充、强底色。叠加使用会立刻变成“模板味”。

---

#### 滤镜软阴影——推荐方案

适用于：卡片、浮层面板、抬升元素。`svg_to_pptx` 转换器会自动把 `feGaussianBlur` + `feOffset` 转为原生 PPTX `<a:outerShdw>`。

```xml
<defs>
  <filter id="softShadow" x="-15%" y="-15%" width="140%" height="140%">
    <feGaussianBlur in="SourceAlpha" stdDeviation="12"/>
    <feOffset dx="0" dy="6" result="offsetBlur"/>
    <feFlood flood-color="#000000" flood-opacity="0.10" result="shadowColor"/>
    <feComposite in="shadowColor" in2="offsetBlur" operator="in" result="shadow"/>
    <feMerge>
      <feMergeNode in="shadow"/>
      <feMergeNode in="SourceGraphic"/>
    </feMerge>
  </filter>
</defs>
<rect x="60" y="60" width="400" height="240" rx="12" fill="#FFFFFF" filter="url(#softShadow)"/>
```

推荐参数（层级含义见上方“抬升层最多两级”）：
```
stdDeviation:   4–16       （静止层卡片：4–8；抬升层元素：10–16）
flood-opacity:  0.06–0.12  （静止层卡片——默认）
                0.12–0.20  （仅用于抬升层元素——主 CTA、覆盖层）
                不要超过 0.20 （会变成 Office 2007 式硬阴影）
dy:             2–10       （静止层：2–4；抬升层：6–10）
dx:             0–2        （必须与页面上其他阴影方向一致——单一光源）
```

#### 彩色阴影

适用于：强调按钮、品牌色卡片。应使用元素自身色系，而不是黑色。

```xml
<filter id="colorShadow" x="-15%" y="-15%" width="140%" height="140%">
  <feGaussianBlur in="SourceAlpha" stdDeviation="10"/>
  <feOffset dx="0" dy="6" result="offsetBlur"/>
  <feFlood flood-color="#1A73E8" flood-opacity="0.20" result="shadowColor"/>
  <feComposite in="shadowColor" in2="offsetBlur" operator="in" result="shadow"/>
  <feMerge>
    <feMergeNode in="shadow"/>
    <feMergeNode in="SourceGraphic"/>
  </feMerge>
</filter>
```

把 `flood-color` 替换为元素的品牌色。`flood-opacity` 建议维持在 0.12-0.20。每页最好只保留给唯一的主 CTA；如果每个按钮都加，强调就失效了。

#### 发光效果

适用于：标题强调、关键指标、hero 文案。转换器会自动把“没有 `feOffset` 的 `feGaussianBlur`”识别为原生 PPTX `<a:glow>`。

```xml
<defs>
  <filter id="titleGlow" x="-30%" y="-30%" width="160%" height="160%">
    <feGaussianBlur in="SourceAlpha" stdDeviation="6" result="blur"/>
    <feFlood flood-color="#1A73E8" flood-opacity="0.45" result="glowColor"/>
    <feComposite in="glowColor" in2="blur" operator="in" result="glow"/>
    <feMerge>
      <feMergeNode in="glow"/>
      <feMergeNode in="SourceGraphic"/>
    </feMerge>
  </filter>
</defs>
<text x="640" y="360" text-anchor="middle" font-size="48" fill="#1A73E8" filter="url(#titleGlow)">关键洞察</text>
```

推荐参数：
```
stdDeviation:   4–8      （更小 = 更克制；更大 = 更显著）
flood-color:    品牌色或强调色（不要用黑色）
flood-opacity:  0.35–0.55  （为了可见性，通常比阴影更强）
```

**与阴影的区别**：不应包含 `<feOffset>`（或 dx=0 / dy=0）。转换器正是通过这一点来区分 glow 和 shadow。

#### 叠层矩形阴影——高兼容回退方案

适用于：需要兼容较旧 PowerPoint 版本时。做法是在主卡片后面叠 2-3 个半透明矩形：

```xml
<!-- 阴影层（从后往前，先放位移最大的） -->
<rect x="68" y="72" width="400" height="240" rx="16" fill="#000000" fill-opacity="0.03"/>
<rect x="65" y="69" width="400" height="240" rx="14" fill="#000000" fill-opacity="0.05"/>
<rect x="62" y="66" width="400" height="240" rx="12" fill="#1A73E8" fill-opacity="0.04"/>
<!-- 主卡片 -->
<rect x="60" y="60" width="400" height="240" rx="12" fill="#FFFFFF"/>
```

### 图片覆盖层

#### 线性渐变覆盖层——最常用

适用于：图文叠加页面。渐变方向应与文字位置一致（文字在左，就让左侧更暗）。

```xml
<image href="..." x="0" y="0" width="1280" height="720" preserveAspectRatio="xMidYMid slice"/>
<defs>
  <linearGradient id="imgOverlay" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0%"   stop-color="#1A1A2E" stop-opacity="0.85"/>
    <stop offset="55%"  stop-color="#1A1A2E" stop-opacity="0.30"/>
    <stop offset="100%" stop-color="#1A1A2E" stop-opacity="0"/>
  </linearGradient>
</defs>
<rect x="0" y="0" width="1280" height="720" fill="url(#imgOverlay)"/>
```

#### 底部渐变条

适用于：封面页，或标题放在底部的全图页面。

```xml
<defs>
  <linearGradient id="bottomBar" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%"   stop-color="#000000" stop-opacity="0"/>
    <stop offset="100%" stop-color="#000000" stop-opacity="0.72"/>
  </linearGradient>
</defs>
<rect x="0" y="380" width="1280" height="340" fill="url(#bottomBar)"/>
```

#### 径向渐变覆盖层——暗角效果

适用于：全屏氛围页；可把注意力拉回中心区域。

```xml
<defs>
  <radialGradient id="vignette" cx="50%" cy="50%" r="70%">
    <stop offset="0%"   stop-color="#000000" stop-opacity="0"/>
    <stop offset="100%" stop-color="#000000" stop-opacity="0.58"/>
  </radialGradient>
</defs>
<rect x="0" y="0" width="1280" height="720" fill="url(#vignette)"/>
```

#### 品牌色覆盖层

适用于：需要强化品牌识别的页面。

```xml
<defs>
  <linearGradient id="brandOverlay" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0%"   stop-color="#005587" stop-opacity="0.80"/>
    <stop offset="100%" stop-color="#005587" stop-opacity="0.10"/>
  </linearGradient>
</defs>
<rect x="0" y="0" width="1280" height="720" fill="url(#brandOverlay)"/>
```

### 快速对照表

| 场景 | 推荐手法 | 避免 |
|----------|-----------------------|-------|
| 卡片 / 面板阴影（仅在浮于照片 / 色块之上时） | 滤镜软阴影（`flood-opacity` 0.06–0.12，单一光源） | 硬黑阴影、整页泛滥使用 |
| 同级卡片网格 | 全部保持平面（无阴影） | 每张卡都一起抬起来 |
| 页面分区背景面板 | 平面填充，无阴影 | 把背景面板当浮层卡片 |
| 强调 / CTA 按钮（每页一个） | 彩色阴影（同色系，`flood-opacity` 0.12–0.20） | 通用灰色阴影，或每个按钮都加 |
| 标题 / 指标强调 | 发光滤镜（品牌色，无偏移） | 在正文里大量滥用 |
| 图片上叠文字 | 线性渐变覆盖层（方向与文字所在侧一致） | 整张图统一压平透明黑层 |
| 封面 / 全图页 | 底部渐变条 + 品牌色 | 纯黑硬蒙层 |
| 氛围 / hero 页 | 径向暗角 | 未处理的原始大图 |
| 最高 PPT 兼容要求 | 叠层矩形阴影 | 滤镜型阴影 |

---

## 7. 描边、文字与图形效果

### `stroke-dasharray` —— 虚线 / 点线

会转换为原生 PPTX `<a:prstDash>`。建议优先使用以下预设模式：

| SVG 值 | PPTX 预设 | 适用场景 |
|-----------|-------------|----------|
| `4,4` | Dash | 普通虚线、分隔线 |
| `2,2` | Dot (sysDot) | 轻量点线边框、占位轮廓 |
| `8,4` | Long dash | 时间轴连接线、流程箭头 |
| `8,4,2,4` | Long dash-dot | 技术图、尺寸线 |

```xml
<rect x="60" y="60" width="400" height="240" rx="12"
  fill="none" stroke="#999999" stroke-width="2" stroke-dasharray="4,4"/>

<line x1="100" y1="360" x2="1180" y2="360"
  stroke="#CCCCCC" stroke-width="1" stroke-dasharray="2,2"/>
```

### `stroke-linejoin`

控制线段在拐角处的连接方式。支持值会转换为原生 PPTX 的 line join 类型：

| SVG 值 | PPTX 等价项 | 适用场景 |
|-----------|-----------------|----------|
| `round` | 圆角连接 | 圆滑折线图、有机形状 |
| `bevel` | 斜角连接 | 技术图 |
| `miter` | 尖角连接（默认） | 尖角矩形、箭头 |

```xml
<polyline points="100,200 200,100 300,200" fill="none"
  stroke="#1A73E8" stroke-width="3" stroke-linejoin="round"/>
```

### `text-decoration`

支持的文字装饰会转换为原生 PPTX 文本格式：

| SVG 值 | PPTX 等价项 | 适用场景 |
|-----------|-----------------|----------|
| `underline` | 单下划线 | 强调、链接、关键术语 |
| `line-through` | 删除线 | 删除项、前后对比 |

```xml
<text x="100" y="200" font-size="20" fill="#333333" text-decoration="underline">重要术语</text>

<!-- 针对单个 tspan 的装饰 -->
<text x="100" y="240" font-size="18" fill="#333333">
  当前值 <tspan text-decoration="line-through" fill="#999999">旧值</tspan> 新值
</text>
```

### 渐变填充——`linearGradient` 与 `radialGradient`

在 `<defs>` 中定义，并通过 `fill="url(#id)"` 引用的渐变，会转换为原生 PPTX `<a:gradFill>`。它们既可用于覆盖层，也可直接作为图形填充，做出更精致的表面效果。

**线性渐变**——适用于按钮、标题栏、背景面板：

```xml
<defs>
  <linearGradient id="btnGrad" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0%" stop-color="#1A73E8"/>
    <stop offset="100%" stop-color="#0D47A1"/>
  </linearGradient>
</defs>
<rect x="540" y="600" width="200" height="48" rx="24" fill="url(#btnGrad)"/>
```

**径向渐变**——适用于聚光背景、圆形强调元素：

```xml
<defs>
  <radialGradient id="spotBg" cx="50%" cy="50%" r="70%">
    <stop offset="0%" stop-color="#1A73E8" stop-opacity="0.15"/>
    <stop offset="100%" stop-color="#1A73E8" stop-opacity="0"/>
  </radialGradient>
</defs>
<circle cx="640" cy="360" r="300" fill="url(#spotBg)"/>
```

### `transform: rotate` —— 元素旋转

旋转会转换为原生 PPTX `<a:xfrm rot="...">`。支持所有常见元素：`rect`、`circle`、`ellipse`、`line`、`path`、`polygon`、`polyline`、`image`、`text`。

```xml
<!-- 旋转的装饰元素 -->
<rect x="100" y="100" width="60" height="60" fill="#1A73E8" fill-opacity="0.1"
  transform="rotate(45, 130, 130)"/>

<!-- 旋转的文字标签 -->
<text x="50" y="400" font-size="14" fill="#999999"
  transform="rotate(-90, 50, 400)">Y 轴标签</text>
```

**语法**：`rotate(angle)` 或 `rotate(angle, cx, cy)`，其中 `cx,cy` 是旋转中心。正角度表示顺时针旋转。

### 圆弧路径——环图 / 饼图

圆弧端点坐标必须用三角函数精确计算，绝不能靠目测估。哪怕很小的误差，也可能让形状完全错误。

**计算公式**（圆心 `cx,cy`，半径 `r`，角度 `θ`，单位为度）：
```
x = cx + r × cos(θ × π / 180)
y = cy + r × sin(θ × π / 180)
```

**关键规则**：
1. 从 **-90°**（12 点钟方向）开始，按顺时针计算
2. 每个扇区的角度 = `percentage × 360°`
3. 当扇区角度 > 180° 时，**large-arc flag = 1**；否则为 **0**
4. 外弧的 `sweep-direction = 1`（顺时针），内弧回程的 `sweep-direction = 0`（逆时针）
5. **务必检查**：所有扇区角度之和是否等于 360°，且最后一个扇区的终点是否与第一个扇区的起点闭合一致

**示例——75% 环形扇区**（圆心 400,400，外半径 r=180，内半径 r=100）：
```
起始角：-90°          → 外弧点(400, 220)，内弧点(400, 300)
结束角：-90+270=180° → 外弧点(220, 400)，内弧点(300, 400)
Large-arc flag：1（270° > 180°）

<path d="M 400,220 A 180,180 0 1,1 220,400 L 300,400 A 100,100 0 1,0 400,300 Z"/>
```

### 斜线上的多边形箭头

> 连接线优先使用 `marker-end` / `marker-start`（见 §1.1）。块状 / 宽体 / 实心 / 非连接器箭头，请使用独立 `polygon` 或 `path`。

水平 / 垂直线可以直接用简单偏移计算 `<polygon>` 箭头。斜线则必须把三角形顶点按线条方向旋转后再计算。

**方法**——通过线段方向向量计算三角形三个顶点：

```
已知线段从 (x1,y1) 到 (x2,y2)：
1. 方向向量：dx = x2-x1, dy = y2-y1
2. 归一化：len = √(dx²+dy²), ux = dx/len, uy = dy/len
3. 垂直向量：px = -uy, py = ux
4. 箭头尖端 = (x2, y2)
5. 底边点 1 = (x2 - ux×12 + px×5,  y2 - uy×12 + py×5)
6. 底边点 2 = (x2 - ux×12 - px×5,  y2 - uy×12 - py×5)
```

**示例——斜线**，从 (260,310) 到 (370,430)：
```
dx=110, dy=120, len≈162.8, ux=0.676, uy=0.737
px=-0.737, py=0.676
尖端： (370, 430)
底边点1： (370-8.1-3.7, 430-8.8+3.4) = (358.2, 424.6)
底边点2： (370-8.1+3.7, 430-8.8-3.4) = (365.6, 417.8)

<polygon points="370,430 365.6,417.8 358.2,424.6" fill="#C8A96E"/>
```

⚠️ 不要在斜线上直接套用“固定朝右 / 朝下”的三角箭头，否则箭头方向一定会错。

---

## 8. 项目目录结构

```
project/
├── svg_output/    # 原始 SVG（Executor 输出，可能含占位内容）
├── svg_final/     # 后处理后的最终 SVG（finalize_svg.py 输出）
├── images/        # 图片资源（用户提供 + AI 生成）
├── notes/         # 演讲备注（与 SVG 文件同名的 .md 文件）
│   └── total.md   # 完整备注文档（拆分前）
├── templates/     # 项目模板（如有）
└── *.pptx         # 导出的 PPT 文件
```
