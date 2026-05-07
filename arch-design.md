# PPT Master 架构设计文档

## 概述

PPT Master 是一个 AI 驱动的多格式 SVG 内容生成系统，通过多角色协作将源文档（PDF/DOCX/URL/Markdown）转换为高质量 SVG 页面，并导出为原生可编辑的 PPTX 文件。

**核心流水线**：`源文档 → 创建项目 → 模板选择 → 策略师 → 图像生成器 → 执行器 → 后处理 → 导出 PPTX`

---

## 1. 系统架构

### 1.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                      用户输入层                                  │
│  PDF/DOCX/URL/Markdown/文本描述/对话内容                          │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   源内容转换层 (Step 1)                          │
│  pdf_to_md.py | doc_to_md.py | excel_to_md.py                   │
│  ppt_to_md.py | web_to_md.py                                     │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   项目管理层 (Step 2)                           │
│  project_manager.py (init/validate/import-sources)               │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   设计规范层 (Step 3-4)                          │
│  模板系统 → Strategist (策略师) → design_spec.md + spec_lock.md │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   LLM SVG 生成层 (Step 5)                        │
│  Executor (执行器) → svg_output/                                  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   质量检查层 (Step 6 Gate)                        │
│  svg_quality_checker.py (黑名单检查/规范合规性)                 │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   SVG 后处理层 (Step 7.1-7.2)                     │
│  total_md_split.py → finalize_svg.py → svg_final/              │
│  (图标嵌入/图片裁剪/文本扁平化/圆角矩形转换)                       │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   PPTX 导出层 (Step 7.3)                          │
│  svg_to_pptx.py → DrawingML 转换 → 原生 PPTX                     │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 核心技术栈

| 层级 | 技术组件 | 说明 |
|------|---------|------|
| 源内容转换 | Python (pypdf, python-docx, pandas, pandoc) | 多格式文档转 Markdown |
| 项目管理 | Python (pathlib, shutil) | 项目结构管理 |
| LLM 生成 | AI Agent (Cascade) | 策略师/执行器角色 |
| SVG 处理 | Python (ElementTree, re, math) | SVG 解析/后处理 |
| PPTX 导出 | Python (python-pptx, zipfile) | DrawingML 生成/PPTX 组装 |
| 质量检查 | Python (ElementTree, xml验证) | SVG 规范检查 |

---

## 2. LLM SVG 生成核心技术

### 2.1 角色协作机制

项目采用多角色协作模式，每个角色负责特定阶段：

| 角色 | 职责 | 输出 |
|------|------|------|
| **Strategist (策略师)** | 分析源内容，确定设计规范 | design_spec.md (人类可读), spec_lock.md (机器可读执行锁) |
| **Executor (执行器)** | 根据 spec_lock.md 生成 SVG 页面 | svg_output/*.svg + notes/total.md |

**关键约束**：
- **串行执行**：步骤必须按顺序执行，每步输出作为下一步输入
- **阻塞点**：Strategist 的八项确认是唯一的阻塞点，需要用户明确确认
- **无跨阶段打包**：禁止跨阶段打包执行
- **每页 spec_lock 重读**：执行器每生成一页前必须重新读取 spec_lock.md，防止上下文压缩导致的设计漂移

### 2.2 spec_lock.md 执行锁机制

spec_lock.md 是机器可读的执行契约，定义了所有 SVG 生成必须遵守的设计参数：

```yaml
colors:
  primary: "#005587"
  secondary: "#F5F5F5"
  accent: "#1A73E8"
  # ... 更多颜色

icons:
  library: "chunk-filled"
  inventory:
    - "home"
    - "bolt"
    - # ... 更多图标

typography:
  font_family: "Microsoft YaHei, Arial, sans-serif"
  body: 18
  # ... 更多字体配置

images:
  - filename: "photo.jpg"
    status: "Generated"
    # ... 更多图片

page_rhythm:
  P01: "anchor"  # 封面
  P02: "dense"   # 内容页
  P03: "breathing"  # 留白页
  # ... 更多页面节奏
```

**执行器必须遵守的规则**：
- 颜色必须来自 `colors` 节
- 图标必须来自 `icons.inventory`，库必须匹配 `icons.library`
- 字体必须来自 `typography` 节
- 图片必须引用 `images` 中列出的文件
- 每页布局节奏来自 `page_rhythm`（anchor/dense/breathing）

### 2.3 SVG 生成规范

#### 2.3.1 黑名单特性

以下 SVG 特性被禁止，会导致 PPT 导出失败：

| 禁止特性 | 替代方案 |
|---------|---------|
| `mask` | 使用 `<rect>` 叠加或 `<filter>` 实现效果 |
| `<style>` / `class` | 使用内联样式 (`fill=""`, `font-size=""`) |
| `<foreignObject>` | 禁止使用 |
| `<symbol>` + `<use>` | 直接绘制元素 |
| `textPath` | 使用普通 `<text>` |
| `@font-face` | 使用预装字体栈 |
| `<animate*>` / `<script>` | 禁止使用 |

#### 2.3.2 文本规则

**单逻辑行 = 单 `<text>` 元素**：
- 即使混合颜色/粗细/大小，必须是一个 `<text>` 包含内联 `<tspan>`
- 多个相邻 `<text>` 会在 PPT 中变成多个独立文本框

```xml
<!-- ✅ 正确：一个 text，三个 tspan -->
<text x="100" y="200" font-size="24" fill="#333333">
  实现<tspan fill="#1A73E8" font-weight="bold">10倍</tspan>效率提升
</text>

<!-- ❌ 错误：三个 text 元素 -->
<text x="100" y="200" font-size="24" fill="#333333">实现</text>
<text x="160" y="200" font-size="24" fill="#1A73E8" font-weight="bold">10倍</text>
<text x="240" y="200" font-size="24" fill="#333333">效率提升</text>
```

**内联 tspan 规则**：
- 内联 tspan（用于颜色/粗细/大小）不能携带 `x`/`y`/`dy`
- 只有真正开始新行的 tspan 才设置 `x`/`y`/`dy`
- `dx` 是安全的（字距调整）

#### 2.3.3 元素分组规则

**必须使用 `<g id="...">` 分组**：
- 逻辑相关的元素必须包装在顶层 `<g id="...">` 组中
- 每页 3-8 个顶层内容组（排除页面装饰）
- 描述性 `id` 是必需的（如 `card-1`, `step-discover`, `header`）

**Chrome 组自动排除**：
- 包含特定 token 的组被视为页面装饰，不参与动画
- Token：`background`, `bg`, `decoration`, `decor`, `header`, `footer`, `chrome`, `watermark`, `pagenumber`

#### 2.3.4 图标占位符系统

使用 `data-icon` 属性作为占位符，后处理时嵌入实际 SVG：

```xml
<use data-icon="chunk-filled/home" x="100" y="200" width="48" height="48" fill="#005587"/>
```

**图标库规则**：
- 每个演示文稿只使用一个图标库
- 可选库：`chunk-filled`（直线几何），`tabler-filled`（贝塞尔曲线），`tabler-outline`（线稿），`phosphor-duotone`（双色）
- `simple-icons` 仅用于真实品牌标志

#### 2.3.5 图像处理

**基本语法**：
```xml
<image href="../images/photo.jpg" x="100" y="100" width="400" height="300" 
       preserveAspectRatio="xMidYMid slice"/>
```

**图片裁剪（条件允许）**：
- 仅允许在 `<image>` 元素上使用 `clip-path`
- 裁剪形状必须是单个 `<circle>`/`<ellipse>`/`<rect>`/`<path>`/`<polygon>`
- 映射到 DrawingML 几何（预设或自定义）

---

## 3. SVG 后处理技术

### 3.1 后处理流水线

`finalize_svg.py` 是统一入口，按顺序执行以下步骤：

```powershell
python scripts/finalize_svg.py <project_path>
```

**处理步骤**：

| 步骤 | 功能 | 实现模块 |
|------|------|---------|
| 1. 图标嵌入 | 将 `<use data-icon="..."/>` 替换为实际 SVG | `embed_icons.py` |
| 2. 图片裁剪 | 根据 `preserveAspectRatio="slice"` 智能裁剪 | `crop_images.py` |
| 3. 比例修正 | 防止 PPT 形状转换时的拉伸 | `fix_image_aspect.py` |
| 4. 图片嵌入 | 将外部图片转换为 Base64 嵌入 | `embed_images.py` |
| 5. 文本扁平化 | 将 `<tspan>` 转换为独立 `<text>`（特殊渲染器） | `flatten_tspan.py` |
| 6. 圆角矩形转换 | 将 `<rect rx="..."/>` 转换为 `<path>`（PPT 形状转换） | `svg_rect_to_path.py` |

### 3.2 关键技术实现

#### 3.2.1 图标嵌入

`embed_icons.py` 解析 `data-icon` 属性，从图标库加载 SVG 并内联：

```python
def process_svg_file(svg_file: Path, icons_dir: Path) -> int:
    """处理单个 SVG 文件，嵌入图标"""
    tree = ET.parse(str(svg_file))
    root = tree.getroot()
    
    # 查找所有 <use data-icon="..."> 元素
    for use_elem in root.iter():
        if use_elem.tag.endswith('use'):
            data_icon = use_elem.get('data-icon')
            if data_icon:
                library, icon_name = data_icon.split('/')
                icon_path = icons_dir / library / f"{icon_name}.svg"
                # 加载图标 SVG 并替换 <use> 元素
                # ...
```

#### 3.2.2 图片裁剪

`crop_images.py` 根据 `preserveAspectRatio="slice"` 计算裁剪区域：

```python
def process_svg_images(svg_path: str) -> tuple[int, int]:
    """处理 SVG 中的图片裁剪"""
    tree = ET.parse(svg_path)
    root = tree.getroot()
    
    for img_elem in root.iter():
        if img_elem.tag.endswith('image'):
            preserve_aspect = img_elem.get('preserveAspectRatio')
            if preserve_aspect and 'slice' in preserve_aspect:
                # 计算裁剪坐标
                # 修改图片的 x, y, width, height
                # ...
```

#### 3.2.3 圆角矩形转换

`svg_rect_to_path.py` 将 `<rect rx="..."/>` 转换为 `<path>` 以支持 PPT 形状转换：

```python
def rect_to_path(x: float, y: float, width: float, height: float, rx: float, ry: float) -> str:
    """将圆角矩形转换为 path 命令"""
    if rx == 0 and ry == 0:
        return f"M {x},{y} h {width} v {height} h {-width} Z"
    
    # 计算圆角矩形的四个角
    # 生成 path 命令：M (起点) L (直线) A (圆弧) ...
    path_commands = []
    # ... 复杂的圆角计算
    return ' '.join(path_commands)
```

---

## 4. SVG 到 PPTX 转换技术

### 4.1 DrawingML 转换架构

`svg_to_pptx/` 包实现 SVG 到 PowerPoint DrawingML 格式的转换：

**核心模块**：

| 模块 | 功能 |
|------|------|
| `drawingml_converter.py` | SVG → DrawingML 分发器，处理 `<g>` 分组 |
| `drawingml_elements.py` | SVG 元素转换器（rect, circle, line, path, text, image） |
| `drawingml_styles.py` | 样式转换（填充、描边、效果） |
| `drawingml_paths.py` | SVG path 命令解析和 DrawingML 路径生成 |
| `drawingml_utils.py` | 工具函数（坐标转换、颜色解析、字体处理） |
| `pptx_builder.py` | PPTX 文件组装 |
| `pptx_animations.py` | 动画效果生成 |

### 4.2 元素转换映射

#### 4.2.1 基本形状

| SVG 元素 | DrawingML 输出 |
|---------|----------------|
| `<rect>` | `<a:prstGeom prst="rect"/>` |
| `<circle>` / `<ellipse>` | `<a:prstGeom prst="ellipse"/>` |
| `<line>` | `<a:ln>` (线条) |
| `<path>` | `<a:custGeom>` (自定义几何) |
| `<polygon>` / `<polyline>` | `<a:custGeom>` |

#### 4.2.2 文本转换

SVG `<text>` 元素映射到 DrawingML 文本框：

```xml
<!-- SVG 输入 -->
<text x="100" y="200" font-size="24" fill="#333333">
  Hello<tspan fill="#1A73E8" font-weight="bold">World</tspan>
</text>

<!-- DrawingML 输出 -->
<p:sp>
  <p:txBody>
    <a:p>
      <a:r>
        <a:t>Hello</a:t>
        <a:rPr lang="en-US" sz="2400" fill="333333"/>
      </a:r>
      <a:r>
        <a:t>World</a:t>
        <a:rPr lang="en-US" sz="2400" fill="1A73E8" b="1"/>
      </a:r>
    </a:p>
  </p:txBody>
</p:sp>
```

**关键转换规则**：
- 每个 `<tspan>` 映射到一个 `<a:r>` (run)
- 字体大小：SVG px → DrawingML hundredths of point (乘以 100)
- 颜色：HEX 字符串直接使用
- 粗体：`font-weight="bold"` → `b="1"`

#### 4.2.3 路径转换

`drawingml_paths.py` 解析 SVG path 命令并转换为 DrawingML 路径：

```python
def parse_svg_path(d: str) -> list[PathCommand]:
    """解析 SVG path d 属性"""
    commands = []
    # 解析 M, L, H, V, C, S, Q, T, A, Z 命令
    # 返回 PathCommand 对象列表
    return commands

def path_commands_to_drawingml(commands: list[PathCommand], w_emu: int, h_emu: int) -> str:
    """将 path 命令转换为 DrawingML 路径 XML"""
    xml_lines = []
    for cmd in commands:
        if cmd.type == 'M':
            xml_lines.append(f'<a:moveTo><a:pt x="{cmd.x}" y="{cmd.y}"/></a:moveTo>')
        elif cmd.type == 'L':
            xml_lines.append(f'<a:lnTo><a:pt x="{cmd.x}" y="{cmd.y}"/></a:lnTo>')
        # ... 其他命令
    return '\n'.join(xml_lines)
```

### 4.3 样式转换

#### 4.3.1 填充转换

`drawingml_styles.py` 处理填充转换：

| SVG 填充 | DrawingML 输出 |
|---------|----------------|
| `fill="#FF0000"` | `<a:solidFill><a:srgbClr val="FF0000"/></a:solidFill>` |
| `fill-opacity="0.5"` | `<a:solidFill><a:srgbClr val="FF0000"><a:alpha val="50000"/></a:srgbClr></a:solidFill>` |
| `fill="url(#gradient)"` | `<a:gradFill>` + `<a:gsLst>` |

#### 4.3.2 描边转换

```python
def build_stroke_xml(elem: ET.Element, ctx: ConvertContext, opacity: float) -> str:
    """构建描边 XML"""
    stroke = _get_attr(elem, 'stroke', ctx)
    if not stroke or stroke == 'none':
        return ''
    
    width = _f(_get_attr(elem, 'stroke-width', ctx), 1)
    dasharray = _get_attr(elem, 'stroke-dasharray', ctx)
    
    stroke_xml = f'<a:ln w="{px_to_emu(width)}">'
    stroke_xml += build_solid_fill(stroke, opacity)
    
    if dasharray:
        stroke_xml += build_dash_xml(dasharray)
    
    stroke_xml += '</a:ln>'
    return stroke_xml
```

**虚线映射**：

| SVG stroke-dasharray | DrawingML 预设 |
|---------------------|----------------|
| `4,4` | `dash` |
| `2,2` | `sysDot` |
| `8,4` | `lgDash` |
| `8,4,2,4` | `dashDot` |

#### 4.3.3 效果转换

`drawingml_styles.py` 处理 SVG 滤镜效果到 DrawingML 效果的转换：

```python
def build_effect_xml(filter_elem: ET.Element) -> str:
    """构建效果 XML（阴影/发光）"""
    # 解析 <feGaussianBlur> + <feOffset> → <a:outerShdw>
    # 解析 <feGaussianBlur> (无 offset) → <a:glow>
    # ...
```

**阴影映射**：

```xml
<!-- SVG 输入 -->
<filter id="shadow">
  <feGaussianBlur in="SourceAlpha" stdDeviation="12"/>
  <feOffset dx="0" dy="6"/>
  <feFlood flood-color="#000000" flood-opacity="0.10"/>
  <feComposite operator="in"/>
  <feMerge>
    <feMergeNode in="shadow"/>
    <feMergeNode in="SourceGraphic"/>
  </feMerge>
</filter>

<!-- DrawingML 输出 -->
<a:effectLst>
  <a:outerShdw blurRad="228600" dist="171450" rotWithShape="0">
    <a:srgbClr val="000000">
      <a:alpha val="10000"/>
    </a:srgbClr>
  </a:outerShdw>
</a:effectLst>
```

### 4.4 分组处理

`drawingml_converter.py` 处理 `<g>` 分组转换：

```python
def convert_g(elem: ET.Element, ctx: ConvertContext) -> ShapeResult | None:
    """转换 SVG <g> 到 DrawingML <p:grpSp>"""
    # 解析 transform (translate, scale, rotate)
    dx, dy, sx, sy, angle_deg = parse_transform(elem.get('transform', ''))
    
    # 递归转换子元素
    child_results = []
    for child in elem:
        result = convert_element(child, child_ctx)
        if result:
            child_results.append(result)
    
    # 计算组边界
    min_x = min(r.bounds_emu[0] for r in child_results)
    min_y = min(r.bounds_emu[1] for r in child_results)
    max_x = max(r.bounds_emu[2] for r in child_results)
    max_y = max(r.bounds_emu[3] for r in child_results)
    
    # 生成 <p:grpSp> XML
    group_xml = f'''<p:grpSp>
<p:nvGrpSpPr>
<p:cNvPr id="{group_id}" name="Group {group_id}"/>
</p:nvGrpSpPr>
<p:grpSpPr>
<a:xfrm rot="{rot_emu}">
<a:off x="{group_x}" y="{group_y}"/>
<a:ext cx="{group_w}" cy="{group_h}"/>
<a:chOff x="{group_x}" y="{group_y}"/>
<a:chExt cx="{group_w}" cy="{group_h}"/>
</a:xfrm>
</p:grpSpPr>
{shapes_xml}
</p:grpSp>'''
    
    return ShapeResult(xml=group_xml, bounds_emu=(min_x, min_y, max_x, max_y))
```

**动画目标记录**：
- 顶层语义组（非 chrome）记录到 `ctx.anim_targets`
- 用于后续生成入场动画时序

### 4.5 PPTX 文件组装

`pptx_builder.py` 组装最终的 PPTX 文件：

```python
def create_pptx_with_native_svg(
    svg_files: list[Path],
    output_path: Path,
    canvas_format: str | None = None,
    use_native_shapes: bool = False,
    animation: str | None = None,
    # ...
) -> bool:
    """创建包含原生 SVG 的 PPTX 文件"""
    
    # 1. 创建空白 PPTX
    prs = Presentation()
    
    # 2. 设置幻灯片尺寸
    width_emu, height_emu = get_slide_dimensions(canvas_format)
    prs.slide_width = Emu(width_emu)
    prs.slide_height = Emu(height_emu)
    
    # 3. 处理每个 SVG 文件
    for i, svg_file in enumerate(svg_files, 1):
        # 转换 SVG 到 DrawingML
        slide_xml, media_files, rel_entries, anim_targets = convert_svg_to_slide_shapes(
            svg_file, slide_num=i, verbose=verbose
        )
        
        # 添加幻灯片
        slide = prs.slides.add_slide()
        
        # 写入 DrawingML XML
        # ...
        
        # 添加动画（如果启用）
        if animation and anim_targets:
            add_animation(slide, anim_targets, animation, animation_trigger)
    
    # 4. 保存 PPTX
    prs.save(str(output_path))
    return True
```

---

## 5. 质量保证技术

### 5.1 SVG 质量检查

`svg_quality_checker.py` 在 SVG 生成后执行，确保符合技术规范：

**检查项目**：

| 检查项 | 说明 | 错误级别 |
|-------|------|---------|
| XML 格式良好性 | 确保文件是有效的 XML | Error |
| viewBox 匹配 | viewBox 必须匹配 width/height | Error |
| 禁止元素 | 检查黑名单特性（mask, style, class 等） | Error |
| 字体合规性 | 字体栈必须以预装字体结尾 | Error/Warning |
| 尺寸一致性 | width/height 必须匹配 viewBox | Error |
| 文本元素 | 检查文本换行方法 | Warning |
| 图片引用 | 检查文件存在性和分辨率 | Warning |
| spec_lock 漂移 | 检查颜色/字体/图标是否偏离 spec_lock | Error |

**关键检查实现**：

```python
def _check_forbidden_elements(self, content: str, result: Dict):
    """检查禁止的 SVG 元素"""
    forbidden_patterns = [
        r'<mask\b',          # mask 元素
        r'<style\b',         # style 元素
        r'class=',           # class 属性
        r'<foreignObject\b', # foreignObject
        r'<symbol\b',        # symbol
        r'textPath=',        # textPath
        r'@font-face',       # @font-face
        r'<animate\b',       # animate
        r'<script\b',        # script
    ]
    
    for pattern in forbidden_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            result['errors'].append(f"禁止元素: {pattern}")
```

### 5.2 spec_lock 漂移检测

```python
def _check_spec_lock_drift(self, content: str, svg_path: Path, result: Dict):
    """检查 spec_lock 漂移"""
    if not _parse_spec_lock:
        return  # 跳过检查
    
    # 加载 spec_lock.md
    lock = self._get_spec_lock(svg_path.parent)
    if not lock:
        return
    
    # 检查颜色漂移
    used_colors = HEX_VALUE_RE.findall(content)
    allowed_colors = set(lock.get('colors', {}).values())
    for color in used_colors:
        if color not in allowed_colors:
            result['errors'].append(f"颜色漂移: {color} 不在 spec_lock 中")
    
    # 检查字体漂移
    # 检查图标漂移
    # ...
```

---

## 6. 动画支持技术

### 6.1 动画架构

`pptx_animations.py` 实现页面过渡和元素入场动画：

**动画类型**：

| 类型 | 效果 | DrawingML 实现 |
|------|------|----------------|
| 页面过渡 | fade, push, wipe, split, strips, cover | `<p:transition>` |
| 元素入场 | fade, zoom, fly, float, bounce 等 22 种效果 | `<p:seq>` + `<p:anim>` |

### 6.2 元素入场动画

基于顶层 `<g id="...">` 分组生成动画：

```python
def create_sequence_timing_xml(
    anim_targets: list[tuple[int, str]],
    effect: str,
    trigger: str = 'after-previous',
    duration: float = 0.3,
    stagger: float = 0.1,
) -> str:
    """创建动画时序 XML"""
    
    # 将动画目标扩展到组的子形状（避免 Mac PowerPoint 的组目标问题）
    expanded_targets = _expand_anim_targets_to_group_children(slide_xml, anim_targets)
    
    xml_lines = ['<p:seq>']
    
    for i, (shape_ids, svg_id) in enumerate(expanded_targets):
        # 计算延迟
        if trigger == 'after-previous':
            delay = i * stagger
        else:
            delay = 0
        
        # 为每个形状添加动画
        for shape_id in shape_ids:
            anim_xml = create_shape_animation_xml(shape_id, effect, duration, delay)
            xml_lines.append(anim_xml)
    
    xml_lines.append('</p:seq>')
    return '\n'.join(xml_lines)
```

**动画触发模式**：

| 模式 | 说明 | PowerPoint 对应 |
|------|------|----------------|
| `after-previous` | 级联播放（默认） | After Previous |
| `on-click` | 点击播放 | On Click |
| `with-previous` | 同时播放 | With Previous |

---

## 7. 坐标系统与单位转换

### 7.1 坐标系统

项目使用 EMU (English Metric Units) 作为内部坐标单位：

```
1 inch = 914400 EMU
1 cm = 360000 EMU
1 px (96 DPI) = 9525 EMU
```

**转换函数**：

```python
def px_to_emu(px: float) -> int:
    """像素转 EMU"""
    return int(px * 9525)

def emu_to_px(emu: int) -> float:
    """EMU 转像素"""
    return emu / 9525
```

### 7.2 字体大小转换

SVG 使用像素单位，DrawingML 使用百分之一点：

```python
FONT_PX_TO_HUNDREDTHS_PT = 100  # 1 px = 100 hundredths of point (at 96 DPI)

def font_size_to_drawingml(px: float) -> int:
    """字体大小转换"""
    return int(px * FONT_PX_TO_HUNDREDTHS_PT)
```

### 7.3 角度转换

SVG 角度（度）到 DrawingML 角度（60,000 分之一度）：

```python
ANGLE_UNIT = 60000  # 1 degree = 60000 units

def angle_to_drawingml(deg: float) -> int:
    """角度转换"""
    return int(deg * ANGLE_UNIT)
```

---

## 8. 图表坐标校准技术

### 8.1 问题背景

AI 模型在将数据映射到像素位置时经常引入 10-50 px 的误差，导致图表不准确。

### 8.2 解决方案

`svg_position_calculator.py` 提供精确的图表坐标计算：

**支持的图表类型**：

| 图表类型 | 计算命令 | 参数 |
|---------|---------|------|
| 柱状图 | `calc bar` | `--data "L1:V1,L2:V2" --area "x_min,y_min,x_max,y_max" --bar-width 120 --value-range "0,axis_max"` |
| 折线图 | `calc line` | `--data "x1:y1,x2:y2" --area "x_min,y_min,x_max,y_max" --y-range "0,max"` |
| 饼图 | `calc pie` | `--data "A:35,B:25" --center "cx,cy" --radius 200 [--inner-radius 120]` |
| 雷达图 | `calc radar` | `--data "D1:V1,D2:V2,D3:V3" --center "cx,cy" --radius 200` |

### 8.3 绘图区标记

每个图表页面必须包含绘图区标记：

```xml
<g id="chartArea">
  <!-- chart-plot-area: x_min,y_min,x_max,y_max -->
  <!-- 轴线 -->
  <!-- 数据元素 -->
</g>
```

**标记格式**：

```xml
<!-- 矩形绘图区（柱状图/折线图等）-->
<!-- chart-plot-area: 100,100,1100,500 -->

<!-- 饼图 -->
<!-- chart-plot-area: pie | center: 640,360 | radius: 200 -->

<!-- 环形图 -->
<!-- chart-plot-area: donut | center: 640,360 | outer-radius: 200 | inner-radius: 120 -->

<!-- 雷达图 -->
<!-- chart-plot-area: radar | center: 640,360 | radius: 200 -->
```

---

## 9. 技术约束与设计决策

### 9.1 为什么使用 SVG 而非直接生成 PPTX

| 方面 | SVG | 直接 PPTX |
|------|-----|-----------|
| 可视化预览 | ✅ 浏览器直接预览 | ❌ 需要打开 PowerPoint |
| 可编辑性 | ✅ 文本格式，易于调试 | ❌ 二进制 XML，难以调试 |
| 跨平台兼容性 | ✅ 标准格式 | ✅ 但依赖 Office 版本 |
| LLM 生成友好性 | ✅ 简洁语法，易于理解 | ❌ DrawingML 复杂冗长 |
| 转换精度 | ✅ 高精度映射 | ⚠️ 可能丢失细节 |

### 9.2 为什么需要 spec_lock.md

| 问题 | 解决方案 |
|------|---------|
| 上下文压缩导致设计漂移 | 每页重读 spec_lock.md |
| 颜色/字体不一致 | 执行锁强制一致性 |
| 图标库混用 | spec_lock 定义单一库 |
| 字体大小失控 | ramp envelope 约束 |

### 9.3 为什么需要后处理

| 处理步骤 | 原因 |
|---------|------|
| 图标嵌入 | 占位符保持 SVG 简洁，后处理嵌入实际内容 |
| 图片裁剪 | preserveAspectRatio="slice" 需要实际裁剪 |
| 文本扁平化 | 某些渲染器不支持 tspan |
| 圆角矩形转换 | PPT 形状转换需要 path 格式 |

### 9.4 为什么使用 DrawingML 而非 SVG 嵌入

| 方面 | DrawingML 转换 | SVG 嵌入 |
|------|---------------|---------|
| 可编辑性 | ✅ 原生形状，完全可编辑 | ⚠️ 整体图片，不可编辑 |
| 文本选择 | ✅ 可选择文本 | ❌ 文本在图片中 |
| 动画支持 | ✅ 原生动画 | ❌ 无动画 |
| 文件大小 | ✅ 矢量，小 | ⚠️ 可能较大 |
| 兼容性 | ✅ 所有版本 | ⚠️ 旧版本不支持 |

---

## 10. 性能优化

### 10.1 批量处理

- 图标嵌入：批量加载图标库，避免重复读取
- 图片处理：并行处理多个 SVG 文件

### 10.2 缓存机制

- spec_lock.md 缓存：避免重复解析
- 图标库缓存：内存中缓存已加载图标

### 10.3 增量处理

- 后处理：仅处理修改过的 SVG 文件
- 质量检查：仅检查新增/修改的文件

---

## 11. 扩展性设计

### 11.1 新增 SVG 元素支持

在 `drawingml_elements.py` 添加转换器：

```python
def convert_new_element(elem: ET.Element, ctx: ConvertContext) -> ShapeResult | None:
    """转换新的 SVG 元素"""
    # 实现转换逻辑
    return ShapeResult(xml=..., bounds_emu=...)
```

在 `_CONVERTERS` 字典注册：

```python
_CONVERTERS = {
    # ... 现有转换器
    'newElement': convert_new_element,
}
```

### 11.2 新增动画效果

在 `pptx_animations.py` 添加效果：

```python
EFFECTS = {
    # ... 现有效果
    'newEffect': {
        'preset': 'newPreset',
        'direction': 'in',
    },
}
```

### 11.3 新增画布格式

在 `pptx_dimensions.py` 添加格式：

```python
CANVAS_FORMATS = {
    # ... 现有格式
    'newFormat': {
        'name': 'New Format',
        'width_px': 1920,
        'height_px': 1080,
        'aspect': '16:9',
    },
}
```

---

## 12. 总结

PPT Master 的核心技术可以概括为：

1. **LLM 驱动的 SVG 生成**：通过多角色协作和 spec_lock.md 执行锁，确保设计一致性和质量
2. **严格的 SVG 技术约束**：黑名单机制和规范检查，确保 SVG 可转换为 PPT
3. **智能后处理流水线**：图标嵌入、图片裁剪、文本扁平化、圆角矩形转换
4. **高精度 DrawingML 转换**：SVG 元素映射到原生 PowerPoint 形状，保持可编辑性
5. **质量保证体系**：SVG 质量检查、spec_lock 漂移检测、图表坐标校准
6. **动画支持**：页面过渡和元素入场动画，增强演示效果

**技术亮点**：

- **可编辑性**：生成的 PPTX 是原生 DrawingML 形状，完全可编辑
- **一致性**：spec_lock.md 确保整个演示文稿的设计一致性
- **可维护性**：SVG 作为中间格式，易于调试和修改
- **可扩展性**：模块化设计，易于添加新功能和格式支持

**应用场景**：

- 快速生成专业演示文稿
- 批量转换文档为 PPT
- 自动化报告生成
- 多语言演示文稿生成

---

## 附录：关键文件索引

| 文件路径 | 功能 |
|---------|------|
| `skills/ppt-master/SKILL.md` | 主工作流文档 |
| `skills/ppt-master/references/shared-standards.md` | SVG/PPT 技术约束 |
| `skills/ppt-master/references/executor-base.md` | 执行器指南 |
| `skills/ppt-master/scripts/finalize_svg.py` | SVG 后处理入口 |
| `skills/ppt-master/scripts/svg_quality_checker.py` | SVG 质量检查 |
| `skills/ppt-master/scripts/svg_to_pptx/drawingml_converter.py` | DrawingML 转换器 |
| `skills/ppt-master/scripts/svg_to_pptx/drawingml_elements.py` | 元素转换器 |
| `skills/ppt-master/scripts/svg_to_pptx/pptx_builder.py` | PPTX 构建器 |
| `skills/ppt-master/scripts/svg_position_calculator.py` | 图表坐标计算器 |
