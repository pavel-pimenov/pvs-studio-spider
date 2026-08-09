from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger("spider.state")


def load_revisions(path: Path) -> dict[str, str]:
    """Read the analyzed-revisions file into a slug -> commit map."""
    if not path.exists():
        return {}
    revisions: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) == 2:
            revisions[parts[0]] = parts[1]
    log.info("loaded %d analyzed revisions from %s", len(revisions), path)
    return revisions


def save_revisions(path: Path, revisions: dict[str, str]) -> None:
    """Write the slug -> commit map to a simple text file."""
    header = ["# PVS-Studio Spider analyzed revisions", "# format: <slug> <git-commit>"]
    body = [f"{slug:<16} {commit}" for slug, commit in sorted(revisions.items())]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(header + body) + "\n", encoding="utf-8")
    log.info("saved %d analyzed revisions to %s", len(revisions), path)


def load_metrics(path: Path) -> dict[str, dict]:
    """Read the per-project resource usage metrics (disk/CPU/wall time)."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {str(slug): dict(entry) for slug, entry in data.items() if isinstance(entry, dict)}


def save_metrics(path: Path, metrics: dict[str, dict]) -> None:
    """Write per-project metrics atomically, preserving the previous file on error."""
    tmp = path.with_name(f"{path.name}.tmp")
    tmp.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
    log.info("saved %d metrics entries to %s", len(metrics), path)
