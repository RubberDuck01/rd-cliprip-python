"""Build script for RD ClipRip.

Produces a single Windows EXE in dist/ using PyInstaller.
Run with: python build.py
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
SOURCE = ROOT / "source"
RESOURCES = SOURCE / "resources"
ICON = RESOURCES / "rd" / "rd-cliprip-logo.ico"
ENTRY = SOURCE / "main.py"

args = [
    sys.executable, "-m", "PyInstaller",
    "--onefile",
    "--windowed",
    f"--icon={ICON}",
    f"--add-data={RESOURCES}{';' if sys.platform == 'win32' else ':'}resources",
    "--name=RD ClipRip",
    f"--paths={SOURCE}",
    str(ENTRY),
]

print("Building RD ClipRip...")
print(f"  Entry : {ENTRY}")
print(f"  Icon  : {ICON}")
print(f"  Output: {ROOT / 'dist' / 'RD ClipRip.exe'}")
print()

result = subprocess.run(args, cwd=ROOT)
if result.returncode == 0:
    print("\nBuild complete! Output: dist/RD ClipRip.exe")
else:
    print(f"\nBuild failed (exit code {result.returncode})")
    sys.exit(result.returncode)
