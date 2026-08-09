from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

from .config import Config, Project
from .util import run

log = logging.getLogger("spider.analyze")


def configure_license() -> None:
    """Enter the PVS-Studio license using credentials or a license file."""
    username = os.environ.get("PVS_USERNAME")
    key = os.environ.get("PVS_KEY")
    if username and key:
        log.info("configuring PVS-Studio credentials")
        run(["pvs-studio-analyzer", "credentials", username, key], check=False)
        return

    license_path = os.environ.get("PVS_STUDIO_LICENSE")
    if license_path:
        resolved = Path(license_path).expanduser().resolve()
        log.info("PVS_STUDIO_LICENSE is set to %s", resolved)
        if not resolved.exists():
            log.warning("license file %s not found, analysis may fail", resolved)
        os.environ["PVS_STUDIO_LICENSE"] = str(resolved)
        return

    log.warning(
        "no license configured (PVS_USERNAME/PVS_KEY or PVS_STUDIO_LICENSE). "
        "The analyzer may run in trial mode or fail."
    )


def _cmake_configure(project: Project, src: Path, build: Path, cfg: Config) -> None:
    cmd = [
        "cmake",
        "-S", str(src),
        "-B", str(build),
        "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
        "-DCMAKE_BUILD_TYPE=Debug",
        "-DBUILD_TESTING=OFF",
        *project.cmake_options,
    ]
    run(cmd, check=True)


def _cmake_build(project: Project, src: Path, build: Path, cfg: Config) -> None:
    run(["cmake", "--build", str(build), "--parallel", str(cfg.jobs)], check=False)


def build_project(project: Project, cfg: Config) -> Path:
    """Configure and build the project, returning a compile_commands.json path."""
    src = cfg.src_dir / project.slug
    build = cfg.work_dir / project.slug / project.build_dir
    if build.exists():
        shutil.rmtree(build)
    build.mkdir(parents=True, exist_ok=True)

    log.info("%s: configuring with CMake", project.slug)
    _cmake_configure(project, src, build, cfg)
    log.info("%s: building", project.slug)
    _cmake_build(project, src, build, cfg)

    compile_db = build / "compile_commands.json"
    if not compile_db.exists():
        # Some projects hide the compile database; retry with `bear` tracing.
        log.warning("%s: no compile_commands.json, retrying with bear", project.slug)
        shutil.rmtree(build)
        build.mkdir(parents=True, exist_ok=True)
        _cmake_configure(project, src, build, cfg)
        run(
            ["bear", "--output", str(compile_db), "--", "cmake", "--build", str(build), "--parallel", str(cfg.jobs)],
            check=False,
        )

    if not compile_db.exists():
        raise RuntimeError(f"{project.slug}: could not produce compile_commands.json")
    return compile_db


def run_pvs(project: Project, compile_db: Path, cfg: Config) -> Path:
    """Run the PVS-Studio analyzer over the compile database."""
    plog = cfg.reports_dir / f"{project.slug}.plog"
    cmd = [
        "pvs-studio-analyzer",
        "analyze",
        "-f", str(compile_db),
        "-o", str(plog),
        "-j", str(cfg.jobs),
    ]
    license_path = os.environ.get("PVS_STUDIO_LICENSE")
    if license_path and Path(license_path).exists():
        cmd += ["--lic-file", license_path]

    log.info("%s: running pvs-studio-analyzer", project.slug)
    run(cmd, check=False)
    if not plog.exists():
        raise RuntimeError(f"{project.slug}: analyzer produced no report")
    return plog
