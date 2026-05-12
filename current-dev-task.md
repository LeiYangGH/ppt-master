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
- 用 `workspace/spec_lock.yaml` 替代当前的 `design_spec.md` 和 `spec_lock.md`；
- YAML 同时承载设计叙事和执行契约；
- 通过 Pydantic 模型统一定义 schema；
- 通过 Pydantic-AI 直接输出结构化对象，确保类型安全和完整性。

## 推荐方案

### 方案总览

采用单文件架构：

1. **单一配置文件**
   - `workspace/spec_lock.yaml`
   - 同时包含：项目信息、设计理由、画布规格、配色、字体、图标、图片、内容大纲、技术约束
   - YAML 的多行字符串支持叙事性内容，结构化字段支持机器读取

2. **Schema 层**
   - 新增 Python Pydantic 模型文件：`scripts/spec_models.py`
   - 明确定义所有字段的类型和约束

3. **生成层**
   - Strategist 使用 Pydantic-AI 直接输出符合 schema 的结构化对象
   - 程序将对象序列化为 YAML
   - 无需 LLM 手工维护两个文件的一致性

4. **校验层**
   - 新增校验脚本：`scripts/validate_spec.py`
   - 验证 YAML 文件是否符合 schema
   - 验证关键字段的合理性（如颜色格式、字号范围等）

### 为什么优先选 YAML

相较于 JSON：
- YAML 对人类更友好，阅读和手工修改成本更低；
- 支持注释，适合承载少量说明；
- 层级结构清晰，适合 design token / layout token / asset mapping；
- 对版本管理 diff 也较友好。

相较于 Markdown + 正则：
- 解析更稳定；
- 可以直接交给成熟 YAML 解析器处理；
- 更适合与 Pydantic 配合，做字段级类型校验和错误提示；
- 对后续扩展字段更自然。

因此，推荐 `spec_lock` 从 Markdown 迁移到 YAML。

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

### 第二阶段：创建 spec_lock.yaml 样例

创建一个完整的 `workspace/spec_lock.yaml` 样例，包含：
- 项目信息（名称、描述、受众、风格）
- 设计理由（为什么选择这个风格、配色）
- 画布规格
- 配色方案
- 字体系统
- 图标库
- 图片列表
- 内容大纲
- 技术约束

目标：
- 展示 YAML 如何同时承载叙事和配置
- 为后续 Pydantic-AI 输出提供参考模板

### 第三阶段：接入现有脚本

修改以下脚本，使其读取 `spec_lock.yaml`：
- `scripts/svg_quality_checker.py`
- `scripts/update_spec.py`

兼容策略：
- 优先读取 `spec_lock.yaml`
- 若不存在，回退到 `spec_lock.md`（保持向后兼容）
- 待迁移稳定后，移除 Markdown 解析代码

### 第四阶段：引入 Pydantic-AI 进行结构化生成

在现有图片审核已使用 Pydantic-AI 的基础上，将其应用到 Strategist 输出阶段：

- 让 Strategist 使用 Pydantic-AI 直接输出符合 schema 的结构化对象
- 程序将对象序列化为 `spec_lock.yaml`
- 无需 LLM 手工维护两个文件的一致性

这会显著提升：
- 规范文件的完整性（不会遗漏字段）
- 类型安全（颜色格式、字号范围等自动校验）
- Agent 对复杂设计状态的掌控力

## 建议的实施顺序

### 优先级 1：建立 schema 和样例

先完成：
- `scripts/spec_models.py`：Pydantic schema 定义
- `workspace/spec_lock.yaml`：完整样例（基于当前项目转换）

这是投入最小、收益最直接的一步。

### 优先级 2：接入现有脚本

修改以下脚本，使其优先读取 `spec_lock.yaml`：
- `scripts/svg_quality_checker.py`
- `scripts/update_spec.py`

保持向后兼容：若不存在 YAML，回退到 Markdown。

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
- 先新增 YAML + schema + 校验；
- 再逐步把现有脚本切换过来；
- 最后再收敛旧格式。

## 交付物建议

建议本轮改造至少包含以下交付物：
- 新的任务说明文档（即本文件）
- `scripts/spec_models.py`：Pydantic schema
- `workspace/spec_lock.yaml`：结构化配置文件样例（基于当前项目转换）
- `scripts/validate_spec.py`：YAML 文件校验脚本
- 对 `svg_quality_checker.py` 的读取逻辑升级（优先 YAML，兼容 Markdown）
- 对 `update_spec.py` 的读取逻辑升级（优先 YAML，兼容 Markdown）

## 一句话总结

当前 `design_spec.md` 与 `spec_lock.md` 的同步机制本质上仍然是"让 LLM 手工写两份文档并希望它们一致"，这已经成为项目继续提升可控性的重要瓶颈。下一步应将两者合并为单一 `spec_lock.yaml` 文件，并以 Pydantic + Pydantic-AI 为核心，建立"结构化生成、程序校验"的新机制。