# Strategist 输出 JSON 指南

## 背景

当前项目采用"同一个 LLM"设计原则：spec 和 SVG 内容由同一个 LLM 在同一上下文中完成，保证设计意图到执行的连贯性。

Strategist 直接输出 `spec_lock.json`——单一结构化配置文件，同时承载设计理由和执行契约。

## 推荐方案：模板填空

### 工作流程

1. **项目初始化**时自动生成 `workspace/spec_lock.json` 模板（带占位符）
2. **Strategist 阶段**读取模板，填写 `<...>` 占位符
3. **校验**使用 `validate_spec.py` 检查填写结果

### 为什么推荐模板填空

| 方面 | 直接生成完整 JSON | 先模板再填空 |
|------|------------------|-------------|
| LLM 负担 | 同时处理内容+格式 | 只处理内容 |
| 格式错误率 | 高（漏逗号、引号、括号） | 低（结构已固定） |
| 出错定位 | 难，需重新生成整个文件 | 易，定位到具体字段 |
| 上下文消耗 | 大 | 小 |

### 模板结构示例

```json
{
  "project": {
    "name": "<填写项目名称>",
    "description": "<填写项目描述>",
    "rationale": "<填写设计理由>"
  },
  "colors": {
    "bg": "#FFFFFF",
    "primary": "<填写主色 HEX，如 #4CAF50>",
    "rationale": "<填写配色理由>"
  }
}
```

### Strategist 提示词建议

```
## 任务

你需要填写 workspace/spec_lock.json 模板中的所有 <...> 占位符。

### 规则

1. 只修改 <...> 中的内容，保持 JSON 结构不变
2. 颜色必须使用 HEX 格式（如 #4CAF50）
3. 字号保持合理（标题 > 正文 > 注释）
4. 每个 rationale 字段填写设计理由
5. 删除多余的占位符行（如不需要的图片项）

### 填写后校验

```bash
python scripts/validate_spec.py workspace/spec_lock.json
```

如果校验失败，根据错误信息修正，直到通过。
```

## 备用方案：直接生成完整 JSON

如果需要直接生成完整 JSON（如脱离 AI IDE 的 agent 应用），可参考以下模板：

```json
{
  "project": {
    "name": "项目名称",
    "description": "项目描述",
    "audience": "目标受众",
    "style": "设计风格",
    "total_pages": 13,
    "created_date": "2026-05-12",
    "rationale": "项目定位理由"
  },
  "canvas": {
    "viewbox": "0 0 1280 720",
    "format": "PPT 16:9",
    "width": 1280,
    "height": 720,
    "margin_left": 60,
    "margin_right": 60,
    "margin_top": 50,
    "margin_bottom": 50,
    "rationale": "画布配置理由"
  },
  "colors": {
    "bg": "#FFFFFF",
    "primary": "#4CAF50",
    "accent": "#2196F3",
    "rationale": "配色理由"
  },
  "typography": {
    "font_family": "\"Microsoft YaHei\", Arial, sans-serif",
    "body": 22,
    "title": 36,
    "rationale": "字体选择理由"
  },
  "icons": {
    "library": "tabler-filled",
    "inventory": ["building", "wind", "droplet"],
    "rationale": "图标选择理由"
  },
  "images": {
    "items": {
      "P01": "image1.jpg",
      "P02": "image2.jpg"
    },
    "rationale": "图片配置理由"
  },
  "page_rhythm": {
    "rhythm": {
      "P01": "structural",
      "P02": "focal"
    },
    "rationale": "节奏配置理由"
  },
  "content_outline": {
    "sections": [
      {
        "page": "P01",
        "title": "封面",
        "layout": "全屏背景图 + 居中标题",
        "content": ["标题", "副标题"],
        "notes_file": "01_cover.md",
        "rationale": "内容设计理由"
      }
    ],
    "rationale": "大纲设计理由"
  },
  "technical_constraints": {
    "forbidden_elements": ["rgba()", "<style>", "class"],
    "forbidden_patterns": ["<g opacity>"],
    "rationale": "技术约束理由"
  },
  "forbidden": [
    "混用图标库",
    "rgba()"
  ],
  "rationale": "整体设计理由"
}
```

## 与现有流程的兼容性

| 方面 | 原流程 | 新流程 |
|------|--------|--------|
| 输出文件 | design_spec.md + spec_lock.md | spec_lock.json |
| 同步机制 | LLM 手工维护两个文件 | 单一文件，无需同步 |
| 校验方式 | 无 | Pydantic 校验 + validate_spec.py |
| 上下文连贯性 | 保持 | 保持（同一个 LLM） |

## 实施步骤

1. **第一步**：运行 `python scripts/project_manager.py` 初始化项目，自动生成模板
2. **第二步**：在 Strategist 提示中添加模板填写要求
3. **第三步**：Strategist 填写模板后运行 `validate_spec.py` 校验
4. **第四步**：观察 LLM 填写质量，迭代优化提示词

## 注意事项

1. JSON 不支持注释，设计理由通过 `rationale` 字段承载
2. 颜色必须使用 HEX 格式（如 `#FFFFFF`），不能使用 `rgba()`
3. 字号必须在 8-120 范围内
4. viewBox 格式必须为 `"0 0 width height"`
5. JSON 必须格式化输出（indent=2），禁止紧凑格式
6. 删除不需要的占位符行，保持 JSON 有效
