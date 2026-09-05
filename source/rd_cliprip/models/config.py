import json
import os
from pathlib import Path
from datetime import datetime
from typing import Any

class Config:
    def __init__(self) -> None:
        # Auto Win/Linux paths:
        if os.name == "nt":
            base = Path(os.getenv("APPDATA", Path.home() / "AppData" / "Roaming"))
        else:
            base = Path.home() / ".config"

        self.config_dir = base / "Rubber Duck Softworks" / "ClipRip" / "Settings"
        self.config_file = self.config_dir / "config.json"
        self.data: dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception:
                self.data = self.default_config()
        else:
            self.data = self.default_config()
            self.save()

    def save(self) -> None:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.data["last_updated"] = datetime.now().isoformat()
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def default_config(self) -> dict[str, Any]:
        return {
            "created_date": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "settings": {
                "downloads_dir": str(Path.home() / "Downloads"),
                "auto_update": True,
                "preferred_format": "mp4",
                "preferred_resolution": "1080p",
                "embed_subs": False,
                "cookies_enabled": False,
                "cookies_path": "",
                "clipboard_paste_enabled": True,
            },
            "other": {
                "i_have_donated": False,
            },
        }

    # --- Getters ---
    @property
    def downloads_dir(self) -> str:
        return self.data["settings"]["downloads_dir"]

    @property
    def auto_update(self) -> bool:
        return self.data["settings"]["auto_update"]

    @property
    def preferred_format(self) -> str:
        return self.data["settings"]["preferred_format"]

    @property
    def preferred_resolution(self) -> str:
        return self.data["settings"]["preferred_resolution"]

    @property
    def embed_subs(self) -> bool:
        return self.data["settings"]["embed_subs"]

    @property
    def cookies_enabled(self) -> bool:
        return bool(self.data["settings"].get("cookies_enabled", False))

    @property
    def cookies_path(self) -> str:
        return str(self.data["settings"].get("cookies_path", ""))

    @property
    def clipboard_paste_enabled(self) -> bool:
        return bool(self.data["settings"].get("clipboard_paste_enabled", True))

    @property
    def i_have_donated(self) -> bool:
        return self.data["other"]["i_have_donated"]

    # --- Setters ---
    def set_downloads_dir(self, path: str) -> None:
        self.data["settings"]["downloads_dir"] = path
        self.save()

    def set_auto_update(self, value: bool) -> None:
        self.data["settings"]["auto_update"] = value
        self.save()

    def set_preferred_format(self, value: str) -> None:
        self.data["settings"]["preferred_format"] = value
        self.save()

    def set_preferred_resolution(self, value: str) -> None:
        self.data["settings"]["preferred_resolution"] = value
        self.save()

    def set_embed_subs(self, value: bool) -> None:
        self.data["settings"]["embed_subs"] = value
        self.save()

    def set_cookies_enabled(self, value: bool) -> None:
        self.data["settings"]["cookies_enabled"] = value
        self.save()

    def set_cookies_path(self, path: str) -> None:
        self.data["settings"]["cookies_path"] = path
        self.save()

    def set_clipboard_paste_enabled(self, value: bool) -> None:
        self.data["settings"]["clipboard_paste_enabled"] = value
        self.save()

    def set_i_have_donated(self, value: bool) -> None:
        self.data["other"]["i_have_donated"] = value
        self.save()
