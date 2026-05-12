#!/usr/bin/env python3
"""LLM-based image review and renaming for PPT Master.

Uses Pydantic-AI to evaluate images for relevance and quality,
then generates concise English filenames for approved images.

Designed to be called from web_search.py after downloading images.

Environment Variables:
    LLM_IMAGE_PROCESS_<MODEL_NAME_UPPER>_API_KEY: API key for the model.
    LLM_IMAGE_PROCESS_<MODEL_NAME_UPPER>_BASE_URL: Base URL for OpenAI-compatible API.
    LLM_IMAGE_PROCESS_<MODEL_NAME_UPPER>_MODEL: Model name to use.

Default configuration (mimo-v2.5):
    Base URL: https://token-plan-cn.xiaomimimo.com/v1
    Model: mimo-v2.5
    API Key env var: LLM_IMAGE_PROCESS_MIMOV25_API_KEY
"""

from __future__ import annotations

import base64
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.messages import ImageUrl

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


# Default model configuration
_DEFAULT_MODEL_NAME = "mimo-v2.5"
_DEFAULT_BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"
_DEFAULT_ENV_PREFIX = "MIMOV25"


def _extract_ppt_context(
    workspace_dir: Optional[Path] = None,
    ppt_style: Optional[str] = None,
    ppt_audience: Optional[str] = None,
) -> dict:
    """Extract PPT context from multiple sources.

    Priority: CLI params > design_spec.md > project directory name > generic

    Returns dict with keys: project_name, audience, style, tone, color_scheme
    """
    # If CLI params provided, use them directly
    if ppt_style or ppt_audience:
        context = {}
        if ppt_style:
            context["style"] = ppt_style
        if ppt_audience:
            context["audience"] = ppt_audience
        return context

    # Try to find workspace directory
    if workspace_dir is None:
        current_dir = Path.cwd()
        workspace_dir = current_dir / "workspace"
        if not workspace_dir.exists():
            workspace_dir = current_dir.parent / "workspace"

    # Try design_spec.md
    design_spec_path = workspace_dir / "design_spec.md"
    if design_spec_path.exists():
        try:
            content = design_spec_path.read_text(encoding="utf-8")

            context = {}

            # Extract project name
            name_match = re.search(r"\*\*项目名称\*\*\s*\|\s*([^|]+)", content)
            if name_match:
                context["project_name"] = name_match.group(1).strip()

            # Extract target audience
            audience_match = re.search(r"\*\*目标受众\*\*\s*\|\s*([^|]+)", content)
            if audience_match:
                context["audience"] = audience_match.group(1).strip()

            # Extract design style
            style_match = re.search(r"\*\*设计风格\*\*\s*\|\s*([^|]+)", content)
            if style_match:
                context["style"] = style_match.group(1).strip()

            # Extract tone (from visual theme section)
            tone_match = re.search(r"\*\*调性\**:\s*([^\n]+)", content)
            if tone_match:
                context["tone"] = tone_match.group(1).strip()

            # Extract color scheme hints
            color_section = re.search(r"配色方案.*?儿童科普教育需要(.+?)。", content, re.DOTALL)
            if color_section:
                context["color_scheme_hint"] = color_section.group(1).strip()

            return context
        except Exception:
            pass

    # Try to infer from project directory name
    # Example: ppt169_高端咨询风_汽车认证五年战略规划
    try:
        parent_dir = workspace_dir.parent
        dir_name = parent_dir.name
        if "风" in dir_name:
            # Extract style from directory name
            parts = dir_name.split("_")
            for part in parts:
                if "风" in part:
                    context = {"style": part.replace("风", "风格")}
                    return context
    except Exception:
        pass

    # Fallback: return empty dict (use generic prompt)
    return {}


class ImageReviewResult(BaseModel):
    """Result of LLM image review."""
    is_relevant: bool = Field(description="图片是否与搜索主题相关")
    is_quality_ok: bool = Field(description="图片质量是否合格")
    is_suitable_for_ppt: bool = Field(description="图片是否适合作为PPT素材")
    reason: str = Field(description="决策理由")
    suggested_filename: Optional[str] = Field(
        default=None,
        description="批准时的英文文件名（不带扩展名）"
    )


@dataclass
class LLMConfig:
    """LLM configuration."""
    base_url: str
    model_name: str
    api_key: str


def _load_llm_config(
    model_name: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> LLMConfig:
    """Load LLM configuration from environment or parameters.

    Priority:
    1. Explicit parameters
    2. Environment variables with pattern:
       - LLM_IMAGE_PROCESS_<MODEL_NAME_UPPER>_API_KEY
       - LLM_IMAGE_PROCESS_<MODEL_NAME_UPPER>_BASE_URL
       - LLM_IMAGE_PROCESS_<MODEL_NAME_UPPER>_MODEL
    3. Default MiMo-V2.5 configuration
    """
    env_prefix = "LLM_IMAGE_PROCESS"

    # Try to detect model from env
    detected_model = model_name
    if detected_model is None:
        # Check for any configured model via env
        for key, value in os.environ.items():
            if key.startswith(env_prefix) and key.endswith("_MODEL"):
                detected_model = value
                # Extract the model identifier from env var name
                # e.g., LLM_IMAGE_PROCESS_MIMOV25_MODEL -> MIMOV25
                parts = key.replace(env_prefix, "").replace("_MODEL", "").strip("_")
                if parts:
                    env_prefix = f"{env_prefix}_{parts}"
                break

    # Use default if nothing detected
    if detected_model is None:
        detected_model = _DEFAULT_MODEL_NAME
        env_prefix = f"{env_prefix}_{_DEFAULT_ENV_PREFIX}"

    # Load from env or parameters
    resolved_api_key = api_key or os.environ.get(f"{env_prefix}_API_KEY", "")
    resolved_base_url = base_url or os.environ.get(f"{env_prefix}_BASE_URL", _DEFAULT_BASE_URL)
    resolved_model = detected_model or os.environ.get(f"{env_prefix}_MODEL", _DEFAULT_MODEL_NAME)

    if not resolved_api_key:
        raise RuntimeError(
            f"API key not found. Set {env_prefix}_API_KEY environment variable "
            f"or pass api_key parameter."
        )

    return LLMConfig(
        base_url=resolved_base_url,
        model_name=resolved_model,
        api_key=resolved_api_key,
    )


def _create_agent(config: LLMConfig, ppt_context: dict) -> Agent[None, ImageReviewResult]:
    """Create a Pydantic-AI agent for image review."""

    # Set environment variables for OpenAI provider
    os.environ["OPENAI_API_KEY"] = config.api_key
    os.environ["OPENAI_BASE_URL"] = config.base_url

    # Disable SSL warnings
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # Create a custom httpx AsyncClient with SSL verification disabled
    import httpx
    http_client = httpx.AsyncClient(verify=False)

    # Use OpenAI model with custom http client via provider
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider

    # Create provider with custom http client
    provider = OpenAIProvider(
        api_key=config.api_key,
        base_url=config.base_url,
        http_client=http_client,
    )

    model = OpenAIChatModel(
        config.model_name,
        provider=provider,
    )

    # Build context-aware system prompt
    context_info = []
    if ppt_context.get("project_name"):
        context_info.append(f"项目：{ppt_context['project_name']}")
    if ppt_context.get("audience"):
        context_info.append(f"目标受众：{ppt_context['audience']}")
    if ppt_context.get("style"):
        context_info.append(f"设计风格：{ppt_context['style']}")
    if ppt_context.get("tone"):
        context_info.append(f"调性：{ppt_context['tone']}")

    context_str = "\n".join(context_info) if context_info else "通用PPT"

    system_prompt = (
        f"你是PPT图片审核员。评估图片是否适合作为PPT素材。\n\n"
        f"**项目上下文**：\n{context_str}\n\n"
        f"审核标准：\n"
        f"1. 相关性：图片是否与搜索主题相关\n"
        f"2. 质量：清晰、构图合理、无模糊变形\n"
        f"3. PPT适用性：是否适合作为PPT素材（无复杂背景、主体突出、风格统一）\n\n"
        f"**坚决拒绝的图片类型**：\n"
        f"- 网页截图（包含浏览器边框、滚动条、网页元素）\n"
        f"- 拼图/拼贴图（多张小图拼接在一起）\n"
        f"- 漫画/连环画（多格漫画）\n"
        f"- 书籍封面、绘本封面、教材封面、杂志封面\n"
        f"- 商品主图、电商图、宣传海报、营销物料\n"
        f"- 含大面积促销文案、价格、品牌宣传语、角标的图片\n"
        f"- 含尺寸标注、规格线、商品展示边框的图片\n"
        f"- 文本信息喧宾夺主、真正主题主体不突出的图片\n"
        f"- 低分辨率图片（模糊、像素化）\n"
        f"- 带水印/logo的图片\n"
        f"- 复杂背景、主体不突出的图片\n\n"
        f"特别注意：如果图片本质上是在展示一本书、一个商品或营销页面，即使主题相关，也必须拒绝。"
        f"如果图片中的大字标题、促销语、封面文案、尺寸标记比真正画面主体更抢眼，也必须拒绝。\n\n"
        f"**拒绝理由撰写规则**：\n"
        f"- 如果判定图片不合格，只需简洁说明拒绝原因（1-2句话），不要提及任何优点或可以接受的地方\n"
        f"- 禁止使用\"虽然...但是...\"、\"整体不错，但...\"等模棱两可的表达\n"
        f"- 直接点明问题所在，例如：\"这是商品主图，包含营销文案和尺寸标注\"、\"这是绘本封面，本质是卖书而非素材\"\n\n"
        f"如果批准，提供简洁的英文文件名（3-5个词，用下划线连接）。\n\n"
        f"严格但公正。只批准专业PPT可用的图片。"
    )

    agent = Agent(
        model,
        output_type=ImageReviewResult,
        system_prompt=system_prompt,
    )
    return agent


def _encode_image(image_path: Path) -> str:
    """Encode image to base64 data URI."""
    suffix = image_path.suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }
    mime_type = mime_map.get(suffix, "image/jpeg")

    with open(image_path, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")

    return f"data:{mime_type};base64,{data}"


def review_image_sync(
    image_path: str | Path,
    search_context: str,
    *,
    model_name: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    ppt_style: str | None = None,
    ppt_audience: str | None = None,
) -> ImageReviewResult:
    """Review a single image for relevance and quality (synchronous).

    Args:
        image_path: Path to the image file.
        search_context: The search keywords/context for relevance check.
        model_name: Override model name.
        base_url: Override API base URL.
        api_key: Override API key.
        ppt_style: PPT style (e.g., "高端咨询风", "科技风").
        ppt_audience: Target audience (e.g., "6-12岁儿童", "企业高管").

    Returns:
        ImageReviewResult with decision and suggested filename.
    """
    image_path = Path(image_path)
    if not image_path.exists():
        return ImageReviewResult(
            is_relevant=False,
            is_quality_ok=False,
            is_suitable_for_ppt=False,
            reason=f"文件不存在：{image_path}",
        )

    config = _load_llm_config(model_name, base_url, api_key)
    ppt_context = _extract_ppt_context(ppt_style=ppt_style, ppt_audience=ppt_audience)
    agent = _create_agent(config, ppt_context)

    # Encode image
    data_uri = _encode_image(image_path)

    prompt = (
        f"搜索主题：{search_context}\n\n"
        f"审核这张图片。是否与主题相关？质量是否合格？是否适合作为PPT素材？"
    )

    try:
        # Use Pydantic-AI's synchronous API with ImageUrl
        image_url = ImageUrl(url=data_uri)
        result = agent.run_sync(
            [prompt, image_url],
        )
        return result.output
    except Exception as e:
        return ImageReviewResult(
            is_relevant=False,
            is_quality_ok=False,
            is_suitable_for_ppt=False,
            reason=f"LLM审核失败：{e}",
        )


def get_extension(filename: str) -> str:
    """Get file extension from filename."""
    return Path(filename).suffix


def review_and_save_image_sync(
    image_data: bytes,
    original_url: str,
    search_context: str,
    output_dir: Path | str,
    *,
    model_name: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    ppt_style: str | None = None,
    ppt_audience: str | None = None,
) -> dict:
    """Review an image from memory and save if approved (synchronous).

    Args:
        image_data: Raw image bytes.
        original_url: Original image URL (for context).
        search_context: Search keywords for relevance check.
        output_dir: Directory to save approved images.
        model_name: Override model name.
        base_url: Override API base URL.
        api_key: Override API key.
        ppt_style: PPT style (e.g., "高端咨询风", "科技风").
        ppt_audience: Target audience (e.g., "6-12岁儿童", "企业高管").

    Returns:
        Dict with status, filename, and reason.
    """
    import tempfile

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Detect extension from URL
    from urllib.parse import urlparse
    parsed = urlparse(original_url)
    path_lower = parsed.path.lower()
    ext = ".jpg"  # default
    for candidate in [".png", ".jpeg", ".jpg", ".gif", ".webp", ".bmp"]:
        if path_lower.endswith(candidate):
            ext = candidate
            break

    # Write to temp file for LLM review
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(image_data)
        tmp_path = Path(tmp.name)

    try:
        # Review with LLM
        result = review_image_sync(
            tmp_path,
            search_context,
            model_name=model_name,
            base_url=base_url,
            api_key=api_key,
            ppt_style=ppt_style,
            ppt_audience=ppt_audience,
        )

        if result.is_relevant and result.is_quality_ok and result.is_suitable_for_ppt and result.suggested_filename:
            # Clean filename
            filename = result.suggested_filename.strip()
            filename = filename.replace(" ", "_")
            # Remove any problematic characters
            filename = "".join(c for c in filename if c.isalnum() or c in "_-")
            if not filename:
                filename = "approved_image"

            dest = output_dir / f"{filename}{ext}"

            # Avoid overwriting
            counter = 1
            while dest.exists():
                dest = output_dir / f"{filename}_{counter}{ext}"
                counter += 1

            # Save image
            dest.write_bytes(image_data)

            return {
                "status": "approved",
                "filename": dest.name,
                "path": str(dest),
                "reason": result.reason,
            }
        else:
            return {
                "status": "rejected",
                "filename": None,
                "reason": result.reason,
            }
    finally:
        # Cleanup temp file
        try:
            tmp_path.unlink()
        except OSError:
            pass


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="使用LLM审核并重命名图片"
    )
    parser.add_argument(
        "image",
        help="要审核的图片路径",
    )
    parser.add_argument(
        "--context",
        required=True,
        help="搜索主题（用于相关性检查）",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="模型名称覆盖",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="API基础URL覆盖",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="API密钥覆盖",
    )
    parser.add_argument(
        "--ppt-style",
        default=None,
        help="PPT风格（如：高端咨询风、科技风）",
    )
    parser.add_argument(
        "--ppt-audience",
        default=None,
        help="目标受众（如：6-12岁儿童、企业高管）",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="JSON格式输出",
    )

    args = parser.parse_args()

    result = review_image_sync(
        args.image,
        args.context,
        model_name=args.model,
        base_url=args.base_url,
        api_key=args.api_key,
        ppt_style=args.ppt_style,
        ppt_audience=args.ppt_audience,
    )

    if args.json:
        print(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))
    else:
        print(f"相关：{result.is_relevant}")
        print(f"质量合格：{result.is_quality_ok}")
        print(f"适合PPT：{result.is_suitable_for_ppt}")
        print(f"理由：{result.reason}")
        if result.suggested_filename:
            print(f"建议文件名：{result.suggested_filename}")
