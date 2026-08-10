from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_ROOT = Path("/data")


@dataclass
class Project:
    """A single open-source repository to analyze."""

    name: str
    repo: str
    ref: str = "main"
    description: str = ""
    cmake_options: list[str] = field(default_factory=list)
    cmake_src: str = ""
    cmake_project_include: str = ""
    build_cmd: str = ""
    submodules: list[str] = field(default_factory=list)
    build_dir: str = "build"
    enabled: bool = True

    @property
    def slug(self) -> str:
        return self.name

    @property
    def repo_url(self) -> str:
        return self.repo.removesuffix(".git")


@dataclass
class Config:
    src_dir: Path
    work_dir: Path
    reports_dir: Path
    revisions_file: Path
    jobs: int
    parallel: int
    convert_groups: str
    base_url: str
    projects: list[Project] = field(default_factory=list)

    @classmethod
    def load(cls, path: str | Path, env: dict | None = None) -> "Config":
        env = env if env is not None else os.environ
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}

        src_dir = Path(raw.get("src_dir", env.get("SPIDER_SRC_DIR", DEFAULT_ROOT / "src")))
        work_dir = Path(raw.get("work_dir", env.get("SPIDER_WORK_DIR", DEFAULT_ROOT / "work")))
        reports_dir = Path(raw.get("reports_dir", env.get("SPIDER_REPORTS_DIR", DEFAULT_ROOT / "reports")))
        revisions_file = Path(str(raw.get("revisions_file", env.get("SPIDER_REVISIONS_FILE", "revisions.txt"))))
        if not revisions_file.is_absolute():
            revisions_file = Path(path).resolve().parent / revisions_file
        default_jobs = max(1, (os.cpu_count() or 2) - 2)
        jobs = int(raw.get("jobs", env.get("SPIDER_JOBS", default_jobs)))
        parallel = max(1, int(raw.get("parallel", env.get("SPIDER_PARALLEL", 1))))
        convert_groups = str(raw.get("convert_groups", env.get("SPIDER_CONVERT_GROUPS", "GA:1,2,3")))
        base_url = str(raw.get("base_url", env.get("SPIDER_BASE_URL", "http://localhost:8000"))).rstrip("/")

        config_root = Path(path).resolve().parent
        projects: list[Project] = []
        for item in raw.get("projects", []):
            if not isinstance(item, dict) or not item.get("name") or not item.get("repo"):
                continue
            include = str(item.get("cmake_project_include", ""))
            if include and not Path(include).is_absolute():
                include = str(config_root / include)
            projects.append(
                Project(
                    name=str(item["name"]),
                    repo=str(item["repo"]),
                    ref=str(item.get("ref", "main")),
                    description=str(item.get("description", "")),
                    cmake_options=[str(o) for o in item.get("cmake_options", [])],
                    cmake_src=str(item.get("cmake_src", "")),
                    cmake_project_include=include,
                    build_cmd=str(item.get("build_cmd", "")),
                    submodules=[str(s) for s in item.get("submodules", [])],
                    build_dir=str(item.get("build_dir", "build")),
                    enabled=bool(item.get("enabled", True)),
                )
            )
        return cls(
            src_dir=src_dir,
            work_dir=work_dir,
            reports_dir=reports_dir,
            revisions_file=revisions_file,
            jobs=jobs,
            parallel=parallel,
            convert_groups=convert_groups,
            base_url=base_url,
            projects=projects,
        )
