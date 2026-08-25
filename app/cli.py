from __future__ import annotations

import argparse
import logging
import os
import shutil
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from . import __version__
from . import analyze as analyze_mod
from . import clone as clone_mod
from . import config as config_mod
from . import discover as discover_mod
from . import report as report_mod
from . import server as server_mod
from . import state as state_mod
from . import status as status_mod
from . import sysmon
from . import util
from .config import Config, Project
from .util import run

log = logging.getLogger("spider")


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s"))
    root = logging.getLogger("spider")
    root.setLevel(level)
    root.addHandler(handler)
    root.propagate = False


def _load_config(args) -> Config:
    return Config.load(args.config)


RESERVED_REPORTS = {"index.html", "links.txt", "status.json", "metrics.json", "server.json"}


def _dir_bytes(path: Path) -> int:
    """Total size of a file or directory in bytes (du -sb, 0 if absent)."""
    if not path.exists():
        return 0
    proc = run(["du", "-sb", str(path)], check=False)
    try:
        return int(proc.stdout.split(maxsplit=1)[0])
    except (ValueError, IndexError):
        return 0


def prune_orphans(cfg: Config) -> None:
    """Remove reports, sources and build dirs of projects no longer in the config."""
    slugs = {p.slug for p in cfg.projects}
    for base, kind in ((cfg.src_dir, "sources"), (cfg.work_dir, "build dirs")):
        if not base.exists():
            continue
        for path in sorted(base.iterdir()):
            if path.is_dir() and path.name not in slugs:
                shutil.rmtree(path, ignore_errors=True)
                log.info("pruned stale %s: %s", kind, path)
    if not cfg.reports_dir.exists():
        return
    for path in sorted(cfg.reports_dir.iterdir()):
        name = path.name
        if name in RESERVED_REPORTS:
            continue
        if path.is_file() and name.endswith((".plog", ".json")):
            if name.rsplit(".", 1)[0] not in slugs:
                path.unlink(missing_ok=True)
                log.info("pruned stale report: %s", path)
        elif path.is_dir() and name not in slugs and report_mod.is_report_dir(path):
            shutil.rmtree(path, ignore_errors=True)
            log.info("pruned stale report dir: %s", path)


def cmd_analyze(args) -> int:
    _setup_logging(args.verbose)
    cfg = _load_config(args)
    full_projects = list(cfg.projects)
    prune_orphans(cfg)

    if args.only:
        wanted = set(args.only)
        missing = wanted - {p.slug for p in cfg.projects}
        if missing:
            log.error("unknown project(s): %s", ", ".join(sorted(missing)))
            return 2
        cfg.projects = [p for p in cfg.projects if p.slug in wanted]

    cfg.src_dir.mkdir(parents=True, exist_ok=True)
    cfg.work_dir.mkdir(parents=True, exist_ok=True)
    cfg.reports_dir.mkdir(parents=True, exist_ok=True)

    analyze_mod.configure_license()

    progress = status_mod.Progress(cfg.reports_dir)
    progress.prepare(cfg.projects, keep={p.slug for p in full_projects})
    report_mod.render_portal(cfg)
    revisions = state_mod.load_revisions(cfg.revisions_file)
    metrics = state_mod.load_metrics(cfg.reports_dir / "metrics.json")

    stats_stop = threading.Event()

    def _stats_loop() -> None:
        while not stats_stop.wait(2):
            try:
                sysmon.write_stats(cfg.reports_dir / "server.json", base=cfg.reports_dir)
            except OSError as exc:
                log.warning("cannot write server.json: %s", exc)

    threading.Thread(target=_stats_loop, daemon=True).start()

    def worker(project: Project) -> tuple[Project, dict | None, dict | None, str | None]:
        log.info("=== %s ===", project.slug)
        wall_start = time.perf_counter()
        cpu_start = util.thread_cpu()
        try:
            progress.set(project.slug, "cloning", "clone / update repository")
            t = time.perf_counter()
            src = clone_mod.clone_or_update(project, cfg.src_dir)
            clone_sec = round(time.perf_counter() - t, 1)
            commit = clone_mod.head_commit(src)
            if not args.force and revisions.get(project.slug) == commit:
                if report_mod.has_report(project, cfg):
                    progress.set(project.slug, "skipped", "revision unchanged, report up to date")
                    log.info("%s: revision %s already analyzed, skipping", project.slug, commit)
                    return project, report_mod.summarize(project, cfg), None, None
            progress.set(project.slug, "building", "cmake configure + build")
            t = time.perf_counter()
            compile_db = analyze_mod.build_project(project, cfg)
            build_sec = round(time.perf_counter() - t, 1)
            progress.set(project.slug, "analyzing", "pvs-studio-analyzer")
            t = time.perf_counter()
            plog = analyze_mod.run_pvs(project, compile_db, cfg)
            analyze_sec = round(time.perf_counter() - t, 1)
            progress.set(project.slug, "converting", "plog-converter fullhtml/json")
            t = time.perf_counter()
            stats = report_mod.convert(project, plog, cfg)
            convert_sec = round(time.perf_counter() - t, 1)
            entry = {
                "commit": commit,
                "analyzed_at": stats["analyzed_at"],
                "clone_sec": clone_sec,
                "build_sec": build_sec,
                "analyze_sec": analyze_sec,
                "convert_sec": convert_sec,
                "wall_sec": round(time.perf_counter() - wall_start, 1),
                "cpu_sec": round(util.thread_cpu() - cpu_start, 1),
                "disk_bytes": (
                    _dir_bytes(src)
                    + _dir_bytes(cfg.work_dir / project.slug)
                    + _dir_bytes(cfg.reports_dir / f"{project.slug}.plog")
                    + _dir_bytes(cfg.reports_dir / f"{project.slug}.json")
                    + _dir_bytes(cfg.reports_dir / project.slug)
                ),
            }
            progress.set(project.slug, "done", "analyzed", stats=stats)
            log.info(
                "%s: %d warnings (%d high, %d medium, %d low)",
                project.slug,
                stats["total"],
                stats["levels"]["High"],
                stats["levels"]["Medium"],
                stats["levels"]["Low"],
            )
            return project, stats, entry, None
        except Exception as exc:
            progress.set(project.slug, "failed", str(exc))
            log.error("%s: analysis failed: %s", project.slug, exc, exc_info=args.verbose)
            return project, None, None, str(exc)
        finally:
            analyze_mod.clean_build(project, cfg)
            analyze_mod.clean_src(project, cfg)

    results: list[tuple] = []
    with ThreadPoolExecutor(max_workers=cfg.parallel) as pool:
        futures = {pool.submit(worker, p): p for p in cfg.projects if p.enabled}
        for future in as_completed(futures):
            project = futures[future]
            try:
                _, stats, entry, error = future.result()
            except Exception as exc:
                log.error("%s: worker crashed: %s", project.slug, exc, exc_info=args.verbose)
                continue
            if stats is not None:
                results.append((project, stats))
            if entry is not None:
                revisions[project.slug] = entry["commit"]
                metrics[project.slug] = entry
                state_mod.save_metrics(cfg.reports_dir / "metrics.json", metrics)

    active = {p.slug for p in full_projects if p.enabled}
    revisions = {k: v for k, v in revisions.items() if k in active}
    metrics = {k: v for k, v in metrics.items() if k in active}
    state_mod.save_revisions(cfg.revisions_file, revisions)
    state_mod.save_metrics(cfg.reports_dir / "metrics.json", metrics)
    report_mod.write_links(cfg)
    stats_stop.set()
    log.info("done. %d/%d projects analyzed", len(results), len(cfg.projects))
    return 0


def cmd_serve(args) -> int:
    _setup_logging(args.verbose)
    cfg = _load_config(args)
    server_mod.serve(cfg.reports_dir, host=args.host, port=args.port)
    return 0


def cmd_discover(args) -> int:
    _setup_logging(args.verbose)
    repos = discover_mod.discover(
        top=args.top,
        language=args.language,
        min_stars=args.min_stars,
    )
    if args.output:
        discover_mod.save_candidates(Path(args.output), repos)
    else:
        for repo in repos:
            print(f"{repo['stars']:>7}  {repo['name']:<24} {repo['repo']}")
    print(f"\n{len(repos)} candidate projects found", file=sys.stderr)
    return 0


def cmd_list(args) -> int:
    _setup_logging(args.verbose)
    cfg = _load_config(args)
    print(f"{'name':<14} {'enabled':<8} {'ref':<10} repo")
    for project in cfg.projects:
        print(f"{project.slug:<14} {str(project.enabled):<8} {project.ref:<10} {project.repo}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pvs-spider",
        description="Automated PVS-Studio analysis of open-source C/C++ projects.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p):
        default_config = os.environ.get("SPIDER_CONFIG", "projects.yaml")
        p.add_argument("--config", default=default_config, help="config file (default: projects.yaml)")
        p.add_argument("--verbose", action="store_true", help="debug logging")

    p_analyze = sub.add_parser("analyze", help="clone, build and analyze all configured projects")
    add_common(p_analyze)
    p_analyze.add_argument("--force", action="store_true", help="re-analyze projects even if the revision is unchanged")
    p_analyze.add_argument("--only", nargs="+", metavar="SLUG", help="analyze only the given projects")
    p_analyze.set_defaults(func=cmd_analyze)

    p_serve = sub.add_parser("serve", help="serve the generated HTML reports over HTTP")
    add_common(p_serve)
    p_serve.add_argument("--host", default="0.0.0.0")
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.set_defaults(func=cmd_serve)

    p_discover = sub.add_parser("discover", help="find popular open-source C/C++ repos on GitHub")
    p_discover.add_argument("--top", type=int, default=10, help="number of repositories to return")
    p_discover.add_argument("--language", default="C++")
    p_discover.add_argument("--min-stars", type=int, default=2000)
    p_discover.add_argument("--output", help="save candidates to a JSON file")
    p_discover.add_argument("--verbose", action="store_true", help="debug logging")
    p_discover.set_defaults(func=cmd_discover)

    p_list = sub.add_parser("list", help="list the configured projects")
    add_common(p_list)
    p_list.set_defaults(func=cmd_list)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
