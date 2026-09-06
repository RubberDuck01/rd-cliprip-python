import json
import locale
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

_PROGRESS_RE = re.compile(r"(\d{1,3}(?:\.\d+)?)%")
YTDLP_EXE = "yt-dlp.exe"
YTDLP_DOWNLOAD_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
FFMPEG_EXE = "ffmpeg.exe"
FFMPEG_DOWNLOAD_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

# Suppress the console window that would otherwise flash on Windows when
# spawning child processes from a --windowed PyInstaller bundle.
_SUBPROCESS_FLAGS: dict = (
    {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}
)

# File extensions we treat as finished media output during finalize.
VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".avi", ".mov", ".flv", ".ts", ".m4v"}

# Strip a trailing yt-dlp id suffix: "Title [aBc123]" -> "Title"
_ID_SUFFIX_RE = re.compile(r"\s*\[[^\]]+\]\s*$")

# ffmpeg "-i" reports container duration on stderr as:  Duration: 01:23:45.67
_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+)")

_SIZE_RE = re.compile(r"of\s+~?([\d.,]+\s?[KMGT]?i?B)")
_SPEED_RE = re.compile(r"at\s+(?:Unknown\s?)?([\d.,]+\s?[KMGT]?i?B/s)")
_ETA_RE = re.compile(r"ETA\s+([0-9:]+)")


def parse_progress_line(line: str) -> dict[str, Any]:
    """Extract percent / total size / speed / ETA from a yt-dlp progress line.

    Returns dict with keys: percent (int or None), total, speed, eta (str).
    """
    info: dict[str, Any] = {"percent": None, "total": "", "speed": "", "eta": ""}
    match = _PROGRESS_RE.search(line)
    if not match:
        return info
    info["percent"] = int(float(match.group(1)))

    size = _SIZE_RE.search(line)
    if size:
        info["total"] = size.group(1).replace(" ", "")
    speed = _SPEED_RE.search(line)
    if speed:
        info["speed"] = speed.group(1).replace(" ", "")
    eta = _ETA_RE.search(line)
    if eta:
        info["eta"] = eta.group(1)
    return info

# Error text that means the URL itself is dead/permanently broken. These must
# never be auto-retried (retrying just hammers a link that will never work).
_FATAL_HINTS = (
    "404",
    "403",
    "410",
    "not found",
    "not available",
    "is unavailable",
    "video unavailable",
    "content unavailable",
    "media is not available",
    "no longer exists",
    "has been removed",
    "removed by",
    "private video",
    "members only",
    "does not exist",
    "invalid url",
    "is not a valid",
    "unsupported url",
    "not a valid url",
    "sign in to confirm",
    "account terminated",
    "executable not found",
)


def is_fatal_error(message: str) -> bool:
    """True when an error message means retrying will never help."""
    if not message:
        return True
    lowered = message.lower()
    return any(hint in lowered for hint in _FATAL_HINTS)


def parse_ffmpeg_duration(text: str) -> int:
    """Extract seconds from ffmpeg's 'Duration: HH:MM:SS.xx' line. 0 if absent."""
    match = _DURATION_RE.search(text or "")
    if not match:
        return 0
    h, m, s = (int(g) for g in match.groups())
    return h * 3600 + m * 60 + s


def _decode_output(raw: bytes) -> str:
    candidates = ["utf-8", locale.getpreferredencoding(False), "cp1251", "cp866", "latin-1"]
    seen: set[str] = set()

    for enc in candidates:
        if not enc or enc in seen:
            continue
        seen.add(enc)
        try:
            return raw.decode(enc)
        except Exception:
            continue

    return raw.decode("utf-8", errors="replace")


def get_tools_dir() -> Path:
    base = Path(sys.argv[0]).resolve().parent
    tools_dir = base / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    return tools_dir


def get_tools_ytdlp_path() -> Path:
    return get_tools_dir() / YTDLP_EXE


def get_tools_ffmpeg_path() -> Path:
    return get_tools_dir() / FFMPEG_EXE


def find_ytdlp_exe() -> str | None:
    path = get_tools_ytdlp_path()
    if path.exists():
        return str(path)
    return None


def find_ffmpeg_exe() -> str | None:
    path = get_tools_ffmpeg_path()
    if path.exists():
        return str(path)
    return None


def _run_tool(
    command: list[str], timeout: int
) -> subprocess.CompletedProcess[bytes] | None:
    try:
        return subprocess.run(
            command, capture_output=True, timeout=timeout, **_SUBPROCESS_FLAGS
        )
    except Exception:
        return None


def get_video_metadata(url: str) -> dict[str, Any] | None:
    ytdlp = find_ytdlp_exe()
    if not ytdlp:
        return None

    result = _run_tool(
        [
            ytdlp,
            "--dump-single-json",
            "--no-warnings",
            "--skip-download",
            "--no-playlist",
            url,
        ],
        timeout=15,
    )
    if result is None or result.returncode != 0:
        return None

    try:
        return json.loads(_decode_output(result.stdout))
    except Exception:
        return None


def get_ytdlp_version() -> str | None:
    ytdlp = find_ytdlp_exe()
    if not ytdlp:
        return None

    result = _run_tool([ytdlp, "--version"], timeout=10)
    if result is not None and result.returncode == 0:
        return _decode_output(result.stdout).strip()
    return None


def install_ytdlp() -> tuple[bool, str]:
    destination = get_tools_dir() / YTDLP_EXE
    try:
        with urllib.request.urlopen(YTDLP_DOWNLOAD_URL, timeout=30) as response:
            destination.write_bytes(response.read())
        return True, f"yt-dlp installed to {destination}"
    except Exception as ex:
        return False, f"Failed to install yt-dlp: {ex}"


def update_ytdlp() -> tuple[bool, str]:
    ytdlp = find_ytdlp_exe()
    if not ytdlp:
        return False, "yt-dlp is not installed."

    try:
        result = subprocess.run(
            [ytdlp, "-U"], capture_output=True, timeout=60, **_SUBPROCESS_FLAGS
        )
    except Exception as ex:
        return False, f"Failed to run yt-dlp update: {ex}"

    output = _decode_output(result.stdout or result.stderr).strip()
    if result.returncode == 0:
        return True, output or "yt-dlp update command completed."
    return False, output or "yt-dlp update failed."


def _extract_ffmpeg(zip_path: Path, destination: Path) -> None:
    with zipfile.ZipFile(zip_path) as archive:
        ffmpeg_member = next(
            (
                name
                for name in archive.namelist()
                if name.lower().endswith("/bin/ffmpeg.exe")
            ),
            None,
        )
        if ffmpeg_member is None:
            raise FileNotFoundError("ffmpeg.exe was not found in the downloaded archive.")
        with archive.open(ffmpeg_member) as source, destination.open("wb") as target:
            target.write(source.read())


def install_or_update_ffmpeg() -> tuple[bool, str]:
    """Download ffmpeg (gyan.dev essentials build) and install it into tools/."""
    destination = get_tools_ffmpeg_path()
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = Path(temp_dir) / "ffmpeg.zip"
            with urllib.request.urlopen(FFMPEG_DOWNLOAD_URL, timeout=60) as response:
                archive_path.write_bytes(response.read())
            _extract_ffmpeg(archive_path, destination)
        return True, f"FFmpeg installed to {destination}"
    except Exception as ex:
        return False, f"Failed to install or update FFmpeg: {ex}"


def get_ffmpeg_version() -> str | None:
    ffmpeg = find_ffmpeg_exe()
    if not ffmpeg:
        return None
    result = _run_tool([ffmpeg, "-version"], timeout=10)
    if result is not None and result.returncode == 0:
        lines = _decode_output(result.stdout).splitlines()
        return lines[0].strip() if lines else None
    return None


def get_playlist_info(url: str) -> tuple[bool, str, int]:
    """Return (is_playlist, playlist_title, track_count) without downloading."""
    ytdlp = find_ytdlp_exe()
    if not ytdlp:
        return False, "", 0

    result = _run_tool(
        [ytdlp, "--flat-playlist", "--dump-single-json", "--no-warnings", url],
        timeout=20,
    )
    if result is None or result.returncode != 0:
        return False, "", 0

    try:
        data = json.loads(_decode_output(result.stdout))
        if data.get("_type") == "playlist":
            title = str(
                data.get("title") or data.get("playlist_title") or "Playlist"
            ).strip()
            count = len(data.get("entries") or []) or int(
                data.get("playlist_count") or 0
            )
            return True, title, count
        return False, "", 0
    except Exception:
        return False, "", 0


def fetch_title(url: str) -> str | None:
    """Fetch a display title for a URL (single video or playlist) or None.

    Uses a flat, no-download query so it stays light even for playlists.
    """
    ytdlp = find_ytdlp_exe()
    if not ytdlp:
        return None

    result = _run_tool(
        [ytdlp, "--flat-playlist", "--dump-single-json", "--no-warnings", url],
        timeout=20,
    )
    if result is None or result.returncode != 0:
        return None

    try:
        data = json.loads(_decode_output(result.stdout))
    except Exception:
        return None

    if not isinstance(data, dict):
        return None
    if data.get("_type") == "playlist":
        title = str(data.get("title") or data.get("playlist_title") or "").strip()
    else:
        title = str(data.get("title") or data.get("fulltitle") or "").strip()
    return title or None


def get_video_info(url: str) -> dict[str, Any]:
    """Get title, duration, filesize for a single video."""
    metadata = get_video_metadata(url)
    if metadata is None:
        return {"title": "Unknown", "size": "Unknown", "duration": "Unknown"}

    title = str(metadata.get("title") or metadata.get("fulltitle") or "Unknown")
    duration = int(metadata.get("duration") or 0)
    filesize = int(metadata.get("filesize") or metadata.get("filesize_approx") or 0)

    m, s = divmod(duration, 60)
    h, m = divmod(m, 60)
    if h > 0:
        duration_str = f"{h:02}:{m:02}:{s:02}"
    else:
        duration_str = f"{m:02}:{s:02}"

    size_str = _format_size_bytes(filesize) if filesize > 0 else "Unknown"
    return {"title": title, "size": size_str, "duration": duration_str}


def get_video_metrics(url: str) -> tuple[float, int]:
    """Return (size_mb, duration_sec) for tracking stats."""
    metadata = get_video_metadata(url)
    if metadata is None:
        return 0.0, 0

    filesize = int(metadata.get("filesize") or metadata.get("filesize_approx") or 0)
    duration = int(metadata.get("duration") or 0)

    size_mb = filesize / (1024 * 1024) if filesize > 0 else 0.0
    return size_mb, duration


def _format_size_bytes(size: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    idx = 0
    while value >= 1024 and idx < len(units) - 1:
        value /= 1024
        idx += 1
    return f"{value:.2f} {units[idx]}"


# ---------------------------------------------------------------------------
#  Build yt-dlp options for video downloads
# ---------------------------------------------------------------------------

def build_ytdlp_args(
    url: str,
    output_dir: str,
    preferred_format: str,
    preferred_resolution: str,
    embed_subs: bool,
    cookies_path: str | None = None,
    output_template: str | None = None,
    ffmpeg_location: str | None = None,
    remux_to_mp4: bool = False,
    no_playlist: bool = True,
    rate_limit_mbps: float = 0.0,
) -> list[str]:
    """Build the yt-dlp argument list for video downloads.

    ``output_template`` may be an absolute path template (e.g. a staging dir)
    or None to fall back to ``<output_dir>/%(title).200s.%(ext)s``.
    ``rate_limit_mbps`` caps each download's speed (0 = unlimited).
    """
    ytdlp = find_ytdlp_exe()
    if not ytdlp:
        raise RuntimeError("yt-dlp is not installed.")

    if output_template is None:
        output_template = "%(title).200s.%(ext)s"

    args = [
        ytdlp,
        "--newline",
        "--progress",
        "--no-simulate",
        "--no-check-certificates",
        "-o",
        str(Path(output_dir) / output_template),
        url,
    ]

    if no_playlist:
        args.insert(2, "--no-playlist")

    # Format selection for video
    if preferred_format == "mp4":
        # Prefer a single-file MP4 with broadly-compatible codecs. AV1-in-MP4
        # plays fine but many thumbnailers/cloud services (e.g. MEGA) can't
        # decode it, so AV1 is only used as a last resort.
        height = _parse_resolution(preferred_resolution)
        fmt = (
            f"best[ext=mp4][vcodec=h264][height<={height}]"
            f"/best[ext=mp4][vcodec!=av1][height<={height}]"
            f"/bestvideo[vcodec=h264][height<={height}]+bestaudio[ext=m4a]"
            f"/bestvideo[vcodec!=av1][height<={height}]+bestaudio[ext=m4a]"
            f"/best"
        )
    elif preferred_format == "mkv":
        fmt = f"bestvideo[height<={_parse_resolution(preferred_resolution)}]+bestaudio/best"
        args.insert(2, "--merge-output-format")
        args.insert(3, "mkv")
    elif preferred_format == "webm":
        fmt = f"bestvideo[ext=webm][height<={_parse_resolution(preferred_resolution)}]+bestaudio[ext=webm]/best[ext=webm]/best"
    else:
        fmt = f"bestvideo[height<={_parse_resolution(preferred_resolution)}]+bestaudio/best"

    args.insert(2, "-f")
    args.insert(3, fmt)

    # Embed subtitles
    if embed_subs:
        args.insert(2, "--embed-subs")

    # Cookies
    if cookies_path and Path(cookies_path).exists():
        args.insert(2, "--cookies")
        args.insert(3, cookies_path)

    # ffmpeg location (for merging/remuxing)
    if ffmpeg_location:
        args.insert(2, "--ffmpeg-location")
        args.insert(3, ffmpeg_location)

    # Per-agent speed cap (yt-dlp accepts K/M/G suffixes)
    if rate_limit_mbps and rate_limit_mbps > 0:
        args.insert(2, "--limit-rate")
        args.insert(3, f"{rate_limit_mbps:.2f}M")

    # Remux final container to MP4 (needs ffmpeg)
    if remux_to_mp4:
        args.insert(2, "--remux-video")
        args.insert(3, "mp4")

    return args


def _parse_resolution(res: str) -> int:
    """Convert a resolution string like '1080p' or '2160p' to a numeric height."""
    return int(res.lower().replace("p", ""))


# ---------------------------------------------------------------------------
#  Staging + finalize helpers
# ---------------------------------------------------------------------------

def clean_name(name: str) -> str:
    """Remove a trailing yt-dlp id suffix: 'Title [aBc123]' -> 'Title'."""
    cleaned = _ID_SUFFIX_RE.sub("", name).strip()
    return cleaned or name.strip()


def unique_dest_path(dest_dir: Path, stem: str, suffix: str) -> Path:
    """Return a non-colliding path, appending (1), (2), ... when needed."""
    dest = dest_dir / f"{stem}{suffix}"
    counter = 1
    while dest.exists():
        dest = dest_dir / f"{stem} ({counter}){suffix}"
        counter += 1
    return dest


def finalize_download(staging_dir: Path, output_dir: Path) -> tuple[list[str], float]:
    """Move every finished media file out of the staging dir into the output dir.

    Files are renamed to a clean title (id suffix stripped) and de-duplicated.
    Returns (list of final file paths, total size in MB).
    """
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    dest_paths: list[str] = []
    total_size_mb = 0.0

    try:
        files = [
            f
            for f in staging_dir.rglob("*")
            if f.is_file() and f.suffix.lower() in VIDEO_EXTS
        ]
    except Exception:
        files = []

    for src in sorted(files, key=lambda f: str(f).lower()):
        try:
            clean_stem = clean_name(src.stem)
            dest = unique_dest_path(output, clean_stem, src.suffix)
            shutil.move(str(src), str(dest))
            dest_paths.append(str(dest))
            try:
                total_size_mb += dest.stat().st_size / (1024 * 1024)
            except Exception:
                pass
        except Exception:
            continue

    return dest_paths, total_size_mb


def probe_duration(path: Path, ffmpeg_exe: str) -> int:
    """Best-effort media duration in seconds from an ffmpeg -i header probe."""
    if not ffmpeg_exe:
        return 0
    try:
        result = subprocess.run(
            [ffmpeg_exe, "-i", str(path)],
            capture_output=True,
            timeout=20,
            **_SUBPROCESS_FLAGS,
        )
    except Exception:
        return 0
    text = _decode_output(result.stdout or b"") + _decode_output(result.stderr or b"")
    return parse_ffmpeg_duration(text)


# ---------------------------------------------------------------------------
#  Single-item download job (runs in a plain worker thread)
# ---------------------------------------------------------------------------

def run_single_item(
    item_id: str,
    url: str,
    staging_dir: Path,
    output_dir: str,
    preferred_format: str,
    preferred_resolution: str,
    embed_subs: bool,
    cookies_enabled: bool = False,
    cookies_path: str = "",
    allow_playlist: bool = True,
    remux_to_mp4: bool = False,
    ffmpeg_location: str | None = None,
    ffmpeg_exe: str | None = None,
    rate_limit_mbps: float = 0.0,
    on_progress: Any = None,
    register_proc: Any = None,
    unregister_proc: Any = None,
) -> dict[str, Any]:
    """Download one URL into ``staging_dir`` and finalize it into ``output_dir``.

    ``register_proc``/``unregister_proc`` are optional callables used by the
    caller to track the live subprocess handle (for cancellation).
    Returns a result dict with: item_id, status ("completed"/"failed"),
    message, rc, dest_paths, size_mb, duration_sec.
    """
    ytdlp = find_ytdlp_exe()
    if not ytdlp:
        return {
            "item_id": item_id,
            "status": "failed",
            "message": "yt-dlp executable not found!",
            "rc": -1,
            "dest_paths": [],
            "size_mb": 0.0,
            "duration_sec": 0,
        }

    staging_dir.mkdir(parents=True, exist_ok=True)
    output_template = "%(title)s [%(id)s].%(ext)s"

    try:
        args = build_ytdlp_args(
            url=url,
            output_dir=str(staging_dir),
            preferred_format=preferred_format,
            preferred_resolution=preferred_resolution,
            embed_subs=embed_subs,
            cookies_path=cookies_path if cookies_enabled else None,
            output_template=output_template,
            ffmpeg_location=ffmpeg_location,
            remux_to_mp4=remux_to_mp4,
            no_playlist=not allow_playlist,
            rate_limit_mbps=rate_limit_mbps,
        )
    except Exception as ex:
        return {
            "item_id": item_id,
            "status": "failed",
            "message": f"Failed to build yt-dlp arguments: {ex}",
            "rc": -1,
            "dest_paths": [],
            "size_mb": 0.0,
            "duration_sec": 0,
        }

    proc: subprocess.Popen | None = None
    try:
        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            **_SUBPROCESS_FLAGS,
        )
    except Exception as ex:
        return {
            "item_id": item_id,
            "status": "failed",
            "message": f"Failed to start yt-dlp: {ex}",
            "rc": -1,
            "dest_paths": [],
            "size_mb": 0.0,
            "duration_sec": 0,
        }

    if register_proc:
        try:
            register_proc(item_id, proc)
        except Exception:
            pass

    last_line = ""
    try:
        assert proc.stdout is not None
        for raw_line in proc.stdout:
            line = _decode_output(raw_line).strip()
            if line:
                last_line = line
            info = parse_progress_line(line)
            if info["percent"] is not None and on_progress:
                try:
                    on_progress(item_id, info)
                except Exception:
                    pass
    finally:
        if unregister_proc:
            try:
                unregister_proc(item_id)
            except Exception:
                pass

    rc = proc.wait()

    if rc == 0:
        dest_paths, size_mb = finalize_download(staging_dir, Path(output_dir))
        if dest_paths:
            duration_sec = 0
            if ffmpeg_exe:
                for p in dest_paths:
                    try:
                        duration_sec += probe_duration(Path(p), ffmpeg_exe)
                    except Exception:
                        pass
            return {
                "item_id": item_id,
                "status": "completed",
                "message": f"Downloaded {len(dest_paths)} file(s).",
                "rc": rc,
                "dest_paths": dest_paths,
                "size_mb": size_mb,
                "duration_sec": duration_sec,
            }
        return {
            "item_id": item_id,
            "status": "failed",
            "message": last_line or "yt-dlp finished but no video file was found.",
            "rc": rc,
            "dest_paths": [],
            "size_mb": 0.0,
            "duration_sec": 0,
        }

    return {
        "item_id": item_id,
        "status": "failed",
        "message": last_line or f"yt-dlp failed with exit code: {rc}",
        "rc": rc,
        "dest_paths": [],
        "size_mb": 0.0,
        "duration_sec": 0,
    }
