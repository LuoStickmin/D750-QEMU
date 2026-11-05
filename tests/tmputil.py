# SPDX-License-Identifier: GPL-2.0-or-later
"""Workspace-local temporary directories.

The DSH sandbox allows writing inside the workspace but rejects the chmod
that ``TemporaryDirectory`` performs during cleanup, so tests use a
context manager that simply leaves its directory behind.  The directories
are ignored by Git and are cheap to remove by hand.
"""
from __future__ import annotations

import contextlib
import shutil
import uuid
from pathlib import Path

TMPBASE = Path(__file__).resolve().parents[1] / ".test-tmp"
TMPBASE.mkdir(exist_ok=True)


@contextlib.contextmanager
def temp_dir():
    path = TMPBASE / ("t" + uuid.uuid4().hex[:10])
    path.mkdir()
    try:
        yield str(path)
    finally:
        shutil.rmtree(path, ignore_errors=True)
