---
description: 当用户仅提供简要描述或需求而无详细源材料时，从零开始研究主题。生成结构化Markdown文档和相关图片文件夹。
---

# 主题研究工作流

> **独立预处理工作流** — 产出可输入主PPT生成流水线的源材料，也可独立使用。

## 触发条件

用户**仅提供主题名称、简要描述或一组需求** — 无PDF、DOCX、URL或其他源文件。

示例：
- "做一个关于久石让的PPT"
- "创建一个关于可再生能源趋势的演示文稿"
- "我想介绍我们的新产品（附带简要描述）"

## 交付物

所有输出必须放在 `projects/` 目录下：

| 交付物 | 路径 | 示例 |
|--------|------|------|
| 结构化Markdown文档 | `projects/<topic_name>.md` | `projects/joe_hisaishi.md` |
| 图片文件夹 | `projects/<topic_name>/`（与文档同名，不含扩展名） | `projects/joe_hisaishi/` |

> **命名一致性规则**：Markdown文件名（不含 `.md`）与图片文件夹名必须完全相同。
>
> **输出目录规则**：文档和图片文件夹必须在 `projects/` 内创建，不得放在仓库根目录或其他位置。

## 流程概览

```
确认主题 → 研究内容 → 收集图片 → 输出
```

## ⛔ 全局硬性约束（适用于所有搜索与图片步骤）

| # | 约束 | 说明 |
|---|------|------|
| 1 | **搜索关键字必须用中文** | 所有 `web_search.py` 调用中的 query、以及 IDE 内置搜索工具的 query，**一律使用中文**（包含人名 / 作品名等固有英文专有名词的情况除外，例如 `久石让 Joe Hisaishi`）。百度后端对中文 query 命中率显著优于英文，Tavily 中英文均可。一律中文能保证在两个后端轮询时结果稳定。 |
| 2 | **自动下载的图片必须逐一查看、标注用途、同时重命名** | 搜索所得的原始文件名多为难以辨认的哈希字符串（如 `5f3a8c1b.jpg`），**禁止直接以此类名称在设计规范或 SVG 中引用**；你必须先运行 `analyze_images.py` 逐张视觉审阅内容，然后：<br>  • **适合使用** → 立即重命名为与图片内容一致的有意义英文名（如 `joe_hisaishi_portrait_2019.jpg`），避免后续因名称模糊出现**图片混用**；<br>  • **不合适** → 直接删除文件；<br>  • **执行完上述筛选后仍没有合适图片** → 换关键字继续搜索，直到满足设计需求为止。 |

> 以上两条为**阻断性**约束：未完成图片审阅与重命名前，不得进入后续设计 / SVG 生成阶段。

---

## 步骤 1：主题确认

⛔ **阻断性步骤**：开始研究前，需与用户确认以下内容。如用户初始消息已清晰涵盖这些要点，则跳过确认直接进行。

| 项目 | 说明 | 示例 |
|------|------|------|
| **主题** | 核心主题 | 久石让 |
| **范围/重点** | 涵盖哪些方面 | 传记、主要作品、与宫崎骏的合作、获奖 |
| **深度** | 概览还是深入 | 通用知识级别 |
| **语言** | 输出语言 | 中文 |

**如用户请求已足够清晰**（如"做一个关于久石让的PPT"），推断合理默认值直接进行 — 不要过度询问。

---

## 步骤 2：内容研究

### 2.1 信息收集

**主工具** — `web_search.py`（自动轮询 Tavily → 百度、遵守域名黑名单；每次调用实时请求 API，**无缓存**，重复搜索会真正拿到新结果）：

```bash
# 全局概览搜索
python3 ${SKILL_DIR}/scripts/web_search.py "<主题> 概述" -n 8 --json

# 定向补充搜索
python3 ${SKILL_DIR}/scripts/web_search.py "<子主题> 数据 统计" -n 5 --json
```

> 该脚本**不再缓存结果**，每次运行都会实时请求 API——好处是你再次发起相同 query 时能拿到新结果（避免被错误的旧结果困住），代价是每次调用都消耗 API 额度。Tavily（每月 1000 次）和百度（每月 1500 次）都属于免费额度；自动轮询可最大化可用配额。

**深度抓取** — 从搜索结果中识别出高信号 URL 后，使用 `web_to_md.py` 或 IDE 的 `WebFetch` 抓取完整页面内容：

```bash
python3 ${SKILL_DIR}/scripts/source_to_md/web_to_md.py <URL>
```

**IDE 网页工具** — 如果 IDE 自带网页搜索能力（如 Claude Code 的 `WebSearch`、Cursor 内置搜索等），可作为补充使用，但 `web_search.py` 仍为首选（因其跟踪域名可靠性并能自动下载图片到项目 `images/` 目录）。

| 来源类型 | 优先级 | 备注 |
|----------|--------|------|
| Wikipedia/百科 | 高 | 权威概览、时间线、关键事实 |
| 官方网站 | 高 | 第一方信息 |
| 新闻/媒体文章 | 中 | 近期事件、获奖、公众反响 |
| 专业数据库 | 低 | 行业相关数据（如适用） |

**研究策略**：
1. 先运行一次宽范围的 `web_search.py` 了解主题全貌
2. 抓取 2–3 个权威页面（Wikipedia、官网）获取详细内容
3. 按需对特定子主题再次运行 `web_search.py` 进行定向补充

### 2.2 内容组织

将收集的信息整理为结构化Markdown文档，骨架如下：

```markdown
# <主题名称>

> 主题的一句话简要描述。

## 概述
[2-3段摘要]

## 背景/历史
[时间线、起源、关键里程碑]

## 核心方面
### 方面1：[...]
### 方面2：[...]
### 方面3：[...]

## 成就/影响
[获奖、认可、影响力]

## 关键数据
| 项目 | 数值 |
|------|------|
| ... | ... |

## 来源
- [来源1标题](URL)
- [来源2标题](URL)
```

> 上述骨架为**参考模板** — 根据主题调整章节结构。人物传记与技术概览或公司简介的结构不同。

**内容准则**：
- 包含具体事实、日期和名称 — 避免模糊概括
- 保留找到的关键引述
- 注明数据来源以保证可验证性
- 追求PPT适用的内容密度：足够填充10-15页幻灯片，但非穷尽式研究论文

### 2.3 保存文档

将Markdown文档保存到 `projects/` 目录：

```
projects/<topic_name>.md
```

---

## 步骤 3：图片收集

### 3.1 图片来源策略

**主工具** — `web_search.py`（搜索后**自动并发下载**图片到当前项目 `images/` 目录，5 秒/张超时，你无需再单独 `curl`）：

```bash
# 先告知脚本当前项目目录（一次即可，后续所有搜索都会命中）
# - 方式 A：环境变量（推荐）
$env:PPT_PROJECT_DIR = "projects/<topic_name>"   # PowerShell
# export PPT_PROJECT_DIR=projects/<topic_name>   # bash
# - 方式 B：每次显式传参 --project-dir projects/<topic_name>
# - 方式 C：不设置时，脚本会自动选择 projects/ 下最近修改的子目录

# 搜索：返回 JSON 里每条结果含 images 列表，同时后台并发下载图片
python3 ${SKILL_DIR}/scripts/web_search.py "<主题> 相片" -n 8 --json

# 返回的 JSON 顶层会多出两个字段：
#   "download_dir":       "<abs path to images/>"
#   "downloaded_images":  [{url, file, status: ok|skip|fail, reason, bytes}, ...]

# 如需禁用自动下载（例如只是探索性搜索），加 --no-auto-download
python3 ${SKILL_DIR}/scripts/web_search.py "<主题>" --no-auto-download

# 手动调参：自定义超时与上限
python3 ${SKILL_DIR}/scripts/web_search.py "<主题>" --auto-download-timeout 5 --auto-download-limit 30

# 下载成功/失败可回写给脚本用于域名排名（一般由自动下载自动调用，无需手动）
python3 ${SKILL_DIR}/scripts/web_search.py --record-download <domain> success|fail
python3 ${SKILL_DIR}/scripts/web_search.py --domain-stats
```

> 📌 **下载的图片文件名保留原始 URL 的 basename**，可能是随机码（如 `5f3a8c1b.jpg`）。后续你需要对 `projects/<topic_name>/images/` 下的图片**逐一审阅**：调用 `analyze_images.py` 获取视觉描述，决定采纳 / 删除 / 重命名为有意义的英文名。

补充策略——按以下优先级搜索**公开可用的免费图片**：

| 来源 | 查找方式 | 许可说明 |
|------|----------|----------|
| **Wikipedia/Wikimedia Commons** | WebFetch Wikipedia页面 → 提取 `upload.wikimedia.org` 图片URL → 获取全分辨率版本（移除URL中的 `/thumb/` 和尺寸后缀） | CC-BY-SA或公共领域 |
| **官方网站** | WebFetch 官方/机构页面 → 查找画廊或新闻区 | 通常可免费用于编辑/教育用途 |
| **政府/机构发布** | WebSearch 官方新闻资料包、公开画廊 | 通常为公共领域 |
| **Creative Commons搜索** | WebSearch `site:commons.wikimedia.org` 或 `site:flickr.com/photos` + creative commons | 检查具体CC许可 |

**避免**：带水印的图库网站、有版权的商业图片、无明确许可的社交媒体上传。

### 3.2 图片选择标准

| 标准 | 指南 |
|------|------|
| **数量** | 6-12张（足以支撑10-15页PPT） |
| **多样性** | 人物像、场景、Logo、活动照片等混合 |
| **分辨率** | 优先宽度1000px+；避免缩略图 |
| **相关性** | 每张图片应有明确用途（封面、插图、背景） |
| **宽高比混合** | 适用时同时包含横版（背景用）和竖版（人物用） |

### 3.3 下载与审阅流程

#### 3.3.1 通过 `web_search.py` 自动下载（**默认路径**）

1. **确认项目目录已识别**。搜索前通过 `PPT_PROJECT_DIR` 环境变量或 `--project-dir` 参数指定当前项目（`projects/<topic_name>`），否则脚本会回退到 `projects/` 下最近修改的子目录，可能错投。
2. **运行若干次 `web_search.py` 搜索（关键字必须中文，见顶部约束 #1）**。每次搜索结束，脚本会并发下载（8 线程 × 5s 超时，单次至多 30 张）到 `projects/<topic_name>/images/`，同一 URL 重复搜索不会重复下载。
3. **查看返回 JSON 的 `downloaded_images` 字段**，快速掌握哪些图片已落地、哪些失败（域名 403、超时、非图片 Content-Type 等）。
4. **⛔ 逐张审阅 + 即时重命名（阻断性）**：
   ```bash
   python3 ${SKILL_DIR}/scripts/analyze_images.py projects/<topic_name>/images
   ```
   根据每张图片的**实际内容**作三选一处理（不得留着原文件名进入下一步）：
   - **采纳** → 立即按 3.3.3 重命名为与图片内容一致的有意义名称（防止后续因随机哈希名导致**图片混用**）；
   - **弃用** → 直接删除文件，绝不留底；
   - **无任何图片合适** → 换一组中文关键字重新搜索，重复本步直至满足设计需求。

   > 完成本步前禁止进入步骤 4 或后续设计 / SVG 生成；未重命名的文件名（如 `5f3a8c1b.jpg`）不得出现在 `design_spec.md` 或 SVG 引用中。

#### 3.3.2 手动补充下载（兜底）

仅在自动下载失败、或从 `web_search.py` 以外的来源（Wikipedia / 官网等）取图时才需要：
```powershell
curl -L -o "projects/<topic_name>/images/descriptive_name.jpg" "<image_url>"
```

#### 3.3.3 文件命名规则（采纳后必然执行，防止图片混用）

- **名称必须与图片实际内容一致**：靠 `analyze_images.py` 给出的视觉描述归纳主体（人物 / 场景 / 对象 / 事件）与上下文（年份 / 地点 / 主题），组合为文件名；
- 示例：`joe_hisaishi_concert_tokyo_2023.jpg`、`spirited_away_poster.jpg`、`thyroid_ultrasound_front_view.png`；
- 反例（绝不得采纳）：`image1.jpg`、`5f3a8c1b.jpg`、`tmp_1.png`、`download.jpg`；
- 全小写，空格用下划线；若图片来自同主体多版本，用数字后缀区分（`joe_hisaishi_portrait_01.jpg`、`joe_hisaishi_portrait_02.jpg`）；
- 重命名后的文件名必须足以让后续设计阶段仅凭文件名就能判断其用途，不需再打开图片确认。

### 3.4 全分辨率URL模式

从已知来源获取全分辨率图片的常见模式：

| 来源 | 缩略图URL | 全分辨率URL |
|------|-----------|-------------|
| Wikimedia | `.../thumb/a/ab/File.jpg/250px-File.jpg` | `.../a/ab/File.jpg`（移除 `thumb/` 和 `/250px-File.jpg`） |
| Ghibli官网 | `www.ghibli.jp/gallery/thumb-xxx.png` | `www.ghibli.jp/gallery/xxx.jpg` |

---

## 步骤 4：输出摘要

完成步骤2和3后，输出简要摘要：

```markdown
## 主题研究完成

**主题**: <topic_name>
**文档**: `projects/<topic_name>.md` — [X个章节，约Y字]
**图片**: `projects/<topic_name>/` — [N张图片]

| 文件名 | 来源 | 描述 |
|--------|------|------|
| ... | ... | ... |
```

> 此后，用户或主流水线可将这些材料作为PPT生成的输入（通过 `project_manager.py import-sources` 导入或直接读取）。

---

## 备注

- 本工作流**仅收集内容** — 不创建PPT项目、不生成SVG、不产出设计规格
- Markdown文档应为**PPT就绪**：结构良好、事实准确、章节清晰对应演示文稿幻灯片
- 始终在Markdown中包含**来源**章节以注明出处和可验证性
- 知名主题（如名人、重大技术）通常2-3轮WebSearch + WebFetch即足够；避免过度研究
- 冷门主题可能需要更多搜索 — 视情况判断
