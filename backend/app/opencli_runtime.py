from __future__ import annotations

import platform
import shutil
import subprocess

from app.config import settings


def opencli_path() -> str:
    return shutil.which(settings.opencli_path) or shutil.which("opencli") or ""


def opencli_window_args() -> list[str]:
    mode = settings.opencli_window_mode
    return ["--window", mode] if mode else []


def prepare_opencli_browser(opencli: str, site_url: str) -> None:
    if not settings.opencli_preflight_enabled or settings.opencli_window_mode != "foreground":
        return
    _ensure_chrome_window(site_url)
    _wake_opencli_bridge(opencli)


def _ensure_chrome_window(site_url: str) -> None:
    if platform.system() != "Darwin" or not shutil.which("open"):
        return
    try:
        running = subprocess.run(["pgrep", "-x", "Google Chrome"], capture_output=True, text=True, timeout=3)
    except Exception:
        _open_chrome(site_url)
        return
    if running.returncode != 0:
        _open_chrome(site_url)
        return
    try:
        windows = subprocess.run(
            ["osascript", "-e", 'tell application "Google Chrome" to count windows'],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if windows.returncode != 0 or int((windows.stdout or "0").strip() or "0") <= 0:
            _open_chrome(site_url)
    except Exception:
        _open_chrome(site_url)


def _open_chrome(site_url: str) -> None:
    try:
        subprocess.run(["open", "-a", "Google Chrome", site_url], check=False, timeout=5)
    except Exception:
        return


def _wake_opencli_bridge(opencli: str) -> None:
    try:
        status = subprocess.run([opencli, "daemon", "status"], capture_output=True, text=True, timeout=5)
    except Exception:
        return
    output = "\n".join(part for part in [status.stdout, status.stderr] if part)
    if status.returncode == 0 and "Extension: connected" in output:
        return
    try:
        subprocess.run([opencli, "doctor"], capture_output=True, text=True, timeout=20)
    except Exception:
        return
