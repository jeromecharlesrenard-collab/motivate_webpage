"""MOTIVATE entry point: set up logging, load config, open the webpage, run the local server.

Launch with: .venv\\Scripts\\pythonw.exe main.py  (or the MOTIVATE.lnk shortcut)
"""

import logging
import sys


def main() -> None:
    """Start logging, then open the site in the default browser."""
    try:
        from app import launcher
    except Exception as exc:  # noqa: BLE001 - nothing is logged yet
        import ctypes
        import traceback
        from pathlib import Path

        (Path(__file__).resolve().parent / "error_log.txt").write_text(
            "".join(traceback.format_exception(exc)), encoding="utf-8"
        )
        ctypes.windll.user32.MessageBoxW(
            None, f"MOTIVATE failed to start:\n{exc}\n\nDetails in error_log.txt", "MOTIVATE - Error", 0x10
        )
        return

    try:
        config = launcher.load_config()
        launcher.setup_logging(config.get("log_level", "INFO"))
    except Exception as exc:  # noqa: BLE001 - logging is not available yet
        launcher.write_early_error(exc)
        return

    sys.excepthook = launcher.handle_exception
    log = logging.getLogger("main")
    log.info("Startup")
    try:
        srv = launcher.open_site(config)
        if srv is not None:
            srv.serve_until_idle(float(config.get("idle_minutes", 120)))
    except Exception as exc:  # noqa: BLE001 - report every failure to the user
        log.exception("Could not open the site")
        launcher.show_error(f"Could not open the MOTIVATE page:\n{exc}\n\nDetails in logs\\app.log")
    finally:
        log.info("Shutdown")


if __name__ == "__main__":
    main()
