# 图像工具

图像工具涵盖基于提示词的生成、图像检查和 Gemini 水印去除。

## `image_gen.py`

统一的图像生成入口。

```bash
python scripts/image_gen.py "A modern futuristic workspace"
python scripts/image_gen.py "Abstract tech background" --aspect_ratio 16:9 --image_size 4K
python scripts/image_gen.py "Concept car" -o projects/demo/images
python scripts/image_gen.py "Beautiful landscape" -n "low quality, blurry, watermark"
python scripts/image_gen.py --list-backends
```

后端分为 Core / Extended / Experimental 三个层级。运行 `python scripts/image_gen.py --list-backends` 查看当前列表。

后端选择：

```bash
python scripts/image_gen.py "A cat" --backend openai
python scripts/image_gen.py "A cinematic portrait" --backend minimax
python scripts/image_gen.py "A product launch hero image" --backend qwen
python scripts/image_gen.py "科技感背景图" --backend zhipu
python scripts/image_gen.py "A product KV in cinematic style" --backend volcengine
```

配置来源：

1. 当前进程环境变量
2. 仓库根目录 `.env` 作为回退

必须通过 `IMAGE_BACKEND` 显式指定活跃后端。

`.env` 示例：

```env
IMAGE_BACKEND=openai
OPENAI_API_KEY=sk-xxx
OPENAI_MODEL=gpt-image-2
# OPENAI_BASE_URL=http://127.0.0.1:3000/v1   # 可选代理
```

进程环境示例：

```bash
export IMAGE_BACKEND=openai
export OPENAI_API_KEY=sk-xxx
export OPENAI_MODEL=gpt-image-2
```

进程环境变量优先于 `.env`。

仅使用供应商专属密钥（如 `GEMINI_API_KEY`、`OPENAI_API_KEY`）。完整列表见 `.env.example`。

`IMAGE_API_KEY`、`IMAGE_MODEL`、`IMAGE_BASE_URL` 故意不支持。

若在同一个 `.env` 或环境中配置多个供应商，`IMAGE_BACKEND` 必须显式选择当前供应商。

建议：
- 日常 PPT 工作默认使用 Core 层级
- 仅在需要特定模型风格时使用 Extended
- Experimental 后端按需启用

MiniMax 图像后端 `.env` 示例：

```env
IMAGE_BACKEND=minimax
MINIMAX_API_KEY=your-api-key
# 可选：覆盖基础 URL（默认 https://api.minimaxi.com，国内端点）
# 海外访问使用 https://api.minimax.io
# MINIMAX_BASE_URL=https://api.minimax.io
# MINIMAX_MODEL=image-01
```

## `analyze_images.py`

在编写设计规格或排版前，分析项目目录中的图像。

```bash
python scripts/analyze_images.py <project_path>/images
```

遵循项目工作流时，使用此工具而非直接打开图像文件。

## `gemini_watermark_remover.py`

手动下载后去除 Gemini 水印资源。

```bash
python scripts/gemini_watermark_remover.py <image_path>
python scripts/gemini_watermark_remover.py <image_path> -o output_path.png
python scripts/gemini_watermark_remover.py <image_path> -q
```

注意：
- 需要 `scripts/assets/bg_48.png` 和 `scripts/assets/bg_96.png`
- 建议在下载 Gemini "full size" 图像后使用

依赖：

```bash
pip install Pillow numpy
```
