from __future__ import annotations

import json
import threading
from pathlib import Path

from .config import Project


class Progress:
    """Mirror analysis progress to reports_dir/status.json for the live portal."""

    def __init__(self, reports_dir: Path):
        self.reports_dir = reports_dir
        self.projects: dict[str, dict] = {}
        self._lock = threading.Lock()

    def prepare(self, projects: list[Project]) -> None:
        for p in projects:
            self.projects[p.slug] = {
                "slug": p.slug,
                "name": p.name,
                "description": p.description,
                "repo": p.repo_url,
                "ref": p.ref,
                "state": "skipped" if not p.enabled else "pending",
                "message": "",
            }
        self.write()

    def set(self, slug: str, state: str, message: str = "", stats: dict | None = None) -> None:
        with self._lock:
            entry = self.projects.setdefault(slug, {"slug": slug, "name": slug})
            entry["state"] = state
            entry["message"] = message
            if stats:
                entry["stats"] = stats
                entry["report"] = stats.get("report", "")
                entry["commit"] = stats.get("commit", "")
                entry["analyzed_at"] = stats.get("analyzed_at", "")
            self.write()

    def write(self) -> None:
        path = self.reports_dir / "status.json"
        tmp = path.with_name("status.json.tmp")
        tmp.write_text(
            json.dumps({"projects": self.projects}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(path)
