---
description: 基于现有项目文件或参考模板生成新的PPT布局模板
---

# 创建新模板工作流

> **调用角色**: [Template_Designer](../references/template-designer.md)

为**全局模板库**生成一套完整的可复用PPT布局模板。

> 本工作流用于**库资产创建**，而非项目级一次性定制。输出必须可被未来PPT项目复用，且可通过 `templates/layouts/layouts_index.json` 发现。

## 流程概览

```
收集需求 → 导入PPTX参考 → 规范化资产 → 创建目录 → 调用Template_Designer → 验证资产 → 注册索引 → 输出
```

---

## 步骤 1：收集模板信息

与用户确认以下内容：

| 项目 | 必填 | 说明 |
|------|------|------|
| 新模板ID | 是 | 模板目录/索引键。推荐ASCII slug如 `my_company`；如使用中文品牌名，须文件系统安全且与 `layouts_index.json` 精确匹配 |
| 模板显示名称 | 是 | 供文档使用的人类可读名称 |
| 分类 | 是 | `brand` / `general` / `scenario` / `government` / `special` 之一 |
| 适用场景 | 是 | 典型用例，如年报/答辩/政府汇报 |
| 风格摘要 | 是 | 简短风格描述，如 `现代、克制、数据驱动` |
| 主题模式 | 是 | 主题描述，如 `浅色主题（白底+蓝色强调）` |
| 画布格式 | 是 | 默认 `ppt169`；如需其他格式，生成前须明确指定 |
| 参考来源 | 可选 | 已有项目、截图文件夹或 `.pptx` 模板文件路径 |
| 主题色 | 可选 | 主色HEX值（可从参考中自动提取） |
| 设计风格 | 可选 | 补充风格说明、装饰语言、品牌线索 |
| 资产清单 | 可选 | 需纳入模板包的Logo/背景纹理/参考图片 |
| 关键词 | 是 | 3–5个短标签，供 `layouts_index.json` 查找（如 `McKinsey`, `Consulting`, `Structured`） |

**步骤1必要产出**：

- 模板明确定位为**全局库模板**
- 画布格式在SVG生成前已确定
- 模板元数据完整，可注册到 `layouts_index.json`

**如提供了参考来源**，先分析其结构：

```powershell
Get-ChildItem -Force "<reference_source_path>"
```

如参考来源为 `.pptx` 模板文件，使用统一准备助手：

```powershell
python /scripts/pptx_template_import.py "<reference_template.pptx>"
```

此助手在一个工作区内完成全部PPTX参考准备：

- 提取可复用资产和样式元数据
- 生成 `manifest.json`
- 生成 `analysis.md`
- 生成 `master_layout_refs.json`
- 生成 `master_layout_analysis.md`
- 将每张幻灯片导出到 `svg/`
- 将大型内联位图外置到 `assets/`
- 生成 `reference_svg_selection.json`

这仍是重建辅助工具，而非最终的直接模板转换。

使用生成的 `manifest.json`、`analysis.md`、`master_layout_refs.json`、`master_layout_analysis.md`、导出的 `assets/` 和 `svg/` 幻灯片参考作为模板重建的内部参考资料。

然后在模板生成前执行**AI资产规范化步骤**：

- 将导出的原始资产（如 `image1.png`）与清理后幻灯片SVG使用的 `inline_*` 资产进行对比
- 若 `inline_*` 可见图片对应一个原始导出资产，以**原始资产**为规范来源
- 若 `inline_*` 资产无匹配的原始导出资产，保留为衍生候选资产
- 若 `inline_*` 资产仅用作遮罩/Alpha辅助/辅助层，默认**不**提升至最终模板资产集
- 将规范化结果写入 `<import_workspace>/normalized_assets.json`

`normalized_assets.json` 推荐字段：

- 规范资产路径
- 匹配的 `inline_*` 引用
- 角色推测，如 `cover_background`、`content_background`、`brand_overlay`、`mask_only`
- 该资产是否应纳入最终模板包

当参考来源为 `.pptx` 时，模板创建中使用以下内部优先级：

1. `manifest.json`
2. `master_layout_refs.json`
3. `master_layout_analysis.md`
4. `analysis.md`
5. `normalized_assets.json`
6. 导出的 `assets/`
7. `svg/` 中的清理后幻灯片SVG参考
8. 用户提供的截图或原始PPTX仅用于视觉交叉校验

解读规则：

- `manifest.json` 是幻灯片尺寸、主题色、字体、背景继承和可复用资产清单的权威来源
- `master_layout_refs.json` 是唯一布局/母版结构、继承背景和幻灯片复用关系的权威来源
- `master_layout_analysis.md` 是快速理解可复用母版/布局模式的精简人类可读摘要
- `analysis.md` 是指导页面类型选择的精简人类可读摘要
- `normalized_assets.json` 是判断哪些导入资产为规范资产、哪些 `inline_*` 仅为衍生辅助的权威来源
- 导出的 `assets/` 仍为原始导入池，规范化存在后不应盲目使用
- 清理后的 `svg/` 幻灯片是布局节奏、页面构成和固定装饰结构的必读参考
- 若清理后SVG参考页 `<= 10`，全部读取；若 `> 10`，只读10个代表性页面
- 截图对判断构图和风格仍有用，但不应覆盖提取的事实元数据，除非导入结果明显不完整

**硬关卡**：

- 创建任何模板文件前，Agent必须完成读取 `reference_svg_selection.json` 中列出的所有SVG文件
- Agent在开始模板生成前必须显式报告已读取的幻灯片索引

**不要**将导入的PPTX或导出的幻灯片SVG直接作为最终模板资产。目标是重建一个干净、可维护的PPT Master模板包，而非1:1形状翻译。

---

## 步骤 2：规范化导入资产

当参考来源为 `.pptx` 时，在生成模板前创建规范化产物。

**步骤2必要产出**：

- 原始导出资产与 `inline_*` 资产已完成对比
- 存在可靠匹配时，规范资产优先使用原始导出文件
- 仅遮罩/辅助用途的 `inline_*` 资产默认排除在最终模板资产候选之外
- `normalized_assets.json` 可供下游模板生成使用

如无 `.pptx` 来源参与，可跳过此步。

---

## 步骤 3：创建模板目录

```powershell
New-Item -ItemType Directory -Force -Path "/templates/layouts/<template_id>"
```

> **输出位置**：全局模板放在 `/templates/layouts/`；项目模板放在 `projects/<project>/templates/`
>
> 生成的目录名必须与 `layouts_index.json` 中的最终模板ID一致。

---

## 步骤 4：调用Template_Designer角色

**切换至Template_Designer角色**并按角色定义生成。角色输入为步骤1确定的模板需求，而非项目设计规格。

如参考来源为 `.pptx`，将以下内部包传递给角色：

- 步骤1确定的模板需求
- `manifest.json`
- `master_layout_refs.json`
- `master_layout_analysis.md`
- `analysis.md`
- `normalized_assets.json`
- 导出的 `assets/`
- `svg/` 中的清理后幻灯片SVG参考
- `reference_svg_selection.json`
- 可选截图（如有）

角色应使用导入输出来锚定客观事实（如主题色、字体、可复用背景、通用品牌资产），然后以简化、可维护的形式重建最终SVG模板。

1. **design_spec.md** — 设计规格文档
2. **4个核心模板** — 封面页、章节页、内容页、结束页
3. **目录页（可选）** — `02_toc.svg`
4. **模板资产（可选）** — 模板包所需的Logo/PNG/JPG/参考SVG

> **角色详情**：参见 [template-designer.md](../references/template-designer.md)

**新模板占位符约定（新建库模板必须遵守）**：

- 封面：`{{TITLE}}`、`{{SUBTITLE}}`、`{{DATE}}`、`{{AUTHOR}}`
- 章节：`{{CHAPTER_NUM}}`、`{{CHAPTER_TITLE}}`
- 内容：`{{PAGE_TITLE}}`、`{{CONTENT_AREA}}`、`{{PAGE_NUM}}`
- 结束：`{{THANK_YOU}}`、`{{CONTACT_INFO}}`
- 目录：使用索引占位符如 `{{TOC_ITEM_1_TITLE}}` 及可选的 `{{TOC_ITEM_1_DESC}}`

**避免**为新模板引入一次性占位符族（如 `{{CHAPTER_01_TITLE}}`）。如确实需要扩展占位符，须在 `design_spec.md` 中明确定义并保持命名模式一致。

---

## 步骤 5：验证模板资产

```powershell
Get-ChildItem -Force "/templates/layouts/<template_id>"
```

对模板目录运行SVG验证：

```powershell
python /scripts/svg_quality_checker.py "/templates/layouts/<template_id>" --format <canvas_format>
```

**检查清单**：

- [ ] `design_spec.md` 包含完整设计规格
- [ ] 4个核心模板齐全
- [ ] 目录页（如有）的占位符使用规范索引格式
- [ ] SVG viewBox与所选画布格式匹配（`ppt169` 为 `0 0 1280 720`）
- [ ] 占位符名称与新模板约定及 `design_spec.md` 一致
- [ ] SVG引用的资产文件在模板包中实际存在

此步为**硬关卡**。验证通过前不得将模板注册到库索引。

---

## 步骤 6：注册模板到库索引

在 `/templates/layouts/layouts_index.json` 中添加顶层条目。该文件为 `template_id → { label, summary, keywords }` 的扁平映射：

```json
"<template_id>": {
  "label": "<人类可读名称>",
  "summary": "<一句话描述此模板用途>",
  "keywords": ["<标签1>", "<标签2>", "<标签3>"]
}
```

`layouts_index.json` 是用户显式选择模板流程时使用的轻量查找表。主工作流默认为自由设计，除非模板触发器激活否则不读取此文件（见 `SKILL.md` 步骤3）。未在此注册的模板目录不会被该流程发现。

同时同步 `templates/layouts/README.md` 中的摘要表（含分类、主色、风格详情的人类可读索引）。

---

## 步骤 7：输出确认

```markdown
## 模板创建完成

**模板名称**: <template_id> (<display_name>)
**模板路径**: `/templates/layouts/<template_id>/`
**分类**: <category>
**画布格式**: <canvas_format>
**索引注册**: 已完成

### 包含文件

| 文件 | 状态 |
|------|------|
| `design_spec.md` | 已完成 |
| `01_cover.svg` | 已完成 |
| `02_chapter.svg` | 已完成 |
| `03_content.svg` | 已完成 |
| `04_ending.svg` | 已完成 |
| `02_toc.svg` | 可选 |
```

---

## 配色方案速查

| 风格 | 主色 | 适用场景 |
|------|------|----------|
| 科技蓝 | `#004098` | 认证、评审 |
| 麦肯锡 | `#005587` | 战略咨询 |
| 政务蓝 | `#003366` | 政务项目 |
| 商务灰 | `#2C3E50` | 通用商务 |

---

## 备注

1. **SVG技术约束**：参见 [template-designer.md](../references/template-designer.md) 中的技术约束部分
2. **色彩一致性**：所有SVG文件必须使用相同配色方案
3. **占位符约定**：使用 `{{}}` 格式及上述新模板占位符约定
4. **可发现性要求**：新模板必须添加到 `layouts_index.json`，否则用户选择模板流程时无法发现

> **详细规格**：参见 [template-designer.md](../references/template-designer.md)
