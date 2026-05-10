#!/usr/bin/env python3
"""Web search CLI for PPT Master.

Searches the web via Tavily or Baidu and returns a unified, LLM-friendly
result dict.  Designed to be both imported as a library and invoked from
the command line.

Features:
    - **Auto-rotation**: Tavily → Baidu; falls back on failure or missing key.
    - **Non-concurrent**: one source at a time to conserve quota.
    - **Domain blacklist**: domains that repeatedly fail image downloads are
      auto-filtered from results.  Blacklist decays after 30 days.
    - **Domain stats**: tracks per-domain image-download success rate so LLM
      or downstream tools can prefer reliable sources.
    - **Result cache**: identical queries reuse cached results within a
      configurable TTL (default 6 h), saving API calls.

Free quotas (as of 2026-05):
    Tavily  — 1 000 calls / month
    Baidu   — 1 500 calls / month  (basic web_search, no LLM summarisation)

Examples:
    # Simple search (auto-selects available provider)
    python scripts/web_search.py "2025年内存涨价趋势"

    # Force a provider, more results
    python scripts/web_search.py "AI chip shortage 2026" --provider tavily -n 8

    # Show domain stats ranking
    python scripts/web_search.py --domain-stats

    # Record an image-download outcome (called by image pipeline)
    python scripts/web_search.py --record-download pic.rmb.bdstatic.com success
    python scripts/web_search.py --record-download example.com fail
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse
import ssl

import requests
import urllib3

# ---------------------------------------------------------------------------
# Path bootstrapping
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from config import load_prefixed_env_file  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROVIDERS = ("tavily", "baidu")

_CACHE_TTL_SECONDS = 6 * 3600  # 6 hours
_BLACKLIST_THRESHOLD = 3        # failures before a domain is blacklisted
_BLACKLIST_DECAY_DAYS = 30      # days after which a blacklisted domain is retried

_DATA_DIR = _SCRIPTS_DIR / "web_search_data"

CACHE_PATH = _DATA_DIR / "search_cache.json"
BLACKLIST_PATH = _DATA_DIR / "domain_blacklist.csv"
DOMAIN_STATS_PATH = _DATA_DIR / "domain_stats.csv"
ROTATION_STATE_PATH = _DATA_DIR / "rotation_state.json"
COLLECTED_IMAGES_PATH = _DATA_DIR / "collected_images.jsonl"

# Image file extensions considered downloadable
_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".svg"}


# ---------------------------------------------------------------------------
# .env loading & SSL auto-fix
# ---------------------------------------------------------------------------

_ZSCALER_CERT_PATHS = [
    Path("C:/IT/ZscalerRootCertificate-2048-SHA256-it251020.crt"),
    Path("C:/IT/ZscalerRootCertificate.crt"),
]

_ssl_checked = False


def _ensure_ssl() -> None:
    """Smoke-test HTTPS connectivity; auto-apply Zscaler cert if needed.

    Runs once per process.  If the default CA bundle works, do nothing.
    If an SSL error occurs and a known Zscaler cert file is found on disk,
    set REQUESTS_CA_BUNDLE / SSL_CERT_FILE so all subsequent requests use it.
    """
    global _ssl_checked
    if _ssl_checked:
        return
    _ssl_checked = True

    # Already configured by the user / environment
    if os.environ.get("REQUESTS_CA_BUNDLE") or os.environ.get("SSL_CERT_FILE"):
        return

    try:
        requests.head("https://www.baidu.com", timeout=5)
        return  # default certs work fine
    except (requests.exceptions.SSLError, ssl.SSLError, urllib3.exceptions.SSLError):
        pass
    except Exception:
        return  # non-SSL error (network down, etc.) — don't interfere

    # SSL failed — look for a Zscaler cert
    for cert_path in _ZSCALER_CERT_PATHS:
        if cert_path.exists():
            os.environ["REQUESTS_CA_BUNDLE"] = str(cert_path)
            os.environ["SSL_CERT_FILE"] = str(cert_path)
            print(
                f"  [ssl] auto-applied Zscaler cert: {cert_path}",
                file=sys.stderr,
            )
            return

    print(
        "  [ssl] SSL verification failed but no Zscaler cert found at known paths."
        "  Set REQUESTS_CA_BUNDLE manually if needed.",
        file=sys.stderr,
    )


def _load_search_env() -> None:
    """Load Tavily / Baidu keys from the shared .env locations."""
    load_prefixed_env_file(("TAVILY_", "BAIDU_"))
    _ensure_ssl()


# ===================================================================
# Result data model
# ===================================================================

def _make_result(
    *,
    query: str,
    results: list[dict],
    source: str,
    cached: bool = False,
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
        "cached": cached,
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
# Provider dispatch with auto-rotation (persisted across invocations)
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
    """Return the provider list with the *other* provider first.

    If last time we used tavily, this time start with baidu, and vice versa.
    """
    last = _rotation_load()
    providers = list(PROVIDERS)  # ("tavily", "baidu")
    if last and last in providers:
        # Move last-used to the end so we try the other one first
        providers.remove(last)
        providers.append(last)
    return providers


def search(
    query: str,
    max_results: int = 5,
    *,
    provider: Optional[str] = None,
    use_cache: bool = True,
    filter_blacklisted: bool = True,
) -> dict:
    """Search the web.  The primary entry-point for LLM callers.

    Args:
        query:              Search query string.
        max_results:        Max results to request from the API.
        provider:           Pin a single provider (``"tavily"`` or ``"baidu"``).
                            ``None`` = auto-rotate Tavily → Baidu.
        use_cache:          Reuse cached results within the TTL window.
        filter_blacklisted: Remove results whose domain is blacklisted.

    Returns:
        Unified result dict (see ``_make_result``).
    """
    _load_search_env()

    # --- Cache lookup ---
    cache_key = _cache_key(query, max_results)
    if use_cache:
        cached = _cache_get(cache_key)
        if cached is not None:
            cached["cached"] = True
            if filter_blacklisted:
                cached["results"] = _apply_blacklist(cached["results"])
            print(f"  [cache hit] query={query!r}", file=sys.stderr)
            return cached

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
            _cache_put(cache_key, result)
            _rotation_save(name)  # persist for next invocation
            if filter_blacklisted:
                result["results"] = _apply_blacklist(result["results"])
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
# Domain helpers
# ===================================================================

def _extract_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


# ===================================================================
# Cache (JSON file, TTL-based)
# ===================================================================

def _cache_key(query: str, max_results: int) -> str:
    raw = f"{query.strip().lower()}|{max_results}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _cache_load() -> dict:
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _cache_save(cache: dict) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _cache_get(key: str) -> Optional[dict]:
    cache = _cache_load()
    entry = cache.get(key)
    if entry is None:
        return None
    if time.time() - entry.get("_ts", 0) > _CACHE_TTL_SECONDS:
        return None
    return entry.get("data")


def _cache_put(key: str, data: dict) -> None:
    cache = _cache_load()
    # Evict expired entries to keep the file small
    now = time.time()
    cache = {
        k: v for k, v in cache.items()
        if now - v.get("_ts", 0) <= _CACHE_TTL_SECONDS
    }
    cache[key] = {"_ts": now, "data": data}
    _cache_save(cache)


def clear_cache() -> int:
    """Remove all cached results.  Returns number of entries cleared."""
    cache = _cache_load()
    n = len(cache)
    if CACHE_PATH.exists():
        CACHE_PATH.unlink()
    return n


# ===================================================================
# Domain blacklist (CSV)
# ===================================================================

def _blacklist_load() -> dict[str, dict]:
    """Return ``{domain: {"fail_count": int, "last_fail": str}}``."""
    if not BLACKLIST_PATH.exists():
        return {}
    entries: dict[str, dict] = {}
    try:
        with BLACKLIST_PATH.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                entries[row["domain"]] = {
                    "fail_count": int(row.get("fail_count", 0)),
                    "last_fail": row.get("last_fail", ""),
                }
    except (OSError, KeyError, ValueError):
        return {}
    return entries


def _blacklist_save(entries: dict[str, dict]) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    with BLACKLIST_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["domain", "fail_count", "last_fail"])
        writer.writeheader()
        for domain, info in sorted(entries.items()):
            writer.writerow({
                "domain": domain,
                "fail_count": info["fail_count"],
                "last_fail": info["last_fail"],
            })


def _is_blacklisted(domain: str, entries: Optional[dict] = None) -> bool:
    if entries is None:
        entries = _blacklist_load()
    info = entries.get(domain)
    if info is None:
        return False
    if info["fail_count"] < _BLACKLIST_THRESHOLD:
        return False
    # Decay: allow retry after N days
    try:
        last = datetime.fromisoformat(info["last_fail"])
        age_days = (datetime.now(timezone.utc) - last).days
        if age_days >= _BLACKLIST_DECAY_DAYS:
            return False
    except (ValueError, TypeError):
        pass
    return True


def record_domain_failure(domain: str) -> None:
    """Increment failure count for *domain* in the blacklist."""
    entries = _blacklist_load()
    info = entries.get(domain, {"fail_count": 0, "last_fail": ""})
    info["fail_count"] += 1
    info["last_fail"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    entries[domain] = info
    _blacklist_save(entries)


def _apply_blacklist(results: list[dict]) -> list[dict]:
    entries = _blacklist_load()
    if not entries:
        return results
    filtered = []
    for r in results:
        domain = r.get("domain") or _extract_domain(r.get("url", ""))
        if _is_blacklisted(domain, entries):
            print(f"    [blacklist] filtered: {domain}", file=sys.stderr)
            continue
        filtered.append(r)
    return filtered


# ===================================================================
# Domain stats — image-download success rate
# ===================================================================

def _stats_load() -> dict[str, dict]:
    """Return ``{domain: {"ok": int, "fail": int, "last": str}}``."""
    if not DOMAIN_STATS_PATH.exists():
        return {}
    entries: dict[str, dict] = {}
    try:
        with DOMAIN_STATS_PATH.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                entries[row["domain"]] = {
                    "ok": int(row.get("ok", 0)),
                    "fail": int(row.get("fail", 0)),
                    "last": row.get("last", ""),
                }
    except (OSError, KeyError, ValueError):
        return {}
    return entries


def _stats_save(entries: dict[str, dict]) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    with DOMAIN_STATS_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["domain", "ok", "fail", "rate", "last"])
        writer.writeheader()
        for domain, info in sorted(
            entries.items(),
            key=lambda kv: _success_rate(kv[1]),
            reverse=True,
        ):
            total = info["ok"] + info["fail"]
            writer.writerow({
                "domain": domain,
                "ok": info["ok"],
                "fail": info["fail"],
                "rate": f"{_success_rate(info):.0%}" if total else "N/A",
                "last": info["last"],
            })


def _success_rate(info: dict) -> float:
    total = info["ok"] + info["fail"]
    return info["ok"] / total if total else 0.0


def record_download(domain: str, success: bool) -> None:
    """Record an image-download outcome for *domain*.

    Also feeds the blacklist: a failure here increments the blacklist
    counter so truly broken domains get auto-removed from search results.
    """
    entries = _stats_load()
    info = entries.get(domain, {"ok": 0, "fail": 0, "last": ""})
    if success:
        info["ok"] += 1
    else:
        info["fail"] += 1
        record_domain_failure(domain)
    info["last"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    entries[domain] = info
    _stats_save(entries)


def get_domain_ranking(min_total: int = 1) -> list[dict]:
    """Return domains sorted by image-download success rate (descending).

    Each entry: ``{"domain", "ok", "fail", "total", "rate"}``
    Useful for LLM to prefer images from reliable domains.
    """
    entries = _stats_load()
    ranking = []
    for domain, info in entries.items():
        total = info["ok"] + info["fail"]
        if total < min_total:
            continue
        ranking.append({
            "domain": domain,
            "ok": info["ok"],
            "fail": info["fail"],
            "total": total,
            "rate": round(_success_rate(info), 3),
        })
    ranking.sort(key=lambda x: (-x["rate"], -x["total"]))
    return ranking


def rank_results_by_domain_reliability(results: list[dict]) -> list[dict]:
    """Re-order search results so that results from higher-success-rate
    domains come first.  Results from unknown domains keep their original
    relative order but are placed after known-good domains.

    This is a *soft* sort — it does not drop anything.  LLM can call
    this to get a reliability-aware ordering.
    """
    stats = _stats_load()
    known: list[tuple[float, int, dict]] = []
    unknown: list[dict] = []

    for idx, r in enumerate(results):
        domain = r.get("domain") or _extract_domain(r.get("url", ""))
        info = stats.get(domain)
        if info and (info["ok"] + info["fail"]) > 0:
            rate = _success_rate(info)
            known.append((rate, idx, r))
        else:
            unknown.append(r)

    known.sort(key=lambda t: (-t[0], t[1]))
    return [item[2] for item in known] + unknown


# ===================================================================
# Image URL collection & download
# ===================================================================

def _is_image_url(url: str) -> bool:
    """Check if a URL likely points to an image based on extension."""
    try:
        path = urlparse(url).path.lower()
        return any(path.endswith(ext) for ext in _IMAGE_EXTENSIONS)
    except Exception:
        return False


def collect_images_from_result(result: dict, output_file: Optional[Path] = None) -> list[dict]:
    """Extract image URLs from a search result and append to a JSONL file.

    Each line in the JSONL file is a JSON object:
        {"url": "...", "title": "...", "source_page": "...", "query": "...", "ts": "..."}

    Returns the list of image entries collected.
    """
    if output_file is None:
        output_file = COLLECTED_IMAGES_PATH

    entries: list[dict] = []
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    query = result.get("query", "")

    # Collect from top-level images array
    for img in result.get("images") or []:
        url = img.get("url", "") if isinstance(img, dict) else str(img)
        if url and _is_image_url(url):
            entries.append({
                "url": url,
                "title": img.get("title", "") if isinstance(img, dict) else "",
                "source_page": "",
                "query": query,
                "ts": ts,
            })

    # Collect from per-result inline images
    for r in result.get("results") or []:
        source_page = r.get("url", "")
        for img_url in r.get("images") or []:
            if img_url and _is_image_url(img_url):
                entries.append({
                    "url": img_url,
                    "title": r.get("title", ""),
                    "source_page": source_page,
                    "query": query,
                    "ts": ts,
                })

    if entries:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        # Deduplicate against existing file
        existing_urls: set[str] = set()
        if output_file.exists():
            try:
                for line in output_file.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line:
                        existing_urls.add(json.loads(line).get("url", ""))
            except (OSError, json.JSONDecodeError):
                pass

        new_entries = [e for e in entries if e["url"] not in existing_urls]
        if new_entries:
            with output_file.open("a", encoding="utf-8") as f:
                for e in new_entries:
                    f.write(json.dumps(e, ensure_ascii=False) + "\n")
            print(
                f"  [images] collected {len(new_entries)} new image URL(s) → {output_file.name}",
                file=sys.stderr,
            )

    return entries


def download_images(
    output_dir: str | Path,
    image_file: Optional[Path] = None,
    *,
    limit: int = 0,
    timeout: int = 20,
) -> list[dict]:
    """Download images from the collected JSONL file.

    Args:
        output_dir:  Directory to save downloaded images.
        image_file:  Path to the JSONL file. Defaults to COLLECTED_IMAGES_PATH.
        limit:       Max number of images to download (0 = all).
        timeout:     HTTP timeout per download.

    Returns:
        List of dicts with download outcomes:
            {"url": ..., "file": ..., "status": "ok"|"fail", "reason": ...}
    """
    if image_file is None:
        image_file = COLLECTED_IMAGES_PATH
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not image_file.exists():
        print(f"  [download] no collected images file: {image_file}", file=sys.stderr)
        return []

    # Read entries
    entries: list[dict] = []
    for line in image_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    if limit > 0:
        entries = entries[:limit]

    results: list[dict] = []
    for i, entry in enumerate(entries, 1):
        url = entry.get("url", "")
        if not url:
            continue

        # Derive filename from URL
        parsed = urlparse(url)
        basename = Path(parsed.path).name
        if not basename or len(basename) > 120:
            basename = f"image_{i}.jpg"
        # Avoid filename collisions
        dest = output_dir / basename
        if dest.exists():
            stem, suffix = dest.stem, dest.suffix
            dest = output_dir / f"{stem}_{i}{suffix}"

        domain = _extract_domain(url)
        print(f"  [{i}/{len(entries)}] {basename} ← {domain} ...", end="", file=sys.stderr)

        try:
            resp = requests.get(
                url,
                timeout=timeout,
                headers={"User-Agent": "Mozilla/5.0 (PPT-Master image downloader)"},
                stream=True,
            )
            resp.raise_for_status()
            content_type = resp.headers.get("Content-Type", "")
            if "text/html" in content_type:
                raise ValueError(f"got HTML instead of image (Content-Type: {content_type})")
            with open(dest, "wb") as f:
                for chunk in resp.iter_content(8192):
                    f.write(chunk)
            # Check minimum file size (< 1KB is likely an error page)
            if dest.stat().st_size < 1024:
                dest.unlink()
                raise ValueError(f"file too small ({dest.stat().st_size} bytes), likely not a real image")
            print(f" OK ({dest.stat().st_size // 1024}KB)", file=sys.stderr)
            record_download(domain, success=True)
            results.append({"url": url, "file": str(dest), "status": "ok", "reason": ""})
        except Exception as exc:
            print(f" FAIL: {exc}", file=sys.stderr)
            record_download(domain, success=False)
            results.append({"url": url, "file": "", "status": "fail", "reason": str(exc)})

    # Summary
    ok = sum(1 for r in results if r["status"] == "ok")
    fail = len(results) - ok
    print(f"\n  [download] done: {ok} ok, {fail} failed, saved to {output_dir}", file=sys.stderr)
    return results


# ===================================================================
# CLI
# ===================================================================

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Web search for PPT Master (Tavily / Baidu with auto-rotation).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "query",
        nargs="?",
        default=None,
        help="Search query.",
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
        "--no-cache",
        action="store_true",
        help="Bypass and do not write the result cache.",
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear all cached results and exit.",
    )
    parser.add_argument(
        "--domain-stats",
        action="store_true",
        help="Print domain download-success ranking and exit.",
    )
    parser.add_argument(
        "--record-download",
        nargs=2,
        metavar=("DOMAIN", "OUTCOME"),
        help="Record an image-download outcome: DOMAIN success|fail.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="Output raw JSON (default: human-readable summary).",
    )
    parser.add_argument(
        "--download-images",
        metavar="OUTPUT_DIR",
        default=None,
        help="Download collected images to OUTPUT_DIR and exit.",
    )
    parser.add_argument(
        "--download-limit",
        type=int,
        default=0,
        help="Max images to download (0 = all). Used with --download-images.",
    )
    parser.add_argument(
        "--list-images",
        action="store_true",
        help="List collected image URLs and exit.",
    )
    parser.add_argument(
        "--clear-images",
        action="store_true",
        help="Clear the collected images file and exit.",
    )
    return parser


def _print_human(result: dict) -> None:
    """Pretty-print search results for human / LLM reading."""
    src = result["source"]
    cached_tag = " (cached)" if result.get("cached") else ""
    print(f"\n== Search: {result['query']} [{src}{cached_tag}] ==\n")
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


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # --- Utility modes ---
    if args.clear_cache:
        n = clear_cache()
        print(f"Cleared {n} cached entries.", file=sys.stderr)
        return 0

    if args.domain_stats:
        ranking = get_domain_ranking()
        if not ranking:
            print("No domain stats recorded yet.", file=sys.stderr)
            return 0
        print(f"{'Domain':<40} {'OK':>5} {'Fail':>5} {'Total':>6} {'Rate':>7}")
        print("-" * 70)
        for r in ranking:
            print(
                f"{r['domain']:<40} {r['ok']:>5} {r['fail']:>5} "
                f"{r['total']:>6} {r['rate']:>6.0%}"
            )
        return 0

    if args.record_download:
        domain, outcome = args.record_download
        if outcome not in ("success", "fail"):
            print("OUTCOME must be 'success' or 'fail'.", file=sys.stderr)
            return 1
        record_download(domain, success=(outcome == "success"))
        print(f"Recorded {outcome} for {domain}.", file=sys.stderr)
        return 0

    # --- Image management modes ---
    if args.list_images:
        if not COLLECTED_IMAGES_PATH.exists():
            print("No collected images yet.", file=sys.stderr)
            return 0
        entries = []
        for line in COLLECTED_IMAGES_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        print(f"Collected images: {len(entries)}")
        for i, e in enumerate(entries, 1):
            print(f"  {i}. {e.get('url', '')}")
            if e.get("title"):
                print(f"     title: {e['title']}")
            if e.get("source_page"):
                print(f"     from: {e['source_page']}")
        return 0

    if args.clear_images:
        if COLLECTED_IMAGES_PATH.exists():
            n = len(COLLECTED_IMAGES_PATH.read_text(encoding="utf-8").splitlines())
            COLLECTED_IMAGES_PATH.unlink()
            print(f"Cleared {n} collected image entries.", file=sys.stderr)
        else:
            print("No collected images to clear.", file=sys.stderr)
        return 0

    if args.download_images:
        outcomes = download_images(
            args.download_images,
            limit=args.download_limit,
        )
        if args.output_json:
            print(json.dumps(outcomes, ensure_ascii=False, indent=2))
        return 0 if any(r["status"] == "ok" for r in outcomes) else 1

    # --- Search mode ---
    if not args.query:
        parser.print_help()
        return 1

    result = search(
        args.query,
        max_results=args.max_results,
        provider=args.provider,
        use_cache=not args.no_cache,
    )

    # Auto-collect image URLs from results
    collect_images_from_result(result)

    if args.output_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_human(result)

    return 0 if result["results"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
