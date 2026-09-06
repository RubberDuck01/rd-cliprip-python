import sys
from pathlib import Path


def get_resources_dir() -> Path:
    """Return the path to the bundled resources folder.

    When running from a PyInstaller --onefile build, extracted files live
    under sys._MEIPASS.  In a normal dev environment the resources folder
    sits two levels above this file (source/resources/).
    """
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "resources"  # type: ignore[attr-defined]
    return Path(__file__).parent.parent / "resources"
