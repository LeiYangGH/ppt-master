> 参见 shared-standards.md 中的通用技术约束。

# SVG 图片嵌入指南

添加图片到 SVG 文件的技术规范和工作流程。

---

## 图片资源清单格式

图片资源清单定义在《设计规范与内容大纲》中。如果图片策略包含 "B) 用户提供"，则应在八项确认之后立刻运行 `analyze_images.py`，并在输出设计规范前补全清单。

```markdown
| 文件名 | 尺寸 | 用途 | 类型 |
|----------|------------|---------|------|
| cover_bg.png | 1280x720 | 封面背景 | 背景 |
| product.png | 600x400 | 第 3 页产品照片 | 摄影 |
```

### 图片状态

图片均由用户提供，状态统一为 **Existing**，直接从 `../images/` 引用。

---

## 工作流

```
1. Strategist 明确图片需求 → 添加图片资源清单
2. 用户将图片放入 project/images/
3. Executor 生成 SVG（svg_output/）
   └── Existing → <image href="../images/xxx.png" .../>
4. 预览：python -m http.server -d <project_path> 8000 → /svg_output/<filename>.svg
5. 后处理与导出 → 按 shared-standards.md §5 执行
```

> 生成阶段请保留 `svg_output/` 中的外部图片引用。`finalize_svg.py` 会自动把它们嵌入到 `svg_final/`；导出 PPTX 时应从 `svg_final/` 导出。

---

## 外部引用 vs Base64 嵌入

| 方法 | 优点 | 缺点 | 适用阶段 |
|--------|------|------|-------------|
| **外部引用** | 文件小、迭代快、易替换 | 预览时需从项目根目录启 HTTP 服务 | `svg_output/` 开发阶段 |
| **Base64 嵌入** | 文件自包含、导出更稳 | 文件体积大 | `svg_final/` 交付阶段 |

---

## 方法一：外部引用（推荐用于生成阶段）

### 语法

```xml
<image href="../images/image.png" x="0" y="0" width="1280" height="720"
       preserveAspectRatio="xMidYMid slice"/>
```

### 关键属性

| 属性 | 说明 | 示例 |
|-----------|-------------|---------|
| `href` | 图片路径（相对或绝对） | `"../images/cover.png"` |
| `x`, `y` | 图片左上角坐标 | `x="0" y="0"` |
| `width`, `height` | 显示尺寸 | `width="1280" height="720"` |
| `preserveAspectRatio` | 缩放模式 | `"xMidYMid slice"` |

### 常见 `preserveAspectRatio` 取值

| 值 | 效果 |
|-------|--------|
| `xMidYMid slice` | 居中裁切，类似 CSS `cover` |
| `xMidYMid meet` | 完整显示，类似 CSS `contain` |
| `none` | 拉伸铺满，不保留比例 |

---

## 方法二：Base64 嵌入（推荐用于交付阶段）

### 语法

```xml
<image href="data:image/png;base64,iVBORw0KGgo..." x="0" y="0" width="1280" height="720"/>
```

### MIME 类型

| MIME Type | 文件格式 |
|-----------|-------------|
| `image/png` | PNG |
| `image/jpeg` | JPG/JPEG |
| `image/gif` | GIF |
| `image/webp` | WebP |
| `image/svg+xml` | SVG |

---

## 转换流程

使用`shared-standards.md`中的统一流程。`finalize_svg.py` 会在导出前把 `svg_output/` 中的图片引用嵌入到 `svg_final/`。

```powershell
python scripts/finalize_svg.py <project_path>
python scripts/svg_to_pptx.py <project_path> -s final
```

### 独立使用：`embed_images.py`（高级）

如果只想处理指定 SVG，而不跑完整流程：

```powershell
python scripts/svg_finalize/embed_images.py <svg_file>                         # 单文件
python scripts/svg_finalize/embed_images.py <project_path>/svg_output/*.svg    # 批量
python scripts/svg_finalize/embed_images.py --dry-run <project_path>/svg_output/*.svg  # 预览
```

---

## 最佳实践

### 图片优化

嵌入前先压缩，减少文件体积：

```powershell
convert input.png -quality 85 -resize 1920x1080\> output.png  # ImageMagick
pngquant --quality=65-80 input.png -o output.png               # pngquant（推荐）
```

### 文件组织

```
project/
├── images/            # 图片资源
├── sources/           # 源文件及其附带图片
│   └── article_files/
├── svg_output/        # 原始版（外部引用）
└── svg_final/         # 最终版（图片已嵌入）
```

### 圆角 / 非矩形图片裁切

仅当 `clipPath` 用在 **`<image>` 元素** 上时，才属于条件允许。权威约束见 [shared-standards.md §1.2](shared-standards.md)，这里不重复放宽。

若 `clipPath` 不适用，兜底方案是在嵌入前先把圆角烘焙进源图（带 alpha 的 PNG）。
