# Image_Generator 参考手册

> 本文件是 Image_Generator 角色的精简参考。通用标准（SVG 技术约束、画布格式、后处理流程等）见 [shared-standards.md](./shared-standards.md)。

## 核心使命

接收 Strategist 输出的《设计规范与内容大纲》中的“图片资源清单”，为每张待生成图片编写优化后的提示词，通过 AI 工具生成图片，并保存到项目的 `images/` 目录。

**触发条件**：需要 AI 生图时（独立使用，或在主流程中被调用）

| 模式 | 触发方式 | 说明 |
|------|---------|-------------|
| **独立模式** | 直接描述图片需求 | 生成单张或多张 AI 图片 |
| **流程内模式** | `generate-ppt` 且选择 AI 生图 | 为项目批量生成图片资源 |

> 流程中的下一步：Executor 生成 SVG

---

## 1. 输入与输出

### 输入

- **设计规范与内容大纲**（来自 Strategist）：项目主题、目标受众、设计风格、配色方案、画布格式
- **图片资源清单**（关键输入）：

  | Filename | Dimensions | Purpose | Type | Status | Generation Description |
  |----------|-----------|---------|------|--------|----------------------|
  | cover_bg.png | 1920x1080 | Cover background | Background | Pending | Modern tech abstract background, deep blue gradient |

  状态定义见 [`svg-image-embedding.md`](svg-image-embedding.md)。Image_Generator 只处理 `Pending` 行，并将其更新为 `Generated` 或 `Needs-Manual`。

### 输出

| 交付物 | 路径 / 说明 | 要求 |
|------------|-------------------|--------------|
| 提示词文档 | `project/images/image_prompts.md` | **必须**实际写入文件，不能只在对话中输出 |
| 优化提示词 | 每张图片一条独立提示词 | 可直接用于 AI 生图，也可兼作 alt text |
| 图片文件 | `project/images/` 目录 | 文件名必须与资源清单一致 |
| 更新后的清单 | 状态变化 | `Pending` -> `Generated`（成功）或 `Pending` -> `Needs-Manual`（尝试生成但失败） |

---

## 2. 统一提示词结构

### 2.1 标准输出格式

每张图片都必须按以下格式输出：

```markdown
### Image N: {filename}

| 属性 | 值 |
| --------- | ----- |
| Purpose   | {用于哪一页 / 起什么作用} |
| Type      | {Background / Illustration / Photography / Diagram / Decorative} |
| Dimensions | {width}x{height} ({aspect ratio}) |
| Original description | {清单中给出的原始描述} |

**Prompt**:
{subject description}, {style directive}, {color directive}, {composition directive}, {quality directive}

**Negative Prompt**:
{elements to exclude}

**Alt Text**:
> {Description for accessibility and image captions}
```

### 2.2 提示词组成

| 组件 | 说明 | 示例 |
|-----------|-------------|---------|
| 主体描述 | 核心内容 | `Abstract geometric shapes`、`Team collaboration scene` |
| 风格指令 | 视觉风格 | `flat design`、`3D isometric`、`watercolor style` |
| 颜色指令 | 配色方案 | `color palette: navy blue (#1E3A5F), gold (#D4AF37)` |
| 构图指令 | 布局比例 | `16:9 aspect ratio`、`centered composition` |
| 质量指令 | 清晰度与分辨率 | `high quality`、`4K resolution`、`sharp details` |
| 负面提示词 | 要排除的元素 | `text, watermark, blurry, low quality` |

### 2.3 风格关键词速查

| 设计风格 | 推荐图片风格 | 核心关键词 |
|-------------|------------------------|---------------|
| 通用创意 | 现代插画、扁平设计 | `modern`, `flat design`, `gradient`, `vibrant colors` |
| 通用咨询 | 干净、专业、企业感 | `professional`, `clean`, `corporate`, `minimalist` |
| 顶级咨询 | 高级极简、抽象几何 | `premium`, `sophisticated`, `geometric`, `abstract`, `elegant` |
| 科技 / SaaS | 未来感、数字感 | `futuristic`, `digital`, `tech grid`, `circuit pattern`, `neon accents`, `dark background` |
| 教育 / 培训 | 友好、教学感 | `friendly`, `instructional`, `whiteboard style`, `pastel colors`, `simple shapes` |
| 营销 / 品牌 | 大胆、有能量 | `bold`, `energetic`, `dynamic composition`, `vivid colors`, `action-oriented` |
| 医疗 / 健康 | 干净、安心 | `clean`, `clinical`, `soft blue-green palette`, `organic curves`, `reassuring` |
| 金融 / 银行 | 保守、可信 | `conservative`, `trustworthy`, `blue-gray palette`, `structured`, `precise` |
| 创意 / 设计 | 艺术化、实验性 | `artistic`, `experimental`, `asymmetric`, `textured`, `hand-crafted feel` |

### 2.4 配色整合法

从设计规范中提取颜色，并转成提示词指令：

```
Primary: #1E3A5F (Deep Navy)  →  "deep navy blue (#1E3A5F)"
Secondary: #F8F9FA (Light Gray) →  "light gray (#F8F9FA)"
Accent: #D4AF37 (Gold)        →  "gold accent (#D4AF37)"

完整指令：`color palette: deep navy blue (#1E3A5F), light gray (#F8F9FA), gold accent (#D4AF37)`
```

### 2.5 画布格式与宽高比

| 画布格式 | 背景图比例 | 推荐分辨率 |
|--------------|------------------------|----------------------|
| PPT 16:9 | 16:9 | 1920x1080 or 2560x1440 |
| PPT 4:3 | 4:3 | 1600x1200 |
| Xiaohongshu (RED) | 3:4 | 1242x1660 |
| WeChat Moments | 1:1 | 1080x1080 |
| Story | 9:16 | 1080x1920 |

> 支持的比例：`1:1`、`2:3`、`3:2`、`3:4`、`4:3`、`4:5`、`5:4`、`9:16`、`16:9`、`21:9`（Gemini 还支持 `1:4`、`1:8`、`4:1`、`8:1`）

### 2.6 多图一致性策略

同一套 deck 生成多张图片时，视觉一致性非常关键。建议使用 **Deck Style Anchor**——一段 15-25 词的共享前缀，放在每张图片提示词最前面。

**构建方法**：把风格关键词（2.3）+ 颜色指令（2.4）+ 质量指令组合成一个可复用前缀。

**示例**：
```
Deck Style Anchor:
"modern flat design illustration, color palette: deep navy (#1E3A5F), light gray (#F8F9FA), gold accent (#D4AF37), clean minimalist, high quality, 4K"

Image 1 prompt: [Deck Style Anchor], abstract technology network showing connected nodes...
Image 2 prompt: [Deck Style Anchor], team of professionals collaborating at a desk...
Image 3 prompt: [Deck Style Anchor], growth chart with upward trending line...
```

**例外**：背景图可以把风格关键词替换为 `background`、`backdrop`、`negative space for text overlay`，但仍保留相同的颜色指令。这样既能保证色彩统一，也不会损害背景图功能。

**规则**：在提示词文档头部（第 5 节）定义一次 Deck Style Anchor，后续每张图都引用它。

---

## 3. 图片类型分类与处理

### 类型判断流程

1. 全页 / 大面积背景 → **Background**（3.1）
2. 真实场景 / 人物 / 产品 → **Photography**（3.2）
3. 扁平 / 插画 / 卡通风格 → **Illustration**（3.3）
4. 流程 / 架构 / 关系表达 → **Diagram**（3.4）
5. 局部装饰 / 纹理 → **Decorative Pattern**（3.5）

### 3.1 背景图

**识别特征**：用于封面或章节页的全页背景，必须支持文字叠加。

| 关键点 | 说明 |
|-----------|-------------|
| 强调背景属性 | 加入 `background`、`backdrop` |
| 预留文字区域 | `negative space in center for text overlay` |
| 避免强主体 | 用抽象、渐变、几何元素 |
| 细节低对比 | `subtle`、`soft`、`muted` |

**模板**：`Abstract {theme element} background, {style} style, {primary color} to {secondary color} gradient, subtle {decorative elements}, clean negative space in center for text overlay, {aspect ratio} aspect ratio, high resolution, professional presentation background`

**负面提示词**：`text, letters, watermark, faces, busy patterns, high contrast details`

### 3.2 摄影图

**识别特征**：真实场景、人物、产品、建筑等，强调摄影质感。

| 关键点 | 说明 |
|-----------|-------------|
| 强调真实感 | `photography`, `photorealistic`, `real photo` |
| 光线效果 | `natural lighting`, `soft shadows`, `studio lighting` |
| 背景处理 | `white background` / `blurred background` / `contextual setting` |
| 人物多样性 | `diverse`, `professional attire` |

**模板**：`{subject description}, professional photography, {lighting type} lighting, {background type} background, color grading matching {color scheme}, high quality, sharp focus, 8K resolution`

**负面提示词**：`watermark, text overlay, artificial, CGI, illustration, cartoon, distorted faces`

### 3.3 插画图

**识别特征**：扁平设计、矢量风格、卡通、概念图。

| 关键点 | 说明 |
|-----------|-------------|
| 明确风格 | `flat design`, `isometric`, `vector style`, `hand-drawn` |
| 简化细节 | `simplified`, `clean lines`, `minimal details` |
| 统一配色 | 严格使用设计规范中的颜色 |
| 背景选择 | `white background` 或 `transparent background` |

**模板**：`{subject description}, {illustration style} illustration style, {detail level} with clean lines, color palette: {color list}, {background type} background, professional {purpose} illustration`

**负面提示词**：`realistic, photography, 3D render, complex textures, watermark`

### 3.4 图解图

**识别特征**：流程图、架构图、概念关系图、数据图解。

| 关键点 | 说明 |
|-----------|-------------|
| 结构清晰 | `clear structure`, `organized layout`, `logical flow` |
| 连接关系明确 | `arrows indicating flow`, `connecting lines` |
| 学术 / 专业感 | `suitable for academic publication`, `professional diagram` |
| 浅色背景 | `white background` 或 `light gray background` |

**模板**：`{diagram type} diagram showing {content description}, {component description} connected by {connection method}, {style} style with {color scheme}, white background, clear labels, professional technical diagram`

**负面提示词**：`cluttered, messy, overlapping elements, dark background, realistic, photography`

### 3.5 装饰纹样

**识别特征**：局部装饰、纹理、边框、分隔元素。

| 关键点 | 说明 |
|-----------|-------------|
| 可重复性 | `seamless`, `tileable`, `repeatable`（如有需要） |
| 低调辅助 | `subtle`, `understated`, `supporting element` |
| 适合透明背景 | `transparent background` 或 `isolated element` |
| 小尺寸可读性 | 考虑缩小时仍能清楚辨认 |

**模板**：`{pattern type} decorative pattern, {style} style, {color scheme}, {background type} background, subtle and elegant, suitable for {purpose}`

**负面提示词**：`busy, cluttered, high contrast, distracting, photorealistic`

---

## 4. 图片生成工作流

### 4.1 分析阶段

1. 阅读设计规范，理解项目整体风格
2. 提取配色、画布格式、目标受众
3. 逐条分析图片资源清单中的图片
4. 判断每张图片的类型（见第 3 节）

### 4.2 提示词生成阶段

对于每一张状态为 `Pending` 的图片：

1. **判断类型** → Background / Photography / Illustration / Diagram / Decorative
2. **理解用途** → 用于哪一页？承担什么作用？
3. **分析原始描述** → 读取用户提供的 `Generation description`
4. **套用类型要点** → 参考对应类型表格
5. **生成优化提示词** → 使用 2.1 的标准格式
6. **保存提示词文档** → **必须**写入 `project/images/image_prompts.md`

### 4.3 图片生成阶段

> 前提：4.2 已完成，且 `images/image_prompts.md` 已存在。

#### 路径选择（确定性）

| 触发条件 | 路径 | 机制 |
|---------|------|-----------|
| **默认情况**——用户未明确指定 | **路径 A**：`image_gen.py` CLI | 使用 `.env` 中的 `IMAGE_BACKEND` 配置 |
| **用户明确指定宿主原生生图工具**（如“用 Codex 自带生图”“用 Antigravity 的图片工具”） | **路径 B**：宿主原生工具 | 直接调用宿主自带生图能力，并将结果保存到 `project/images/` |

Agent **不能**根据自己判断的宿主能力擅自切换路径。只有用户对当前项目或本轮任务作出明确指令时，才可使用路径 B。否则一律默认使用路径 A。

#### 路径 A —— `image_gen.py` CLI（默认）

```bash
python scripts/image_gen.py "your prompt" \
  --aspect_ratio 16:9 --image_size 1K \
  --output project/images --filename cover_bg
```

**参数**：

| Parameter | Short | Description | Default |
|-----------|-------|-------------|---------|
| `prompt` | - | Positive prompt (positional arg) | - |
| `--negative_prompt` | `-n` | Negative prompt | None |
| `--aspect_ratio` | - | Image aspect ratio | `1:1` |
| `--image_size` | - | Size (`1K`/`2K`/`4K`) | `1K` |
| `--output` | `-o` | Output directory | Current directory |
| `--filename` | `-f` | Output filename (no extension) | Auto-named |
| `--backend` | `-b` | Override backend (see `--list-backends` for options) | None |
| `--model` | `-m` | Model name | Backend default |
| `--list-backends` | - | Print support tiers and exit | `false` |

**配置来源**：
- 当前进程环境变量
- 项目根目录 `.env` 作为兜底

优先级：
- 当前进程环境变量优先
- `.env` 只补缺失值

| 变量 | 必填 | 说明 |
|----------|----------|-------------|
| `IMAGE_BACKEND` | 必填 | 后端标识；当前可用值请运行 `image_gen.py --list-backends` |
| `{PROVIDER}_API_KEY` | 必填 | 各服务商的 API Key，如 `GEMINI_API_KEY`、`ZHIPU_API_KEY` |
| `{PROVIDER}_BASE_URL` | 可选 | 各服务商自定义接口地址 |
| `{PROVIDER}_MODEL` | 可选 | 各服务商模型覆盖配置 |

> 只能使用服务商专属变量名（如 `GEMINI_API_KEY`、`OPENAI_API_KEY`）。完整列表见 `.env.example`。

> `IMAGE_API_KEY`、`IMAGE_MODEL` 和 `IMAGE_BASE_URL` 故意不支持。

> 如果 `.env` 或当前环境同时配置了多个服务商，`IMAGE_BACKEND` 会显式决定启用哪一个。

**支持级别**（推荐用法）：Core / Extended / Experimental。当前分组请运行 `image_gen.py --list-backends`。

**生成节奏（强制）**：
- 一次只执行一条生成命令；确认文件落地后再进行下一张
- 建议图片之间间隔 2-5 秒，以避免并发失败

#### 路径 B —— 宿主原生生图工具（仅在用户明确要求时）

只有当用户明确要求使用宿主自带生图工具时，才启用此路径（例如 Codex、Antigravity 或其他提供原生生图能力的宿主）。

- Agent 直接调用宿主原生生图工具；提示词仍来自同一份 `image_prompts.md`
- 输出结果**必须**保存到 `project/images/<资源清单中的文件名>`，且尺寸与图片资源清单一致
- 下游 Executor 不关心来源路径，因此路径 A 与路径 B 之间无需修改规范

#### 失败处理（两条路径都适用）

如果某张图片生成失败：

1. **只重试一次。** 若重试仍失败，则停止该图片生成，不要无限循环。
2. **不要中断主流程。** 需要向用户报告失败项：列出受影响文件名和错误原因，并要求用户手动生成这些图片，放到 `project/images/<filename>`，文件名必须与资源清单完全一致。
3. **更新状态**：将对应资源清单条目标记为 `Needs-Manual`，而不是 `Generated`。
4. **继续进入 Executor 阶段。** Executor 只消费运行时 `project/images/` 中实际存在的文件；缺图由下游以占位或提示方式处理，不在此处阻塞。

如果用户选择在带水印的平台手动生成（如 Gemini 网页版），仓库中提供了 `scripts/gemini_watermark_remover.py` 作为辅助工具。

#### 护栏规则（两条路径都适用）

- 没有在预期路径生成出真实文件时，Agent **不能**声称图片已生成
- 没有真实尝试且失败时，Agent **不能**把图片标为 `Needs-Manual`
- 状态变化必须有证据：`Pending` -> `Generated`（预期路径已有文件）或 `Pending` -> `Needs-Manual`（尝试生成且重试一次后仍失败）

### 4.4 校验阶段

- 确认所有成功生成的图片都已保存到 `images/` 目录
- 检查文件名是否与资源清单一致
- 更新图片资源清单：存在文件则标 `Generated`；重试后仍失败则标 `Needs-Manual`
- 所有 `Needs-Manual` 条目，都必须在此阶段结束前向用户报告文件名和错误原因

---

## 5. 提示词文档模板

创建 `project/images/image_prompts.md` 时，使用以下结构：

```markdown
# 图片生成提示词

> 项目：{project_name}
> 生成时间：{date}
> 配色方案：主色 {#HEX} | 辅色 {#HEX} | 强调色 {#HEX}

---

## 图片清单概览

| # | 文件名 | 类型 | 尺寸 | 状态 |
|---|----------|------|-----------|--------|
| 1 | cover_bg.png | 背景图 | 1920x1080 | Pending |

---

## 详细提示词

### 图片 1：cover_bg.png

| 属性 | 值 |
|-----------|-------|
| 用途 | 封面背景 |
| 类型 | 背景图 |
| 尺寸 | 1920x1080 (16:9) |
| 原始描述 | 现代科技感抽象背景，深蓝渐变 |

**提示词**：
Abstract futuristic background with flowing digital waves...

**Alt Text**：
> 深蓝渐变的现代科技感抽象背景，包含数字波纹和粒子效果

---

## 使用说明

1. 将上方 `Prompt` 复制到 AI 生图工具中
2. 推荐平台：gpt-image-2 / Midjourney / DALL-E 3 / Gemini / Stable Diffusion
3. 将生成结果重命名为对应文件名
4. 放入 `images/` 目录
```

---

## 6. 负面提示词速查

### 按图片类型

| 类型 | 推荐负面提示词 |
|------|---------------------------|
| 背景图 | `text, letters, watermark, faces, busy patterns, high contrast details` |
| 摄影图 | `watermark, text overlay, artificial, CGI, illustration, cartoon, distorted faces` |
| 插画图 | `realistic, photography, 3D render, complex textures, watermark` |
| 图解图 | `cluttered, messy, overlapping elements, dark background, realistic` |
| 装饰纹样 | `busy, cluttered, high contrast, distracting, photorealistic` |

### 通用负面提示词

- **标准版**：`text, watermark, signature, blurry, distorted, low quality`
- **扩展版**（人物场景）：`text, watermark, signature, blurry, low quality, distorted, extra fingers, mutated hands, poorly drawn face, bad anatomy, extra limbs, disfigured, deformed`

---

## 7. 常见问题

### 缺少 "Generation Description" 时的默认推断

| 用途 | 默认推断 |
|---------|------------------|
| 封面背景 | 抽象渐变背景，并预留中央文字区 |
| 章节页背景 | 干净的几何图案，突出单色基调 |
| 团队介绍页 | 团队协作场景插画（扁平风格） |
| 数据展示页 | 干净的几何图案或纯色背景 |
| 产品展示页 | 产品摄影风格，白色或渐变背景 |

### 当图片效果不理想时

先判断问题类型，再针对性修改提示词：

| 问题 | 诊断 | 提示词修正 |
|---------|-----------|-------------------|
| 风格错误 | 想要扁平设计，结果却偏写实 | 修改风格指令：把 `photography` 换成 `flat design illustration` |
| 配色错误 | 颜色不符合设计规范 | 强化颜色指令：加入明确 HEX 值，并重复颜色名 |
| 构图错误 | 主体偏移，或布局不适合页面 | 调整构图指令：加入 `centered composition`、`rule of thirds` 或 `wide negative space on left` |
| 主体错误 | 生成内容与原描述不符 | 重写主体描述，加入更具体的细节 |
| 质量不足 | 图片模糊、有伪影、缺细节 | 增加 `highly detailed, sharp focus, professional quality, 8K resolution` |

**变体流程**：
1. 在 `image_prompts.md` 中保留原始提示词作为 “Variant A”
2. 根据上表定向修正，生成 “Variant B”
3. 如有需要，再生成不同风格路线的 “Variant C”
4. 清晰标注所有变体，便于用户比较效果

---

## 8. 角色协作

### 与 Strategist 的交接

| 方向 | 内容 |
|-----------|---------|
| 接收 | 设计规范与内容大纲（含图片资源清单） |
| 触发条件 | 用户在 “Image usage” 中选择了 “C) AI generation” |
| 关键信息 | 配色方案、设计风格、画布格式 |

### 与 Executor 的交接

| 方向 | 内容 |
|-----------|---------|
| 交付 | 所有图片都放在 `project/images/` 目录 |
| Executor 引用方式 | `<image href="../images/xxx.png" .../>` |
| 路径说明 | SVG 在 `svg_output/`，图片在 `images/`；相对路径使用 `../images/` |

---

## 9. 任务完成检查点

### 必做项

- [ ] 已创建提示词文档 `project/images/image_prompts.md`
- [ ] 每张图片都包含：类型判断 + 优化提示词 + 负面提示词 + Alt Text
- [ ] 使用统一输出格式（2.1 标准格式）
- [ ] 已输出阶段完成确认

### 图片就绪状态（至少满足一项）

- [ ] 所有图片都已保存到 `project/images/` 目录
- [ ] 或：已明确告知用户使用 `image_prompts.md` 自行生成

### 流程推进

- [ ] 已提示用户进入下一步（切换到 Executor 角色）

> **关键检查**：如果没有创建 `images/image_prompts.md`，或输出格式不符合 2.1 标准，则任务**未完成**。

### 完成确认输出格式

```markdown
## Image_Generator 阶段完成

- [x] 已创建提示词文档 `project/images/image_prompts.md`
- [x] 已为 X 张图片生成优化提示词
- [x] 所有图片已保存到 `images/` 目录
- [x] 已更新图片资源清单状态

**图片状态汇总**：

| 文件名 | 类型 | 尺寸 | 状态 |
|----------|------|-----------|--------|
| cover_bg.png | 背景图 | 1920x1080 | Generated |

**下一步**：切换到 Executor 角色，开始生成 SVG
```
