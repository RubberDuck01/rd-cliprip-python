import json
import threading
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

# Lightweight JSON endpoints that report the current public IP + location.
_IPWHOIS_URL = "https://ipwho.is/"

# Generic providers / hosting ranges commonly associated with VPN exit nodes.
_VPN_HINTS = (
    "vpn",
    "proxy",
    "mullvad",
    "nordvpn",
    "expressvpn",
    "surfshark",
    "protonvpn",
    "private internet access",
    "windscribe",
    "cyberghost",
    "private relay",
    "openvpn",
    "wireguard",
)


@dataclass
class NetworkStatus:
    connected: bool = False
    ip: str = ""
    country: str = ""
    country_code: str = ""
    isp: str = ""
    asn: str = ""
    vpn_hint: bool = False
    error: str = ""
    checked_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def display_text(self) -> str:
        """Short human-readable label for the footer pill."""
        if not self.connected:
            return "● Offline"
        parts = ["● Online"]
        if self.ip:
            parts.append(self.ip)
        if self.country_code:
            parts.append(self._flag(self.country_code))
        elif self.country:
            parts.append(self.country)
        text = "  ·  ".join(parts)
        if self.vpn_hint:
            text += "  (VPN)"
        return text

    def tooltip(self) -> str:
        if not self.connected:
            reason = f"\n{self.error}" if self.error else ""
            return f"Not connected to the internet.{reason}"
        lines = ["Connection details:"]
        lines.append(f"IP: {self.ip or 'unknown'}")
        if self.country or self.country_code:
            lines.append(f"Country: {self.country or self.country_code}")
        if self.isp:
            lines.append(f"Provider: {self.isp}")
        if self.asn:
            lines.append(f"ASN: {self.asn}")
        if self.vpn_hint:
            lines.append("Note: This connection looks like a VPN/proxy.")
        return "\n".join(lines)

    @staticmethod
    def _flag(country_code: str) -> str:
        code = country_code.strip().upper()
        if len(code) != 2 or not code.isalpha():
            return country_code
        return "".join(chr(ord(c) + 127397) for c in code)


def _http_json(url: str, timeout: int) -> dict | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "RD-ClipRip/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read().decode("utf-8", errors="replace")
        return json.loads(data)
    except Exception:
        return None


def _looks_like_vpn(isp: str, org: str) -> bool:
    blob = f"{isp} {org}".lower()
    return any(hint in blob for hint in _VPN_HINTS)


def check_network(timeout: int = 6) -> NetworkStatus:
    """Query the current network state. Never raises."""
    status = NetworkStatus(checked_at=datetime.now().isoformat())

    data = _http_json(_IPWHOIS_URL, timeout)
    if data is None:
        status.connected = False
        status.error = "Timed out contacting the lookup service."
        return status

    if not data.get("success", True):
        status.connected = False
        status.error = str(data.get("message", "Lookup service error."))
        return status

    status.connected = True
    status.ip = str(data.get("ip", ""))
    status.country = str(data.get("country", ""))
    status.country_code = str(data.get("country_code", "")).upper()

    conn = data.get("connection") or {}
    status.isp = str(conn.get("isp", ""))
    status.asn = str(conn.get("asn", ""))
    status.vpn_hint = _looks_like_vpn(status.isp, str(conn.get("org", "")))
    return status


class NetworkMonitor(QObject):
    """Periodically checks connectivity and public network identity.

    Checks run on a background thread so the UI never blocks; results are
    delivered to the GUI thread via ``status_changed``.
    """

    status_changed = pyqtSignal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.check_now)
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self.latest = NetworkStatus()

    def start(self, interval_seconds: int) -> None:
        self._timer.start(max(5, interval_seconds) * 1000)
        self.check_now()

    def stop(self) -> None:
        self._timer.stop()

    def set_interval(self, interval_seconds: int) -> None:
        self._timer.setInterval(max(5, interval_seconds) * 1000)

    def check_now(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._thread = threading.Thread(target=self._run_check, daemon=True)
            self._thread.start()

    def _run_check(self) -> None:
        status = check_network()
        self.latest = status
        self.status_changed.emit(status)
