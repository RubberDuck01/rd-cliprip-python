import json
import os
import re
import threading
import urllib.request
from datetime import datetime
from pathlib import Path

SUPPORTED_SITES_URL = (
    "https://raw.githubusercontent.com/yt-dlp/yt-dlp/master/supportedsites.md"
)

_SITE_LINE_RE = re.compile(r"^\s*-\s+\*\*(.+?)\*\*")


def _web_dir() -> Path:
    if os.name == "nt":
        base = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path.home() / ".config"
    return base / "Rubber Duck Softworks" / "ClipRip" / "Data" / "web"


def cache_file() -> Path:
    return _web_dir() / "supported_websites.json"


def _parse_sites(text: str) -> list[str]:
    sites: list[str] = []
    seen: set[str] = set()
    for line in text.splitlines():
        match = _SITE_LINE_RE.match(line)
        if not match:
            continue
        name = match.group(1).strip()
        if name and name not in seen:
            seen.add(name)
            sites.append(name)
    return sites


def fetch_sites(timeout: int = 30) -> list[str] | None:
    """Download the current yt-dlp supportedsites.md and parse the site names."""
    try:
        req = urllib.request.Request(
            SUPPORTED_SITES_URL, headers={"User-Agent": "RD-ClipRip/1.0"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None
    sites = _parse_sites(text)
    return sites or None


def load_cache() -> dict | None:
    """Return {'sites': [...], 'fetched_at': iso} or None when not cached."""
    try:
        if not cache_file().exists():
            return None
        payload = json.loads(cache_file().read_text(encoding="utf-8"))
        sites = payload.get("sites") or []
        return {"sites": sites, "fetched_at": payload.get("fetched_at", "")}
    except Exception:
        return None


def save_cache(sites: list[str]) -> None:
    try:
        path = cache_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "fetched_at": datetime.now().isoformat(),
            "count": len(sites),
            "sites": sites,
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def fetch_and_cache() -> dict | None:
    sites = fetch_sites()
    if sites is None:
        return None
    save_cache(sites)
    return load_cache()


def prefetch_in_background() -> None:
    """Fetch once on first run so the cache is ready before the dialog opens."""
    if load_cache() is not None:
        return

    def _run() -> None:
        fetch_and_cache()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
