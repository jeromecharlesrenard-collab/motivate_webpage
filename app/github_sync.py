"""Upload page builder changes to GitHub (git add / commit / push).

Runs from the pythonw server: no console window, no prompts (GIT_TERMINAL_PROMPT=0),
and a time limit so a network problem cannot hang the page builder.
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

TIMEOUT = 60
WEBSITE = "https://jeromecharlesrenard-collab.github.io/motivate_webpage/"


def _git(project_dir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=project_dir,
        capture_output=True,
        text=True,
        timeout=TIMEOUT,
        env=os.environ | {"GIT_TERMINAL_PROMPT": "0"},
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def upload(project_dir: Path, message: str) -> tuple[bool, str]:
    """Commit every change in the project and push it; return (ok, notice for the user)."""
    try:
        steps = [("add", "-A"), ("commit", "-q", "-m", message), ("push", "-q")]
        for args in steps:
            if args[0] == "commit" and not _git(project_dir, "status", "--porcelain").stdout.strip():
                return True, "No changes to upload to GitHub."
            result = _git(project_dir, *args)
            if result.returncode != 0:
                detail = (result.stderr or result.stdout).strip().splitlines()
                log.error("git %s failed: %s", args[0], result.stderr.strip() or result.stdout.strip())
                return False, f"git {args[0]} failed: {detail[-1] if detail else 'unknown error'}"
    except FileNotFoundError:
        log.error("git is not installed or not on PATH")
        return False, "git was not found on this PC."
    except subprocess.TimeoutExpired:
        log.error("git timed out after %s s", TIMEOUT)
        return False, f"GitHub did not answer within {TIMEOUT} seconds."
    log.info("Uploaded to GitHub: %s", message)
    return True, f"Uploaded to GitHub. The website updates in about a minute:\n{WEBSITE}"
