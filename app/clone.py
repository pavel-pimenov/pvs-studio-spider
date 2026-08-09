from __future__ import annotations

import logging
from pathlib import Path

from .config import Project
from .util import run

log = logging.getLogger("spider.clone")


def clone_or_update(project: Project, src_dir: Path) -> Path:
    """Clone the repository or pull the latest changes if it already exists."""
    dest = src_dir / project.slug
    if dest.exists():
        log.info("%s: updating existing checkout", project.slug)
        run(["git", "-C", str(dest), "fetch", "--all", "--tags", "--prune"], check=False)
        run(["git", "-C", str(dest), "checkout", project.ref], check=False)
        run(["git", "-C", str(dest), "pull", "--ff-only"], check=False)
    else:
        log.info("%s: cloning %s (branch %s)", project.slug, project.repo, project.ref)
        proc = run(
            ["git", "clone", "--depth", "1", "--single-branch", "--branch", project.ref, project.repo, str(dest)],
            check=False,
        )
        if proc.returncode != 0:
            log.warning(
                "%s: branch %r not found, falling back to the default branch",
                project.slug,
                project.ref,
            )
            run(["git", "clone", "--depth", "1", project.repo, str(dest)], check=True)
    return dest


def head_commit(src: Path) -> str:
    proc = run(["git", "-C", str(src), "rev-parse", "--short", "HEAD"])
    return proc.stdout.strip() or ""
