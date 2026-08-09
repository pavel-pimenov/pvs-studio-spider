from __future__ import annotations

import logging
import os
import shlex
import subprocess
import threading
from pathlib import Path

log = logging.getLogger("spider")

_local = threading.local()


def _thread_cpu() -> float:
    """Cumulative child CPU seconds consumed by commands on the current thread."""
    value = getattr(_local, "cpu", None)
    if value is None:
        value = 0.0
        _local.cpu = value
    return value


def thread_cpu() -> float:
    """Child CPU time (utime+stime) accrued by run() calls on this thread."""
    return _thread_cpu()


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
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    stdout = proc.stdout.read() if proc.stdout else ""
    if proc.stdout:
        proc.stdout.close()
    try:
        _, status, ru = os.wait4(proc.pid, 0)
        returncode = os.waitstatus_to_exitcode(status)
    except OSError:
        returncode = proc.wait()
        ru = None
    _local.cpu = _thread_cpu() + ((ru.ru_utime + ru.ru_stime) if ru else 0.0)
    if stdout:
        log.info("--- output ---\n%s--- end ---", stdout.rstrip())
    if check and returncode != 0:
        raise CommandError(cmd, returncode, stdout)
    return subprocess.CompletedProcess(cmd, returncode, stdout, None)
