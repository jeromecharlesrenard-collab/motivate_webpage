"""Local web server for MOTIVATE: serves site/ and the page builder API.

API: GET /api/ping, GET /api/page?n=N, POST /api/preview, /api/create, /api/update, /api/shutdown.
Listens on 127.0.0.1 only. The server stops by itself after `idle_minutes`
without any request (open pages ping it every minute).
"""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from app import page_builder

log = logging.getLogger(__name__)

MAX_BODY = 1_000_000
API_VERSION = 2          # bump when the API changes; the launcher replaces an older server


class MotivateServer(ThreadingHTTPServer):
    """HTTP server that remembers its site folder and the time of the last request."""

    daemon_threads = True

    def __init__(self, port: int, site_dir: Path, backup_dir: Path) -> None:
        self.site_dir = site_dir
        self.backup_dir = backup_dir
        self.last_request = time.monotonic()
        self.write_lock = threading.Lock()
        super().__init__(("127.0.0.1", port), partial(Handler, directory=str(site_dir)))

    def serve_until_idle(self, idle_minutes: float) -> None:
        """Serve requests; shut down after idle_minutes with no requests."""
        def watchdog() -> None:
            while True:
                time.sleep(30)
                if time.monotonic() - self.last_request > idle_minutes * 60:
                    log.info("No requests for %s minutes; stopping server", idle_minutes)
                    self.shutdown()
                    return

        threading.Thread(target=watchdog, daemon=True).start()
        log.info("Serving %s at http://127.0.0.1:%s/", self.site_dir, self.server_address[1])
        self.serve_forever()
        self.server_close()


class Handler(SimpleHTTPRequestHandler):
    """Static files from site/ plus the page builder API."""

    server: MotivateServer

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - stdlib signature
        log.debug("%s - %s", self.address_string(), format % args)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _local_request(self) -> bool:
        """Reject requests from other web sites (Host/Origin must be this server)."""
        port = self.server.server_address[1]
        allowed = {f"127.0.0.1:{port}", f"localhost:{port}"}
        origin = self.headers.get("Origin")
        return self.headers.get("Host") in allowed and (
            origin is None or origin.removeprefix("http://") in allowed
        )

    def do_GET(self) -> None:  # noqa: N802 - stdlib name
        self.server.last_request = time.monotonic()
        url = urlsplit(self.path)
        if url.path == "/api/ping":
            self._send_json(200, {"ok": True, "app": "MOTIVATE", "version": API_VERSION})
        elif url.path == "/api/page":
            try:
                number = int(parse_qs(url.query).get("n", [""])[0])
                spec = page_builder.load_page(self.server.site_dir, number)
            except ValueError as exc:
                self._send_json(400, {"ok": False, "error": str(exc) or "Invalid page number"})
                return
            except Exception:  # noqa: BLE001 - report to the page, details in the log
                log.exception("Loading page %s failed", self.path)
                self._send_json(500, {"ok": False, "error": "Unexpected error - see logs\\app.log"})
                return
            log.info("User action: load page %s for editing", number)
            self._send_json(200, {"ok": True, "spec": spec.to_dict()})
        else:
            super().do_GET()

    def do_POST(self) -> None:  # noqa: N802 - stdlib name
        self.server.last_request = time.monotonic()
        route = self.path.split("?")[0]
        if route == "/api/shutdown" and self._local_request():
            log.info("Shutdown requested (newer launcher)")
            self._send_json(200, {"ok": True})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        if route not in ("/api/preview", "/api/create", "/api/update"):
            self._send_json(404, {"ok": False, "error": "Unknown action"})
            return
        if not self._local_request() or self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            log.warning("Rejected %s from Origin=%s Host=%s", route, self.headers.get("Origin"), self.headers.get("Host"))
            self._send_json(403, {"ok": False, "error": "Request refused"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        if not 0 < length <= MAX_BODY:
            self._send_json(400, {"ok": False, "error": "Empty or too large request"})
            return
        try:
            spec = page_builder.PageSpec.from_dict(json.loads(self.rfile.read(length)))
            with self.server.write_lock:
                if route == "/api/preview":
                    path = page_builder.write_preview(self.server.site_dir, spec)
                elif route == "/api/update":
                    log.info("User action: edit page %s %r", spec.number, spec.name)
                    path = page_builder.update_page(self.server.site_dir, spec, self.server.backup_dir)
                else:
                    log.info("User action: create page %s %r", spec.number, spec.name)
                    path = page_builder.insert_page(self.server.site_dir, spec, self.server.backup_dir)
        except ValueError as exc:
            self._send_json(400, {"ok": False, "error": str(exc)})
            return
        except Exception:  # noqa: BLE001 - report to the page, details in the log
            log.exception("Page builder %s failed", route)
            self._send_json(500, {"ok": False, "error": "Unexpected error - see logs\\app.log"})
            return
        self._send_json(200, {"ok": True, "file": path.name})


def running_version(port: int) -> int | None:
    """API version of the MOTIVATE server on this port (1 = before versions), None if none answers."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1) as resp:
            info = json.load(resp)
    except (OSError, ValueError):
        return None
    return int(info.get("version", 1)) if info.get("app") == "MOTIVATE" else None


def is_running(port: int) -> bool:
    """True if a MOTIVATE server already answers on this port."""
    return running_version(port) is not None


def stop_server(port: int) -> bool:
    """Ask the MOTIVATE server on this port to stop; True once the port is free."""
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/shutdown", data=b"{}", method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=2).close()
    except OSError:
        pass
    for _ in range(20):
        if not is_running(port):
            return True
        time.sleep(0.25)
    return False
