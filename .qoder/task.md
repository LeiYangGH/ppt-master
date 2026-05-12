# 修改 web_search 让 LLM 更方便使用

## 背景

之前 LLM 运行 PPT 制作过程发现：
- 下载的很多图片与搜索关键词 / 返回内容 / 文件名完全不一致，且与已采纳图片混在 `workspace/images` 同目录，易被 SVG 误引用；
- 缩略图墙虽然有助于 LLM 查看图片，但需要主动调用；迭代搜索时又会对同一批图片重复生成缩略图，浪费 token 与时间。

## 任务目标

把 `web_search.py` 从"下载即完事"升级为**下载—分析—拼图—采纳**的状态驱动管道，让 LLM 每次搜索后只需看一张增量缩略图墙就能完成筛选，并通过显式"采纳"动作把图片晋升到正式资产区。

## 核心决策

### 1. 目录分层：暂存区与正式区分离

- 所有 web_search 下载的素材（文本 + 图片）默认进 `workspace/downloads/`，叠加保存（LLM 会多次搜索）。
  - 图片：`workspace/downloads/*.{jpg,png,webp,...}`
  - 文本：每次搜索的完整 JSON 快照落在 `workspace/downloads/searches/<ts>_<qhash>.json`，供审计与二次检索，不改变主流程（LLM 仍从 stdout 直接读 JSON）。
- `workspace/images/` 语义收窄为**纯正式资产**：只存已经审阅、已重命名为描述性文件名的图片。
- 文件名统一为 `img_<sha1_8>.ext`（8 位 hex 与 git 短哈希一致，150 文件规模下冲突概率约百万分之三，同 URL 天然去重）。

### 2. 下载配额：数量 + 体积双阈值

- `workspace/downloads/` 文件数上限 **150**，总体积上限 **300 MB**（均可通过 `--downloads-max-files` / `--downloads-max-bytes` 覆盖）。
- 任一阈值触顶：拒绝继续下载，返回**可执行**的处置提示，例如：
  > `downloads/ 已达上限（148/150, 287MB/300MB）。请先 python scripts/web_search.py --adopt <file> <images/描述名.ext> 采纳，或 --purge-downloads 清理后再搜索。`

### 3. 自动管道：下载后串联分析与拼图（增量）

- 每次 `web_search.py` 搜索结束、新图落盘后，在同进程内直接调用 `analyze_images` 与 `image_montage`（import 方式，不再 subprocess）。
- **workspace 级状态文件** `workspace/downloads/_state.jsonl`，每条记录：  
  `{url, filename, sha1, size, w, h, aspect, category, query, ts, analyzed_at, montage_batch, adopted_as}`
  - `analyze_images` 只处理 `analyzed_at == null` 的行；
  - `image_montage` 只对 `montage_batch == null` 的新图生成**增量拼图** `montage_batch_NN.jpg`，旧图不再入墙；
  - 单张新图不足 5 张时跳过拼图（避免每搜一次就出一张稀疏墙），LLM 可用 `--force-montage` 强制生成；
  - 状态写入走 "tmp + os.replace" 原子覆盖；**不**引入文件锁（LLM 串行调用，锁带来的僵死风险大于收益）。

### 4. 采纳动作：显式的晋升命令

- 新增 `python scripts/web_search.py --adopt <downloads/xxx.jpg> <images/描述名.jpg>`，完成：
  1. 把文件从 downloads 移到 images；
  2. 在 `_state.jsonl` 对应条目写入 `adopted_as`，后续相同 URL 的搜索结果自动跳过下载；
  3. 校验目标文件名：禁止以 `img_`、`image_\d+`、`tmp_`、`download` 等哈希/通用前缀命名。
- `--purge-downloads` 清空暂存区但保留 `_state.jsonl` 中 `adopted_as` 记录，以维持跨会话去重。

### 5. 管道级硬门禁（防最终交付污染）

- 在 SVG finalize / design_spec 校验阶段扫描 `workspace/images/`，遇到 `img_[0-9a-f]{8,}`、`image_\d+`、`tmp_*`、`download*` 等形态的文件名 → 直接 block 并报错。
- 这是比 prompt 说教更可靠的兜底，把"哈希名混入最终交付"这一历史故障模式堵死。

### 6. 文档拆分与同步更新

- **新增 `references/web-search.md`**：集中收纳工具级说明——CLI 参数全集（search / `--adopt` / `--purge-downloads` / `--force-montage` / `--domain-stats` 等）、`workspace/downloads/` 布局与 `_state.jsonl` 字段、150/300MB 阈值语义、返回 JSON schema（含新增 `downloads_dir` / `new_files` / `montage_batch`）、典型调用片段。
- **不收纳**：调研策略、中文搜索的阻断性约束——这些是流程约束而非工具约束，留在 `topic-research.md`。
- `SKILL.md` 脚本表中 `web_search.py` 行压缩为一句话 + "详见 `references/web-search.md`"；图片章节相关表述同步改为 `workspace/downloads/` → `--adopt` 晋升到 `workspace/images/`。
- `optional-workflows/topic-research.md` 步骤 3.1–3.3 中的命令行用法、阈值、状态文件说明全部删除，改为链接 `references/web-search.md`；顶部阻断性约束（中文搜索、审阅后重命名）原地保留。
- 新 LLM 工作流一句话：  
  > 搜索 → 读返回 JSON 与增量缩略图墙 → 对合适图片用 `--adopt` 一次性完成移动+重命名；不合适直接不管（由 `--purge-downloads` 或自然淘汰清理）。

## 非目标（明确不做）

- 不加文件锁、不做跨进程并发控制。
- 不对 `workspace/downloads/` 按 query 分子目录（保持扁平利于去重）。
- 不改变 `web_search.py` 的返回 JSON 对外 schema（仅新增 `downloads_dir` / `new_files` / `montage_batch` 字段）。
