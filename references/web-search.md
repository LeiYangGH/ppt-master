# web_search.py — 工具参考

> 本文件是 `scripts/web_search.py` 的工具级说明：CLI 参数、返回 JSON schema、典型调用片段。

---

## 一句话心智模型

```
search  →  收集图片 URL  →  下载到内存  →  LLM 审查  →  保存到 workspace/images/
```

- `workspace/images/` = 正式区：只放 LLM 审查通过、自动命名的图片
- 使用 Pydantic-AI 进行图片识别和重命名

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
| `--project-dir PATH` | 自动 | 工作区路径，覆盖 `PPT_PROJECT_DIR` |
| `--review-images` | 否 | 启用 LLM 图片审查模式 |
| `--image-limit` | 30 | 单次搜索最多审查多少张图片 |
| `--llm-model` | 自动 | 覆盖 LLM 模型名 |
| `--llm-base-url` | 自动 | 覆盖 LLM API base URL |
| `--llm-api-key` | 自动 | 覆盖 LLM API key |

---

## LLM 图片审查模式

使用 `--review-images` 启用 LLM 图片审查模式：

```bash
python scripts/web_search.py "久石让 Joe Hisaishi" --review-images
```

### 工作流程

1. 搜索网页，自动增强关键词（追加"图片 素材 插图 配图 示意图"，并补充"非书封 非绘本封面 非商品图 非海报 非营销图"以过滤书籍和商业物料）
   - 如果query已包含图片相关关键词（图片、素材、插图、配图、照片、壁纸、背景图），则不重复追加图片类关键词
   - 如果query已包含类似"非书封"、"非商品图"等限制词，则不重复追加限制词
2. 逐个下载图片到内存
3. 调用 LLM 审查图片（相关性、质量、PPT适用性）
4. 通过审查的图片自动保存到 `workspace/images/`，文件名为 LLM 生成的描述性英文名称
5. 返回审查结果摘要

### 审查标准

LLM 从三个维度评估图片：
- **相关性**：图片是否与搜索主题相关
- **质量**：图片是否清晰、构图合理、无模糊变形
- **PPT适用性**：图片是否适合作为PPT素材（无复杂背景、主体突出、风格统一）

**坚决拒绝的图片类型**：
- 网页截图（包含浏览器边框、滚动条、网页元素）
- 拼图/拼贴图（多张小图拼接在一起）
- 漫画/连环画（多格漫画）
- 书籍封面、绘本封面、教材封面、杂志封面
- 商品主图、电商图、宣传海报、营销物料
- 含大面积促销文案、价格、品牌宣传语、角标的图片
- 含尺寸标注、规格线、商品展示边框的图片
- 文本信息喧宾夺主、真正主题主体不突出的图片
- 低分辨率图片（模糊、像素化）
- 带水印/logo的图片
- 复杂背景、主体不突出的图片

### PPT上下文注入

LLM 会自动从以下来源获取PPT方向信息（优先级从高到低）：
1. **CLI参数**：`--ppt-style` 和 `--ppt-audience` 显式指定
2. **design_spec.md**：从 `workspace/design_spec.md` 读取项目信息
3. **项目目录名**：从目录名推断风格（如 `ppt169_高端咨询风_汽车认证五年战略规划`）
4. **通用提示**：无上下文时使用通用PPT标准

使用示例：
```bash
# 显式指定PPT风格
python scripts/web_search.py "久石让 Joe Hisaishi" --review-images --ppt-style "高端咨询风" --ppt-audience "企业高管"

# 自动从design_spec.md读取
python scripts/web_search.py "久石让 Joe Hisaishi" --review-images
```

### 返回 JSON schema

```jsonc
{
  "query": "...",
  "answer": "...",
  "results": [...],
  "images": [...],
  "source": "tavily|baidu|none",
  "timestamp": "2026-05-12T...Z",

  // —— LLM 图片审查字段 ——
  "image_review": {
    "total_found": 15,        // 搜索到的图片总数
    "downloaded": 12,         // 成功下载到内存的图片数
    "approved": 5,            // LLM 审查通过的图片数
    "rejected": 7,            // LLM 审查拒绝的图片数
    "files": [                // 审查通过的文件名列表
      "joe_hisaishi_portrait.jpg",
      "joe_hisaishi_conducting.png"
    ],
    "details": [              // 每张图片的审查详情
      {
        "url": "https://...",
        "status": "approved|rejected|download_failed",
        "filename": "joe_hisaishi_portrait.jpg",
        "reason": "..."
      }
    ]
  }
}
```

---

## LLM 配置

### 环境变量

LLM 配置使用环境变量，格式为：

```
LLM_IMAGE_PROCESS_<MODEL_NAME_UPPER>_API_KEY=<api_key>
LLM_IMAGE_PROCESS_<MODEL_NAME_UPPER>_BASE_URL=<base_url>
LLM_IMAGE_PROCESS_<MODEL_NAME_UPPER>_MODEL=<model_name>
```

### 默认配置（mimo-v2.5）

- Base URL: `https://token-plan-cn.xiaomimimo.com/v1`
- Model: `mimo-v2.5`
- API Key 环境变量: `LLM_IMAGE_PROCESS_MIMOV25_API_KEY`

### 配置示例

```bash
# .env 文件
LLM_IMAGE_PROCESS_MIMOV25_API_KEY=your_api_key_here
LLM_IMAGE_PROCESS_MIMOV25_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1
LLM_IMAGE_PROCESS_MIMOV25_MODEL=mimo-v2.5
```

或使用其他模型：

```bash
# 使用 OpenAI
LLM_IMAGE_PROCESS_OPENAI_API_KEY=sk-xxx
LLM_IMAGE_PROCESS_OPENAI_BASE_URL=https://api.openai.com/v1
LLM_IMAGE_PROCESS_OPENAI_MODEL=gpt-4o
```

---

## 典型调用片段

### LLM 标准工作流

```powershell
# 1. 配置工作区（会话开始一次即可）
$env:PPT_PROJECT_DIR = "workspace"

# 2. 配置 LLM（.env 文件或环境变量）
$env:LLM_IMAGE_PROCESS_MIMOV25_API_KEY = "your_api_key"

# 3. 搜索 + LLM 图片审查
python scripts/web_search.py "久石让 Joe Hisaishi" --review-images --json

# 4. 查看审查结果
# 返回的 image_review 字段包含审查摘要和文件列表
```

### 简单搜索（不审查图片）

```powershell
python scripts/web_search.py "2025年内存涨价趋势" -n 8
```

---

## 相关脚本

| 脚本 | 在本工具中的角色 |
|------|-----------------|
| `scripts/llm_process_image.py` | LLM 图片审查模块，由 `--review-images` 自动调用 |
