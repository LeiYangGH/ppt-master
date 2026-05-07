> 通用技术约束见 shared-standards.md。

# 模板设计器 — 模板设计角色

## 核心使命

基于最终模板 brief，生成可复用的页面模板，用于 **全局模板库**。

> 这是一个独立角色：只在 `/create-template` 工作流中触发。**不是**主 PPT 生成流程里的项目级模板选择或定制步骤。

## 用法

- **触发方式**：`/create-template` 工作流
- **输出位置**：`templates/layouts/<template_name>/`
- **输入内容**：最终模板 brief（模板 ID、显示名、类别、适用场景、语气、主题模式、画布格式，以及可选参考资源）

若工作流提供 PPTX 参考源，则实际输入包来自统一的 `pptx_template_import.py` 预处理工作区，包括：

- 最终模板 brief
- `manifest.json`
- `master_layout_refs.json`
- `master_layout_analysis.md`
- `analysis.md`
- `normalized_assets.json`
- 导出的 `assets/`
- `svg/` 中清洗后的参考页面 SVG
- `reference_svg_selection.json`
- 可选截图（用于视觉交叉核对）

基于 PPTX 参考创建模板时，读取优先级如下：

1. `manifest.json`：事实元数据
2. `master_layout_refs.json`：母版/版式结构与继承关系
3. `master_layout_analysis.md`：快速结构分析
4. `normalized_assets.json`：规范化资源决策
5. 导出的 `assets/`：可复用视觉资源
6. `analysis.md`：页面类型参考
7. `reference_svg_selection.json`：决定优先查看哪些导出 SVG
8. 清洗后的参考 SVG：查看构图、间距、层级和固定装饰
9. 截图 / 原始 PPTX：仅用于风格核验

---

## 核心模板库存

| # | 文件名 | 用途 | 说明 |
|---|----------|---------|-------------|
| 01 | `01_cover.svg` | 封面页 | 固定结构：标题、副标题、日期、组织 |
| 02 | `02_chapter.svg` | 章节页 | 固定结构：章节号、章节标题 |
| 03 | `03_content.svg` | 内容页 | 灵活结构：仅定义页眉/页脚；内容区域由 AI 自由布局 |
| 04 | `04_ending.svg` | 结尾页 | 固定结构：感谢信息、联系方式 |
| -- | `02_toc.svg` | 目录页 | 可选：目录标题、章节列表（章节号 + 标题） |

**设计理念**：模板负责视觉统一和结构页；内容页尽量保持最高灵活性。

**命名说明**：目录页保留 `02_toc.svg` 命名，以兼容模板库排序和历史约定。

### 可选扩展页

- 过渡页 / 子章节页（如 `05_section_break.svg`）
- 附录页（如 `06_appendix.svg`）
- 免责声明 / 保密页（如 `07_disclaimer.svg`）

---

创建全局模板时，必须生成 `design_spec.md`，包含：

```markdown
# [模板名称] - 设计规范

## 一、模板概述（名称、适用场景、设计基调）
## 二、画布规格（16:9、1280x720、viewBox）
## 三、配色方案（主色、辅色、强调色 HEX 值）
## 四、字体系统（字体栈、字号层级）
## 五、页面结构（通用布局、装饰设计）
## 六、页面类型（4 种核心页面类型）
## 七、布局模式（推荐）
## 八、间距规范
## 九、SVG 技术约束
## 十、占位符规范
```

### 2. 遵循设计规范

模板必须严格遵循最终模板 brief 和生成的 `design_spec.md`：
- **画布尺寸**：viewBox 与设计规范一致
- **配色方案**：使用规范中的主色、辅色和强调色
- **字体方案**：使用规范中声明的各角色字体族
- **布局原则**：边距和间距符合规范

若存在 PPTX 导入输出：
- 优先使用导入的主题色和字体，而非视觉猜测值
- 从 `normalized_assets.json` 中复用具有全局意义的规范背景和 Logo
- 将 `analysis.md` 中的页面类型候选视为提示，而非确定性结论

**前置条件**：

- 若提供了 `reference_svg_selection.json`，在读取完所有选定的参考 SVG 文件之前，不得生成任何模板 SVG 或 `design_spec.md`
- 模板生成开始前，须明确报告已读取的幻灯片索引

### 2.1 PPTX 导入简化规则

导入的 PPTX 是**参考来源**，而非直接转换目标。

应做：
- 保留品牌资产、循环背景和稳定的结构元素
- 将布局重建为符合 PPT Master 约束的简洁 SVG 结构
- 将重复的装饰片段简化为更少且可维护的 SVG 元素
- 当原始装饰层过于复杂无法干净重建时，使用背景图片资源
- 当 AI 规范化判定原始导出资源（如 `image1.png`）与匹配的 `inline_*` 资源表示同一可见图像时，优先使用原始导出资源
- 将 `inline_*` 资源主要作为导出参考层，而非最终模板资源名
- 仅在事实元数据锚定后，才使用清洗后的幻灯片 SVG 参考来检查构图、间距、文本层级和固定装饰结构
- 若清洗后的 SVG 参考页面数 ≤ 10，则全部读取；若超过 10，则只读取 10 个代表性页面

不应做：
- 尝试逐个翻译每个 PowerPoint 形状、组合、阴影或装饰片段（1:1 还原）
- 照搬 PPT 特有的复杂性，导致 SVG 脆弱或难以编辑
- 引入对模板复用没有实质提升的密集低价值矢量细节
- 将仅用作遮罩/Alpha 辅助的 `inline_*` 资源纳入最终模板包，除非它们是唯一可行的可复用表示

### 2.2 原始资源与内联资源规范化

当 `normalized_assets.json` 存在时，遵循以下规则：

1. 若原始导出资源与 `inline_*` 资源明确对应同一可见图像，使用**原始导出资源**作为规范模板源。
2. 若 `inline_*` 资源没有可靠的原始导出对应项，可作为派生模板资源保留。
3. 若 `inline_*` 资源仅作为遮罩、Alpha 辅助或其他非语义支持层出现在 SVG 导出中，默认不纳入最终模板资源集。
4. 最终模板资源名应为语义化命名，如 `cover_bg.png` 或 `brand_emblem.png`，而非 `image3.png` 或 `inline_abcd1234.png`。

### 3. 占位符标记

为可替换内容使用清晰的占位符标记：

```xml
<!-- 文本占位符 -->
<text x="80" y="320" fill="#FFFFFF" font-size="48" font-weight="bold">
  {{TITLE}}
</text>

<!-- 内容区域占位符（仅内容页） -->
<rect x="40" y="90" width="1200" height="550" fill="#FFFFFF" rx="8"/>
<text x="640" y="365" text-anchor="middle" fill="#CBD5E1" font-size="16">
  {{CONTENT_AREA}}
</text>
```

### 4. 占位符参考

| 占位符 | 用途 | 适用模板 |
|------------|---------|-------------------|
| `{{TITLE}}` | 主标题 | 封面页 |
| `{{SUBTITLE}}` | 副标题 | 封面页 |
| `{{DATE}}` | 日期 | 封面页 |
| `{{AUTHOR}}` | 作者/组织 | 封面页 |
| `{{CHAPTER_NUM}}` | 章节号 | 章节页 |
| `{{CHAPTER_TITLE}}` | 章节标题 | 章节页 |
| `{{CHAPTER_DESC}}` | 章节描述 | 章节页 |
| `{{PAGE_TITLE}}` | 页面标题 | 内容页 |
| `{{KEY_MESSAGE}}` | 核心要点 | 内容页（咨询风格） |
| `{{CONTENT_AREA}}` | 内容区域 | 内容页 |
| `{{SECTION_NAME}}` | 章节名称 | 内容页页脚 |
| `{{SOURCE}}` | 数据来源 | 内容页页脚 |
| `{{PAGE_NUM}}` | 页码 | 内容页、结尾页 |
| `{{THANK_YOU}}` | 致谢语 | 结尾页 |
| `{{ENDING_SUBTITLE}}` | 结尾副标题 | 结尾页 |
| `{{CLOSING_MESSAGE}}` | 结语 | 结尾页 |
| `{{CONTACT_INFO}}` | 联系方式 | 结尾页 |
| `{{COPYRIGHT}}` | 版权信息 | 结尾页 |

对于**新建库模板**中的目录页，使用索引占位符：

- `{{TOC_ITEM_1_TITLE}}`, `{{TOC_ITEM_1_DESC}}`
- `{{TOC_ITEM_2_TITLE}}`, `{{TOC_ITEM_2_DESC}}`
- ...

新建模板**不要**创建新的目录占位符族（如 `{{CHAPTER_01_TITLE}}`）。现有模板可能包含遗留占位符变体，但新建库资源应统一使用索引式目录占位符约定。

从导入的 PPTX 参考重建时，占位符插入优先于视觉模仿。若原始布局没有为规范占位符留出足够空间，应调整布局而非发明临时占位符族。

---

## 输出要求

### 文件保存位置

```
templates/layouts/<template_name>/
├── design_spec.md     # 设计规范（必需）
├── 01_cover.svg
├── 02_chapter.svg
├── 02_toc.svg          # Optional
├── 03_content.svg
├── 04_ending.svg
└── *.png / *.jpg       # 图片资源（如有）
```

### 模板预览

每个模板生成后，提供简短的汇总表列出各模板状态。

若模板基于 PPTX 导入输出，简要说明：
- 哪些提取资源被直接复用
- 哪些复杂的原始装饰被有意简化
- 是否有页面类型映射超出了导入启发式规则需要人工判断

---

## 使用预构建模板库（可选）

若已有合适的模板资源，直接使用而非重新生成：

1. **复制模板**：将模板文件复制到项目的 `templates/` 目录
2. **调整配色**：按项目设计规范修改颜色
3. **定制化**：做项目特定的调整

本节描述的是下游复用。`Template_Designer` 角色本身负责首先创建或规范化可复用的库资产。

**库目录示例**（查询 `templates/layouts/layouts_index.json`）：

```
templates/layouts/
├── exhibit/           # 展示风格（结论先行、数据驱动）
├── 科技蓝商务/         # 科技蓝商务风格
└── smart_red/         # 智能红橙风格
```

---

## 阶段完成检查点

```markdown
## Template_Designer 阶段完成

- [x] 已读取 `references/template-designer.md`
- [x] 已生成 4 个核心页面模板
- [ ] 目录页模板（可选）
- [ ] 可选扩展页（如需要）
- [x] 所有模板已保存至 `templates/layouts/<template_name>/`
- [x] 模板遵循设计规范（配色、字体、布局）
- [x] 占位符标记清晰且标准化
- [ ] **下一步**：验证资源并在 `layouts_index.json` 中注册模板
```
