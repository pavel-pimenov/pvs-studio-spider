from __future__ import annotations

import datetime as dt
import json
import logging
from collections import Counter
from pathlib import Path

from .clone import head_commit
from .config import Config, Project
from .util import run

log = logging.getLogger("spider.report")

LEVEL_NAMES = {1: "High", 2: "Medium", 3: "Low"}


def _find_index(report_dir: Path) -> str | None:
    direct = report_dir / "index.html"
    if direct.exists():
        return direct.name
    for sub in sorted(report_dir.iterdir()):
        candidate = sub / "index.html"
        if candidate.exists():
            return f"{sub.name}/index.html"
    return None


def convert(project: Project, plog: Path, cfg: Config) -> dict:
    """Convert a .plog report into an interactive HTML report and JSON stats."""
    report_dir = cfg.reports_dir / project.slug
    report_dir.mkdir(parents=True, exist_ok=True)

    fullhtml = [
        "plog-converter",
        "-a", cfg.convert_groups,
        "-t", "fullhtml",
        "-o", str(report_dir),
        str(plog),
    ]
    run(fullhtml, check=False)

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


def generate_index(cfg: Config, results: list[tuple[Project, dict]]) -> None:
    """Write the landing page that links every project report."""
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    template_dir = Path(__file__).parent / "templates"
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html", "j2"]),
    )
    template = env.get_template("index.html.j2")

    rows = []
    for project, stats in results:
        rows.append(
            {
                "slug": project.slug,
                "name": project.name,
                "description": project.description,
                "repo_url": project.repo_url,
                "ref": project.ref,
                "commit": stats.get("commit", ""),
                "report": stats.get("report") or "",
                "analyzed_at": stats.get("analyzed_at", ""),
                "total": stats.get("total", 0),
                "high": stats.get("levels", {}).get("High", 0),
                "medium": stats.get("levels", {}).get("Medium", 0),
                "low": stats.get("levels", {}).get("Low", 0),
                "top_codes": stats.get("by_code", [])[:8],
            }
        )

    html = template.render(
        rows=rows,
        generated_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    )
    index_path = cfg.reports_dir / "index.html"
    index_path.write_text(html, encoding="utf-8")
    log.info("landing page written to %s", index_path)


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
