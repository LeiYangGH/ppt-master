**核心流程**：(用户手动)创建项目（可选提供素材） → (可选)模板选项 → Strategist → Executor → 后处理 → 导出

## 全局执行纪律

1. **串行执行** —— 步骤必须按顺序执行；上一步的输出是下一步的输入。每步骤开始前必须核实其前提条件（🚧 GATE）。满足前提条件的非阻塞相邻步骤可连续进行，无需等待用户确认。
2. **阻塞 = 强制停止** —— 标有 ⛔ BLOCKING 的步骤需要完全停止；AI **必须**等待用户的明确回复后才能继续，**绝对不能**替用户做决定。
3. **极简改动**
4. **每页重读 SPEC_LOCK** —— 在生成每页 SVG 之前，Executor **必须** `read_file workspace/spec_lock.md`。所有颜色 / 字体 / 图标 / 图片**必须**来自此文件。Executor 还**必须**查找当前页的 `page_rhythm` 标签，并应用匹配的布局纪律（`structural` / `analytical` / `focal`——见 executor.md §3.1）。
5. **先思考后动手** —— 在关键决策前，**必须**先读取 `workspace/state.md`，确保理解当前状态和已积累的经验教训。如果对用户需求存在多种解读，**必须**呈现权衡让用户选择，而非默默选一种。如果存在更简单的方案，**必须**提出来。困惑时停下来问，不要假设。


## 运行环境与命令规则

- **优先使用虚拟环境**：`venv`，已安装依赖。如果需要安装请使用阿里云镜像源。
- **操作系统适配**：Windows 使用 PowerShell（如 `Get-ChildItem`），Linux 使用 Bash（如 `ls`）。
- **直接读写文件**：当前运行于 AI IDE 环境（如 opencode cli），具备原生文件读写能力。**必须**使用 IDE 提供的文件读写工具直接操作文件，**禁止**通过新建 Python 脚本等迂回方式间接读写文件。

- **回复语言**：简体中文。

## 📋 会话状态管理

单个状态文件 `workspace/state.md` 作为 LLM 的**磁盘工作内存**——对抗上下文压缩、会话中断、重复犯错。

**读写时机**：

| 时机 | 必须读 | 必须写 |
|------|--------|--------|
| 会话启动 / 恢复 | `workspace/state.md` | — |
| 阶段切换 | — | 更新当前阶段 + 阶段清单 |
| 每页 SVG 生成后 | — | 更新当前页进度（如 P03/12） |
| 遇到并解决错误 | — | 追加错误日志 + 经验教训 |
| 用户做出关键决策 | — | 追加决策记录 |
| 关键动作完成（脚本执行、⛔ 通过等） | — | 追加进度记录 |
| 发现图片/源文档关键信息 | — | 追加发现记录 |

## 主要流程脚本

| 脚本 | 用途 |
|--------|---------|
| `scripts/project_manager.py` | 工作区初始化 / 校验 / 管理（含状态文件初始化） |
| `scripts/web_search.py` | 网页 / 图片搜索（Tavily + 百度自动轮询）。**搜索后自动下载到 `workspace/downloads/` 暂存区**并自动生成**增量缩略图墙**；通过 `--adopt` 晋升到 `workspace/images/`。⚠ 搜索关键字必须用中文。**完整 CLI / 状态文件 / 配额 / 返回 schema 见 `references/web-search.md`**。 |
| `scripts/analyze_images.py` | 图片分析（尺寸比例等）。由 `web_search.py` 自动管道调用，通常无需手动运行。 |
| `scripts/image_montage.py` | 图片缩略图墙生成器（4×5 格 + 文件名标签）。由 `web_search.py` 自动管道**按下载批次增量**调用，通常无需手动运行。 |
| `scripts/svg_repair.py` | SVG XML 自动修复（基于 sloppy-xml，修复 LLM 输出的不规范 XML） |
| `scripts/svg_quality_checker.py` | SVG 质量检查 |
| `scripts/render_svg.py` | SVG → PNG 预览渲染（用于逐页视觉复检） |
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
| `topic-research` | `optional-workflows/topic-research.md` | 主题研究 —— 当用户仅提供简要描述时，从零研究主题并生成结构化 Markdown 文档和相关图片 |
| `verify-charts` | `optional-workflows/verify-charts.md` | 图表坐标校准 —— 若 deck 包含数据图表，在生成 SVG 后运行 |

---

## 工作流

### 第 1 步：用户准备工作

1. **初始化工作区**：`python scripts/project_manager.py`
2. **放置素材**：将源文件放入 `workspace/sources/`

**会话恢复**：若 `workspace/state.md` 存在且非 S0 阶段，从记录阶段继续。

**✅ 检查点**：工作区已初始化且素材已就绪。

---

### 第 2 步：模板选项

🚧 **GATE**

**默认 —— 自由设计。** 直接进入第 3 步。

**模板流程是可选的。** 仅当用户明确指定模板、风格或询问可用模板时才进入。

触发时：读取 `templates/layouts/layouts_index.json`，匹配模板，复制文件到 `workspace/templates/` 和 `workspace/images/`。

**✅ 检查点**：默认路径无需交互；如触发模板，需复制文件后进入第 3 步。

---

### 第 3 步：Strategist 阶段

🚧 **GATE**

首先，读取角色定义 `references/strategist.md`。


**八项确认**（完整模板见：`templates/design_spec_reference.md`）：

⛔ **BLOCKING**：将八项确认作为一组打包的建议呈现给用户，并**等待用户的明确确认或修改**后，才能输出设计规范和内容大纲。

1. 画布格式 (Canvas format)
2. 页数范围 (Page count range)
3. 目标受众 (Target audience)
4. 风格目标 (Style objective)
5. 配色方案 (Color scheme)
6. 图标使用方式 (Icon usage approach)
7. 字体方案 (Typography plan)
8. 图片使用方式 (Image usage approach)

如果用户提供了图片，**在输出设计规范之前**进行分析：`python scripts/analyze_images.py`

⚠️ **图片处理**：`workspace/images/` 只存**已采纳、已重命名**的正式资产；`web_search.py` 的自动下载落在 `workspace/downloads/`，并同步生成增量缩略图墙。LLM 通过读缩略图墙批量判定，然后用 `python scripts/web_search.py --adopt <downloads/xxx> <images/描述名>` 一次性完成移动+重命名。详见 `references/web-search.md`。

⛔ **BLOCKING**：所有准备采纳到 SVG 的图片，必须重命名为 `<ppt号>-<简洁图片内容>` 的格式（例如 `P03-团队合影.jpg`）。完成重命名后，**必须等待人工核查确认图片内容与命名一致**，人工核查通过后才能继续输出设计规范。

⛔ **硬门禁**：`scripts/finalize_svg.py` 会在后处理阶段扫描 `workspace/images/`，如果发现 `img_<hash>` / `image_\d+` / `tmp_*` / `download*` 等哈希/占位命名的文件直接 block——必须全部采纳或删除后方可 finalize。

**输出**：`workspace/design_spec.md`、`workspace/spec_lock.md`

**✅ 检查点**：八项确认完成，设计规范和 spec_lock 已生成，自动进入第 4 步。

**状态更新**：`workspace/state.md` 标记 S0-S3 完成，当前阶段改为 S4。

---

### 第 4 步：Executor 阶段

🚧 **GATE**

读取角色定义：`references/executor.md`、`references/shared-standards.md`

**设计参数确认**：在生成第一个 SVG 之前，输出关键设计参数（画布尺寸、配色、字体、字号）。

**每页重读 spec_lock**：生成每页 SVG 前重读 `workspace/spec_lock.md`，仅使用其中的颜色/字体/图标/图片。

**视觉构建**：逐页生成 SVG → `workspace/svg_output/`

**每页更新页进度**：完成后立即更新 `workspace/state.md` 的当前页进度（如 P03/12）。

**质量检查门控**（所有 SVG 生成后）：`python scripts/svg_quality_checker.py`
- error 必须修复后重查
- warning 可修复则修复，否则放行

**状态更新**：error 记入日志，发现新错误模式追加经验教训。

**逻辑构建**：生成演讲备注 → `workspace/notes/notes_all.md`

**✅ 检查点**：所有 SVG 和演讲备注已生成，质量检查通过，自动进入第 5 步。

**成功标准**：svg_quality_checker.py 返回 0 errors。

**状态更新**：`workspace/state.md` 标记 S4 完成，当前阶段改为 S5。

**图表页**：如有数据图表，运行 `verify-charts` 工作流校准坐标。

---

### 第 5 步：后处理

🚧 **GATE**

⚠️ 两个子步骤必须依次单独运行。

**第 5.1 步** —— 拆分演讲备注：`python scripts/notes_all_md_split.py`

**第 5.2 步** —— SVG 后处理：`python scripts/finalize_svg.py`

**成功标准**：svg_final 文件数与 svg_output 一致，notes 下每页一个独立 .md 文件。

---

### 第 6 步：导出 PPTX

🚧 **GATE**

**导出 PPTX**：`python scripts/svg_to_pptx.py`（默认嵌入演讲备注，输出到 workspace/exports/）

**可选动画参数**（如需自定义，直接调用 svg_to_pptx 包）：完整效果列表见 `references/animations.md`。

**成功标准**：`workspace/exports/` 下存在带时间戳的 `.pptx` 文件且文件大小 > 0。

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
| 状态模板 | `templates/state.md` |

---

## 错误恢复协议

**会话中断恢复**：读取 `workspace/state.md`，从记录阶段/页继续，不重跑已完成阶段。

**tool call 失败**：记录到 state.md，重试一次，仍失败则告知用户。

**spec_lock 漂移**：记录错误日志，修复后追加经验教训。

**脚本执行失败**：记录错误日志，分析原因，首次错误追加经验教训，修正后重试。

### 手术刀修复

修复错误时**只动目标页/目标元素**，不连带改写无关内容：
- 用户说"P05 标题溢出" → 只缩小 P05 标题字号或换行，**不要**重新布局 P05 整页
- 修一个颜色漂移 → 只替换该颜色值，**不要**"统一"相邻页面的间距或布局
- 修改产生孤儿代码时（如删除了图片引用后的 `<clipPath>`），**必须**清理；但预先存在的死代码不要删

**检验标准**：diff 中每一行改动都应该能直接追溯到触发修复的那个错误。
