from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from . import __version__
from . import analyze as analyze_mod
from . import clone as clone_mod
from . import config as config_mod
from . import discover as discover_mod
from . import report as report_mod
from . import server as server_mod
from . import status as status_mod
from .config import Config

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


def cmd_analyze(args) -> int:
    _setup_logging(args.verbose)
    cfg = _load_config(args)
    cfg.src_dir.mkdir(parents=True, exist_ok=True)
    cfg.work_dir.mkdir(parents=True, exist_ok=True)
    cfg.reports_dir.mkdir(parents=True, exist_ok=True)

    analyze_mod.configure_license()

    progress = status_mod.Progress(cfg.reports_dir)
    progress.prepare(cfg.projects)
    report_mod.render_portal(cfg)

    results: list[tuple] = []
    for project in cfg.projects:
        if not project.enabled:
            log.info("%s: skipped (disabled in config)", project.slug)
            continue
        log.info("=== %s ===", project.slug)
        try:
            progress.set(project.slug, "cloning", "clone / update repository")
            src = clone_mod.clone_or_update(project, cfg.src_dir)
            progress.set(project.slug, "building", "cmake configure + build")
            compile_db = analyze_mod.build_project(project, cfg)
            progress.set(project.slug, "analyzing", "pvs-studio-analyzer")
            plog = analyze_mod.run_pvs(project, compile_db, cfg)
            progress.set(project.slug, "converting", "plog-converter fullhtml/json")
            stats = report_mod.convert(project, plog, cfg)
            progress.set(project.slug, "done", "analyzed", stats=stats)
            log.info(
                "%s: %d warnings (%d high, %d medium, %d low)",
                project.slug,
                stats["total"],
                stats["levels"]["High"],
                stats["levels"]["Medium"],
                stats["levels"]["Low"],
            )
            results.append((project, stats))
        except Exception as exc:
            progress.set(project.slug, "failed", str(exc))
            log.error("%s: analysis failed: %s", project.slug, exc, exc_info=args.verbose)
        finally:
            analyze_mod.clean_build(project, cfg)

    report_mod.write_links(cfg, results)
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
