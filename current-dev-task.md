使用结构化配置重构 design_spec / spec_lock 同步机制

## 背景

当前项目在 Strategist 阶段会同时产出 `workspace/design_spec.md` 和 `workspace/spec_lock.md`。

其中：
- `design_spec.md` 是面向人类阅读的完整设计规范，包含设计叙事、受众、风格、配色理由、内容大纲、演讲备注要求等。
- `spec_lock.md` 是面向 Executor 和校验脚本读取的执行锁定，包含颜色、字体、图标、图片、page_rhythm、forbidden 等关键约束。

项目模板已经明确规定：
- 两个文件必须保持同步；
- 如果存在冲突，以 `spec_lock.md` 为准；
- Executor 在生成每一页 SVG 之前，必须重新读取 `spec_lock.md`，以抵抗上下文压缩和注意力漂移。

最近项目已经在图片审查环节引入了基于 Pydantic-AI 的独立 agent，以提升单点任务的精确控制能力。进一步分析后发现，`design_spec` / `spec_lock` 这一组文件也是当前系统中非常适合采用同类改造的部分。

## 当前问题

### 1. design_spec 与 spec_lock 的同步完全依赖 LLM 手工维护

目前没有发现专门的自动同步脚本。
Strategist 阶段是由 LLM 在同一轮流程中分别写出两个文件，再依赖模型自己保证两者一致。

这会带来以下风险：
- `design_spec.md` 中已经调整了颜色、字体、图标、图片，但 `spec_lock.md` 没有同步更新；
- `spec_lock.md` 中的值被后续人工或脚本局部改动后，`design_spec.md` 没有同步修订；
- 长流程中 LLM 容易丢失局部约束，两个文件逐渐漂移；
- 一旦冲突，Executor 按 `spec_lock.md` 执行，而人类往往参考 `design_spec.md`，容易造成理解偏差。

### 2. 当前部分脚本依赖 Markdown + 正则解析，稳定性不足

当前已有脚本（如 `scripts/update_spec.py`、`scripts/svg_quality_checker.py`）会从 `spec_lock.md` 中提取结构化信息。
但 `spec_lock.md` 本质上是 Markdown 文本，解析依赖较脆弱的规则：
- 依赖标题层级、列表格式、冒号位置、空格缩进；
- 对字段缺失、拼写变化、格式变体的容错有限；
- 缺少强类型约束；
- 错误提示不够精确；
- 新增字段时，需要继续扩展解析逻辑。

虽然这种方式在项目早期能快速落地，但随着流程复杂度上升，会逐步成为稳定性瓶颈。

### 3. 当前校验链条只覆盖“SVG 是否偏离 spec_lock”，没有覆盖“design_spec 是否与 spec_lock 一致”

现在已有的 `svg_quality_checker.py` 主要检查：
- SVG 是否使用了 `spec_lock.md` 之外的颜色、字体、字号；
- SVG 是否发生 spec drift。

但目前缺少一层更上游的校验：
- `design_spec.md` 与 `spec_lock.md` 的关键字段是否一致；
- `spec_lock.md` 是否完整覆盖了 `design_spec.md` 中声明给 Executor 的可执行约束。

这意味着问题经常要到 SVG 生成甚至质量检查阶段才暴露，反馈链条过长。

### 4. update_spec.py 目前只支持有限的局部同步

`scripts/update_spec.py` 的能力主要是：
- 修改 `spec_lock.md` 中的 `colors.*`；
- 修改 `typography.font_family`；
- 并将这些改动传播到 `svg_output/*.svg`。

它并不负责：
- 从 `design_spec.md` 自动提取并生成 `spec_lock`；
- 校验两个规范文件之间的一致性；
- 同步更广泛的结构（图片、图标、page_rhythm、forbidden、角色级字体等）。

因此它只是一个局部修补工具，不是根本性的同步方案。

## 改造目标

本次改造希望解决以下问题：
- 用单一结构化文件替代当前的双文件设计，消除同步问题；
- 用更稳定、更适合机器处理的数据格式替代关键执行约束上的 Markdown 正则解析；
- 缩短错误暴露链路，让不一致在 Strategist 阶段或提交规范时就被发现；
- 为后续引入 Pydantic-AI 驱动的更强流程控制打下基础。

## 总体设计方向

核心思想：

**用单一结构化文件替代当前的双文件设计，由模型按强约束生成，再由程序进行类型校验。**

建议采用：
- 用 `workspace/spec_lock.json` 替代当前的 `design_spec.md` 和 `spec_lock.md`；
- JSON 作为唯一配置文件，同时承载设计理由和执行契约；
- 通过 Pydantic 模型统一定义 schema；
- 通过 Pydantic-AI 直接输出结构化对象，确保类型安全和完整性；
- **JSON 必须格式化输出（pretty print），不能使用紧凑格式，确保人类可读性。**

## 推荐方案

### 方案总览

采用单文件架构：

1. **单一配置文件**
   - `workspace/spec_lock.json`
   - 同时包含：项目信息、设计理由、画布规格、配色、字体、图标、图片、内容大纲、技术约束
   - **必须使用格式化输出（`json.dumps(indent=2)` 或 Pydantic 的 `model_dump_json(indent=2)`），禁止紧凑格式**
   - 设计理由通过结构化字段（如 `_rationale`）承载，而非注释

2. **Schema 层**
   - 新增 Python Pydantic 模型文件：`scripts/spec_models.py`
   - 明确定义所有字段的类型和约束

3. **生成层**
   - Strategist 使用 Pydantic-AI 直接输出符合 schema 的结构化对象
   - 程序将对象序列化为格式化的 JSON（`indent=2`）
   - 无需 LLM 手工维护两个文件的一致性

4. **校验层**
   - 新增校验脚本：`scripts/validate_spec.py`
   - 验证 JSON 文件是否符合 schema
   - 验证关键字段的合理性（如颜色格式、字号范围等）
   - 验证 JSON 是否为格式化输出（非紧凑格式）

### 为什么选择 JSON

相较于 YAML：
- 无隐式类型转换陷阱（`yes` 不会变成 `True`，`1.0` 不会变成浮点数）
- 无缩进敏感问题，解析更可靠
- Pydantic 原生支持 JSON（`model_dump_json()`），无需额外序列化步骤
- 类型安全是显式的，所有值都有明确的引号/类型标记
- 所有编程语言都有可靠的 JSON 解析器

相较于 Markdown + 正则：
- 解析更稳定，无需脆弱的正则匹配
- 可以直接交给标准 `json.loads()` 处理
- 适合与 Pydantic 配合，做字段级类型校验和错误提示
- 对后续扩展字段更自然

JSON 不支持注释，但可以通过结构化字段（如 `_rationale`、`_notes`）承载设计理由，保持单一数据源。

## 具体改造方案

### 第一阶段：建立结构化 schema

新增 Pydantic 模型，用于描述执行锁文件，例如：
- `CanvasConfig`
- `ColorConfig`
- `TypographyConfig`
- `IconsConfig`
- `ImagesConfig`
- `SpecLock`

要求：
- 对 HEX 颜色、字号、page 编号、page_rhythm 枚举值等做基本类型约束；
- 明确必填字段与可选字段；
- 为后续 LLM 结构化输出提供稳定接口。

### 第二阶段：创建 spec_lock.json 样例

创建一个完整的 `workspace/spec_lock.json` 样例，包含：
- 项目信息（名称、描述、受众、风格）
- 设计理由（使用 `_rationale` 等结构化字段）
- 画布规格
- 配色方案
- 字体系统
- 图标库
- 图片列表
- 内容大纲
- 技术约束

目标：
- 展示 JSON 如何同时承载设计理由和执行配置（通过结构化字段）
- 确保使用格式化输出（`indent=2`），人类可直接阅读
- 为后续 Pydantic-AI 输出提供参考模板

### 第三阶段：接入现有脚本

修改以下脚本，使其读取 `spec_lock.json`：
- `scripts/svg_quality_checker.py`
- `scripts/update_spec.py`

兼容策略：
- 优先读取 `spec_lock.json`
- 若不存在，回退到 `spec_lock.md`（保持向后兼容）
- 待迁移稳定后，移除 Markdown 解析代码

### 第四阶段：引入 Pydantic-AI 进行结构化生成

在现有图片审核已使用 Pydantic-AI 的基础上，将其应用到 Strategist 输出阶段：

**当前推荐方案**：
- 保持"同一个 LLM"设计原则
- Strategist 在 AI IDE 中直接输出 `spec_lock.json`
- 使用 `validate_spec.py` 进行程序化校验
- 参考 `references/strategist-json-output-guide.md` 修改 Strategist 提示

**备用方案**（保留用于未来 agent 应用开发）：
- `pydantic_ai_spec_generator.py` 展示如何使用 Pydantic-AI 生成结构化配置
- 适用于脱离 AI IDE 环境的场景
- 局限性：无法获取 AI IDE 的完整上下文

这会显著提升：
- 规范文件的完整性（不会遗漏字段）
- 类型安全（颜色格式、字号范围等自动校验）
- Agent 对复杂设计状态的掌控力

## 建议的实施顺序

### 优先级 1：建立 schema 和样例

先完成：
- `scripts/spec_models.py`：Pydantic schema 定义
- `workspace/spec_lock.json`：完整样例（基于当前项目转换）

这是投入最小、收益最直接的一步。

### 优先级 2：接入现有脚本

修改以下脚本，使其优先读取 `spec_lock.json`：
- `scripts/svg_quality_checker.py`
- `scripts/update_spec.py`

保持向后兼容：若不存在 JSON，回退到 Markdown。

### 优先级 3：Pydantic-AI 结构化生成

在 schema 和读取链稳定后，将 Strategist 改造为使用 Pydantic-AI 输出结构化对象。

## 预期收益

完成改造后，预期会带来以下收益：
- 单一配置文件，无需维护两个文件的一致性；
- 关键配置从 Markdown 正则解析转向标准结构化解析，稳定性明显提升；
- 错误从 SVG 后期质量检查前移到规范生成阶段（Pydantic 校验）；
- 后续扩展字段、加校验、接入更多 agent 时，工程成本更低；
- 整个项目在"人类可理解"和"机器可验证"两条链路上都更清晰。

## 非目标

本次改造暂不追求：
- 一次性重写所有 Strategist / Executor 流程；
- 一次性删除 `spec_lock.md`（保持向后兼容）
- 在首个版本中让所有历史项目自动迁移。

更合理的路径是：
- 先新增 JSON + schema + 校验；
- 再逐步把现有脚本切换过来；
- 最后再收敛旧格式。

## 交付物建议

建议本轮改造至少包含以下交付物：
- 新的任务说明文档（即本文件）
- `scripts/spec_models.py`：Pydantic schema
- `workspace/spec_lock.json`：结构化配置文件样例（基于当前项目转换，格式化输出）
- `scripts/validate_spec.py`：JSON 文件校验脚本
- 对 `svg_quality_checker.py` 的读取逻辑升级（优先 JSON，兼容 Markdown）
- 对 `update_spec.py` 的读取逻辑升级（优先 JSON，兼容 Markdown）

## 一句话总结

当前 `design_spec.md` 与 `spec_lock.md` 的同步机制本质上仍然是"让 LLM 手工写两份文档并希望它们一致"，这已经成为项目继续提升可控性的重要瓶颈。下一步应将两者合并为单一 `spec_lock.json` 文件（格式化输出），并以 Pydantic + Pydantic-AI 为核心，建立"结构化生成、程序校验"的新机制。

---

## 任务执行状态

### 第一阶段：建立结构化 schema ✅
- 已创建 `scripts/spec_models.py`
- 定义了所有 Pydantic 模型：CanvasConfig, ColorConfig, TypographyConfig, IconsConfig, ImagesConfig, SpecLock 等
- 对 HEX 颜色、字号、page 编号、page_rhythm 枚举值等做了类型约束

### 第二阶段：创建 spec_lock.json 样例 ✅
- 已创建 `workspace/spec_lock.json`
- 包含完整的项目信息、设计理由、画布规格、配色、字体、图标、图片、内容大纲、技术约束
- 使用格式化输出（indent=2），人类可读

### 第三阶段：接入现有脚本 ✅
- 已修改 `scripts/svg_quality_checker.py`：只读取 spec_lock.json，移除 MD 回退
- 已修改 `scripts/update_spec.py`：只读取 spec_lock.json，移除 MD 回退
- 已修改 `scripts/pathutil.py`：SPEC_LOCK_FILE 改为 spec_lock.json，删除 DESIGN_SPEC_FILE
- 已修改 `scripts/llm_process_image.py`：从 spec_lock.json 读取项目上下文
- 已修改 `scripts/project_utils.py`：项目校验改为检查 spec_lock.json
- 已修改 `scripts/error_helper.py`：错误提示改为 spec_lock.json

### 第四阶段：引入 Pydantic-AI 进行结构化生成 ✅
- 已创建 `scripts/pydantic_ai_spec_generator.py`：Pydantic-AI 生成示例（备用方案，用于未来 agent 应用开发）
- 已创建 `scripts/validate_spec.py`：验证 spec_lock.json 文件是否符合 schema
- 已修改 `scripts/project_manager.py`：项目初始化时自动生成 spec_lock.json 模板
- 已创建 `references/strategist-json-output-guide.md`：Strategist 输出 JSON 指南

### 第五阶段：完全迁移到 JSON ✅
- 已重写 `SKILL.md`：所有 spec_lock.md 引用改为 spec_lock.json，删除 design_spec.md 引用
- 已重写 `references/executor.md`：所有引用改为 spec_lock.json
- 已重写 `references/executor-base.md`：所有引用改为 spec_lock.json，删除 design_spec.md 回退
- 已重写 `references/strategist.md`：输出改为 spec_lock.json，删除 design_spec.md 流程
- 已更新 `references/executor-consultant.md`、`executor-consultant-top.md`、`executor-general.md`
- 已更新 `optional-workflows/verify-charts.md`：改为从 spec_lock.json 读取
- 已更新 `references/web-search.md`：改为从 spec_lock.json 读取
- 已更新 `optional-workflows/topic-research.md`：改为从 spec_lock.json 读取
- 已更新 `templates/layouts/README.md`：改为 spec_lock.json
- 已删除 `templates/design_spec_reference.md`：不再需要
- 已删除 `templates/spec_lock_reference.md`：不再需要

### 推荐工作流程 ✅
1. 运行 `python scripts/project_manager.py` 初始化项目，自动生成 spec_lock.json 模板
2. Strategist 读取模板，填写 `<...>` 占位符
3. 运行 `python scripts/validate_spec.py workspace/spec_lock.json` 校验
4. 如果校验失败，根据错误信息修正，直到通过

### 额外交付物 ✅
- `scripts/spec_models.py`：Pydantic schema 定义
- `workspace/spec_lock.json`：结构化配置文件样例
- `scripts/validate_spec.py`：JSON 文件校验脚本
- `scripts/pydantic_ai_spec_generator.py`：Pydantic-AI 生成示例（备用方案）
- `scripts/svg_quality_checker.py`：只读取 spec_lock.json
- `scripts/update_spec.py`：只读取 spec_lock.json
- `scripts/project_manager.py`：项目初始化时自动生成 spec_lock.json 模板
- `references/strategist-json-output-guide.md`：Strategist 输出 JSON 指南

---

## 验证结果

```
✓ 配置验证成功: workspace\spec_lock.json
  项目名称: 儿童科普自然灾害
  画布尺寸: 1280x720
  主色: #4CAF50
  正文字号: 22
  总页数: 13

验证通过!
```