from __future__ import annotations

import json
import logging
import shutil
import time
from pathlib import Path

log = logging.getLogger("spider.sysmon")


def _cpu_percent(sample_sec: float = 0.5) -> float:
    """Current CPU load averaged over a short window, from /proc/stat."""
    def _read() -> tuple[int, int]:
        with open("/proc/stat", encoding="utf-8") as fh:
            fields = fh.readline().split()
        total = sum(int(v) for v in fields[1:])
        idle = int(fields[4]) + int(fields[5])
        return total, idle

    try:
        total0, idle0 = _read()
        time.sleep(sample_sec)
        total1, idle1 = _read()
        d_total = total1 - total0
        d_idle = idle1 - idle0
        if d_total <= 0:
            return 0.0
        return max(0.0, min(100.0, 100.0 * (d_total - d_idle) / d_total))
    except (OSError, IndexError, ValueError) as exc:
        log.warning("could not read CPU stats: %s", exc)
        return 0.0


def sys_stats(base: Path) -> dict:
    """Remaining disk space on the mount holding base and current CPU load."""
    usage = shutil.disk_usage(base)
    return {
        "disk_free": usage.free,
        "disk_total": usage.total,
        "cpu_percent": round(_cpu_percent(), 1),
    }


def write_stats(path: Path, base: Path) -> None:
    """Atomically write current server stats to path (for the portal)."""
    stats = sys_stats(base)
    stats["updated_at"] = time.time()
    tmp = path.with_name(f"{path.name}.tmp")
    tmp.write_text(json.dumps(stats), encoding="utf-8")
    tmp.replace(path)
