from __future__ import annotations

import datetime as dt
import json
import logging
import os
import shutil
from collections import Counter
from pathlib import Path

from .clone import head_commit
from .config import Config, Project
from .util import run

log = logging.getLogger("spider.report")

LEVEL_NAMES = {1: "High", 2: "Medium", 3: "Low"}


def _find_index(report_dir: Path) -> str | None:
    if not report_dir.is_dir():
        return None
    direct = report_dir / "index.html"
    if direct.exists():
        return direct.name
    for sub in sorted(report_dir.iterdir()):
        candidate = sub / "index.html"
        if candidate.exists():
            return f"{sub.name}/index.html"
    return None


def is_report_dir(path: Path) -> bool:
    """True if the directory contains a converted HTML report."""
    return _find_index(path) is not None


def _dedup_jquery(report_dir: Path, shared_dir: Path) -> None:
    """Share the jQuery copy between all reports via a hardlink to one file."""
    jq = report_dir / "jquery-3.5.1.min.js"
    if not jq.exists():
        return
    shared_dir.mkdir(parents=True, exist_ok=True)
    shared = shared_dir / jq.name
    if not shared.exists():
        shutil.copy2(jq, shared)
    jq.unlink()
    os.link(shared, jq)


def has_report(project: Project, cfg: Config) -> bool:
    """True if a converted HTML report and JSON stats already exist."""
    if not (cfg.reports_dir / f"{project.slug}.json").exists():
        return False
    return _find_index(cfg.reports_dir / project.slug) is not None


def summarize(project: Project, cfg: Config) -> dict:
    """Recompute stats from stored artifacts without re-running the analyzer."""
    stats = parse_json(cfg.reports_dir / f"{project.slug}.json")
    stats["report"] = _find_index(cfg.reports_dir / project.slug) or ""
    return stats


def convert(project: Project, plog: Path, cfg: Config) -> dict:
    """Convert a .plog report into an interactive HTML report and JSON stats."""
    report_dir = cfg.reports_dir / project.slug
    shutil.rmtree(report_dir, ignore_errors=True)

    fullhtml = [
        "plog-converter",
        "-a", cfg.convert_groups,
        "-t", "fullhtml",
        "-o", str(report_dir),
        str(plog),
    ]
    run(fullhtml, check=False)
    _dedup_jquery(report_dir, cfg.reports_dir / "static")

    json_path = cfg.reports_dir / f"{project.slug}.json"
    to_json = [
        "plog-converter",
        "-a", cfg.convert_groups,
        "-t", "json",
        "-o", str(json_path),
        str(plog),
    ]
    run(to_json, check=False)

    stats = parse_json(json_path)
    stats["report"] = _find_index(report_dir)
    stats["plog"] = plog.name
    stats["commit"] = head_commit(cfg.src_dir / project.slug)
    stats["analyzed_at"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    return stats


def parse_json(path: Path) -> dict:
    """Extract per-level/per-code counters from a JSON report."""
    total = 0
    by_level: Counter = Counter()
    by_code: Counter = Counter()
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("could not read JSON report %s: %s", path, exc)
        data = []

    if isinstance(data, dict):
        data = data.get("issues") or data.get("warnings") or []

    for entry in data:
        code = str(entry.get("Code") or entry.get("code") or "?")
        try:
            level = int(entry.get("Level", entry.get("level", 0)))
        except (TypeError, ValueError):
            level = 0
        total += 1
        by_level[level] += 1
        by_code[code] += 1

    return {
        "total": total,
        "levels": {name: by_level.get(num, 0) for num, name in LEVEL_NAMES.items()},
        "by_code": by_code.most_common(),
    }


def render_portal(cfg: Config) -> None:
    """Write the portal shell; the sidebar is populated live from status.json."""
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    template_dir = Path(__file__).parent / "templates"
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html", "j2"]),
    )
    template = env.get_template("index.html.j2")

    html = template.render(
        generated_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    )
    index_path = cfg.reports_dir / "index.html"
    index_path.write_text(html, encoding="utf-8")
    log.info("portal page written to %s", index_path)


def write_links(cfg: Config, results: list[tuple[Project, dict]]) -> None:
    """Write links.txt with ready-to-share URLs for every project report."""
    lines = ["# PVS-Studio Spider report links", "# share these with project maintainers", ""]
    for project, stats in results:
        report = stats.get("report") or ""
        url = f"{cfg.base_url}/{project.slug}/" + (report or "")
        lines.append(f"{project.slug:<14} {url}")
    links_path = cfg.reports_dir / "links.txt"
    links_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log.info("shareable links written to %s", links_path)
