---
name: ppt-master
description: >
  AI驱动的多格式SVG内容生成系统。通过多角色协作，将源文档Markdown转换为高质量SVG页面，用户手动导出为PPTX。当用户要求“生成PPT”、“做PPT”、“制作演示文稿”时调用。
---

# PPT Master 技能

> AI驱动的多格式SVG内容生成系统。通过多角色协作将源文档转换为高质量SVG页面，用户手动导出为PPTX。

**核心流程**：`源文档 → 创建项目 → 模板选项 → Strategist → Executor → 后处理 → 用户手动导出`

> [!CAUTION]
> ## 🚨 全局执行纪律（强制）
>
> **本工作流是严格的串行流程。以下规则具有最高优先级——违反任何一条都视为执行失败：**
>
> 1. **串行执行** —— 步骤必须按顺序执行；上一步的输出是下一步的输入。满足前提条件的非阻塞相邻步骤可连续进行，无需等待用户确认。
> 2. **阻塞 = 强制停止** —— 标有 ⛔ BLOCKING 的步骤需要完全停止；AI **必须**等待用户的明确回复后才能继续，**绝对不能**替用户做决定。
> 3. **禁止跨阶段打包** —— 跨阶段打包是禁止的。（注：第 3 步中的八项确认是 ⛔ BLOCKING——AI 必须提供建议并等待用户的明确确认。一旦用户确认，后续所有非阻塞步骤——设计规范、SVG、演讲备注和后处理——都可自动连续进行）。
> 4. **先检查门控** —— 每个步骤顶部都列有前提条件（🚧 GATE）；在开始该步骤前**必须**核实。
> 5. **极简改动** —— **禁止**为后续步骤"预先准备"内容（例如，在 Strategist 阶段编写 SVG 代码）。**禁止**添加用户未要求的功能、装饰、颜色或布局变体。不为一次性场景创建抽象。如果 50 行 SVG 能解决的问题不要用 200 行。**检验标准**：每一处改动都能直接溯源到用户的请求或 spec_lock 的要求——无法溯源的改动就是过度工程。
> 6. **禁止子智能体生成 SVG** —— 第 4 步 Executor 生成 SVG 高度依赖上下文，**必须**由当前主智能体端到端完成。**禁止**委托给子智能体。
> 7. **仅限逐页生成** —— 在第 4 步 Executor 中，全局设计上下文确认后，SVG 页面**必须**在一个连续的上下文中按顺序一页一页地生成。**禁止**批量生成（例如每次 5 页）。
> 8. **每页重读 SPEC_LOCK** —— 在生成每页 SVG 之前，Executor **必须** `read_file workspace/spec_lock.md`。所有颜色 / 字体 / 图标 / 图片**必须**来自此文件。Executor 还**必须**查找当前页的 `page_rhythm` 标签，并应用匹配的布局纪律（`structural` / `analytical` / `focal`——见 executor.md §3.1）。
> 9. **先思考后动手** —— 在关键决策前，**必须**先读取 `workspace/state.md`，确保理解当前状态和已积累的经验教训。如果对用户需求存在多种解读，**必须**呈现权衡让用户选择，而非默默选一种。如果存在更简单的方案，**必须**提出来。困惑时停下来问，不要假设。


> [!IMPORTANT]
> ## 💻 运行环境与命令规则（强制）
>
> - **优先使用虚拟环境**：本项目应优先使用工作区下的虚拟环境（如 `.venv` 或 `venv`）。**绝不能**使用系统默认的 Python。所有示例指令中的 `python xxx.py` 仅为简单惯例，实际执行时必须使用当前项目的虚拟环境中的 python。
> - **操作系统适配**：必须先确定当前操作系统（Windows 或 Linux），再决定使用对应的命令。Windows 使用 PowerShell（如 `Get-ChildItem`），Linux 使用 Shell（如 `ls`）。禁止混用不同系统的命令。
> - **直接读写文件**：当前运行于 AI IDE 环境（如 opencode），具备原生文件读写能力。**必须**使用 IDE 提供的文件读写工具直接操作文件，**禁止**通过新建 Python 脚本等迂回方式间接读写文件。调用文件读写工具时须注意传参规范，确保路径正确、编码无误。

> - **回复语言**：简体中文。

> [!IMPORTANT]
> ## 🔌 与通用编码技能的兼容性
>
> - `ppt-master` 是一个特定于该仓库的工作流，而不是通用的应用程序脚手架。
> - **不要**默认创建 `.worktrees/`、`tests/`、分支工作流或通用工程结构。
> - 当与通用编码技能发生冲突时，优先遵循本技能规则。

> [!IMPORTANT]
> ## 📋 会话状态管理
>
> 单个状态文件 `workspace/state.md` 作为 LLM 的**磁盘工作内存**——对抗上下文压缩、会话中断、重复犯错。
>
> **读写时机（强制）**：
>
> | 时机 | 必须读 | 必须写 |
> |------|--------|--------|
> | 会话启动 / 恢复 | `workspace/state.md` | — |
> | 阶段切换 | — | 更新当前阶段 + 阶段清单 |
> | 每页 SVG 生成后 | — | 更新当前页进度（如 P03/12） |
> | 遇到并解决错误 | — | 追加错误日志 + 经验教训 |
> | 用户做出关键决策 | — | 追加决策记录 |
> | 关键动作完成（脚本执行、⛔ 通过等） | — | 追加进度记录 |
> | 发现图片/源文档关键信息 | — | 追加发现记录 |

## 主要流程脚本

| 脚本 | 用途 |
|--------|---------|
| `scripts/project_manager.py` | 工作区初始化 / 校验 / 管理（含状态文件初始化） |
| `scripts/analyze_images.py` | 图片分析（单张精查） |
| `scripts/image_montage.py` | **图片批量缩略图墙**（将 `images/` 下所有图片拼接为 `montage_NN_of_MM.jpg`，每张 4×5=20 格且每格底部带文件名标签）——供 LLM **一次视觉读图批量判定保留 / 删除 / 重命名**，避免对数十张图通过 `analyze_images.py` 逐张读取的高成本。 |
| `scripts/web_search.py` | 网页 / 图片搜索（Tavily + 百度自动轮询，**搜索后自动并发下载图片到当前项目 `images/` 目录**，5 秒/张超时，无缓存（每次调用实时请求 API，重试可真正拿到新结果），带域名黑名单；⚠ **搜索关键字必须用中文**，下载后需逐张审阅并重命名，详见 `optional-workflows/topic-research.md` 顶部约束） |
| `scripts/svg_quality_checker.py` | SVG 质量检查 |
| `scripts/render_svg.py` | SVG → PNG 预览渲染（用于逐页视觉复检） |
| `scripts/svg_repair.py` | SVG XML 自动修复（基于 sloppy-xml，修复 LLM 输出的不规范 XML） |
| `scripts/notes_all_md_split.py` | 演讲备注拆分 |
| `scripts/finalize_svg.py` | SVG 后处理（统一入口） |
| `scripts/svg_to_pptx.py` | 导出为 PPTX |
| `scripts/update_spec.py` | 将 `spec_lock.md` 中的颜色 / 字体变更同步到所有 SVG |


## 模板索引

| 索引 | 路径 | 用途 |
|-------|------|---------|
| 布局模板 | `templates/layouts/layouts_index.json` | 查询可用的页面布局模板 |
| 可视化模板 | `templates/charts/charts_index.json` | 查询可用的可视化 SVG 模板（图表、信息图、流程图等） |
| 图标库 | `templates/icons/` | 见 `templates/icons/README.md`；按需搜索：`Get-ChildItem templates\icons\<library>\*<keyword>*` |

## 独立工作流

| 工作流 | 路径 | 用途 |
|----------|------|---------|
| `verify-charts` | `optional-workflows/verify-charts.md` | 图表坐标校准 —— 若 deck 包含数据图表，在生成 SVG 后运行 |

---

## 工作流

### 第 1 步：用户准备工作

用户需手动完成以下操作：

1. **初始化工作区**：
   ```powershell
   python scripts/project_manager.py init
   ```

2. **放置素材**：将源文件（Markdown、图片等）放入 `workspace/sources/`

3. **提供源内容**：在对话中提供 Markdown 内容，或告知素材已准备好

**会话恢复检测**：如果 `workspace/state.md` 存在且当前阶段非 S0，说明有未完成的项目——读取 `state.md`，从记录的阶段继续，不要重新开始。

**✅ 检查点 —— 确认工作区已初始化且素材已就绪。**

> **成功标准**：`workspace/` 目录存在，`workspace/sources/` 包含素材文件，或用户已在对话中提供了文本内容。

---

### 第 2 步：模板选项

🚧 **GATE**：第 1 步完成；工作区已初始化且素材已就绪。

**默认 —— 自由设计。** 直接进入第 3 步。不要查询 `layouts_index.json`。不要向用户询问选择模板还是自由设计的问题。

**模板流程是可选的。** 仅当用户之前的消息中出现明确触发条件时才进入：

1. 指定了具体模板（如“用 mckinsey 模板” / “use the academic_defense template”）
2. 指定了对应模板的风格/品牌（如“McKinsey 那种” / “Google style” / “学术答辩样式”）
3. 询问有哪些模板可用（如“有哪些模板可以用”）

触发时：读取 `templates/layouts/layouts_index.json`，匹配模板（对于触发条件 3 则列出选项），并复制：

```powershell
Copy-Item "templates\layouts\<template_name>\*.svg" -Destination "workspace\templates\"
Copy-Item "templates\layouts\<template_name>\design_spec.md" -Destination "workspace\templates\"
Copy-Item "templates\layouts\<template_name>\*.png" -Destination "workspace\images\" -ErrorAction SilentlyContinue
Copy-Item "templates\layouts\<template_name>\*.jpg" -Destination "workspace\images\" -ErrorAction SilentlyContinue
```

**软提示（非阻塞）。** 当内容非常契合某个现有模板（例如学术答辩、政府报告、McKinsey 风格），且**未触发**上述模板条件时，输出一句简短提示并继续（不等待用户回复）：

> 提示：内置库中有一个非常契合此场景的模板 `<name>`。如果你想使用它请告诉我，否则我将继续进行自由设计。

这只是提示，不是提问 —— **不要阻塞**。如果匹配度低或不明确则完全跳过。

**✅ 检查点 —— 默认路径无需用户交互即可进入第 3 步。如果触发了模板，需在进入下一步前复制模板文件。**

> **成功标准**：如触发了模板，`workspace/templates/` 下存在对应的 `.svg` 和 `design_spec.md` 文件；如未触发，无额外文件。

---

### 第 3 步：Strategist 阶段（强制 —— 不可跳过）

🚧 **GATE**：第 2 步完成；采用默认的自由设计路径，或者（如果触发）已将模板文件复制到项目中。

首先，读取角色定义：
```
读取 references/strategist.md
```

> ⚠️ **强制门控**：在编写 `design_spec.md` 之前，Strategist **必须** `read_file templates/design_spec_reference.md` 并遵循其完整的 I-XI 章节结构。详见 `strategist.md` 第 1 节。

**八项确认**（完整模板见：`templates/design_spec_reference.md`）：

⛔ **BLOCKING**：将八项确认作为一组打包的建议呈现给用户，并**等待用户的明确确认或修改**后，才能输出设计规范和内容大纲。这是整个流程中唯一的核心确认点 —— 一旦确认，后续所有步骤自动进行。

1. 画布格式 (Canvas format)
2. 页数范围 (Page count range)
3. 目标受众 (Target audience)
4. 风格目标 (Style objective)
5. 配色方案 (Color scheme)
6. 图标使用方式 (Icon usage approach)
7. 字体方案 (Typography plan)
8. 图片使用方式 (Image usage approach)

如果用户提供了图片，**在输出设计规范之前**进行分析：
```powershell
python scripts/analyze_images.py workspace/images
```

> ⚠️ **图片处理**：应该直接读取并确保每张最终采纳的图片都是亲自校验过内容一致的，而不仅是根据文件名或轻信搜索引擎等。可参考 `analyze_images.py` 的分析结果作为辅助。如果图片数量较多，可使用 `scripts/image_montage.py` 制作缩略图墙以提高批量审阅效率。

⛔ **BLOCKING**：所有准备采纳到 SVG 的图片，必须重命名为 `<ppt号>-<简洁图片内容>` 的格式（例如 `P03-团队合影.jpg`）。完成重命名后，**必须等待人工核查确认图片内容与命名一致**，人工核查通过后才能继续输出设计规范。

**输出**：
- `workspace/design_spec.md` —— 供人类阅读的设计叙述
- `workspace/spec_lock.md` —— 机器可读的执行契约（骨架见：`templates/spec_lock_reference.md`）；Executor 在生成每页前会重读此文件

**✅ 检查点 —— 阶段交付物完成，自动进入下一步**：
```markdown
## ✅ Strategist 阶段完成
- [x] 八项确认完成（用户已确认）
- [x] 图片已按 `<ppt号>-<简洁图片内容>` 格式重命名并通过人工核查
- [x] 已生成设计规范和内容大纲 (Design Specification & Content Outline)
- [x] 已生成执行锁文件 (spec_lock.md)
- [ ] **下一步**：自动进入 Executor 阶段
```

> **成功标准**：`design_spec.md` 包含完整的 I-XI 章节；`spec_lock.md` 包含 `colors` / `typography` / `icons` / `page_rhythm` 四个必需段；用户已对八项确认明确回复；所有采纳到 SVG 的图片已按 `<ppt号>-<简洁图片内容>` 格式重命名并通过人工核查。

**状态更新**：更新 `workspace/state.md`——阶段清单标记 S0-S3 完成，当前阶段改为 S4。如果用户在 ⛔ 处做了修改决策，记入决策记录。

---

### 第 4 步：Executor 阶段

🚧 **GATE**：第 3 步完成；所有前置交付物已准备就绪。

读取角色定义：
```
读取 references/executor.md               # 必需：角色定义、执行规则、风格指南
读取 references/shared-standards.md       # 必需：SVG/PPT 技术约束
```

> 只需读取 executor.md + shared-standards.md。

**设计参数确认（强制）**：在生成第一个 SVG 之前，输出规范中的关键设计参数（画布尺寸、配色方案、字体方案、正文字号）。详见 executor.md §3。

**每页重读 spec_lock（强制）**：在生成**每页** SVG 之前，`read_file workspace/spec_lock.md` 并且仅使用其中的颜色 / 字体 / 图标 / 图片。防止长 deck 发生上下文漂移。详见 executor.md §3.1。

> ⚠️ **仅限主智能体**：SVG 生成**必须**留在当前主智能体中 —— 页面设计依赖完整的上游上下文。**禁止**委托给子智能体。
> ⚠️ **生成节奏**：在同一个连续上下文中，一页一页地按顺序生成页面。**禁止**批量生成（如每组 5 页）。

**视觉构建阶段**：一次连续处理中按顺序逐页生成 SVG 页面 → `workspace/svg_output/`

**每页更新页进度（强制）**：每完成一页 SVG 写入后，立即更新 `workspace/state.md` 的“当前页进度”字段（如 P03/12），以便会话中断后可从该页恢复。

**质量检查门控（强制）** —— 在所有 SVG 生成后，生成演讲备注之前：
```powershell
python scripts/svg_quality_checker.py workspace
```
- 任何 `error`（使用了禁用的 SVG 特性、viewBox 不匹配、偏离 spec_lock 等）**必须**在继续前修复 —— 返回视觉构建阶段，重新生成该页，再次运行检查。
- `warning` 条目（低分辨率图片、非 PPT 安全字体结尾等）：如果容易修复就修复，否则确认情况后放行。
- 对 `svg_output/` 运行检查（不要在运行 `finalize_svg.py` 之后检查，因为 finalize 会重写 SVG 并掩盖违规项）。

**状态更新**：如果 quality_checker 报告 error，将错误记入 `workspace/state.md` 错误日志。如果发现新类型的错误模式（如首次遇到的 spec_lock 漂移原因），追加经验教训。修复后更新进度。

**逻辑构建阶段**：生成演讲备注 → `workspace/notes/notes_all.md`

**✅ 检查点 —— 确认所有 SVG 和演讲备注均已生成并完成质量检查。直接进入第 5 步后处理（然后用户手动执行第 6 步导出 PPTX）**：
```markdown
## ✅ Executor 阶段完成
- [x] 所有 SVG 均已生成到 svg_output/
- [x] svg_quality_checker.py 检查通过 (0 errors)
- [x] 演讲备注已生成到 notes/notes_all.md
- [x] state.md 页进度已更新至最后一页
```

> **成功标准**：`svg_output/` 包含与 spec_lock `page_rhythm` 页数匹配的 SVG 文件；`svg_quality_checker.py` 返回 0 errors；每页 SVG 的颜色/字体/图标均来自 spec_lock。

**状态更新**：`workspace/state.md` 阶段清单标记 S4 完成，当前阶段改为 S5。

> **图表页？** 如果该 deck 包含数据图表（柱状图 / 折线图 / 饼图 / 雷达图等），在进入第 5 步前运行独立的 [`verify-charts`](optional-workflows/verify-charts.md) 工作流以校准坐标。AI 模型在将数据映射到像素位置时通常会产生 10-50 px 的误差；verify-charts 可以消除此类误差。如果没有图表页则跳过。完成图表校准后，进入第 5 步后处理，然后用户手动执行第 6 步导出 PPTX。

---

### 第 5 步：后处理

🚧 **GATE**：第 4 步完成；所有 SVG 生成到 `workspace/svg_output/`；演讲备注 `workspace/notes/notes_all.md` 已生成。

> ⚠️ 这两个子步骤必须**依次单独运行** —— 每一步成功完成后才能进行下一步。
> ❌ **绝不要**把它们合并成一个代码块或一次 Shell 调用。

标准两命令流程（参考 `references/shared-standards.md` §5）：

**第 5.1 步** —— 拆分演讲备注：
```powershell
python scripts/notes_all_md_split.py workspace
```

**第 5.2 步** —— SVG 后处理（图标嵌入 / 图片裁剪与嵌入 / 文本扁平化 / 圆角矩形转路径）：
```powershell
python scripts/finalize_svg.py workspace
```

> ❌ **绝不要**用 `cp` 替代 `finalize_svg.py` —— finalize 执行多个关键处理步骤

> **成功标准**：`workspace/svg_final/` 文件数与 `workspace/svg_output/` 一致；`workspace/notes/` 下每页一个独立 `.md` 文件。

---

### 第 6 步：用户手动导出 PPTX

🚧 **GATE**：第 5 步完成；`workspace/svg_final/` 已生成。

**导出 PPTX（默认嵌入演讲备注）**：
```powershell
python scripts/svg_to_pptx.py workspace -s final
# 输出：
#   workspace/exports/<timestamp>.pptx           ← 最终原生 pptx
#   workspace/backup/<timestamp>/svg.pptx        ← SVG 格式快照
#   workspace/backup/<timestamp>/svg_output/     ← Executor SVG 源码备份
```

**可选动画参数**（默认已开启丰富的入场动画 —— 仅在用户有不同要求时调整）：
- `-t <effect>` —— 页面切换动画。默认 `fade`。选项：`fade` / `push` / `wipe` / `split` / `strips` / `cover` / `random` / `none`。
- `-a <effect>` —— 元素入场动画。默认 `mixed`（整个 deck 自动随机变化）。传 `none` 可禁用，或指定特定效果如 `fade`。要求顶层必须有 `<g id="...">` 分组（Executor 已被要求这样做）。
- `--animation-trigger {on-click,with-previous,after-previous}` —— 启动模式（对应 PowerPoint 动画窗格的启动下拉菜单）。默认 `after-previous`（无需点击的级联播放；通过 `--animation-stagger` 控制节奏）。使用 `on-click` 让演讲者手动控制，或使用 `with-previous` 同时入场。
- `--auto-advance <seconds>` —— 展台式的自动播放时间。

完整效果列表、锚点逻辑及限制见：`references/animations.md`。

> ❌ **绝不要**从 `svg_output/` 目录导出 —— **必须**使用 `-s final`（从 `svg_final/` 导出）
> ❌ **绝不要**使用 `--only`（这会抑制生成两个输出文件之一）

> **成功标准**：`workspace/exports/` 下存在带时间戳的 `.pptx` 文件且文件大小 > 0。

---

## 角色切换协议

在切换角色前，**必须先阅读**对应的参考文件。输出标记：

```markdown
## [角色切换: <角色名称>]
📖 读取角色定义：references/<filename>.md
📋 当前任务：<简要描述>
```

---

## 参考资源

| 资源 | 路径 |
|----------|------|
| 共享技术约束（含画布格式、图片布局、图片嵌入） | `references/shared-standards.md` |
| Executor 角色定义与执行指南 | `references/executor.md` |
| 图标库说明 | `templates/icons/README.md` |
| 三件套状态模板 | `templates/state/` |

---

## 错误恢复协议

当 LLM 遇到以下情况时，按照标准流程处理并记录到状态文件：

### 会话中断恢复

1. 新会话启动时，`read_file workspace/state.md`
2. 根据 state.md 的“当前阶段”和“当前页进度”定位恢复点
3. 从该阶段继续，**不要**从头重跑已完成阶段
4. 恢复后追加进度记录：`| <时间> | 会话恢复 | 从 <阶段/页> 继续 |`

### tool call 失败

1. 记录到 `workspace/state.md`
2. 重试一次（使用相同或等效的调用方式）
3. 仍失败：写入经验教训，告知用户具体错误

### spec_lock 漂移

1. 记录到 `workspace/state.md` 错误日志（漂移值 + 所在页）
2. 修复后追加经验教训（漂移原因 + 修复方式），防止后续页面重犯
3. 更新进度

### 脚本执行失败

1. 记录错误信息到 `workspace/state.md` 错误日志
2. 分析错误原因（参数错误？路径问题？Python 异常？）
3. 如果是首次遇到的错误类型，追加经验教训
4. 修正后重试；修正动作也追加到进度

### 手术刀修复（强制）

修复错误时**只动目标页/目标元素**，不连带改写无关内容：

- quality_checker 报 P05 漂移 → 只重生成 P05，**不要**"顺便"检查/修改 P04 和 P06
- 用户说"P05 标题溢出" → 只缩小 P05 标题字号或换行，**不要**重新布局 P05 整页
- 修一个颜色漂移 → 只替换该颜色值，**不要**"统一"相邻页面的间距或布局
- 修改产生孤儿代码时（如删除了图片引用后的 `<clipPath>`），**必须**清理；但预先存在的死代码不要删

**检验标准**：diff 中每一行改动都应该能直接追溯到触发修复的那个错误。
