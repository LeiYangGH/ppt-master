# PPT Master 定制化架构蓝图

> 本文件是对 [`arch-design.md`](./arch-design.md) 的**定制化分支设计**，结合 [`customize-direction.md`](./customize-direction.md) 中的个人需求，并参考：
> - [`references/andrej-karpathy-skills-main`](./references/andrej-karpathy-skills-main/) —— LLM 行为四原则（Think Before Coding / Simplicity First / Surgical Changes / Goal-Driven Execution）
> - [`references/planning-with-files-master`](./references/planning-with-files-master/) —— Manus 风格"硬盘即工作内存"的三文件计划机制（`task_plan.md` / `findings.md` / `progress.md`）
>
> 本蓝图**只描述目标架构**，不包含改造步骤；落地拆解放在后续的迁移计划中。

---

## 0. 设计原则（最高优先级）

| # | 原则 | 来自 | 在本项目的具体含义 |
|---|------|------|--------------------|
| P1 | **中文优先** | 个人需求 | 所有面向 LLM 的提示词、角色定义、spec_lock 字段名说明、错误信息、交互文案默认中文；保留英文模板结构（DrawingML 字段名、SVG 标签名等技术词不翻译）|
| P2 | **人在回路 (HITL)** | 个人需求 | 每个"典型阶段"结束都有显式 ⛔ BLOCKING 确认点，LLM 提交建议、用户决定走/改/退 |
| P3 | **本地文件即工作内存** | planning-with-files | 关键状态全部落盘（spec_lock + 三件套），LLM 每次决策前重读关键文件，对抗上下文压缩 |
| P4 | **极简改动** | karpathy | 不为单次使用做抽象；每次 LLM 改动必须能溯源到用户请求；禁止顺手"优化"无关代码/SVG |
| P5 | **目标驱动** | karpathy | 每阶段定义可验证的成功标准（脚本检查 / 视觉审查 / 用户确认），LLM 自循环到达标 |
| P6 | **AI IDE 无关** | 个人需求 | 工作流不依赖任何商业 AI IDE 的私有 API；以 `SKILL.md` + 命令行脚本为契约，可在 Claude Code / Cursor / Cline / Continue / 纯 CLI agent 之间无缝迁移 |
| P7 | **素材解耦** | 个人需求 | 源文档转换不属于核心流水线；用户自备 Markdown 素材，LLM 仅做"基于现有素材的增量建议"|
| P8 | **Token 节约** | 个人需求 | 每次 BLOCKING 都是阶段性快照，失败回滚不需重跑前序；提示词中文化也降低同义 token 数 |

---

## 1. 整体架构（定制版）

### 1.1 流水线对比

```
原版： 源文档 → 转换 → 项目 → 模板 → 策略师(8确认) → 图像生成 → 执行器 → 后处理 → 导出
       └────────内嵌────────┘                  └─单一阻塞点─┘                 └自动连跑┘

定制： 用户自备MD素材 → 项目 → ⛔大纲DSL → ⛔策略师 → ⛔执行器(分批) → ⛔视觉审查回环 → 后处理 → 导出
       └用户域(脚本可选)┘   └每个⛔=人工确认+token快照, 失败只回滚到上一⛔, 不重跑前序─┘
```

### 1.2 分层架构图

```
┌──────────────────────────────────────────────────────────────────┐
│ L0  用户素材域（项目外，用户自治）                                 │
│      用户用任何工具产出 Markdown / 图片 / 数据                     │
│      LLM 不主动转换，只在用户请求时调用脚本辅助                    │
└────────────────────────────┬─────────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│ L1  项目工作区（本地硬盘 = LLM 工作内存）                          │
│      sources/  outline.ppt.yml  spec_lock.md  task_plan.md       │
│      findings.md  progress.md  svg_output/  svg_final/  exports/ │
└────────────────────────────┬─────────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│ L2  角色与阶段层（中文提示词，每阶段 ⛔ HITL 确认）                  │
│   ① 大纲师 Outliner   → outline.ppt.yml （新增 DSL）              │
│   ② 策略师 Strategist → design_spec.md + spec_lock.md             │
│   ③ 图像生成 ImageGen → images/*.png（可选）                      │
│   ④ 执行器 Executor   → svg_output/*.svg （分批, 每批可独立确认）   │
│   ⑤ 视觉审查 Reviewer → review_report.md（新增, VLM 审查回环）    │
└────────────────────────────┬─────────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│ L3  确定性工具层（纯 Python，无 LLM）                              │
│   project_manager / svg_quality_checker / finalize_svg /         │
│   svg_to_pptx / svg_position_calculator / outline_validator(新)  │
│   render_to_png(新, 给视觉审查用)                                  │
└──────────────────────────────────────────────────────────────────┘
                             ▲
                             │ 命令行接口（与 IDE 无关）
┌────────────────────────────┴─────────────────────────────────────┐
│ L4  AI Runner 适配层（薄壳，可替换）                                │
│   Cascade / Claude Code / Cursor / Cline / Aider / 纯 CLI         │
│   仅依赖：(a) 读写本地文件 (b) 执行 shell 命令 (c) 调用脚本         │
└──────────────────────────────────────────────────────────────────┘
```

**关键变化（vs 原架构）**：

| 变化 | 说明 |
|------|------|
| 新增 L0/L4 显式分层 | 强调用户域与 IDE 域不属于核心架构，本质是 L1+L2+L3 |
| 引入 Outline DSL | 在策略师之前增加结构化大纲阶段，作为最早的可确认快照 |
| 引入视觉审查回环 | 在 svg_quality_checker（结构性）之外增加 VLM 审查（视觉性）|
| 阶段切分粒度提升 | Executor 由"一次性顺序生成所有页"改为"分批+每批可确认" |
| 八确认拆散 | 不再是策略师内部独立流程，分摊到大纲与策略师两个 ⛔ |
| 三件套常驻 | 借鉴 planning-with-files，task_plan/findings/progress 全程持有 |

---

## 2. 项目目录结构（定制版）

```
projects/<project_name>/
├── sources/                  # 用户自备的 Markdown / 图片 / 数据（L0 输入）
│
├── outline.ppt.yml           # 【新增】PPT 大纲 DSL（最早的人工确认快照）
├── design_spec.md            # 策略师产出：人类可读设计叙事（中文）
├── spec_lock.md              # 策略师产出：机器可读执行锁（保留原机制）
│
├── task_plan.md              # 【新增, planning-with-files】阶段、状态、决策
├── findings.md               # 【新增】研究/发现（图像分析、用户确认要点等）
├── progress.md               # 【新增】会话日志（记录每个 ⛔ 通过时间与产物）
│
├── images/                   # 图片资源 + image_prompts.md
├── svg_output/               # 执行器产出（按批次组织）
│   ├── batch-01/             # 例如：封面+目录批
│   ├── batch-02/             # 例如：核心论点批
│   └── ...
├── notes/                    # 演讲者备注
│
├── review/                   # 【新增】视觉审查工件
│   ├── png/<page>.png        # 渲染快照
│   ├── review_report.md      # VLM 审查报告 + 修改建议
│   └── review_lock.md        # 用户确认采纳的修改清单
│
├── svg_final/                # finalize_svg 产物
├── exports/                  # 最终 PPTX
└── backup/<timestamp>/       # 阶段快照（每个 ⛔ 通过自动归档）
```

---

## 3. 大纲 DSL（新增）

### 3.1 为什么需要 DSL

`customize-direction.md` 第 2 条提出此疑问。结论：**值得**，理由：
- 大纲是最便宜的"走偏检测器"——比生成完整 design_spec 早一步、token 成本低一个数量级
- 结构化（YAML）便于脚本校验（`outline_validator.py`）：页数、节奏分布、必填字段
- 可作为策略师与执行器之间的"可重入契约"——任何时候 LLM 跑偏，都可以让用户改 outline.ppt.yml 后只重跑下游
- 用户可手写/口述/由 LLM 草拟，三种入口都能接

### 3.2 最小可行 schema

```yaml
# outline.ppt.yml —— 中文字段名 + 中文描述, 对中文擅长模型更友好
版本: 1
项目名: 高效能产品方法论
画布: ppt169                  # 与 canvas-formats.md 对齐
预计页数: 18
目标受众: 公司内部产品经理
风格目标: 专业冷静, 弱装饰, 重逻辑
语言: zh-CN

页面:
  - 序号: 1
    类型: 封面               # 封面|目录|章节扉页|论点|论据|图表|引用|结尾
    节奏: structural             # structural|analytical|focal （沿用原 page_rhythm）
    标题: 高效能产品方法论
    要点: []
    素材: []                 # 引用 sources/ 下的文件或片段锚点
  - 序号: 2
    类型: 目录
    节奏: focal
    标题: 我们将讨论的四件事
    要点: ["问题定义", "用户访谈", "MVP 设计", "复盘机制"]
    素材: []
  - 序号: 3
    类型: 论点
    节奏: analytical
    标题: 80% 的失败源于问题定义不清
    要点:
      - 数据: McKinsey 2023, 失败项目根因分析
      - 论据: 三类典型偏差
    素材: ["sources/mck-report.md#root-causes"]
    图表建议: bar             # 可选, 给执行器的提示
    图片建议: null
```

**约束**（由 `outline_validator.py` 强制）：
- `预计页数` ≤ `页面[]` 长度的 +/-2
- `节奏` 分布合理：`structural` 不超过 20%，连续 ≥3 页 `analytical` 触发警告
- 每页 `要点` ≤ 6 项
- `素材` 引用必须能在 `sources/` 解析到

### 3.3 与 spec_lock 的关系

`outline.ppt.yml` 锁定**内容骨架与节奏**，`spec_lock.md` 锁定**视觉契约**。两者正交、各自独立 ⛔ 确认。执行器每页必须同时满足两份锁。

---

## 4. 角色与阶段（中文化 + HITL）

### 4.1 阶段总表

| 阶段 | 角色 | 输入 | 产出 | ⛔ 阻塞点 | 失败回滚到 |
|------|------|------|------|-----------|------------|
| S0 | 项目初始化 | 用户描述 | 项目骨架 + 三件套 | 否 | — |
| S1 | **大纲师** | sources/ + 对话 | `outline.ppt.yml` | ⛔ 用户确认大纲 | S0 |
| S2 | **策略师** | outline + sources | `design_spec.md` + `spec_lock.md` | ⛔ 用户确认八项 | S1 |
| S3 | 图像生成（可选） | spec_lock | `images/*.png` | ⛔ 用户验收图片 | S2 |
| S4 | **执行器（分批）** | spec_lock + outline | `svg_output/batch-NN/` | ⛔ 每批用户确认 | 上一批 |
| S5 | **视觉审查** | svg_final 渲染 PNG | `review_report.md` | ⛔ 用户采纳清单 | S4 当前批 |
| S6 | 后处理 + 导出 | svg_output + notes | `exports/*.pptx` | 否 | S4 |

**核心承诺**：任何 ⛔ 失败，只回滚到"上一确认快照"，前序产物不重跑——这是 Token 节约的根本机制。

### 4.2 角色定义文件（全部中文化）

`skills/ppt-master/references/` 下原英文角色文件保留为 `*.en.md`，新增：

| 中文文件 | 来源 |
|----------|------|
| `outliner.zh.md` | 【新增】大纲师 |
| `strategist.zh.md` | 翻译 + 中文示例化 |
| `executor-base.zh.md` | 翻译 + 保留 SVG/DrawingML 技术词 |
| `executor-general.zh.md` / `executor-consultant.zh.md` / ... | 翻译 |
| `image-generator.zh.md` | 翻译 |
| `reviewer.zh.md` | 【新增】视觉审查员 |
| `shared-standards.md` | **保持英文**——纯技术约束（XML/SVG/DrawingML 标签），翻译反损失精度 |

> 取舍：`shared-standards.md` 中 SVG 黑名单、DrawingML 字段表等是事实而非话术，中文化无收益且增加歧义。其余角色话术全部中文。

### 4.3 提示词中文化的具体收益

| 维度 | 英文版 | 中文版 |
|------|--------|--------|
| Token 数（同语义） | 基线 | -15% ~ -25%（中文 1 字 ≈ 1-2 token，但语义密度更高）|
| 中文模型对齐度 | 一般（需跨语言对齐） | 高（直接命中训练分布）|
| 用户阅读成本 | 高 | 低（你自己也要读）|
| 与中文素材一致性 | 易出现"中英混用"输出 | 默认中文输出 |

---

## 5. 视觉审查回环（新增）

### 5.1 动机

`customize-direction.md` 第 7 条：现有 `svg_quality_checker.py` 只能查**结构性问题**（黑名单标签、viewBox、spec_lock 漂移），无法发现：
- 文字溢出画布 / 遮挡
- 视觉重心失衡、留白失调
- 配色实际呈现与设计预期偏差
- 图标语义与文本不匹配

需要 VLM（Vision-Language Model）做**视觉审查**。

### 5.2 设计

```
┌─────────────┐  ┌──────────────────┐  ┌──────────────────┐  ┌─────────────────┐
│ svg_output/ │→ │ render_to_png.py │→ │ Reviewer (VLM)   │→ │ review_report.md│
│ (一批)      │  │ (Playwright/cdp) │  │ 角色: 资深设计师 │  │ + 建议清单       │
└─────────────┘  └──────────────────┘  └──────────────────┘  └─────────────────┘
                                                                      │
                                                          ⛔ 用户挑选采纳的建议
                                                                      ▼
                                                            ┌─────────────────┐
                                                            │ review_lock.md  │
                                                            │ (机器可读补丁列)│
                                                            └────────┬────────┘
                                                                     ▼
                                                            执行器按 review_lock 修订
```

### 5.3 接口约定

`review_report.md`（人类可读）+ `review_lock.md`（机器可读 YAML），后者样例：

```yaml
版本: 1
批次: batch-02
修订项:
  - 页号: 5
    位置: { x: 120, y: 380, w: 480, h: 60 }
    问题: 标题文字溢出右侧画布 32px
    建议: 缩小字号 36→30 或换行
    严重度: 高
    采纳: true              # 用户在 ⛔ 时勾选
  - 页号: 7
    问题: 主图标"home"与"安全"主题不匹配
    建议: 改用 shield-filled
    严重度: 中
    采纳: false
```

执行器读取 `采纳: true` 的项目，按 surgical changes 原则**只动指定页面的指定元素**，不连带改写。

### 5.4 模型选择无关性

`reviewer.zh.md` 仅描述**评审标准**与**输出格式**，不绑定具体 VLM。当前 AI IDE 提供什么视觉模型就用什么；纯 CLI 场景可调用本地脚本（如 `claude` / `codex` CLI 的 vision 入口）传入 PNG。

---

## 6. AI IDE 无关性 (P6) 的具体实现

### 6.1 契约式约束

工作流契约只依赖三件事，全部是**开源/标准**：
1. **本地文件读写**——任何 IDE/CLI agent 都能做
2. **执行本地 shell 命令**——同上
3. **`SKILL.md` 中的中文 Markdown 流程描述**——纯文本，可被任何 LLM 解释

### 6.2 多入口适配

```
.windsurf/workflows/   ← 现有
.claude/commands/      ← 新增（参考 planning-with-files 的 commands/）
.cursor/rules/         ← 新增（短规则文件指向 SKILL.md）
.codex/                ← 新增（OpenAI Codex CLI）
.continue/             ← 新增
AGENTS.md              ← 现有，作为通用入口
CLAUDE.md              ← 现有
```

每个入口都是**薄壳**——内容仅一句"读 `skills/ppt-master/SKILL.md` 并按其执行"。真正的逻辑只在 `SKILL.md` 一处维护。

### 6.3 反例（必须避免）

| 反模式 | 为什么禁止 |
|--------|------------|
| 在 SKILL.md 中调用 Cascade 私有 API | 锁定单一 IDE |
| 用 IDE 内置的 TODO 面板代替 task_plan.md | 状态丢失，无法跨 IDE |
| 假定 LLM 能"看到"打开的文件 tab | 不同 IDE 行为不一 |
| 依赖 hooks（如 planning-with-files 的 PreToolUse） | 仅 Claude Code 支持；可作为**可选增强**，不能作为必要条件 |

### 6.4 hooks 作为可选增强

planning-with-files 用 `PreToolUse` hook 自动重读 `task_plan.md`。在本项目中：
- **必要路径**：在 `SKILL.md` 中显式写"每个 ⛔ 通过前 LLM 必须 `read_file task_plan.md`"——任何 agent 都能执行
- **可选路径**：在 `.claude-plugin/` 提供 hook 实现，使 Claude Code 用户体验更自动

---

## 7. 三件套（task_plan / findings / progress）适配

直接借用 planning-with-files 的语义，但裁剪到 PPT 场景：

### 7.1 `task_plan.md`

```markdown
# 项目: 高效能产品方法论 (ppt169, 18 页)

## 当前阶段
S4-执行器 (批次 02 / 共 4 批) — 进行中

## 阶段清单
- [x] S0 项目初始化           → 2026-04-30 14:00
- [x] S1 大纲                 → 2026-04-30 14:30  (1 次返工)
- [x] S2 策略 + spec_lock     → 2026-04-30 15:10
- [ ] S3 图像生成              (跳过 — 不使用 AI 图)
- [/] S4 执行器分批
  - [x] batch-01 封面+目录 (3 页)
  - [/] batch-02 核心论点 (5 页) ← 当前
  - [ ] batch-03 论据图表 (6 页)
  - [ ] batch-04 收尾 (4 页)
- [ ] S5 视觉审查
- [ ] S6 后处理 + 导出

## 决策记录
| # | 决策 | 时间 | 原因 |
|---|------|------|------|
| 1 | 取消 AI 图像生成 | 14:35 | 用户偏好真实素材 |
| 2 | batch 分 4 组 | 15:15 | 每批控制在 5±1 页便于审查 |

## 错误日志
| 错误 | 阶段 | 处理 |
|------|------|------|
| spec_lock 漂移 #1A73E8 | S4 batch-01 | 替换为 #005587 后重生成 P02 |
```

### 7.2 `findings.md`

研究/发现/图像分析输出/用户当面口述的关键信息——任何"看过一次怕忘"的内容都写这里，**绝不回头再 view 第二次图片**（沿用 2-Action Rule）。

### 7.3 `progress.md`

会话级日志：每个 ⛔ 通过、每次脚本执行、每次回滚都打一行时间戳。用于 token 重置/会话切换后的**状态恢复**。

### 7.4 与 spec_lock 的分工

| 文件 | 内容性质 | 写者 | 读者 |
|------|----------|------|------|
| `spec_lock.md` | 视觉契约（颜色/字体/图标/图片清单） | 策略师 | 执行器（每页重读）|
| `outline.ppt.yml` | 内容骨架（页序/类型/要点/节奏） | 大纲师 | 执行器、视觉审查员 |
| `task_plan.md` | 流程状态 | LLM 自更新 | 所有角色（每阶段重读）|
| `findings.md` | 易失信息存档 | LLM 在发现时立即写 | 后续阶段按需读 |
| `progress.md` | 历史日志 | LLM 每动作后追加 | 会话恢复时读 |

---

## 8. Token 与返工节约模型

### 8.1 节约来源

| 来源 | 估算节约 |
|------|----------|
| 提示词中文化 | -15~25% per call |
| 大纲 DSL 早期拦截 | 走偏 → 重跑代价从「策略+执行」降到「仅大纲」≈ -80% |
| 分批执行 | 单批失败回滚 ≈ -60~75% (vs 整篇重跑) |
| spec_lock 重读取代上下文携带 | 长 deck 后段每页节省 1k-3k token |
| 三件套显式状态 | 会话切换无需用户口述上下文 |
| 视觉审查 lock 化 | 修订只动指定项，不重生成整页 |

### 8.2 ⛔ 阻塞点的成本/收益

每个 ⛔ 看似增加用户操作，但：
- 阻塞点**之前**的所有 token 已花费且**已快照**——失败也不重花
- 阻塞点**之后**的失败只重跑该阶段
- 用户在 ⛔ 处的判断成本（秒级）远低于 LLM 在错误方向上跑出整页的成本（分钟级 + 数 k token）

---

## 9. 与原架构的兼容性矩阵

| 原架构资产 | 定制后命运 | 说明 |
|------------|------------|------|
| `pdf_to_md.py` 等转换脚本 | **保留**（移到可选工具） | 用户偶尔仍会需要 |
| `project_manager.py` | **保留+扩展** | 增加 `init` 时落地三件套 + outline 模板 |
| `Strategist 八确认` | **拆分** | 画布/页数/受众 → 大纲；色彩/图标/字体/图片 → 策略师 |
| `spec_lock.md` 机制 | **完全保留** | 已被验证有效 |
| `Executor 顺序生成` | **改为分批** | 每批 5±1 页 |
| `svg_quality_checker.py` | **保留** | 结构性检查，不可替代 |
| `finalize_svg.py` 流水线 | **完全保留** | 纯确定性，无需动 |
| `svg_to_pptx/` 包 | **完全保留** | DrawingML 转换是项目最硬核资产 |
| `svg_position_calculator.py` | **保留** | 图表校准已经是独立 workflow |
| `references/*.md`（英文） | **保留并双语化** | 中文版优先，英文版作为技术参考 |
| Cascade 特有指令 | **抽离** | 移到 `.windsurf/` 下，主流程不引用 |

**不引入新依赖**：除视觉审查需要的 `playwright`（或 `cairosvg` 作为更轻量替代）外，无其他第三方依赖；继续维持轻量原则。

---

## 10. 风险与权衡

| 风险 | 缓解 |
|------|------|
| ⛔ 太多让用户疲劳 | 每个 ⛔ 都允许"全部确认"快捷路径；非首次项目可由用户在 `.ppt-master.config.yml` 中关闭部分 ⛔ |
| 中文提示词在英文模型上效果下降 | 角色文件保留 `.en.md` 版本；通过 `SKILL.md` 中一行配置切换 |
| 大纲 DSL 学习成本 | 字段全中文 + 模板齐全；用户可让 LLM 草拟、自己改 |
| 视觉审查依赖 VLM 质量 | 审查输出是**建议**而非自动应用；用户在 ⛔ 处筛选 |
| 三件套与 spec_lock 信息重复 | 严格分工（见 §7.4），review checker 脚本拒绝跨界 |
| 多 IDE 入口维护成本 | 入口都是薄壳指向 SKILL.md，零业务逻辑 |

---

## 11. 成功标准（Goal-Driven, P5 落地）

定制化完成的可验证信号：

1. ✅ 在**纯 CLI**（无任何 IDE）下，仅靠 `python3` + 一个 LLM CLI（如 `claude`/`codex`），能跑通 S0→S6 全流程
2. ✅ 在 S2 ⛔ 处主动改 `outline.ppt.yml`，重跑后 S0/S1 不重新执行任何 LLM 调用
3. ✅ 单批执行器失败回滚后，前 N-1 批 SVG 文件不被触碰
4. ✅ `task_plan.md` 在会话清空后能 100% 恢复"我在哪、要去哪、做过什么"
5. ✅ 视觉审查至少能识别一类结构性检查器漏掉的问题（如文字溢出）
6. ✅ 所有 LLM 输出默认中文，技术 token（DrawingML/SVG 标签）保持英文
7. ✅ 同一个项目在 Windsurf / Claude Code / Cursor 三个环境下能交替推进，状态文件无冲突

---

## 12. 不在本蓝图范围内（明确排除）

为了不违反 P4（极简改动），下列**暂不**纳入：

- ❌ Web UI / 服务化部署
- ❌ 多人协作 / 云端 spec_lock
- ❌ 自动主题学习 / 风格迁移训练
- ❌ 替换 `python-pptx` 为自研 PPTX 写库
- ❌ 在 LLM 之外引入 Agent 编排框架（LangGraph / AutoGen 等）
- ❌ 数据库化 spec_lock（本地 Markdown 已足够）

如未来需要，按"先原则后实现"再讨论。

---

## 附录 A：与参考项目的对应关系

| 参考来源 | 本蓝图采纳的具体机制 | 位置 |
|----------|---------------------|------|
| karpathy: Think Before Coding | 每个 ⛔ 前 LLM 必须重读 task_plan + spec_lock | §4.1, §7 |
| karpathy: Simplicity First | §12 显式排除清单；不引入 Agent 编排 | §12 |
| karpathy: Surgical Changes | 视觉审查 lock 仅修订采纳项；执行器改批不动它批 | §5.3, §4.1 |
| karpathy: Goal-Driven Execution | §11 可验证成功标准 | §11 |
| planning-with-files: 三文件 | task_plan / findings / progress 全程持有 | §7 |
| planning-with-files: 2-Action Rule | "看过的图立即写 findings"；从不二次 view | §7.2 |
| planning-with-files: 3-Strike 协议 | 失败 3 次后回滚到上一 ⛔，请求用户决策 | §4.1 失败回滚列 |
| planning-with-files: hooks 作为增强 | `.claude-plugin/` 可选；主流程不依赖 | §6.4 |

---

## 附录 B：本蓝图 vs 原架构 一句话差异

> **原架构**是"一条尽可能自动化的流水线，单点（八确认）阻塞"。
> **定制版**是"一组以本地文件为契约的独立阶段，每个阶段都可独立确认/回滚/换 IDE 推进，提示词全部中文"。
