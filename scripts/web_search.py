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
    - **No result cache**: every call hits the live API so that retries
      genuinely re-fetch (prevents LLM from looping on stale wrong images).

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
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import unquote, urlparse
import ssl

import requests
import urllib3

# Suppress InsecureRequestWarning when SSL verification is disabled
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Disable SSL verification globally
_ssl_verify_disabled = True

# ---------------------------------------------------------------------------
# Path bootstrapping
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

try:
    from config import load_prefixed_env_file  # type: ignore  # noqa: E402
except ImportError:
    # Fallback: minimal .env loader. Searches, in priority order:
    #   1. <repo>/.env
    #   2. <skill>/.env  (/.env)
    #   3. <scripts>/.env
    def load_prefixed_env_file(prefixes):  # type: ignore[no-redef]
        """Load ``KEY=VALUE`` pairs whose KEY starts with any of *prefixes*.

        Values that are already present in ``os.environ`` are not overwritten,
        so explicit shell exports still take precedence over .env files.
        """
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

_BLACKLIST_THRESHOLD = 3        # failures before a domain is blacklisted
_BLACKLIST_DECAY_DAYS = 30      # days after which a blacklisted domain is retried

_DATA_DIR = _SCRIPTS_DIR / "web_search_data"

BLACKLIST_PATH = _DATA_DIR / "domain_blacklist.csv"
DOMAIN_STATS_PATH = _DATA_DIR / "domain_stats.csv"
ROTATION_STATE_PATH = _DATA_DIR / "rotation_state.json"
COLLECTED_IMAGES_PATH = _DATA_DIR / "collected_images.jsonl"

# Image file extensions considered downloadable
_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".svg"}

# Auto-download defaults (tuned for LLM-friendly short blocking time)
_AUTO_DOWNLOAD_TIMEOUT = 5        # per-image HTTP timeout in seconds
_AUTO_DOWNLOAD_WORKERS = 8        # concurrent download threads
_AUTO_DOWNLOAD_MAX_IMAGES = 30    # cap per single search invocation
_MIN_IMAGE_BYTES = 1024           # files smaller than this are treated as errors

# --- downloads/ staging area (task.md decision 1/2/3) ----------------------
_DOWNLOADS_DIR_NAME     = "downloads"
_DOWNLOADS_SEARCHES_DIR = "searches"   # JSON snapshots live here
_STATE_FILE_NAME        = "_state.jsonl"
_DEFAULT_MAX_FILES      = 150
_DEFAULT_MAX_BYTES      = 300 * 1024 * 1024   # 300 MB
_MONTAGE_TRIGGER_MIN    = 5     # run montage only when >= N new images (unless --force-montage)

# Project root (one level above this script: .../ppt-master)
_PROJECT_ROOT = _SCRIPTS_DIR.parent


# ---------------------------------------------------------------------------
# .env loading
# ---------------------------------------------------------------------------

def _load_search_env() -> None:
    """Load Tavily / Baidu keys from the shared .env locations."""
    load_prefixed_env_file(("TAVILY_", "BAIDU_"))


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
        verify=False,  # Baidu doesn't need SSL verification
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
    filter_blacklisted: bool = True,
) -> dict:
    """Search the web.  The primary entry-point for LLM callers.

    Args:
        query:              Search query string.
        max_results:        Max results to request from the API.
        provider:           Pin a single provider (``"tavily"`` or ``"baidu"``).
                            ``None`` = auto-rotate Tavily → Baidu.
        filter_blacklisted: Remove results whose domain is blacklisted.

    Returns:
        Unified result dict (see ``_make_result``).

    No result caching is performed — every call hits the live API so that
    repeated searches with identical queries can genuinely re-fetch fresh
    data (prevents LLM from being stuck with stale wrong images on retry).
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
                domain = row.get("domain")
                if not domain:
                    continue
                try:
                    fail_count_val = row.get("fail_count")
                    entries[domain] = {
                        "fail_count": int(fail_count_val) if fail_count_val is not None else 0,
                        "last_fail": row.get("last_fail", ""),
                    }
                except (ValueError, TypeError):
                    # Skip rows with invalid data
                    continue
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
                domain = row.get("domain")
                if not domain:
                    continue
                try:
                    ok_val = row.get("ok")
                    fail_val = row.get("fail")
                    entries[domain] = {
                        "ok": int(ok_val) if ok_val is not None else 0,
                        "fail": int(fail_val) if fail_val is not None else 0,
                        "last": row.get("last", ""),
                    }
                except (ValueError, TypeError):
                    # Skip rows with invalid data
                    continue
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
# Project directory resolution (for auto-download destination)
# ===================================================================

def _is_project_dir(path: Path) -> bool:
    """A PPT Master project dir is the workspace directory."""
    try:
        path = path.resolve()
    except OSError:
        return False
    workspace_root = (_PROJECT_ROOT / "workspace").resolve()
    if not workspace_root.exists():
        return False
    try:
        rel = path.relative_to(workspace_root)
    except ValueError:
        return False
    # Direct child of workspace/ (depth == 1)
    return len(rel.parts) >= 1 and rel.parts[0] not in ("", ".")


def _latest_project_dir() -> Optional[Path]:
    """Return the workspace directory if it exists."""
    workspace_root = _PROJECT_ROOT / "workspace"
    if not workspace_root.exists():
        return None
    return workspace_root


def resolve_project_images_dir(hint: Optional[str] = None) -> Optional[Path]:
    """Locate the best ``images/`` directory to drop auto-downloaded files in.

    Priority (first match wins):
      1. Explicit ``hint`` (CLI ``--project-dir`` or ``--images-dir``).
         May be an absolute path, a relative path, or "workspace".
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
            # Try: relative to cwd, then as workspace
            rel_cwd = (Path.cwd() / candidate).resolve()
            if rel_cwd.exists():
                candidate = rel_cwd
            else:
                candidate = (_PROJECT_ROOT / "workspace").resolve()
        # Accept either the workspace dir itself or its images/ sub-dir
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
    latest = _latest_project_dir()
    if latest is not None:
        return latest / "images"

    # (5) give up
    return None


# ===================================================================
# workspace/downloads/ —— staging area, state file, quota, pipeline
# ===================================================================

def resolve_project_downloads_dir(hint: Optional[str] = None) -> Optional[Path]:
    """Resolve the staging ``<workspace>/downloads`` directory.

    Uses the same priority logic as :func:`resolve_project_images_dir` but
    returns the sibling ``downloads/`` path.
    """
    images_dir = resolve_project_images_dir(hint)
    if images_dir is None:
        return None
    return images_dir.parent / _DOWNLOADS_DIR_NAME


def _state_path(downloads_dir: Path) -> Path:
    return downloads_dir / _STATE_FILE_NAME


def _state_load(downloads_dir: Path) -> list[dict]:
    """Load ``_state.jsonl`` as a list of dicts.  Corrupt lines are skipped."""
    path = _state_path(downloads_dir)
    if not path.exists():
        return []
    records: list[dict] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return []
    return records


def _state_write(downloads_dir: Path, records: list[dict]) -> None:
    """Atomic rewrite of ``_state.jsonl`` (tmp + os.replace)."""
    downloads_dir.mkdir(parents=True, exist_ok=True)
    path = _state_path(downloads_dir)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def _state_index_by_url(records: list[dict]) -> dict[str, dict]:
    return {r["url"]: r for r in records if r.get("url")}


def _downloads_usage(downloads_dir: Path) -> tuple[int, int]:
    """Return (file_count, total_bytes) of image files directly under downloads/.

    Excludes the state file, ``searches/`` sub-directory and montages.
    """
    if not downloads_dir.exists():
        return 0, 0
    n = 0
    b = 0
    for p in downloads_dir.iterdir():
        if not p.is_file():
            continue
        if p.name == _STATE_FILE_NAME:
            continue
        if p.suffix.lower() not in _IMAGE_EXTENSIONS:
            continue
        try:
            b += p.stat().st_size
            n += 1
        except OSError:
            continue
    return n, b


def _check_quota(
    downloads_dir: Path,
    *,
    max_files: int,
    max_bytes: int,
) -> Optional[str]:
    """Return an actionable error string if quota is exceeded, else None."""
    n, b = _downloads_usage(downloads_dir)
    if n >= max_files or b >= max_bytes:
        return (
            f"downloads/ 已达上限（{n}/{max_files} 文件, "
            f"{b // (1024 * 1024)}MB/{max_bytes // (1024 * 1024)}MB）。"
            f"请先用 `python scripts/web_search.py --adopt <file> "
            f"<images/描述名.ext>` 采纳，或 `--purge-downloads` 清理后再搜索。"
        )
    return None


def _save_search_snapshot(result: dict, downloads_dir: Path) -> Path:
    """Persist the raw search result JSON under downloads/searches/."""
    snap_dir = downloads_dir / _DOWNLOADS_SEARCHES_DIR
    snap_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    qhash = hashlib.sha1((result.get("query") or "").encode("utf-8")).hexdigest()[:8]
    path = snap_dir / f"{ts}_{qhash}.json"
    try:
        path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        print(f"  [snapshot] failed: {exc}", file=sys.stderr)
    return path


# ------------------------------------------------------------------
# State-aware filtering before download
# ------------------------------------------------------------------

def _filter_entries_by_state(
    entries: list[dict],
    records: list[dict],
) -> list[dict]:
    """Drop entries whose URL already has an ``adopted_as`` record.

    Also drops entries whose URL already has a valid on-disk downloaded
    file (handled by the per-file skip in :func:`_download_single_image`,
    but filtering here keeps the state/pipeline numbers honest).
    """
    adopted_urls = {r["url"] for r in records if r.get("adopted_as")}
    if not adopted_urls:
        return entries
    return [e for e in entries if e.get("url") not in adopted_urls]


# ------------------------------------------------------------------
# Post-download pipeline: analyze + incremental montage
# ------------------------------------------------------------------

def _run_analyze(downloads_dir: Path, filenames: list[str]) -> dict[str, dict]:
    """Call analyze_images on *filenames* only.  Returns {filename: record}.

    Uses the public ``analyze_images()`` function; it scans the whole
    directory so we filter its output to the list we care about.
    """
    if not filenames:
        return {}
    try:
        from analyze_images import analyze_images, classify_ratio  # type: ignore
    except Exception as exc:  # pragma: no cover - defensive
        print(f"  [analyze] import failed: {exc}", file=sys.stderr)
        return {}
    try:
        all_results = analyze_images(str(downloads_dir))
    except Exception as exc:  # pragma: no cover - defensive
        print(f"  [analyze] failed: {exc}", file=sys.stderr)
        return {}
    wanted = set(filenames)
    out: dict[str, dict] = {}
    for r in all_results:
        name = r.get("filename")
        if name in wanted:
            out[name] = {
                "w": int(r.get("width", 0)),
                "h": int(r.get("height", 0)),
                "aspect": round(float(r.get("aspect_ratio", 0.0)), 3),
                "category": r.get("layout_hint", ""),
            }
    return out


def _run_incremental_montage(
    downloads_dir: Path,
    new_filenames: list[str],
    batch_id: int,
) -> Optional[dict]:
    """Produce a montage containing ONLY the freshly downloaded files.

    Called with a temporary staging sub-dir of symlinks/copies to
    ``_montage/batch_NN_src/``; falls back to copying when symlinks
    aren't supported (Windows without admin).
    """
    if not new_filenames:
        return None
    try:
        from image_montage import build_montages  # type: ignore
    except Exception as exc:  # pragma: no cover - defensive
        print(f"  [montage] import failed: {exc}", file=sys.stderr)
        return None

    import shutil

    montage_root = downloads_dir / "_montage"
    stage_dir = montage_root / f"batch_{batch_id:02d}_src"
    if stage_dir.exists():
        shutil.rmtree(stage_dir, ignore_errors=True)
    stage_dir.mkdir(parents=True, exist_ok=True)
    # Stage by hard-link (cheap on NTFS / ext4); fall back to copy.
    for name in new_filenames:
        src = downloads_dir / name
        if not src.exists():
            continue
        dst = stage_dir / name
        try:
            os.link(src, dst)
        except OSError:
            try:
                shutil.copy2(src, dst)
            except OSError as exc:
                print(f"  [montage] skip {name}: {exc}", file=sys.stderr)
                continue
    out_dir = montage_root
    try:
        manifest = build_montages(stage_dir, output_dir=out_dir)
    except Exception as exc:
        print(f"  [montage] build failed: {exc}", file=sys.stderr)
        return None
    # Rename the generated montage to include our batch id so the LLM can
    # see which batch each montage covers.
    renamed: list[str] = []
    for m in manifest.get("montages", []):
        orig = Path(m["path"])
        if not orig.exists():
            continue
        target = out_dir / f"montage_batch_{batch_id:02d}_{orig.name}"
        try:
            orig.replace(target)
            renamed.append(target.name)
        except OSError as exc:
            print(f"  [montage] rename failed: {exc}", file=sys.stderr)
            renamed.append(orig.name)
    # Staging dir no longer needed.
    shutil.rmtree(stage_dir, ignore_errors=True)
    return {
        "batch_id": batch_id,
        "count": len(new_filenames),
        "montages": renamed,
        "dir": str(out_dir),
    }


def _next_montage_batch(records: list[dict]) -> int:
    """Return the next batch id = max(existing) + 1, or 1."""
    batches = [int(r["montage_batch"]) for r in records
               if isinstance(r.get("montage_batch"), (int, float))]
    return (max(batches) + 1) if batches else 1


def run_post_download_pipeline(
    downloads_dir: Path,
    outcomes: list[dict],
    *,
    query: str,
    force_montage: bool = False,
) -> dict:
    """After async_download_images: update state, analyze, maybe montage.

    Returns a summary dict attached to the CLI JSON output:
        {"new_files": [...], "analyzed": N, "montage_batch": {...}|None}
    """
    records = _state_load(downloads_dir)
    index = _state_index_by_url(records)
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # 1) Upsert state rows for every ok/skip outcome (skip = already existed).
    new_filenames: list[str] = []
    for o in outcomes:
        if o.get("status") not in ("ok", "skip"):
            continue
        url = o.get("url", "")
        file_path = o.get("file", "")
        if not url or not file_path:
            continue
        filename = Path(file_path).name
        rec = index.get(url)
        if rec is None:
            rec = {
                "url":           url,
                "filename":      filename,
                "sha1":          hashlib.sha1(url.encode("utf-8")).hexdigest()[:8],
                "size":          int(o.get("bytes", 0)) or None,
                "w":             None,
                "h":             None,
                "aspect":        None,
                "category":      None,
                "query":         query,
                "ts":            ts,
                "analyzed_at":   None,
                "montage_batch": None,
                "adopted_as":    None,
            }
            records.append(rec)
            index[url] = rec
        else:
            # keep original metadata; only refresh filename/size if changed
            if not rec.get("filename"):
                rec["filename"] = filename
            if rec.get("size") in (None, 0) and o.get("bytes"):
                rec["size"] = int(o["bytes"])
        if o.get("status") == "ok" and rec.get("analyzed_at") is None:
            # Only count genuinely new files (not skips) as "new" for montage.
            new_filenames.append(filename)

    # 2) Analyze only rows without analyzed_at.
    to_analyze = [r["filename"] for r in records
                  if r.get("analyzed_at") is None and r.get("filename")]
    analyzed = _run_analyze(downloads_dir, to_analyze)
    for r in records:
        name = r.get("filename")
        if name in analyzed:
            r.update(analyzed[name])
            r["analyzed_at"] = ts

    # 3) Incremental montage.
    pending_for_montage = [r["filename"] for r in records
                           if r.get("montage_batch") is None and r.get("filename")
                           and (downloads_dir / r["filename"]).exists()]
    montage_summary: Optional[dict] = None
    if pending_for_montage and (force_montage or len(pending_for_montage) >= _MONTAGE_TRIGGER_MIN):
        batch_id = _next_montage_batch(records)
        montage_summary = _run_incremental_montage(downloads_dir, pending_for_montage, batch_id)
        if montage_summary:
            pending_set = set(pending_for_montage)
            for r in records:
                if r.get("filename") in pending_set:
                    r["montage_batch"] = batch_id

    _state_write(downloads_dir, records)

    return {
        "new_files":     new_filenames,
        "analyzed":      sum(1 for r in records if r.get("analyzed_at")),
        "pending_montage": len(pending_for_montage) if not montage_summary else 0,
        "montage_batch": montage_summary,
    }


# ------------------------------------------------------------------
# adopt / purge CLI helpers
# ------------------------------------------------------------------

_BAD_ADOPT_NAME_RE = None


def _validate_adopt_target_name(name: str) -> Optional[str]:
    """Return an error string if *name* uses a forbidden hash/generic pattern."""
    import re
    bad_patterns = [
        r"^img_[0-9a-f]{8,}\.",         # our own hash prefix
        r"^image_\d+\.",                # enumerated placeholder
        r"^tmp_",
        r"^download",
        r"^untitled",
    ]
    low = name.lower()
    for pat in bad_patterns:
        if re.match(pat, low):
            return (
                f"拒绝采纳：目标文件名 '{name}' 命中禁用模式 ({pat})。"
                f"请改为与图片内容一致的描述性名称"
                f"（如 joe_hisaishi_portrait_01.jpg）。"
            )
    return None


def adopt_image(
    src: str | Path,
    dest: str | Path,
    *,
    project_hint: Optional[str] = None,
) -> dict:
    """Promote a file from downloads/ to images/ with a descriptive name."""
    src_path = Path(src)
    dest_path = Path(dest)

    downloads_dir = resolve_project_downloads_dir(project_hint)
    images_dir = resolve_project_images_dir(project_hint)
    if downloads_dir is None or images_dir is None:
        raise RuntimeError("无法定位 workspace；请设 PPT_PROJECT_DIR 或传 --project-dir。")

    # Resolve src relative to downloads/ if not absolute.
    if not src_path.is_absolute():
        src_path = (downloads_dir / src_path).resolve()
    if not src_path.exists():
        raise FileNotFoundError(f"源文件不存在: {src_path}")

    # Resolve dest relative to images/ if not absolute and not already there.
    if not dest_path.is_absolute():
        # Accept either 'foo.jpg' or 'images/foo.jpg'
        if dest_path.parts and dest_path.parts[0] == "images":
            dest_path = images_dir.parent / dest_path
        else:
            dest_path = images_dir / dest_path

    dest_path.parent.mkdir(parents=True, exist_ok=True)

    err = _validate_adopt_target_name(dest_path.name)
    if err:
        raise ValueError(err)

    if dest_path.exists():
        raise FileExistsError(f"目标已存在: {dest_path}")

    import shutil
    shutil.move(str(src_path), str(dest_path))

    # Update state.
    records = _state_load(downloads_dir)
    changed = False
    for r in records:
        if r.get("filename") == src_path.name:
            r["adopted_as"] = str(dest_path)
            changed = True
            break
    if changed:
        _state_write(downloads_dir, records)

    return {
        "src":  str(src_path),
        "dest": str(dest_path),
        "state_updated": changed,
    }


def purge_downloads(
    project_hint: Optional[str] = None,
    *,
    keep_snapshots: bool = True,
) -> dict:
    """Delete all image files and the montage dir under downloads/.

    Keeps ``_state.jsonl`` so already-adopted URLs stay de-duped across
    sessions.  Keeps ``searches/`` snapshots unless *keep_snapshots* is False.
    """
    downloads_dir = resolve_project_downloads_dir(project_hint)
    if downloads_dir is None or not downloads_dir.exists():
        return {"removed": 0, "dir": None}

    import shutil
    removed = 0
    for p in list(downloads_dir.iterdir()):
        if p.name == _STATE_FILE_NAME:
            continue
        if p.name == _DOWNLOADS_SEARCHES_DIR and keep_snapshots:
            continue
        try:
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            else:
                p.unlink()
            removed += 1
        except OSError:
            continue

    # Reset pending pipeline fields on non-adopted records so the next
    # search can re-download cleanly.
    records = _state_load(downloads_dir)
    for r in records:
        if r.get("adopted_as"):
            continue
        # Mark as purged: clear filename so it can be re-downloaded.
        r["filename"] = None
        r["analyzed_at"] = None
        r["montage_batch"] = None
        r["size"] = None
    _state_write(downloads_dir, records)

    return {"removed": removed, "dir": str(downloads_dir)}



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


def _derive_filename(url: str, fallback_index: int = 0) -> str:
    """Pick a filesystem-safe filename from a URL.

    Per task.md decision 1: **all** files use ``img_<sha1_8>.ext`` (8-hex,
    matches git short-hash length; collision odds at 150 files ≈ 3e-6).
    Server-provided basenames are ignored because they often look like
    ``5f3a8c1b.jpg`` and mislead the LLM into thinking the name is
    meaningful.  Same URL → same filename → natural de-duplication.
    """
    try:
        parsed = urlparse(url)
        raw_basename = unquote(Path(parsed.path).name or "")
    except Exception:
        raw_basename = ""

    # Only use the URL basename to sniff a sensible extension.
    cleaned = raw_basename
    for ch in '<>:"|?*':
        cleaned = cleaned.replace(ch, "_")
    cleaned = cleaned.strip().strip(".")

    suffix = ""
    if cleaned:
        candidate = Path(cleaned).suffix.lower()
        if candidate in _IMAGE_EXTENSIONS:
            suffix = candidate
    if not suffix:
        lower_url = url.lower()
        for ext in _IMAGE_EXTENSIONS:
            if ext in lower_url:
                suffix = ext
                break
    if not suffix:
        suffix = ".jpg"

    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]
    return f"img_{digest}{suffix}"


def collect_images_from_result(result: dict, output_file: Optional[Path] = None) -> list[dict]:
    """Extract image URLs from a search result and append to a JSONL file.

    Each line in the JSONL file is a JSON object:
        {"url": "...", "title": "...", "source_page": "...", "query": "...", "ts": "..."}

    Returns the list of image entries collected (pre-dedup against the file).
    URLs from the top-level ``images`` field are trusted as images regardless
    of extension (API providers label them explicitly).  Per-result inline
    images still pass through an extension filter to suppress false positives
    (e.g. HTML links that merely contain an image anywhere on the page).
    """
    if output_file is None:
        output_file = COLLECTED_IMAGES_PATH

    entries: list[dict] = []
    seen: set[str] = set()
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    query = result.get("query", "")

    # Collect from top-level images array (trusted — no extension filter)
    for img in result.get("images") or []:
        url = img.get("url", "") if isinstance(img, dict) else str(img)
        if url and url not in seen:
            seen.add(url)
            entries.append({
                "url": url,
                "title": img.get("title", "") if isinstance(img, dict) else "",
                "source_page": "",
                "query": query,
                "ts": ts,
            })

    # Collect from per-result inline images (extension filter keeps noise out)
    for r in result.get("results") or []:
        source_page = r.get("url", "")
        for img_url in r.get("images") or []:
            if img_url and img_url not in seen and _is_image_url(img_url):
                seen.add(img_url)
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


# ------------------------------------------------------------------
# Concurrent ("async") image download — the main LLM-friendly entry
# ------------------------------------------------------------------

def _download_single_image(
    entry: dict,
    output_dir: Path,
    timeout: int,
    index: int,
) -> dict:
    """Worker: download one image.  Never raises — returns an outcome dict.

    Outcome keys: ``url``, ``file``, ``status`` ("ok" | "skip" | "fail"),
    ``reason``, ``domain``, ``bytes``.
    """
    import traceback

    try:
        url = entry.get("url", "")
        domain = _extract_domain(url)
        outcome = {"url": url, "file": "", "status": "fail", "reason": "", "domain": domain, "bytes": 0}
        if not url:
            outcome["reason"] = "empty url"
            return outcome

        try:
            basename = _derive_filename(url, fallback_index=index)
        except Exception as exc:
            outcome["reason"] = f"_derive_filename error: {exc}"
            return outcome

        dest = output_dir / basename
        # Skip if already present (same URL likely re-surfaced across searches)
        if dest.exists() and dest.stat().st_size >= _MIN_IMAGE_BYTES:
            outcome.update(status="skip", file=str(dest), reason="exists",
                           bytes=dest.stat().st_size)
            return outcome
        # Avoid collision when the basename exists but is too small (stale error)
        if dest.exists():
            try:
                dest.unlink()
            except OSError:
                try:
                    stem, suffix = dest.stem, dest.suffix or ".jpg"
                    dest = output_dir / f"{stem}_{index}{suffix}"
                except Exception as exc:
                    outcome["reason"] = f"filename collision error: {exc}"
                    return outcome

        try:
            resp = requests.get(
                url,
                timeout=timeout,
                headers={"User-Agent": "Mozilla/5.0 (PPT-Master image downloader)"},
                stream=True,
                verify=False,
            )
            resp.raise_for_status()
            content_type = resp.headers.get("Content-Type", "").lower()
            if "text/html" in content_type or "text/plain" in content_type:
                raise ValueError(f"non-image content-type: {content_type}")
            tmp = dest.with_suffix(dest.suffix + ".part")
            with open(tmp, "wb") as f:
                for chunk in resp.iter_content(8192):
                    if chunk:
                        f.write(chunk)
            size = tmp.stat().st_size
            if size < _MIN_IMAGE_BYTES:
                tmp.unlink(missing_ok=True)
                raise ValueError(f"file too small ({size} bytes)")
            tmp.replace(dest)
            outcome.update(status="ok", file=str(dest), bytes=size)
            record_download(domain, success=True)
        except Exception as exc:  # noqa: BLE001
            outcome["reason"] = str(exc)
            record_download(domain, success=False)
        return outcome
    except Exception as exc:
        # This should not happen, but catch it just in case
        return {
            "url": entry.get("url", ""),
            "file": "",
            "status": "fail",
            "reason": f"worker crash: {exc}\n{traceback.format_exc()}",
            "domain": "",
            "bytes": 0,
        }


def async_download_images(
    entries: list[dict],
    output_dir: Path,
    *,
    timeout: int = _AUTO_DOWNLOAD_TIMEOUT,
    max_workers: int = _AUTO_DOWNLOAD_WORKERS,
    limit: int = _AUTO_DOWNLOAD_MAX_IMAGES,
) -> list[dict]:
    """Concurrently download up to ``limit`` images with per-request timeout.

    "Async" here means *parallel with a short per-image timeout* — the caller
    still blocks until all workers finish, but each individual request is
    capped at ``timeout`` seconds, so the worst-case wall-clock is roughly
    ``ceil(N / max_workers) * timeout``.  For the default 30 images / 8
    workers / 5 s timeout, that is under 20 s in the worst case and usually
    only 1–2 s when the network is healthy.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Deduplicate and apply limit
    seen: set[str] = set()
    work: list[dict] = []
    for e in entries:
        url = e.get("url", "")
        if not url or url in seen:
            continue
        seen.add(url)
        work.append(e)
    if limit > 0:
        work = work[:limit]
    if not work:
        return []

    print(
        f"  [auto-download] {len(work)} image(s) → {output_dir} "
        f"(timeout={timeout}s, workers={max_workers})",
        file=sys.stderr,
    )

    outcomes: list[dict] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(_download_single_image, e, output_dir, timeout, i): e
            for i, e in enumerate(work, 1)
        }
        for fut in as_completed(futures):
            try:
                outcomes.append(fut.result())
            except Exception as exc:  # defensive — worker already catches
                outcomes.append({
                    "url": futures[fut].get("url", ""),
                    "file": "",
                    "status": "fail",
                    "reason": f"worker crash: {exc}",
                    "domain": "",
                    "bytes": 0,
                })

    ok = sum(1 for o in outcomes if o["status"] == "ok")
    skip = sum(1 for o in outcomes if o["status"] == "skip")
    fail = sum(1 for o in outcomes if o["status"] == "fail")
    print(
        f"  [auto-download] done: {ok} downloaded, {skip} skipped (exists), {fail} failed",
        file=sys.stderr,
    )
    return outcomes


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
                verify=False,
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
        description=(
            "PPT Master 的网页搜索工具（Tavily / 百度自动轮询）。\n"
            "\n"
            "LLM 使用要点（完整规格见 references/web-search.md）：\n"
            "  * query 必须写成中文——百度后端对中文 query 的召回率远优于英文，\n"
            "    一律中文可保证两个后端轮询时结果稳定。仅有拉丁文名称的专有\n"
            "    名词可附在中文旁边（例：‘久石让 Joe Hisaishi’）。\n"
            "  * 搜索后自动下载的图片落在工作区的 downloads/ 暂存区（非 images/），\n"
            "    文件名为 img_<sha1_8>.ext。新增图片累计 ≥ 5 张时自动生成增量\n"
            "    缩略图墙 downloads/_montage/montage_batch_NN_*.jpg。downloads/ 受双阈值\n"
            "    配额保护（默认 150 文件 + 300MB）。\n"
            "  * 凭缩略图墙批量判定后，用 --adopt SRC DEST 一次性完成移动+重命名，\n"
            "    将采纳的图片晋升到 images/ 并赋予描述性名称；未采纳的哈希名\n"
            "    文件禁止出现在 design_spec.md / SVG 中（finalize_svg.py 会在后\n"
            "    处理阶段硬门禁）。配额触顶后用 --purge-downloads 清理暂存区。"
        ),
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
        "--project-dir",
        metavar="PATH_OR_NAME",
        default=None,
        help=(
            "Target workspace for auto-download (absolute path, relative path, "
            "or 'workspace'). Overrides PPT_PROJECT_DIR."
        ),
    )
    parser.add_argument(
        "--no-auto-download",
        action="store_true",
        help="Disable the post-search concurrent image download.",
    )
    parser.add_argument(
        "--auto-download-timeout",
        type=int,
        default=_AUTO_DOWNLOAD_TIMEOUT,
        help=f"Per-image HTTP timeout for auto-download (default: {_AUTO_DOWNLOAD_TIMEOUT}s).",
    )
    parser.add_argument(
        "--auto-download-limit",
        type=int,
        default=_AUTO_DOWNLOAD_MAX_IMAGES,
        help=f"Max images auto-downloaded per search (default: {_AUTO_DOWNLOAD_MAX_IMAGES}).",
    )
    parser.add_argument(
        "--downloads-max-files",
        type=int,
        default=_DEFAULT_MAX_FILES,
        help=f"workspace/downloads/ 总文件数上限（默认 {_DEFAULT_MAX_FILES}）。",
    )
    parser.add_argument(
        "--downloads-max-bytes",
        type=int,
        default=_DEFAULT_MAX_BYTES,
        help=(
            f"workspace/downloads/ 总体积上限（字节，默认 "
            f"{_DEFAULT_MAX_BYTES // (1024 * 1024)}MB）。"
        ),
    )
    parser.add_argument(
        "--force-montage",
        action="store_true",
        help="即使新图不足阈值也立即生成增量缩略图墙。",
    )
    parser.add_argument(
        "--no-snapshot",
        action="store_true",
        help="不保存搜索结果的 JSON 快照到 downloads/searches/。",
    )
    parser.add_argument(
        "--adopt",
        nargs=2,
        metavar=("SRC", "DEST"),
        default=None,
        help=(
            "采纳：把 downloads/ 下的文件移动并重命名到 images/ 下的描述性名称。"
            "SRC 可为相对 downloads/ 的文件名或绝对路径；DEST 可为相对 images/ 的文件名。"
        ),
    )
    parser.add_argument(
        "--purge-downloads",
        action="store_true",
        help="清空 downloads/ 下的图片与拼图目录，保留 _state.jsonl 以维持跨会话去重。",
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

    dl = result.get("downloaded_images")
    if dl:
        ok = [o for o in dl if o["status"] == "ok"]
        skipped = [o for o in dl if o["status"] == "skip"]
        failed = [o for o in dl if o["status"] == "fail"]
        print(f"-- Auto-downloaded images: {len(ok)} new, {len(skipped)} skipped, {len(failed)} failed --")
        target = result.get("downloads_dir") or result.get("download_dir")
        if target:
            print(f"   saved to: {target}")
        for o in ok[:20]:
            size_kb = o.get("bytes", 0) // 1024
            print(f"   + {Path(o['file']).name}  ({size_kb}KB)")
        if failed:
            print("   failed:")
            for o in failed[:5]:
                print(f"     - {o['url']} -> {o['reason']}")
        print()

    montage = result.get("montage_batch")
    if montage:
        print(
            f"-- 新增量缩略图墙 batch_{montage['batch_id']:02d} "
            f"({montage['count']} 张新图，共 {len(montage['montages'])} 张 montage) --"
        )
        for name in montage["montages"]:
            print(f"   + {name}")
        print(f"   目录: {montage['dir']}")
        print()

    quota_err = result.get("downloads_quota_error")
    if quota_err:
        print(f"-- ⛔ {quota_err} --\n")


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # --- Utility modes ---
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

    # --- Adopt / purge (task.md §4) ---
    if args.adopt:
        src, dest = args.adopt
        try:
            info = adopt_image(src, dest, project_hint=args.project_dir)
        except Exception as exc:
            print(f"[adopt] 失败: {exc}", file=sys.stderr)
            return 1
        print(
            f"[adopt] {Path(info['src']).name} → {info['dest']}"
            + (" (state updated)" if info.get("state_updated") else ""),
            file=sys.stderr,
        )
        return 0

    if args.purge_downloads:
        info = purge_downloads(project_hint=args.project_dir)
        print(
            f"[purge] 删除 {info['removed']} 个条目于 {info.get('dir')}。"
            f"_state.jsonl 已保留（同 URL 不会不重复下载）。",
            file=sys.stderr,
        )
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
    )

    # Auto-collect image URLs from results
    collected = collect_images_from_result(result)

    # Auto-download to workspace/downloads/ (task.md §1/§3)
    if not args.no_auto_download and collected:
        downloads_dir = resolve_project_downloads_dir(args.project_dir)
        if downloads_dir is None:
            print(
                "  [auto-download] skipped: no target workspace found. "
                "Set PPT_PROJECT_DIR, run inside workspace/, "
                "or pass --project-dir.",
                file=sys.stderr,
            )
        else:
            downloads_dir.mkdir(parents=True, exist_ok=True)
            # Quota check (task.md §2)
            quota_err = _check_quota(
                downloads_dir,
                max_files=args.downloads_max_files,
                max_bytes=args.downloads_max_bytes,
            )
            if quota_err:
                print(f"  [auto-download] {quota_err}", file=sys.stderr)
                result["downloads_dir"] = str(downloads_dir)
                result["downloads_quota_error"] = quota_err
            else:
                # Drop URLs already adopted in previous sessions.
                records_now = _state_load(downloads_dir)
                filtered = _filter_entries_by_state(collected, records_now)
                outcomes = async_download_images(
                    filtered,
                    downloads_dir,
                    timeout=args.auto_download_timeout,
                    limit=args.auto_download_limit,
                )
                # Post-download pipeline: state + analyze + incremental montage
                pipeline = run_post_download_pipeline(
                    downloads_dir,
                    outcomes,
                    query=args.query,
                    force_montage=args.force_montage,
                )
                result["downloaded_images"] = outcomes
                result["downloads_dir"] = str(downloads_dir)
                result["new_files"] = pipeline["new_files"]
                result["montage_batch"] = pipeline["montage_batch"]
                result["analyzed"] = pipeline["analyzed"]

    # Persist raw search JSON snapshot for audit/reuse (task.md §1)
    if not args.no_snapshot and result.get("downloads_dir"):
        try:
            snap = _save_search_snapshot(result, Path(result["downloads_dir"]))
            result["snapshot"] = str(snap)
        except Exception as exc:
            print(f"  [snapshot] failed: {exc}", file=sys.stderr)

    if args.output_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_human(result)

    return 0 if result["results"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
