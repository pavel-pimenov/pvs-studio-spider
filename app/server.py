from __future__ import annotations

import functools
import http.server
import logging
import socketserver
import threading
import time
from pathlib import Path

from . import sysmon

log = logging.getLogger("spider.server")


def serve(reports_dir: Path, host: str = "0.0.0.0", port: int = 8000) -> None:
    """Serve the generated HTML reports over HTTP."""
    try:
        reports_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        log.warning("cannot create reports dir %s: %s", reports_dir, exc)

    def _stats_loop() -> None:
        while True:
            try:
                sysmon.write_stats(reports_dir / "server.json", base=reports_dir)
            except OSError as exc:
                log.warning("cannot write server.json: %s", exc)
            time.sleep(2)

    threading.Thread(target=_stats_loop, daemon=True).start()

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(reports_dir))
    with socketserver.ThreadingTCPServer((host, port), handler) as httpd:
        base = f"http://{host if host != '0.0.0.0' else 'localhost'}:{port}"
        log.info("report server listening on %s (root: %s)", base, reports_dir)
        links = reports_dir / "links.txt"
        if links.exists():
            log.info("shareable links:\n%s", links.read_text(encoding="utf-8"))
        httpd.serve_forever()
