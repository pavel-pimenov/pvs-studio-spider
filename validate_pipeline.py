"""Validate build_project() for the given slugs using the real app code (in-container)."""
import shutil
import sys

from app import analyze as analyze_mod
from app import clone as clone_mod
from app.config import Config


def main() -> int:
    slugs = set(sys.argv[1:])
    cfg = Config.load("/app/projects.yaml")
    failures = []
    for project in cfg.projects:
        if project.slug not in slugs:
            continue
        src = cfg.src_dir / project.slug
        shutil.rmtree(src, ignore_errors=True)
        print(f"=== {project.slug} ===", flush=True)
        try:
            src = clone_mod.clone_or_update(project, cfg.src_dir)
            commit = clone_mod.head_commit(src)
            compile_db = analyze_mod.build_project(project, cfg)
            entries = compile_db.read_text(encoding="utf-8").count('"file"')
            print(f"  OK commit={commit} compile_db_entries~={entries}", flush=True)
        except Exception as exc:
            print(f"  FAIL: {exc}", flush=True)
            failures.append(project.slug)
        finally:
            analyze_mod.clean_build(project, cfg)
            analyze_mod.clean_src(project, cfg)
    if failures:
        print("FAILED:", ", ".join(failures))
        return 1
    print("ALL OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
