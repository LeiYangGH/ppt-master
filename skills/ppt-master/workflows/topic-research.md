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

**主工具** — `web_search.py`（自动轮询 Tavily → 百度、缓存结果、遵守域名黑名单）：

```bash
# 全局概览搜索
python3 ${SKILL_DIR}/scripts/web_search.py "<主题> 概述" -n 8 --json

# 定向补充搜索
python3 ${SKILL_DIR}/scripts/web_search.py "<子主题> 数据 统计" -n 5 --json
```

> 该脚本对相同查询缓存 6 小时——重复运行不会额外消耗 API 调用。Tavily（每月 1000 次）和百度（每月 1500 次）都属于免费额度；自动轮询可最大化可用配额。

**深度抓取** — 从搜索结果中识别出高信号 URL 后，使用 `web_to_md.py` 或 IDE 的 `WebFetch` 抓取完整页面内容：

```bash
python3 ${SKILL_DIR}/scripts/source_to_md/web_to_md.py <URL>
```

**IDE 网页工具** — 如果 IDE 自带网页搜索能力（如 Claude Code 的 `WebSearch`、Cursor 内置搜索等），可作为补充使用，但 `web_search.py` 仍为首选（因它跟踪域名可靠性并缓存结果）。

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

**主工具** — `web_search.py`（返回结果中内联 `images` 字段，包含每个结果页面的引用图片 URL）：

```bash
# 搜索时返回的 JSON 中每条数据就含 images 列表
python3 ${SKILL_DIR}/scripts/web_search.py "<主题> 相片" -n 8 --json

# 下载成功/失败可回写给脚本用于域名排名
python3 ${SKILL_DIR}/scripts/web_search.py --record-download <domain> success|fail
python3 ${SKILL_DIR}/scripts/web_search.py --domain-stats
```

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

### 3.3 下载流程

```powershell
# 在projects/下创建图片文件夹（与文档同名）
New-Item -ItemType Directory -Force -Path "projects/<topic_name>"

# 用描述性文件名下载图片
curl -L -o "projects/<topic_name>/descriptive_name.jpg" "<image_url>"
```

**文件命名规则**：
- 使用描述性英文名：`joe_hisaishi_concert.jpg`，而非 `image1.jpg`
- 小写，空格用下划线
- 包含主体和上下文：`spirited_away_poster.jpg`、`tokyo_concert_2023.jpg`

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
