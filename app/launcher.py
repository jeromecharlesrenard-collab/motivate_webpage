"""Logic for the MOTIVATE launcher: config, logging, and opening the site.

Runs under pythonw.exe: no console, no print(). Errors are logged and shown
in a native Windows message box (no Tk window is created).
"""

from __future__ import annotations

import ctypes
import json
import logging
import sys
import traceback
import webbrowser
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import TracebackType
from typing import Any
from zoneinfo import ZoneInfo

from app import server
from app.server import MotivateServer

APP_NAME = "MOTIVATE"
PROJECT_DIR = Path(__file__).resolve().parent.parent
SITE_DIR = PROJECT_DIR / "site"
LOG_FILE = PROJECT_DIR / "logs" / "app.log"
CONFIG_FILE = PROJECT_DIR / "config.json"
ERROR_LOG = PROJECT_DIR / "error_log.txt"
BACKUP_DIR = PROJECT_DIR / "assets" / "archives" / "saved"
EDT = ZoneInfo("America/New_York")

DEFAULT_CONFIG: dict[str, Any] = {
    "log_level": "INFO",
    "start_page": "index.html",
    "port": 8765,
    "idle_minutes": 120,
    "auto_upload": True,
}

log = logging.getLogger(__name__)


class EdtFormatter(logging.Formatter):
    """Log formatter that stamps every record in America/New_York time."""

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        stamp = datetime.fromtimestamp(record.created, EDT)
        return stamp.strftime(datefmt or "%Y-%m-%d %H:%M:%S %Z")


def load_config(path: Path = CONFIG_FILE) -> dict[str, Any]:
    """Return config.json merged over the defaults; recreate it if missing."""
    config = dict(DEFAULT_CONFIG)
    if path.exists():
        config.update(json.loads(path.read_text(encoding="utf-8")))
    else:
        path.write_text(json.dumps(config, indent=4) + "\n", encoding="utf-8")
    return config


def setup_logging(level: str = "INFO", log_file: Path = LOG_FILE) -> None:
    """Send all logging to a rotating logs/app.log (1 MB x 5 files)."""
    log_file.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=5, encoding="utf-8")
    handler.setFormatter(EdtFormatter("%(asctime)s | %(levelname)s | %(module)s | %(message)s"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(getattr(logging, level.upper(), logging.INFO))


def show_error(message: str) -> None:
    """Show a native Windows error box (safe under pythonw.exe)."""
    ctypes.windll.user32.MessageBoxW(None, message, f"{APP_NAME} - Error", 0x10 | 0x40000)


def handle_exception(
    exc_type: type[BaseException], exc: BaseException, tb: TracebackType | None
) -> None:
    """sys.excepthook: log any uncaught exception and tell the user."""
    log.critical("Uncaught exception", exc_info=(exc_type, exc, tb))
    show_error(f"{exc_type.__name__}: {exc}\n\nDetails in logs\\app.log")


def write_early_error(exc: BaseException) -> None:
    """Record a failure that happened before logging was available."""
    stamp = datetime.now(EDT).strftime("%Y-%m-%d %H:%M:%S %Z")
    ERROR_LOG.write_text(f"{stamp}\n{''.join(traceback.format_exception(exc))}", encoding="utf-8")
    show_error(f"{APP_NAME} failed to start:\n{exc}\n\nDetails in error_log.txt")


def start_page_path(config: dict[str, Any], site_dir: Path = SITE_DIR) -> Path:
    """Resolve the page to open; fall back to index.html if the name is invalid."""
    page = (site_dir / config.get("start_page", "index.html")).resolve()
    if page.parent != site_dir.resolve() or page.suffix != ".html" or not page.exists():
        log.warning("Start page %r not found; using index.html", config.get("start_page"))
        page = site_dir / "index.html"
    if not page.exists():
        raise FileNotFoundError(f"Missing site page: {page}")
    return page


def open_site(config: dict[str, Any]) -> MotivateServer | None:
    """Open the start page in the default browser.

    Starts the local server (needed by the page builder) and returns it for the
    caller to run; returns None if a MOTIVATE server is already running, or if
    the port is busy (the page then opens from disk, builder read-only).
    """
    page = start_page_path(config)
    port = int(config.get("port", 8765))
    url = f"http://127.0.0.1:{port}/{page.name}"
    srv = None
    version = server.running_version(port)
    if version is not None and version < server.API_VERSION:
        log.info("Older server (version %s) running on port %s; replacing it", version, port)
        if not server.stop_server(port):
            raise RuntimeError(
                "An older MOTIVATE server is still running and could not be stopped. "
                "Close it in Task Manager (pythonw.exe), then open MOTIVATE again."
            )
        version = None
    if version is not None:
        log.info("Server already running on port %s", port)
    else:
        try:
            srv = MotivateServer(port, SITE_DIR, BACKUP_DIR, bool(config.get("auto_upload", True)))
        except OSError as exc:
            log.warning("Port %s unavailable (%s); opening the page from disk", port, exc)
            url = page.as_uri()
    log.info("Opening %s", url)
    if not webbrowser.open(url):
        raise RuntimeError(f"No web browser could open {url}")
    return srv
