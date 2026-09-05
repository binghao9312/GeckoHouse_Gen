"""Test-process workaround for CadQuery/OCP Windows interpreter teardown."""

from __future__ import annotations

import os
import sys

import pytest


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus: int) -> None:
    """Preserve pytest's real status despite OCP mutating it at interpreter exit."""
    if sys.platform == "win32":
        status = "passed" if exitstatus == 0 else f"finished with pytest exit status {exitstatus}"
        print(f"\n{session.testscollected} tests {status}")
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(exitstatus)
