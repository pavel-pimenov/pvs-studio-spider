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
    jobs: int
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
        jobs = int(raw.get("jobs", env.get("SPIDER_JOBS", 4)))
        convert_groups = str(raw.get("convert_groups", env.get("SPIDER_CONVERT_GROUPS", "GA:1,2,3")))
        base_url = str(raw.get("base_url", env.get("SPIDER_BASE_URL", "http://localhost:8000"))).rstrip("/")

        projects: list[Project] = []
        for item in raw.get("projects", []):
            if not isinstance(item, dict) or not item.get("name") or not item.get("repo"):
                continue
            projects.append(
                Project(
                    name=str(item["name"]),
                    repo=str(item["repo"]),
                    ref=str(item.get("ref", "main")),
                    description=str(item.get("description", "")),
                    cmake_options=[str(o) for o in item.get("cmake_options", [])],
                    build_dir=str(item.get("build_dir", "build")),
                    enabled=bool(item.get("enabled", True)),
                )
            )
        return cls(
            src_dir=src_dir,
            work_dir=work_dir,
            reports_dir=reports_dir,
            jobs=jobs,
            convert_groups=convert_groups,
            base_url=base_url,
            projects=projects,
        )
