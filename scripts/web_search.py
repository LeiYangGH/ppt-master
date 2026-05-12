#!/usr/bin/env python3
"""Web search CLI for PPT Master.

Searches the web via Tavily or Baidu and returns a unified, LLM-friendly
result dict.  Designed to be both imported as a library and invoked from
the command line.

Features:
    - **Auto-rotation**: Tavily → Baidu; falls back on failure or missing key.
    - **Non-concurrent**: one source at a time to conserve quota.
    - **No result cache**: every call hits the live API so that retries
      genuinely re-fetch (prevents LLM from looping on stale wrong images).
    - **LLM image review**: downloads images to memory, reviews with LLM,
      and saves approved images with descriptive English filenames.

Free quotas (as of 2026-05):
    Tavily  — 1 000 calls / month
    Baidu   — 1 500 calls / month  (basic web_search, no LLM summarisation)

Examples:
    # Simple search (auto-selects available provider)
    python scripts/web_search.py "2025年内存涨价趋势"

    # Force a provider, more results
    python scripts/web_search.py "AI chip shortage 2026" --provider tavily -n 8

    # Search with LLM image review (default behavior)
    python scripts/web_search.py "久石让 Joe Hisaishi" --review-images
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import requests
import urllib3

# Suppress InsecureRequestWarning when SSL verification is disabled
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------------------------
# Path bootstrapping
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

try:
    from config import load_prefixed_env_file  # type: ignore  # noqa: E402
except ImportError:
    # Fallback: minimal .env loader
    def load_prefixed_env_file(prefixes):  # type: ignore[no-redef]
        """Load ``KEY=VALUE`` pairs whose KEY starts with any of *prefixes*."""
        if isinstance(prefixes, str):
            prefixes = (prefixes,)
        prefixes = tuple(prefixes)
        repo_root = _SCRIPTS_DIR.parent
        candidate_files = [
            repo_root / ".env",
            _SCRIPTS_DIR.parent / ".env",
            _SCRIPTS_DIR / ".env",
        ]
        for env_path in candidate_files:
            if not env_path.exists():
                continue
            try:
                for raw in env_path.read_text(encoding="utf-8").splitlines():
                    line = raw.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    if line.lower().startswith("export "):
                        line = line[7:].lstrip()
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if not key or not any(key.startswith(p) for p in prefixes):
                        continue
                    os.environ.setdefault(key, value)
            except OSError:
                continue

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROVIDERS = ("tavily", "baidu")

_DATA_DIR = _SCRIPTS_DIR / "web_search_data"

ROTATION_STATE_PATH = _DATA_DIR / "rotation_state.json"

# Image file extensions considered downloadable
_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".svg"}

# Auto-download defaults
_AUTO_DOWNLOAD_TIMEOUT = 5        # per-image HTTP timeout in seconds
_AUTO_DOWNLOAD_MAX_IMAGES = 30    # cap per single search invocation
_MIN_IMAGE_BYTES = 1024           # files smaller than this are treated as errors

# Project root (one level above this script: .../ppt-master)
_PROJECT_ROOT = _SCRIPTS_DIR.parent


# ---------------------------------------------------------------------------
# .env loading
# ---------------------------------------------------------------------------

def _load_search_env() -> None:
    """Load Tavily / Baidu keys from the shared .env locations."""
    load_prefixed_env_file(("TAVILY_", "BAIDU_", "LLM_IMAGE_PROCESS_"))


# ===================================================================
# Result data model
# ===================================================================

def _make_result(
    *,
    query: str,
    results: list[dict],
    source: str,
    answer: Optional[str] = None,
    images: Optional[list[dict]] = None,
) -> dict:
    """Build the unified result dict returned to callers / LLM."""
    return {
        "query": query,
        "answer": answer,
        "results": results,
        "images": images or [],
        "source": source,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


# ===================================================================
# Tavily backend
# ===================================================================

def _search_tavily(query: str, max_results: int) -> dict:
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        raise RuntimeError("TAVILY_API_KEY not set")

    resp = requests.post(
        "https://api.tavily.com/search",
        json={
            "query": query,
            "api_key": api_key,
            "max_results": max_results,
            "include_answer": "basic",
            "search_depth": "basic",
            "include_images": True,
            "include_image_descriptions": True,
        },
        timeout=10,
        verify=False,
    )
    resp.raise_for_status()
    data = resp.json()

    results = []
    for item in data.get("results") or []:
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "content": item.get("content", ""),
            "score": item.get("score", 0.0),
            "date": "",
            "domain": _extract_domain(item.get("url", "")),
            "images": [
                img.get("url", "") for img in (item.get("images") or [])
                if img.get("url")
            ],
        })

    images = []
    for img in data.get("images") or []:
        if isinstance(img, dict):
            images.append({"url": img.get("url", ""), "title": img.get("title", "")})
        elif isinstance(img, str):
            images.append({"url": img, "title": ""})

    return _make_result(
        query=query,
        results=results,
        source="tavily",
        answer=data.get("answer"),
        images=images,
    )


# ===================================================================
# Baidu backend
# ===================================================================

def _search_baidu(query: str, max_results: int) -> dict:
    api_key = os.environ.get("BAIDU_API_KEY")
    if not api_key:
        raise RuntimeError("BAIDU_API_KEY not set")

    resp = requests.post(
        "https://qianfan.baidubce.com/v2/ai_search/web_search",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "messages": [{"content": query, "role": "user"}],
            "top_k": max_results,
            "safe_search": False,
        },
        timeout=10,
        verify=False,
    )
    resp.raise_for_status()
    data = resp.json()

    results = []
    images: list[dict] = []

    for item in data.get("references") or []:
        if item.get("type") != "web":
            continue
        # Collect inline images from web_extensions
        inline_imgs: list[str] = []
        ext = item.get("web_extensions") or {}
        for img in ext.get("images") or []:
            url = img.get("url", "")
            if url:
                if not url.startswith("http"):
                    url = "https://" + url
                inline_imgs.append(url)
                images.append({"url": url, "title": item.get("title", "")})

        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "content": item.get("content") or item.get("snippet", ""),
            "score": item.get("rerank_score") or item.get("authority_score") or 0.0,
            "date": item.get("date", ""),
            "domain": _extract_domain(item.get("url", "")),
            "images": inline_imgs,
        })

    return _make_result(
        query=query,
        results=results,
        source="baidu",
        images=images,
    )


# ===================================================================
# Provider dispatch with auto-rotation
# ===================================================================

_BACKEND_MAP = {
    "tavily": _search_tavily,
    "baidu": _search_baidu,
}


def _rotation_load() -> str:
    """Return the provider used in the *last* successful search."""
    if not ROTATION_STATE_PATH.exists():
        return ""
    try:
        data = json.loads(ROTATION_STATE_PATH.read_text(encoding="utf-8"))
        return data.get("last_provider", "")
    except (OSError, json.JSONDecodeError):
        return ""


def _rotation_save(provider: str) -> None:
    """Persist which provider was just used so the next call starts elsewhere."""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    ROTATION_STATE_PATH.write_text(
        json.dumps({"last_provider": provider, "ts": time.time()}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _rotated_chain() -> list[str]:
    """Return the provider list with the *other* provider first."""
    last = _rotation_load()
    providers = list(PROVIDERS)
    if last and last in providers:
        providers.remove(last)
        providers.append(last)
    return providers


def search(
    query: str,
    max_results: int = 5,
    *,
    provider: Optional[str] = None,
) -> dict:
    """Search the web.  The primary entry-point for LLM callers.

    Args:
        query:              Search query string.
        max_results:        Max results to request from the API.
        provider:           Pin a single provider (``"tavily"`` or ``"baidu"``).
                            ``None`` = auto-rotate Tavily → Baidu.

    Returns:
        Unified result dict (see ``_make_result``).
    """
    _load_search_env()

    # --- Provider chain (persisted rotation) ---
    chain = [provider] if provider else _rotated_chain()
    last_error: Optional[Exception] = None

    for name in chain:
        fn = _BACKEND_MAP.get(name)
        if fn is None:
            print(f"  [web_search] unknown provider: {name}", file=sys.stderr)
            continue
        try:
            print(f"  [web_search] trying {name} ...", file=sys.stderr)
            result = fn(query, max_results)
            _rotation_save(name)
            return result
        except Exception as exc:
            last_error = exc
            print(f"  [web_search] {name} failed: {exc}", file=sys.stderr)
            continue

    # All providers failed
    err_msg = f"All search providers failed. Last error: {last_error}"
    print(f"  [web_search] {err_msg}", file=sys.stderr)
    return _make_result(
        query=query,
        results=[],
        source="none",
        answer=err_msg,
    )


# ===================================================================
# Query enhancement for image search
# ===================================================================

def _enhance_query_for_images(query: str) -> str:
    """Enhance search query to prioritize images over books/text.

    Appends keywords to filter out books and prioritize visual content.

    Args:
        query: Original search query.

    Returns:
        Enhanced query with image-related keywords.
    """
    # Keywords to prioritize standalone visual materials instead of
    # book covers, product images, or other commercial graphics.
    image_keywords = " 图片 素材 插图 配图 示意图"
    negative_hint_keywords = " 非书封 非绘本封面 非商品图 非海报 非营销图"

    # Check if query already contains image-related keywords
    existing_keywords = ["图片", "素材", "插图", "配图", "照片", "壁纸", "背景图"]
    has_image_keywords = any(kw in query for kw in existing_keywords)
    has_negative_hints = any(
        kw in query for kw in ["非书封", "非绘本封面", "非商品图", "非海报", "非营销图"]
    )

    additions = []
    if not has_image_keywords:
        additions.append(image_keywords.strip())
    if not has_negative_hints:
        additions.append(negative_hint_keywords.strip())

    if not additions:
        return query

    # Append keywords to prioritize images
    return f"{query} {' '.join(additions)}"


# ===================================================================
# Domain helpers
# ===================================================================

def _extract_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def _normalize_url(url: str) -> str:
    """Normalize URL for deduplication by removing query parameters and fragments."""
    try:
        parsed = urlparse(url)
        # Remove query parameters and fragments, keep only scheme, netloc, and path
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        return normalized
    except Exception:
        return url


# ===================================================================
# Project directory resolution
# ===================================================================

def resolve_project_images_dir(hint: Optional[str] = None) -> Optional[Path]:
    """Locate the best ``images/`` directory to drop auto-downloaded files in.

    Priority (first match wins):
      1. Explicit ``hint`` (CLI ``--project-dir`` or ``--images-dir``).
      2. Env ``PPT_PROJECT_DIR`` / ``PPT_CURRENT_PROJECT``.
      3. CWD is inside ``<repo>/workspace/`` — use that.
      4. ``<repo>/workspace/`` directory.
      5. ``None`` — caller should skip auto-download.

    Returns the ``<workspace>/images`` path (created on demand by caller).
    """

    def _normalise(raw: str) -> Optional[Path]:
        if not raw:
            return None
        raw = raw.strip().strip('"').strip("'")
        if not raw:
            return None
        candidate = Path(raw)
        if not candidate.is_absolute():
            rel_cwd = (Path.cwd() / candidate).resolve()
            if rel_cwd.exists():
                candidate = rel_cwd
            else:
                candidate = (_PROJECT_ROOT / "workspace").resolve()
        if candidate.name == "images":
            return candidate
        return candidate / "images"

    # (1) explicit hint
    if hint:
        resolved = _normalise(hint)
        if resolved is not None:
            return resolved

    # (2) environment variable
    for env_key in ("PPT_PROJECT_DIR", "PPT_CURRENT_PROJECT"):
        env_val = os.environ.get(env_key)
        if env_val:
            resolved = _normalise(env_val)
            if resolved is not None:
                return resolved

    # (3) CWD inside workspace/...
    cwd = Path.cwd().resolve()
    workspace_root = (_PROJECT_ROOT / "workspace").resolve()
    if workspace_root.exists():
        try:
            rel = cwd.relative_to(workspace_root)
            if rel.parts and rel.parts[0] not in ("", "."):
                return workspace_root / "images"
        except ValueError:
            pass

    # (4) workspace directory
    workspace_root = _PROJECT_ROOT / "workspace"
    if workspace_root.exists():
        return workspace_root / "images"

    # (5) give up
    return None


# ===================================================================
# Image URL collection
# ===================================================================

def _is_image_url(url: str) -> bool:
    """Check if a URL likely points to an image based on extension."""
    try:
        path = urlparse(url).path.lower()
        return any(path.endswith(ext) for ext in _IMAGE_EXTENSIONS)
    except Exception:
        return False


def collect_image_urls_from_result(result: dict) -> list[dict]:
    """Extract image URLs from a search result.

    Returns the list of image entries with url and title.
    URLs from the top-level ``images`` field are trusted as images regardless
    of extension.  Per-result inline images pass through an extension filter.
    """
    entries: list[dict] = []
    seen: set[str] = set()

    # Collect from top-level images array (trusted)
    for img in result.get("images") or []:
        url = img.get("url", "") if isinstance(img, dict) else str(img)
        if url:
            normalized = _normalize_url(url)
            if normalized not in seen:
                seen.add(normalized)
                entries.append({
                    "url": url,
                    "title": img.get("title", "") if isinstance(img, dict) else "",
                })

    # Collect from per-result inline images (extension filter)
    for r in result.get("results") or []:
        for img_url in r.get("images") or []:
            if img_url and _is_image_url(img_url):
                normalized = _normalize_url(img_url)
                if normalized not in seen:
                    seen.add(normalized)
                    entries.append({
                        "url": img_url,
                        "title": r.get("title", ""),
                    })

    return entries


# ===================================================================
# Image download with LLM review
# ===================================================================

def _download_image_to_memory(url: str, timeout: int = _AUTO_DOWNLOAD_TIMEOUT) -> Optional[bytes]:
    """Download an image to memory. Returns bytes or None on failure."""
    try:
        resp = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 (PPT-Master image downloader)"},
            verify=False,
        )
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "").lower()
        if "text/html" in content_type or "text/plain" in content_type:
            return None
        data = resp.content
        if len(data) < _MIN_IMAGE_BYTES:
            return None
        return data
    except Exception:
        return None


def search_with_llm_review(
    query: str,
    max_results: int = 5,
    *,
    provider: Optional[str] = None,
    project_hint: Optional[str] = None,
    limit: int = _AUTO_DOWNLOAD_MAX_IMAGES,
    model_name: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    ppt_style: Optional[str] = None,
    ppt_audience: Optional[str] = None,
) -> dict:
    """Search the web, download images, review with LLM, and save approved ones.

    This is the main entry point for the LLM image review workflow.

    Args:
        query: Search query string (should be Chinese).
        max_results: Max results to request from the API.
        provider: Pin a single provider.
        project_hint: Project directory hint.
        limit: Max images to review.
        model_name: Override LLM model name.
        base_url: Override LLM API base URL.
        api_key: Override LLM API key.
        ppt_style: PPT style (e.g., "高端咨询风", "科技风").
        ppt_audience: Target audience (e.g., "6-12岁儿童", "企业高管").

    Returns:
        Unified result dict with additional image review information.
    """
    # Step 1: Search with enhanced query for images
    enhanced_query = _enhance_query_for_images(query)
    if enhanced_query != query:
        print(f"  [web_search] 增强搜索关键词：{query} → {enhanced_query}", file=sys.stderr)
    result = search(enhanced_query, max_results=max_results, provider=provider)

    # Restore original query in result for user visibility
    result["query"] = query

    # Step 2: Collect image URLs
    image_entries = collect_image_urls_from_result(result)
    if not image_entries:
        result["image_review"] = {
            "total_found": 0,
            "downloaded": 0,
            "approved": 0,
            "rejected": 0,
            "files": [],
        }
        return result

    # Limit the number of images to review
    if limit > 0:
        image_entries = image_entries[:limit]

    # Step 3: Resolve output directory
    images_dir = resolve_project_images_dir(project_hint)
    if images_dir is None:
        result["image_review"] = {
            "total_found": len(image_entries),
            "downloaded": 0,
            "approved": 0,
            "rejected": 0,
            "error": "No workspace/images directory found. Set PPT_PROJECT_DIR or run inside workspace/.",
            "files": [],
        }
        return result

    images_dir.mkdir(parents=True, exist_ok=True)

    # Step 4: Import LLM review function
    try:
        from llm_process_image import review_and_save_image_sync
    except ImportError as exc:
        result["image_review"] = {
            "total_found": len(image_entries),
            "downloaded": 0,
            "approved": 0,
            "rejected": 0,
            "error": f"Failed to import llm_process_image: {exc}",
            "files": [],
        }
        return result

    # Step 5: Download and review each image
    total_found = len(image_entries)
    downloaded = 0
    approved = 0
    rejected = 0
    approved_files = []
    review_details = []

    print(f"  [llm-review] 正在处理 {total_found} 张图片...", file=sys.stderr)

    for i, entry in enumerate(image_entries, 1):
        url = entry.get("url", "")
        title = entry.get("title", "")
        # Print full URL to help identify duplicates
        print(f"  [{i}/{total_found}] 下载中 {url}...", end="", file=sys.stderr)

        # Download to memory
        image_data = _download_image_to_memory(url)
        if image_data is None:
            print(" 失败（下载）", file=sys.stderr)
            review_details.append({
                "url": url,
                "status": "download_failed",
            })
            continue

        downloaded += 1
        print(" 成功，审核中...", end="", file=sys.stderr)

        # Review with LLM
        search_context = f"{query} {title}".strip()
        review_result = review_and_save_image_sync(
            image_data=image_data,
            original_url=url,
            search_context=search_context,
            output_dir=images_dir,
            model_name=model_name,
            base_url=base_url,
            api_key=api_key,
            ppt_style=ppt_style,
            ppt_audience=ppt_audience,
        )

        if review_result.get("status") == "approved":
            approved += 1
            filename = review_result.get("filename", "")
            approved_files.append(filename)
            print(f" 通过 → {filename}", file=sys.stderr)
        else:
            rejected += 1
            reason = review_result.get("reason", "unknown")
            print(f" 拒绝 ({reason[:50]})", file=sys.stderr)

        review_details.append({
            "url": url,
            "status": review_result.get("status", "unknown"),
            "filename": review_result.get("filename"),
            "reason": review_result.get("reason", ""),
        })

    # Step 6: Summary
    summary = {
        "total_found": total_found,
        "downloaded": downloaded,
        "approved": approved,
        "rejected": rejected,
        "files": approved_files,
        "details": review_details,
    }
    result["image_review"] = summary

    print(f"\n  [llm-review] 汇总：发现 {total_found} 张，下载 {downloaded} 张，"
          f"通过 {approved} 张，拒绝 {rejected} 张", file=sys.stderr)
    if approved_files:
        print(f"  [llm-review] 通过的文件：", file=sys.stderr)
        for f in approved_files:
            print(f"    + {f}", file=sys.stderr)

    return result


# ===================================================================
# CLI
# ===================================================================

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "PPT Master 的网页搜索工具（Tavily / 百度自动轮询）。\n"
            "\n"
            "LLM 使用要点：\n"
            "  * query 必须写成中文——百度后端对中文 query 的召回率远优于英文。\n"
            "  * 使用 --review-images 启用 LLM 图片审查模式，自动下载图片到内存，\n"
            "    由 LLM 审查相关性和质量，通过的图片自动保存到 workspace/images/。\n"
            "  * 需要配置 LLM_IMAGE_PROCESS_<MODEL>_API_KEY 环境变量。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "query",
        nargs="?",
        default=None,
        help="Search query (should be Chinese).",
    )
    parser.add_argument(
        "-n", "--max-results",
        type=int,
        default=5,
        help="Max results to request (default: 5).",
    )
    parser.add_argument(
        "--provider",
        choices=PROVIDERS,
        default=None,
        help="Pin a single provider. Default: auto-rotate.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="Output raw JSON (default: human-readable summary).",
    )
    parser.add_argument(
        "--project-dir",
        metavar="PATH_OR_NAME",
        default=None,
        help="Target workspace (absolute path, relative path, or 'workspace'). Overrides PPT_PROJECT_DIR.",
    )
    parser.add_argument(
        "--review-images",
        action="store_true",
        help="Enable LLM image review: download images to memory, review with LLM, save approved ones.",
    )
    parser.add_argument(
        "--image-limit",
        type=int,
        default=_AUTO_DOWNLOAD_MAX_IMAGES,
        help=f"Max images to review per search (default: {_AUTO_DOWNLOAD_MAX_IMAGES}).",
    )
    parser.add_argument(
        "--llm-model",
        default=None,
        help="Override LLM model name for image review.",
    )
    parser.add_argument(
        "--llm-base-url",
        default=None,
        help="Override LLM API base URL for image review.",
    )
    parser.add_argument(
        "--llm-api-key",
        default=None,
        help="Override LLM API key for image review.",
    )
    parser.add_argument(
        "--ppt-style",
        default=None,
        help="PPT style for image review (e.g., '高端咨询风', '科技风').",
    )
    parser.add_argument(
        "--ppt-audience",
        default=None,
        help="Target audience for image review (e.g., '6-12岁儿童', '企业高管').",
    )
    return parser


def _print_human(result: dict) -> None:
    """Pretty-print search results for human / LLM reading."""
    src = result["source"]
    print(f"\n== Search: {result['query']} [{src}] ==\n")
    if result.get("answer"):
        print(f"Answer: {result['answer']}\n")
    for i, r in enumerate(result["results"], 1):
        date_tag = f"  [{r['date']}]" if r.get("date") else ""
        print(f"{i}. {r['title']}{date_tag}")
        print(f"   {r['url']}")
        snippet = (r.get("content") or "")[:200]
        if snippet:
            print(f"   {snippet}...")
        if r.get("images"):
            print(f"   images: {len(r['images'])}")
        print()

    review = result.get("image_review")
    if review:
        print(f"-- LLM Image Review --")
        print(f"   Found: {review.get('total_found', 0)}")
        print(f"   Downloaded: {review.get('downloaded', 0)}")
        print(f"   Approved: {review.get('approved', 0)}")
        print(f"   Rejected: {review.get('rejected', 0)}")
        if review.get("error"):
            print(f"   Error: {review['error']}")
        if review.get("files"):
            print(f"   Approved files:")
            for f in review["files"]:
                print(f"     + {f}")
        print()


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.query:
        parser.print_help()
        return 1

    if args.review_images:
        # LLM image review mode
        result = search_with_llm_review(
            args.query,
            max_results=args.max_results,
            provider=args.provider,
            project_hint=args.project_dir,
            limit=args.image_limit,
            model_name=args.llm_model,
            base_url=args.llm_base_url,
            api_key=args.llm_api_key,
            ppt_style=args.ppt_style,
            ppt_audience=args.ppt_audience,
        )
    else:
        # Simple search mode
        result = search(
            args.query,
            max_results=args.max_results,
            provider=args.provider,
        )

    if args.output_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_human(result)

    return 0 if result["results"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
