import json
import re
import subprocess
import sys
import locale
import urllib.request
from pathlib import Path
from typing import Any
from PyQt6.QtCore import QObject, pyqtSignal

_PROGRESS_RE = re.compile(r"(\d{1,3}(?:\.\d+)?)%")
YTDLP_EXE = "yt-dlp.exe"
YTDLP_DOWNLOAD_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"

# Suppress the console window that would otherwise flash on Windows when
# spawning child processes from a --windowed PyInstaller bundle.
_SUBPROCESS_FLAGS: dict = (
    {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}
)


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


def find_ytdlp_exe() -> str | None:
    path = get_tools_ytdlp_path()
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
) -> list[str]:
    """Build the yt-dlp argument list for video downloads."""
    ytdlp = find_ytdlp_exe()
    if not ytdlp:
        raise RuntimeError("yt-dlp is not installed.")

    args = [
        ytdlp,
        "--newline",
        "--progress",
        "--no-simulate",
        "--no-playlist",
        "--no-check-certificates",
        "-o",
        str(Path(output_dir) / "%(title).200s.%(ext)s"),
        url,
    ]

    # Format selection for video
    if preferred_format == "mp4":
        # Best mp4 video + audio merged
        fmt = f"bestvideo[ext=mp4][height<={_parse_resolution(preferred_resolution)}]+bestaudio[ext=m4a]/best[ext=mp4]/best"
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

    return args


def _parse_resolution(res: str) -> int:
    """Convert a resolution string like '1080p' or '2160p' to a numeric height."""
    return int(res.lower().replace("p", ""))


# ---------------------------------------------------------------------------
#  Download worker (runs yt-dlp in a subprocess on a QThread)
# ---------------------------------------------------------------------------

class DownloadWorker(QObject):
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    output_file = pyqtSignal(str)
    download_size_mb = pyqtSignal(float)  # emitted once after process exits

    def __init__(
        self,
        url: str,
        output_dir: str,
        preferred_format: str,
        preferred_resolution: str,
        embed_subs: bool,
        is_playlist: bool = False,
        cookies_enabled: bool = False,
        cookies_path: str = "",
    ) -> None:
        super().__init__()
        self.url = url
        self.output_dir = output_dir
        self.preferred_format = (preferred_format or "mp4").lower()
        self.preferred_resolution = preferred_resolution or "1080p"
        self.embed_subs = embed_subs
        self.is_playlist = is_playlist
        self.cookies_enabled = cookies_enabled
        self.cookies_path = cookies_path

    def run(self) -> None:
        ytdlp = find_ytdlp_exe()
        if not ytdlp:
            self.error.emit("yt-dlp executable not found!")
            return

        # Snapshot existing video files so we can diff after download
        output_path = Path(self.output_dir)
        video_exts = {".mp4", ".mkv", ".webm", ".avi", ".mov", ".flv"}
        try:
            before_files: set[str] = {
                str(f)
                for f in output_path.rglob("*")
                if f.is_file() and f.suffix.lower() in video_exts
            }
        except Exception:
            before_files = set()

        output_template = (
            "%(playlist_title)s/%(title).200s.%(ext)s"
            if self.is_playlist
            else "%(title).200s.%(ext)s"
        )

        args = build_ytdlp_args(
            url=self.url,
            output_dir=self.output_dir,
            preferred_format=self.preferred_format,
            preferred_resolution=self.preferred_resolution,
            embed_subs=self.embed_subs,
            cookies_path=self.cookies_path if self.cookies_enabled else None,
        )

        # Override the output template with the playlist-aware one
        # Remove the old -o and add our custom one
        for i, arg in enumerate(args):
            if arg == "-o":
                args[i + 1] = str(output_path / output_template)
                break

        if not self.is_playlist:
            # --no-playlist is already in build_ytdlp_args; for playlists we remove it
            if "--no-playlist" in args:
                args.remove("--no-playlist")

        try:
            proc = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                **_SUBPROCESS_FLAGS,
            )
        except Exception as ex:
            self.error.emit(f"Failed to start yt-dlp: {ex}")
            return

        last_line = ""
        assert proc.stdout is not None
        for raw_line in proc.stdout:
            line = _decode_output(raw_line).strip()
            last_line = line
            match = _PROGRESS_RE.search(line)
            if match:
                self.progress.emit(int(float(match.group(1))))
            # Detect output file destination from yt-dlp output
            if "[download] Destination:" in line:
                dest = line.split("Destination:", 1)[-1].strip()
                self.output_file.emit(dest)

        rc = proc.wait()
        if rc == 0:
            # Compute size of newly created video files
            total_size_mb = 0.0
            try:
                for f in output_path.rglob("*"):
                    if f.is_file() and f.suffix.lower() in video_exts and str(f) not in before_files:
                        total_size_mb += f.stat().st_size / (1024 * 1024)
            except Exception:
                pass
            self.download_size_mb.emit(total_size_mb)
            self.finished.emit("Download completed successfully!")
        else:
            self.error.emit(last_line or f"yt-dlp failed with exit code: {rc}")
