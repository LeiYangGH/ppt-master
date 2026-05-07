---
name: ppt-master
description: >
  AI驱动的多格式SVG内容生成系统。通过多角色协作，将源文档Markdown转换为高质量SVG页面并导出为PPTX。当用户要求“生成PPT”、“做PPT”、“制作演示文稿”时调用。
---

# PPT Master 技能

> AI驱动的多格式SVG内容生成系统。通过多角色协作将源文档转换为高质量SVG页面，并导出为PPTX。

**核心流程**：`源文档 → 创建项目 → 模板选项 → Strategist → [Image_Generator] → Executor → 后处理 → 导出`

> [!CAUTION]
> ## 🚨 全局执行纪律（强制）
>
> **本工作流是严格的串行流程。以下规则具有最高优先级——违反任何一条都视为执行失败：**
>
> 1. **串行执行** —— 步骤必须按顺序执行；上一步的输出是下一步的输入。满足前提条件的非阻塞相邻步骤可连续进行，无需等待用户确认。
> 2. **阻塞 = 强制停止** —— 标有 ⛔ BLOCKING 的步骤需要完全停止；AI **必须**等待用户的明确回复后才能继续，**绝对不能**替用户做决定。
> 3. **禁止跨阶段打包** —— 跨阶段打包是禁止的。（注：第 4 步中的八项确认是 ⛔ BLOCKING——AI 必须提供建议并等待用户的明确确认。一旦用户确认，后续所有非阻塞步骤——设计规范、SVG、演讲备注和后处理——都可自动连续进行）。
> 4. **先检查门控** —— 每个步骤顶部都列有前提条件（🚧 GATE）；在开始该步骤前**必须**核实。
> 5. **禁止推测性执行** —— **禁止**为后续步骤“预先准备”内容（例如，在 Strategist 阶段编写 SVG 代码）。
> 6. **禁止子智能体生成 SVG** —— 第 6 步 Executor 生成 SVG 高度依赖上下文，**必须**由当前主智能体端到端完成。**禁止**委托给子智能体。
> 7. **仅限逐页生成** —— 在第 6 步 Executor 中，全局设计上下文确认后，SVG 页面**必须**在一个连续的上下文中按顺序一页一页地生成。**禁止**批量生成（例如每次 5 页）。
> 8. **每页重读 SPEC_LOCK** —— 在生成每页 SVG 之前，Executor **必须** `read_file <project_path>/spec_lock.md`。所有颜色 / 字体 / 图标 / 图片**必须**来自此文件。Executor 还**必须**查找当前页的 `page_rhythm` 标签，并应用匹配的布局纪律（`anchor` / `dense` / `breathing`——见 executor-base.md §2.1）。

> [!IMPORTANT]
> ## 💻 运行环境与命令规则（强制）
>
> - **优先使用虚拟环境**：本项目应优先使用工作区下的虚拟环境（如 `.venv` 或 `venv`）。**绝不能**使用系统默认的 Python。所有示例指令中的 `python xxx.py` 仅为简单惯例，实际执行时必须使用当前项目的虚拟环境中的 python。
> - **使用 Windows PowerShell**：所有的终端操作都在 Windows PowerShell 下进行。**绝不能使用 Linux 命令**（如 `cp`、`ls`、`grep`、`rm` 等）。所有向终端发送的命令必须是原生兼容 PowerShell 的。
> - **直接读写文件**：当前运行于 AI IDE 环境（如 VS Code + Continue 插件），具备原生文件读写能力。**必须**使用 IDE 提供的文件读写工具直接操作文件，**禁止**通过新建 Python 脚本等迂回方式间接读写文件。调用文件读写工具时须注意传参规范，确保路径正确、编码无误。

> [!IMPORTANT]
> ## 🌐 语言与沟通规则
>
> - **回复语言**：与用户输入和源材料保持一致。明确的用户指令（如“请用英文回答”）具有最高优先级。
> - **模板格式**：无论对话语言为何，`design_spec.md` **必须**遵循其原始的英文模板结构（章节标题、字段名）。内容值可以使用用户的语言。

> [!IMPORTANT]
> ## 🔌 与通用编码技能的兼容性
>
> - `ppt-master` 是一个特定于该仓库的工作流，而不是通用的应用程序脚手架。
> - **不要**默认创建 `.worktrees/`、`tests/`、分支工作流或通用工程结构。
> - 当与通用编码技能发生冲突时，优先遵循本技能规则。

## 主要流程脚本

| 脚本 | 用途 |
|--------|---------|
| `${SKILL_DIR}/scripts/project_manager.py` | 项目初始化 / 校验 / 管理 |
| `${SKILL_DIR}/scripts/analyze_images.py` | 图片分析 |
| `${SKILL_DIR}/scripts/image_gen.py` | AI 图片生成（多服务商） |
| `${SKILL_DIR}/scripts/svg_quality_checker.py` | SVG 质量检查 |
| `${SKILL_DIR}/scripts/total_md_split.py` | 演讲备注拆分 |
| `${SKILL_DIR}/scripts/finalize_svg.py` | SVG 后处理（统一入口） |
| `${SKILL_DIR}/scripts/svg_to_pptx.py` | 导出为 PPTX |
| `${SKILL_DIR}/scripts/update_spec.py` | 将 `spec_lock.md` 中的颜色 / 字体变更同步到所有 SVG |

完整的工具文档见 `${SKILL_DIR}/scripts/README.md`。

## 模板索引

| 索引 | 路径 | 用途 |
|-------|------|---------|
| 布局模板 | `${SKILL_DIR}/templates/layouts/layouts_index.json` | 查询可用的页面布局模板 |
| 可视化模板 | `${SKILL_DIR}/templates/charts/charts_index.json` | 查询可用的可视化 SVG 模板（图表、信息图、流程图等） |
| 图标库 | `${SKILL_DIR}/templates/icons/` | 见 `${SKILL_DIR}/templates/icons/README.md`；按需搜索：`Get-ChildItem templates\icons\<library>\*<keyword>*` |

## 独立工作流

| 工作流 | 路径 | 用途 |
|----------|------|---------|
| `create-template` | `workflows/create-template.md` | 独立模板创建工作流 |
| `verify-charts` | `workflows/verify-charts.md` | 图表坐标校准 —— 若 deck 包含数据图表，在生成 SVG 后运行 |

---

## 工作流

### 第 1 步：源内容处理

🚧 **GATE**：用户已准备好 Markdown 格式的源材料。

直接读取用户提供的 Markdown 源内容即可。

**✅ 检查点 —— 确认源内容准备就绪，继续进入第 2 步。**

---

### 第 2 步：项目初始化

🚧 **GATE**：第 1 步完成；源内容准备就绪（Markdown 文件或对话中描述的需求均有效）。

```powershell
python ${SKILL_DIR}/scripts/project_manager.py init <project_name> --format <format>
```

格式选项：`ppt169` (默认)、`ppt43`、`xhs`、`story` 等。完整格式列表请参见 `references/canvas-formats.md`。

导入源内容（视情况选择）：

| 情况 | 操作 |
|-----------|--------|
| 有源 Markdown 等文件 | `python ${SKILL_DIR}/scripts/project_manager.py import-sources <project_path> <source_files...> --move` |
| 用户在对话中直接提供文本 | 无需导入 —— 内容已在对话上下文中；后续步骤可直接引用 |

> ⚠️ **必须使用 `--move`** (而不是复制)：所有源文件 —— 原始 Markdown / 图片 —— 都通过 `import-sources --move` 移动到 `sources/` 中。执行后它们在原位置将不再存在。中间产物（例如 `_files/`）会自动处理。

**✅ 检查点 —— 确认项目结构创建成功，`sources/` 包含所有源文件，转换材料准备就绪。继续进入第 3 步。**

---

### 第 3 步：模板选项

🚧 **GATE**：第 2 步完成；项目目录结构准备就绪。

**默认 —— 自由设计。** 直接进入第 4 步。不要查询 `layouts_index.json`。不要向用户询问选择模板还是自由设计的问题。

**模板流程是可选的。** 仅当用户之前的消息中出现明确触发条件时才进入：

1. 指定了具体模板（如“用 mckinsey 模板” / “use the academic_defense template”）
2. 指定了对应模板的风格/品牌（如“McKinsey 那种” / “Google style” / “学术答辩样式”）
3. 询问有哪些模板可用（如“有哪些模板可以用”）

触发时：读取 `${SKILL_DIR}/templates/layouts/layouts_index.json`，匹配模板（对于触发条件 3 则列出选项），并复制：

```powershell
Copy-Item "${SKILL_DIR}\templates\layouts\<template_name>\*.svg" -Destination "<project_path>\templates\"
Copy-Item "${SKILL_DIR}\templates\layouts\<template_name>\design_spec.md" -Destination "<project_path>\templates\"
Copy-Item "${SKILL_DIR}\templates\layouts\<template_name>\*.png" -Destination "<project_path>\images\" -ErrorAction SilentlyContinue
Copy-Item "${SKILL_DIR}\templates\layouts\<template_name>\*.jpg" -Destination "<project_path>\images\" -ErrorAction SilentlyContinue
```

**软提示（非阻塞）。** 当内容非常契合某个现有模板（例如学术答辩、政府报告、McKinsey 风格），且**未触发**上述模板条件时，输出一句简短提示并继续（不等待用户回复）：

> 提示：内置库中有一个非常契合此场景的模板 `<name>`。如果你想使用它请告诉我，否则我将继续进行自由设计。

这只是提示，不是提问 —— **不要阻塞**。如果匹配度低或不明确则完全跳过。

> 要创建新的全局模板，请阅读 `workflows/create-template.md`

**✅ 检查点 —— 默认路径无需用户交互即可进入第 4 步。如果触发了模板，需在进入下一步前复制模板文件。**

---

### 第 4 步：Strategist 阶段（强制 —— 不可跳过）

🚧 **GATE**：第 3 步完成；采用默认的自由设计路径，或者（如果触发）已将模板文件复制到项目中。

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
python ${SKILL_DIR}/scripts/analyze_images.py <project_path>/images
```

> ⚠️ **图片处理**：绝不要直接读取 / 打开 / 查看图片文件（`.jpg`、`.png` 等）。所有图片信息必须来自 `analyze_images.py` 的输出或设计规范中的图片资源列表。

**输出**：
- `<project_path>/design_spec.md` —— 供人类阅读的设计叙述
- `<project_path>/spec_lock.md` —— 机器可读的执行契约（骨架见：`templates/spec_lock_reference.md`）；Executor 在生成每页前会重读此文件

**✅ 检查点 —— 阶段交付物完成，自动进入下一步**：
```markdown
## ✅ Strategist 阶段完成
- [x] 八项确认完成（用户已确认）
- [x] 已生成设计规范和内容大纲 (Design Specification & Content Outline)
- [x] 已生成执行锁文件 (spec_lock.md)
- [ ] **下一步**：自动进入 [Image_Generator / Executor] 阶段
```

---

### 第 5 步：Image_Generator 阶段（按需执行）

🚧 **GATE**：第 4 步完成；已生成设计规范与内容大纲并获用户确认。

> **触发条件**：图片使用方式包含“AI generation (AI 生成)”。否则跳过此步直接进入第 6 步。

读取 `references/image-generator.md`

1. 从设计规范中提取所有状态为 `Pending` 的图片
2. 生成提示词文档 → `<project_path>/images/image_prompts.md`
3. 生成图片（推荐使用 CLI 工具）：
   ```powershell
   python ${SKILL_DIR}/scripts/image_gen.py "prompt" --aspect_ratio 16:9 --image_size 1K -o <project_path>/images
   ```

**✅ 检查点 —— 确认已为每一行尝试生成图片，继续进入第 6 步**：
```markdown
## ✅ Image_Generator 阶段完成
- [x] 提示词文档已创建
- [x] 每张图片：状态为 `Generated`（文件存在于 images/ 目录）或 `Needs-Manual`（已向用户报告文件名及原因）
- [x] 没有状态仍为 `Pending` 的行
```

> 生成失败时不要停止 —— 遵循 `references/image-generator.md` §4.3 中的失败处理规则：重试一次，然后将该行标记为 `Needs-Manual`，向用户报告并继续执行第 6 步。

---

### 第 6 步：Executor 阶段

🚧 **GATE**：第 4 步（如果触发还包括第 5 步）完成；所有前置交付物已准备就绪。

根据选定的风格读取角色定义：
```
读取 references/executor-base.md          # 必需：通用准则
读取 references/shared-standards.md       # 必需：SVG/PPT 技术约束
读取 references/executor-general.md       # 通用灵活风格
读取 references/executor-consultant.md    # 咨询风格
读取 references/executor-consultant-top.md # 顶级咨询风格（MBB 级别）
```

> 只需读取 executor-base + shared-standards + 其中一个风格文件。

**设计参数确认（强制）**：在生成第一个 SVG 之前，输出规范中的关键设计参数（画布尺寸、配色方案、字体方案、正文字号）。详见 executor-base.md §2。

**每页重读 spec_lock（强制）**：在生成**每页** SVG 之前，`read_file <project_path>/spec_lock.md` 并且仅使用其中的颜色 / 字体 / 图标 / 图片。防止长 deck 发生上下文漂移。详见 executor-base.md §2.1。

> ⚠️ **仅限主智能体**：SVG 生成**必须**留在当前主智能体中 —— 页面设计依赖完整的上游上下文。**禁止**委托给子智能体。
> ⚠️ **生成节奏**：在同一个连续上下文中，一页一页地按顺序生成页面。**禁止**批量生成（如每组 5 页）。

**视觉构建阶段**：一次连续处理中按顺序逐页生成 SVG 页面 → `<project_path>/svg_output/`

**质量检查门控（强制）** —— 在所有 SVG 生成后，生成演讲备注之前：
```powershell
python ${SKILL_DIR}/scripts/svg_quality_checker.py <project_path>
```
- 任何 `error`（使用了禁用的 SVG 特性、viewBox 不匹配、偏离 spec_lock 等）**必须**在继续前修复 —— 返回视觉构建阶段，重新生成该页，再次运行检查。
- `warning` 条目（低分辨率图片、非 PPT 安全字体结尾等）：如果容易修复就修复，否则确认情况后放行。
- 对 `svg_output/` 运行检查（不要在运行 `finalize_svg.py` 之后检查，因为 finalize 会重写 SVG 并掩盖违规项）。

**逻辑构建阶段**：生成演讲备注 → `<project_path>/notes/total.md`

**✅ 检查点 —— 确认所有 SVG 和演讲备注均已生成并完成质量检查。直接进入第 7 步后处理**：
```markdown
## ✅ Executor 阶段完成
- [x] 所有 SVG 均已生成到 svg_output/
- [x] svg_quality_checker.py 检查通过 (0 errors)
- [x] 演讲备注已生成到 notes/total.md
```

> **图表页？** 如果该 deck 包含数据图表（柱状图 / 折线图 / 饼图 / 雷达图等），在进入第 7 步前运行独立的 [`verify-charts`](workflows/verify-charts.md) 工作流以校准坐标。AI 模型在将数据映射到像素位置时通常会产生 10-50 px 的误差；verify-charts 可以消除此类误差。如果没有图表页则跳过。

---

### 第 7 步：后处理与导出

🚧 **GATE**：第 6 步完成；所有 SVG 生成到 `svg_output/`；演讲备注 `notes/total.md` 已生成。

> ⚠️ 这三个子步骤必须**依次单独运行** —— 每一步成功完成后才能进行下一步。
> ❌ **绝不要**把它们合并成一个代码块或一次 Shell 调用。

标准三命令流程（参考 `references/shared-standards.md` §5）：

**第 7.1 步** —— 拆分演讲备注：
```powershell
python ${SKILL_DIR}/scripts/total_md_split.py <project_path>
```

**第 7.2 步** —— SVG 后处理（图标嵌入 / 图片裁剪与嵌入 / 文本扁平化 / 圆角矩形转路径）：
```powershell
python ${SKILL_DIR}/scripts/finalize_svg.py <project_path>
```

**第 7.3 步** —— 导出 PPTX（默认嵌入演讲备注）：
```powershell
python ${SKILL_DIR}/scripts/svg_to_pptx.py <project_path> -s final
# 输出：
#   exports/<project_name>_<timestamp>.pptx           ← 最终原生 pptx
#   backup/<timestamp>/<project_name>_svg.pptx        ← SVG 格式快照
#   backup/<timestamp>/svg_output/                    ← Executor SVG 源码备份
```

**可选动画参数**（默认已开启丰富的入场动画 —— 仅在用户有不同要求时调整）：
- `-t <effect>` —— 页面切换动画。默认 `fade`。选项：`fade` / `push` / `wipe` / `split` / `strips` / `cover` / `random` / `none`。
- `-a <effect>` —— 元素入场动画。默认 `mixed`（整个 deck 自动随机变化）。传 `none` 可禁用，或指定特定效果如 `fade`。要求顶层必须有 `<g id="...">` 分组（Executor 已被要求这样做）。
- `--animation-trigger {on-click,with-previous,after-previous}` —— 启动模式（对应 PowerPoint 动画窗格的启动下拉菜单）。默认 `after-previous`（无需点击的级联播放；通过 `--animation-stagger` 控制节奏）。使用 `on-click` 让演讲者手动控制，或使用 `with-previous` 同时入场。
- `--auto-advance <seconds>` —— 展台式的自动播放时间。

完整效果列表、锚点逻辑及限制见：`references/animations.md`。

> ❌ **绝不要**用 `cp` 替代 `finalize_svg.py` —— finalize 执行多个关键处理步骤
> ❌ **绝不要**从 `svg_output/` 目录导出 —— **必须**使用 `-s final`（从 `svg_final/` 导出）
> ❌ **绝不要**使用 `--only`（这会抑制生成两个输出文件之一）

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
| 共享技术约束 | `references/shared-standards.md` |
| 画布格式规范 | `references/canvas-formats.md` |
| 图片布局规范 | `references/image-layout-spec.md` |
| SVG 图片嵌入说明 | `references/svg-image-embedding.md` |
| 图标库说明 | `templates/icons/README.md` |
