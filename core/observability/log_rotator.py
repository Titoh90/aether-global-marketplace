"""
log_rotator.py — Rotate and compress JSONL/log files to prevent disk pressure.

Compresses files older than N days with gzip, deletes compressed files older
than M days. Designed to run as step 0 of launch_daily.sh.

Usage:
    from core.observability.log_rotator import rotate_logs
    report = rotate_logs([Path("logs/"), Path("SRE/")])
    print(report)

CLI:
    python3 -m core.observability.log_rotator
"""

from __future__ import annotations

import gzip
import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

# IMPERIO_ROOT for default log directories
IMPERIO_ROOT = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT")

DEFAULT_LOG_DIRS = [
    IMPERIO_ROOT / "logs",
    IMPERIO_ROOT / "SRE",
    IMPERIO_ROOT / "REVENUE",
    IMPERIO_ROOT / "operator" / "logs",
]

# File patterns to rotate
ROTATABLE_EXTENSIONS = {".jsonl", ".log", ".csv"}


@dataclass
class RotationReport:
    compressed: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        return (
            f"Log rotation: {len(self.compressed)} compressed, "
            f"{len(self.deleted)} deleted, {self.skipped} skipped, "
            f"{len(self.errors)} errors"
        )


def _file_age_days(path: Path) -> float:
    """Days since last modification."""
    return (time.time() - path.stat().st_mtime) / 86400


def rotate_logs(
    log_dirs: list[Path] | None = None,
    compress_after_days: int = 7,
    delete_after_days: int = 90,
) -> RotationReport:
    """
    Walk log_dirs, compress old JSONL/log files, delete ancient compressed files.

    Args:
        log_dirs: directories to scan (default: IMPERIO standard log dirs)
        compress_after_days: compress files older than this (default 7)
        delete_after_days: delete .gz files older than this (default 90)

    Returns:
        RotationReport with counts and file lists
    """
    if log_dirs is None:
        log_dirs = DEFAULT_LOG_DIRS

    report = RotationReport()

    for log_dir in log_dirs:
        if not log_dir.exists():
            continue

        for root, _dirs, files in os.walk(log_dir):
            root_path = Path(root)
            for fname in files:
                fpath = root_path / fname

                try:
                    # Delete old compressed files
                    if fpath.suffix == ".gz":
                        if _file_age_days(fpath) > delete_after_days:
                            fpath.unlink()
                            report.deleted.append(str(fpath))
                        continue

                    # Only process rotatable file types
                    if fpath.suffix not in ROTATABLE_EXTENSIONS:
                        report.skipped += 1
                        continue

                    # Skip small files (< 1KB) and recent files
                    if fpath.stat().st_size < 1024:
                        report.skipped += 1
                        continue

                    if _file_age_days(fpath) < compress_after_days:
                        report.skipped += 1
                        continue

                    # Skip files that are date-stamped for today
                    today = time.strftime("%Y-%m-%d")
                    if today in fname:
                        report.skipped += 1
                        continue

                    # Compress
                    gz_path = fpath.with_suffix(fpath.suffix + ".gz")
                    if gz_path.exists():
                        report.skipped += 1
                        continue

                    with open(fpath, "rb") as f_in:
                        with gzip.open(gz_path, "wb") as f_out:
                            shutil.copyfileobj(f_in, f_out)

                    # Verify compressed file exists and has size
                    if gz_path.exists() and gz_path.stat().st_size > 0:
                        fpath.unlink()
                        report.compressed.append(str(fpath))
                    else:
                        report.errors.append(f"compression failed: {fpath}")

                except Exception as e:
                    report.errors.append(f"{fpath}: {e}")

    return report


if __name__ == "__main__":
    report = rotate_logs()
    print(report)
    if report.compressed:
        print("Compressed:")
        for f in report.compressed:
            print(f"  {f}")
    if report.deleted:
        print("Deleted:")
        for f in report.deleted:
            print(f"  {f}")
    if report.errors:
        print("Errors:")
        for e in report.errors:
            print(f"  {e}")
