# web_search.py — 工具参考

> 本文件是 `scripts/web_search.py` 的工具级说明：CLI 参数、目录布局、状态文件、返回 JSON schema、典型调用片段。
>
> 使用流程约束（中文搜索、审阅后重命名、图片混用防范等）见 [`optional-workflows/topic-research.md`](../optional-workflows/topic-research.md)。

---

## 一句话心智模型

```
search  →  自动下载到 workspace/downloads/  →  自动生成增量缩略图墙
                                              ↓
                                   LLM 读 montage_batch_NN.jpg
                                              ↓
                            合适的图片 → --adopt 晋升到 workspace/images/
                            不合适的图片 → 不管（自然淘汰或 --purge-downloads）
```

- `workspace/downloads/` = 暂存区：哈希名、状态追踪、配额限制
- `workspace/images/` = 正式区：只放已采纳、已重命名为描述性名称的图片

---

## 目录布局

```
workspace/
├── downloads/
│   ├── img_<sha1_8>.jpg              ← 自动下载的原始图片（文件名为 8 位 hex 哈希）
│   ├── img_<sha1_8>.png
│   ├── _state.jsonl                  ← 每张图一条记录，下载/分析/拼图/采纳状态
│   ├── _montage/                     ← 增量缩略图墙
│   │   ├── montage_batch_01_*.jpg
│   │   └── montage_batch_02_*.jpg
│   └── searches/                     ← 每次搜索的 JSON 快照（审计/二次检索）
│       └── <UTC ts>_<qhash>.json
└── images/
    └── joe_hisaishi_portrait_01.jpg  ← 只允许描述性文件名
```

**硬规则**：`workspace/images/` 中如果出现 `img_[0-9a-f]{8,}`、`image_\d+`、`tmp_*`、`download*`、`untitled*` 等形态的文件名，`scripts/finalize_svg.py` 会在 finalize 阶段直接 block。

---

## CLI 参数全集

### 搜索

```bash
python scripts/web_search.py "<中文 query>" [options]
```

| 参数 | 默认 | 说明 |
|------|------|------|
| `query` | 必填 | 搜索关键字，**必须中文**（专有名词可并列英文） |
| `-n / --max-results` | 5 | 每次搜索向 API 请求的最大结果数 |
| `--provider {tavily,baidu}` | 自动轮询 | 锁定单一后端 |
| `--json` | 否 | 输出原始 JSON（默认人类可读摘要） |
| `--no-auto-download` | 否 | 只搜索不下载图片 |
| `--no-snapshot` | 否 | 不把搜索 JSON 落到 `downloads/searches/` |
| `--auto-download-timeout` | 5 | 单张图片 HTTP 超时（秒） |
| `--auto-download-limit` | 30 | 单次搜索最多下载多少张 |
| `--downloads-max-files` | 150 | `downloads/` 总文件数上限，触顶拒绝继续下载 |
| `--downloads-max-bytes` | 300MB | `downloads/` 总体积上限 |
| `--force-montage` | 否 | 即使新图不足 5 张，也立刻生成一张增量缩略图墙 |
| `--project-dir PATH` | 自动 | 工作区路径，覆盖 `PPT_PROJECT_DIR` |

### 采纳（晋升到正式资产）

```bash
python scripts/web_search.py --adopt <SRC> <DEST>
```

- `SRC`：`downloads/` 下的文件名（相对）或绝对路径
- `DEST`：`images/` 下的**描述性文件名**（相对）或绝对路径
- 效果：
  1. 把文件从 `downloads/` 移到 `images/`
  2. 在 `_state.jsonl` 对应条目写入 `adopted_as`，后续搜索到同 URL 自动跳过下载
  3. 校验目标名；命中 `img_`/`image_\d+`/`tmp_`/`download`/`untitled` 前缀直接报错

示例：
```bash
python scripts/web_search.py --adopt img_5f3a8c1b.jpg joe_hisaishi_portrait_01.jpg
python scripts/web_search.py --adopt img_5f3a8c1b.jpg images/joe_hisaishi_portrait_01.jpg
```

### 清理暂存区

```bash
python scripts/web_search.py --purge-downloads
```

- 删除 `downloads/` 下所有图片与 `_montage/` 目录
- **保留** `_state.jsonl`（维持跨会话 URL 去重）与 `searches/` 快照
- 将非 adopted 记录的 `filename` / `analyzed_at` / `montage_batch` / `size` 重置为 null，以便下次重新下载

### 域名统计 / 黑名单

```bash
python scripts/web_search.py --domain-stats                         # 打印域名可靠度排名
python scripts/web_search.py --record-download <domain> success|fail # 记录下载结果（一般由自动下载内部调用）
```

### 其他

```bash
python scripts/web_search.py --list-images       # 打印 collected_images.jsonl
python scripts/web_search.py --clear-images      # 清空 collected_images.jsonl
python scripts/web_search.py --download-images OUTPUT_DIR  # 从 collected_images.jsonl 批量下载
```

---

## 配额语义

- `downloads/` 下**图片文件数** ≥ `--downloads-max-files`（默认 150），或**总体积** ≥ `--downloads-max-bytes`（默认 300MB），任一触顶即拒绝继续下载。
- 返回 JSON 带 `downloads_quota_error` 字段，提示如：
  > `downloads/ 已达上限（148/150 文件, 287MB/300MB）。请先用 --adopt 采纳，或 --purge-downloads 清理后再搜索。`
- 搜索本身仍正常返回 `results`，只是图片下载被跳过。

---

## 文件名规则

- **所有** `downloads/` 下的自动下载图片统一为 `img_<sha1_8>.ext`
  - `sha1_8` = URL 的 SHA-1 前 8 位 hex（与 git 短哈希对齐，150 文件规模下冲突概率约百万分之三）
  - 同 URL → 同文件名 → 天然去重
- 服务器返回的原始 basename 一律忽略（它们经常伪装成有意义的名字但其实毫无价值）
- 只从 URL 后缀推断 `.jpg/.png/.webp/.gif/.bmp/.svg` 之一；识别失败回退 `.jpg`

---

## `_state.jsonl` schema

每行一条 JSON 记录，字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `url` | str | 源图片 URL，主键 |
| `filename` | str? | `downloads/` 下的文件名；`--purge-downloads` 后变 null |
| `sha1` | str | URL 的 SHA-1 前 8 位 |
| `size` | int? | 字节数 |
| `w` / `h` | int? | 图片像素尺寸（`analyze_images` 填） |
| `aspect` | float? | w/h（`analyze_images` 填，3 位小数） |
| `category` | str? | `analyze_images` 的 layout_hint |
| `query` | str | 首次下载时的搜索 query |
| `ts` | str | 首次下载 UTC 时间戳 |
| `analyzed_at` | str? | 分析完成时间戳；null 表示尚未分析 |
| `montage_batch` | int? | 所属增量拼图批次号；null 表示尚未拼图 |
| `adopted_as` | str? | 晋升后的 images/ 绝对路径；非 null 表示已采纳 |

**写入协议**：每次更新走 "tmp + os.replace" 原子覆盖；**不**使用文件锁。

---

## 自动管道

每次 `search` 结束、新图落盘后，同进程内顺序执行：

1. **upsert state**：对每个 `status == "ok"|"skip"` 的 outcome，按 URL 找/建 `_state.jsonl` 条目
2. **analyze**：调用 `analyze_images.analyze_images(downloads_dir)`，只更新 `analyzed_at == null` 的行（填 `w/h/aspect/category/analyzed_at`）
3. **incremental montage**：
   - 筛出 `montage_batch == null` 且文件仍在盘上的新图
   - **>= 5 张** 或显式 `--force-montage` 时，用**硬链接**（不支持则 fallback copy）把新图暂存到 `_montage/batch_NN_src/`
   - 调用 `image_montage.build_montages(stage_dir, output_dir=_montage)`
   - 产出的 montage 重命名为 `montage_batch_NN_<原名>.jpg`
   - 给所有参与此批次的条目写入 `montage_batch = NN`

不足 5 张时跳过拼图，避免稀疏墙浪费 token。

---

## 返回 JSON schema（新增字段）

```jsonc
{
  "query": "...",
  "answer": "...",
  "results": [...],
  "images": [...],
  "source": "tavily|baidu|none",
  "timestamp": "2026-05-12T...Z",

  // —— 以下为本工具新增字段 ——
  "downloads_dir": "/abs/path/to/workspace/downloads",
  "downloaded_images": [
    {"url": "...", "file": "...", "status": "ok|skip|fail", "reason": "...", "domain": "...", "bytes": 12345}
  ],
  "new_files": ["img_aabb1122.jpg", ...],   // 本次新增的图片文件名
  "analyzed": 87,                            // 本次调用后 _state.jsonl 中 analyzed_at 非 null 的总数
  "montage_batch": {                         // 本次生成了新 batch 时存在；否则 null
    "batch_id": 3,
    "count": 7,
    "montages": ["montage_batch_03_montage_01_of_01.jpg"],
    "dir": "/abs/path/to/workspace/downloads/_montage"
  },
  "downloads_quota_error": "downloads/ 已达上限...",  // 仅触顶时存在
  "snapshot": "/abs/path/to/workspace/downloads/searches/20260512T...Z_<qhash>.json"
}
```

---

## 典型调用片段

### LLM 标准工作流

```powershell
# 1. 配置工作区（会话开始一次即可）
$env:PPT_PROJECT_DIR = "workspace"

# 2. 搜索，自动下载 + 自动拼图
python scripts/web_search.py "久石让 Joe Hisaishi 肖像" -n 8 --json

# 3. 读返回 JSON 的 montage_batch.montages 字段指向的图片
#    对缩略图墙中合适的图片逐张采纳
python scripts/web_search.py --adopt img_5f3a8c1b.jpg joe_hisaishi_portrait_01.jpg
python scripts/web_search.py --adopt img_a1b2c3d4.png joe_hisaishi_conducting.png

# 4. 不合适的图片无需手动删除——交给 --purge-downloads 或自然淘汰
#    迭代搜索 → 新增图片自动追加到 batch_02/03/...
python scripts/web_search.py "久石让 演出现场" -n 8 --json

# 5.（可选）会话结束前清理暂存区
python scripts/web_search.py --purge-downloads
```

### 配额触顶后的恢复

```powershell
python scripts/web_search.py "..."     # 返回 downloads_quota_error
python scripts/web_search.py --purge-downloads
python scripts/web_search.py "..."     # 恢复可下载
```

### 强制拼图（新图不足 5 张时）

```powershell
python scripts/web_search.py "..." --force-montage
```

---

## 非目标（明确不做）

- 不加文件锁，不做跨进程并发控制（LLM 串行调用，锁带来的僵死风险大于收益）
- 不按 query 给 `downloads/` 分子目录（保持扁平有利于跨 query 去重）
- 不改变返回 JSON 的对外 schema 兼容性（仅新增 `downloads_dir` / `new_files` / `montage_batch` / `analyzed` / `snapshot` / `downloads_quota_error`）
- 不把 `_montage/` 列为最终交付的一部分，finalize 时可清理

---

## 相关脚本

| 脚本 | 在本工具中的角色 |
|------|-----------------|
| `scripts/analyze_images.py` | 被自动管道 import 调用，填 `w/h/aspect/category` |
| `scripts/image_montage.py` | 被自动管道 import 调用，产出增量缩略图墙 |
| `scripts/finalize_svg.py` | finalize 阶段扫描 `workspace/images/`，block 哈希/占位文件名 |
