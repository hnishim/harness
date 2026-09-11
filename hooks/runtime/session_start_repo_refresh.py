#!/usr/bin/env python3
"""Refresh the current Codex project's Git remote refs on SessionStart."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any


FETCH_TIMEOUT_SECONDS = 10


def _git(cwd: str, *args: str, timeout: float | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", cwd, *args],
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
        env=env,
    )


def _value(cwd: str, *args: str) -> str | None:
    result = _git(cwd, *args)
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def _context(**fields: object) -> dict[str, Any]:
    parts = ["repository_remote_refresh:"]
    for key, value in fields.items():
        if value is None:
            continue
        if isinstance(value, bool):
            rendered = "true" if value else "false"
        else:
            rendered = str(value).replace("\n", " ").replace("\r", " ")
        parts.append(f"{key}={rendered}")
    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": " ".join(parts),
        }
    }


def _repo_root(cwd: str) -> tuple[str | None, str | None]:
    env = os.environ.copy()
    env["LC_ALL"] = "C"
    env["LANG"] = "C"
    result = _git(cwd, "rev-parse", "--show-toplevel", env=env)
    if result.returncode != 0:
        if "not a git repository" in result.stderr.lower():
            return None, "not_git"
        return None, "git_root_failed"
    root = result.stdout.strip()
    if not root:
        return None, "git_root_failed"
    return root, None


def _branch(root: str) -> str | None:
    return _value(root, "symbolic-ref", "--quiet", "--short", "HEAD")


def _remotes(root: str) -> list[str]:
    result = _git(root, "remote")
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _configured_upstream_remote(root: str, branch: str | None, remotes: list[str]) -> str | None:
    if not branch:
        return None
    remote = _value(root, "config", "--get", f"branch.{branch}.remote")
    merge = _value(root, "config", "--get", f"branch.{branch}.merge")
    if remote in remotes and merge:
        return remote
    return None


def _select_remote(root: str, branch: str | None, remotes: list[str]) -> tuple[str | None, str | None]:
    upstream_remote = _configured_upstream_remote(root, branch, remotes)
    if upstream_remote:
        return upstream_remote, None
    if not remotes:
        return None, "no_remote"
    if len(remotes) == 1:
        return remotes[0], None
    if "origin" in remotes:
        return "origin", None
    return None, "remote_ambiguous"


def _fetch(root: str, remote: str) -> tuple[bool, str | None, int | None]:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "Never"
    try:
        result = _git(
            root,
            "fetch",
            "--prune",
            remote,
            timeout=FETCH_TIMEOUT_SECONDS,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return False, "fetch_timeout", None
    if result.returncode != 0:
        return False, "fetch_failed", result.returncode
    return True, None, 0


def _observe(root: str, branch: str | None, remote: str | None) -> dict[str, object]:
    head = _value(root, "rev-parse", "HEAD")
    dirty_result = _git(root, "status", "--porcelain=v1")
    dirty = bool(dirty_result.stdout) if dirty_result.returncode == 0 else None

    configured_remote = _configured_upstream_remote(root, branch, _remotes(root))
    upstream_ref = _value(root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
    upstream: str | None
    sync: str | None = None
    ahead: int | None = None
    behind: int | None = None

    if upstream_ref:
        upstream = upstream_ref
        counts = _git(root, "rev-list", "--left-right", "--count", "HEAD...@{upstream}")
        if counts.returncode == 0:
            values = counts.stdout.strip().split()
            if len(values) == 2:
                ahead, behind = int(values[0]), int(values[1])
                if ahead == 0 and behind == 0:
                    sync = "same"
                elif ahead == 0:
                    sync = "remote_ahead"
                elif behind == 0:
                    sync = "local_ahead"
                else:
                    sync = "diverged"
    elif configured_remote:
        upstream = "missing"
    else:
        upstream = "none"

    return {
        "repo_root": root,
        "branch": branch or "detached",
        "head": head,
        "remote": remote,
        "upstream": upstream,
        "dirty": dirty,
        "ahead": ahead,
        "behind": behind,
        "sync": sync or "unknown",
    }


def handle(payload: dict[str, Any]) -> dict[str, Any]:
    cwd = payload.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        return _context(status="refresh_failed", reason="invalid_cwd")

    root, root_state = _repo_root(cwd)
    if root_state == "not_git":
        return _context(status="not_git")
    if root_state is not None or root is None:
        return _context(status="refresh_failed", reason="git_root_failed")

    branch = _branch(root)
    remotes = _remotes(root)
    remote, selection_state = _select_remote(root, branch, remotes)

    if selection_state == "no_remote":
        observed = _observe(root, branch, None)
        return _context(status="no_remote", **observed)

    if selection_state == "remote_ambiguous":
        observed = _observe(root, branch, None)
        return _context(status="refresh_failed", reason="remote_ambiguous", **observed)

    assert remote is not None
    fetched, failure, exit_code = _fetch(root, remote)
    if not fetched:
        return _context(
            status="refresh_failed",
            reason=failure,
            fetch_exit=exit_code,
            repo_root=root,
            branch=branch or "detached",
            remote=remote,
        )

    observed = _observe(root, branch, remote)
    return _context(status="refreshed", **observed)


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        print(json.dumps(_context(status="refresh_failed", reason="invalid_payload")))
        return 0
    if not isinstance(payload, dict):
        print(json.dumps(_context(status="refresh_failed", reason="invalid_payload")))
        return 0
    print(json.dumps(handle(payload), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
