from __future__ import annotations

import logging
import shlex
import subprocess
from pathlib import Path

log = logging.getLogger("spider")


class CommandError(RuntimeError):
    """A subprocess finished with a non-zero exit code."""

    def __init__(self, cmd: list[str], returncode: int, output: str):
        self.cmd = cmd
        self.returncode = returncode
        self.output = output
        super().__init__(f"command failed ({returncode}): {shlex.join(cmd)}")


def run(
    cmd: list[str],
    *,
    cwd: str | Path | None = None,
    env: dict | None = None,
    check: bool = False,
) -> subprocess.CompletedProcess:
    """Run a command, log the command line and its full output."""
    log.info("$ %s", shlex.join(cmd))
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if proc.stdout:
        log.info("--- output ---\n%s--- end ---", proc.stdout.rstrip())
    if check and proc.returncode != 0:
        raise CommandError(cmd, proc.returncode, proc.stdout)
    return proc
