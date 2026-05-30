"""
pipeline_lock.py — flock-based singleton to prevent concurrent pipeline runs.

Prevents master_pipeline.py and revenue_daily.py from running simultaneously
(e.g. cron fires while manual run is still active).

Usage:
    from core.guardrails.pipeline_lock import pipeline_lock

    with pipeline_lock("master_pipeline"):
        run_pipeline()
    # Lock automatically released on exit (even on crash)
"""

from __future__ import annotations

import fcntl
import os
import time
from contextlib import contextmanager
from pathlib import Path


class PipelineAlreadyRunningError(RuntimeError):
    """Raised when another instance of the pipeline is already running."""
    pass


@contextmanager
def pipeline_lock(
    pipeline_name: str,
    timeout_seconds: int = 10,
    lock_dir: str = "/tmp",
):
    """
    Acquire exclusive flock on /tmp/imperio-pipeline-{name}.lock.

    If lock cannot be acquired within timeout_seconds, raises
    PipelineAlreadyRunningError. Lock is released on context exit
    (including crashes — OS releases flock on process death).

    Args:
        pipeline_name: identifier (e.g. "master_pipeline", "revenue_daily")
        timeout_seconds: max wait before giving up (0 = fail immediately)
        lock_dir: directory for lock files
    """
    lock_path = Path(lock_dir) / f"imperio-pipeline-{pipeline_name}.lock"
    lock_fd = None

    try:
        lock_fd = open(lock_path, "w")

        if timeout_seconds <= 0:
            # Non-blocking attempt
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (IOError, OSError):
                raise PipelineAlreadyRunningError(
                    f"Pipeline '{pipeline_name}' is already running "
                    f"(lock: {lock_path})"
                )
        else:
            # Polling with timeout
            deadline = time.monotonic() + timeout_seconds
            acquired = False
            while time.monotonic() < deadline:
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                    break
                except (IOError, OSError):
                    time.sleep(0.5)

            if not acquired:
                raise PipelineAlreadyRunningError(
                    f"Pipeline '{pipeline_name}' is already running "
                    f"(waited {timeout_seconds}s, lock: {lock_path})"
                )

        # Write PID for debugging
        lock_fd.seek(0)
        lock_fd.truncate()
        lock_fd.write(f"{os.getpid()}\n")
        lock_fd.flush()

        yield

    finally:
        if lock_fd is not None:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                lock_fd.close()
            except Exception:
                pass
