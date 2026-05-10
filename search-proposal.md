# 搜索工具提案 / Search Tool Proposal

## 背景

PPT制作过程中，LLM需要搜索网页来拓展思路和搜集素材。当前仓库仅有图像搜索工具(`image_search.py`)，缺少通用网页搜索能力。

## 搜索源选择

| 服务 | 免费额度 | 优势 |
|------|----------|------|
| Tavily | 1000次/月 | AI优化搜索，质量高 |
| 百度搜索API | 1500次/月 | 中文内容最强 |

## 核心设计

### 1. 自动轮询
- 优先级：Tavily → 百度
- 单源失败后自动切换下一个
- 禁止并发，避免被封或过早耗尽额度

### 2. 黑名单机制
- 文件：`domain_blacklist.csv`（域名, 失败次数, 最后失败时间）
- 自动过滤：失败 ≥ 3次的域名
- 定期清理：30天后重试

### 3. LLM友好接口
```python
def search(query: str, max_results: int = 5) -> dict:
    """
    返回格式:
    {
        "query": "...",
        "results": [...],
        "source": "tavily/baidu",
        "cached": false
    }
    """
```

### 4. 可选：结果缓存
- 相同查询短期内不重复调用API
- 节省配额

## 文件结构

```
skills/ppt-master/scripts/
├── web_search.py                  # 主脚本（CLI + 可导入模块）
└── web_search_data/               # 运行时数据（自动创建）
    ├── search_cache.json          # 查询缓存（TTL 6h）
    ├── domain_blacklist.csv       # 域名黑名单（失败≥3次自动过滤）
    └── domain_stats.csv           # 域名图片下载成功率排名
```
