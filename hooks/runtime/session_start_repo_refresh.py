#!/usr/bin/env python3
"""Refresh the Harness control plane and current project's Git refs on SessionStart."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


FETCH_TIMEOUT_SECONDS = 5
_CANONICAL_HARNESS = ("github.com", "hnishim", "harness")


def _git(cwd: str | Path, *args: str, timeout: float | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
        env=env,
    )


def _value(cwd: str | Path, *args: str) -> str | None:
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


def _repo_root(cwd: str | Path) -> tuple[str | None, str | None]:
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


def _branch(root: str | Path) -> str | None:
    return _value(root, "symbolic-ref", "--quiet", "--short", "HEAD")


def _remotes(root: str | Path) -> list[str]:
    result = _git(root, "remote")
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _configured_upstream_remote(root: str | Path, branch: str | None, remotes: list[str]) -> str | None:
    if not branch:
        return None
    remote = _value(root, "config", "--get", f"branch.{branch}.remote")
    merge = _value(root, "config", "--get", f"branch.{branch}.merge")
    if remote in remotes and merge:
        return remote
    return None


def _select_remote(root: str | Path, branch: str | None, remotes: list[str]) -> tuple[str | None, str | None]:
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


def _fetch(root: str | Path, remote: str) -> tuple[bool, str | None, int | None]:
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


def _observe(root: str | Path, branch: str | None, remote: str | None) -> dict[str, object]:
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
        "repo_root": str(root),
        "branch": branch or "detached",
        "head": head,
        "remote": remote,
        "upstream": upstream,
        "dirty": dirty,
        "ahead": ahead,
        "behind": behind,
        "sync": sync or "unknown",
    }


def _canonical_harness_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _normalized_remote_identity(url: str) -> tuple[str, str, str] | None:
    value = url.strip()
    match = re.match(r"^(?:https?|ssh)://(?:[^@/]+@)?([^/:]+)(?::\d+)?/(.+)$", value)
    if match:
        host, path = match.group(1), match.group(2)
    else:
        match = re.match(r"^(?:[^@/:]+@)?([^:]+):(.+)$", value)
        if not match:
            return None
        host, path = match.group(1), match.group(2)
    parts = path.strip("/").split("/")
    if len(parts) != 2:
        return None
    owner, repo = parts
    if repo.endswith(".git"):
        repo = repo[:-4]
    return host.lower(), owner.lower(), repo.lower()


def _is_canonical_harness_origin(root: str | Path) -> bool:
    url = _value(root, "config", "--get", "remote.origin.url")
    return url is not None and _normalized_remote_identity(url) == _CANONICAL_HARNESS


def _harness_counts(root: str | Path) -> tuple[int, int] | None:
    result = _git(root, "rev-list", "--left-right", "--count", "HEAD...origin/main")
    if result.returncode != 0:
        return None
    values = result.stdout.strip().split()
    if len(values) != 2:
        return None
    return int(values[0]), int(values[1])


def _fast_forward_harness(root: str | Path) -> tuple[bool, str | None]:
    result = _git(root, "merge", "--ff-only", "origin/main")
    if result.returncode != 0:
        return False, "fast_forward_failed"
    return True, None


def _verify_harness_readback(root: str | Path) -> bool:
    head = _value(root, "rev-parse", "HEAD")
    remote_head = _value(root, "rev-parse", "origin/main")
    return head is not None and head == remote_head


def _blocked_harness(reason: str) -> dict[str, object]:
    return {
        "harness_gate": "blocked",
        "harness_reason": reason,
        "implementation_loop_start": "prohibited",
    }


def _sync_harness(root: Path) -> dict[str, object]:
    git_root, root_state = _repo_root(root)
    if root_state is not None or git_root is None:
        return _blocked_harness("git_root_failed")
    if Path(git_root).resolve() != root.resolve():
        return _blocked_harness("root_mismatch")

    branch = _branch(git_root)
    if branch is None:
        return _blocked_harness("detached")
    if branch != "main":
        return _blocked_harness("non_main_branch")

    dirty = _git(git_root, "status", "--porcelain=v1")
    if dirty.returncode != 0:
        return _blocked_harness("status_failed")
    if dirty.stdout:
        return _blocked_harness("dirty")

    if "origin" not in _remotes(git_root):
        return _blocked_harness("no_origin")
    if not _is_canonical_harness_origin(git_root):
        return _blocked_harness("unexpected_origin")

    fetched, failure, _ = _fetch(git_root, "origin")
    if not fetched:
        return _blocked_harness(failure or "fetch_failed")

    counts = _harness_counts(git_root)
    if counts is None:
        return _blocked_harness("comparison_failed")
    ahead, behind = counts
    if ahead > 0 and behind > 0:
        return _blocked_harness("diverged")
    if ahead > 0:
        return _blocked_harness("local_ahead")
    if behind == 0:
        return {"harness_gate": "ready", "implementation_loop_start": "allowed"}

    forwarded, reason = _fast_forward_harness(git_root)
    if not forwarded:
        return _blocked_harness(reason or "fast_forward_failed")
    if not _verify_harness_readback(git_root):
        return _blocked_harness("post_readback_mismatch")
    return {"harness_gate": "updated", "implementation_loop_start": "allowed"}


def _refresh_target_repo(cwd: str) -> dict[str, object]:
    root, root_state = _repo_root(cwd)
    if root_state == "not_git":
        return {"status": "not_git"}
    if root_state is not None or root is None:
        return {"status": "refresh_failed", "reason": "git_root_failed"}

    branch = _branch(root)
    remotes = _remotes(root)
    remote, selection_state = _select_remote(root, branch, remotes)

    if selection_state == "no_remote":
        return {"status": "no_remote", **_observe(root, branch, None)}
    if selection_state == "remote_ambiguous":
        return {"status": "refresh_failed", "reason": "remote_ambiguous", **_observe(root, branch, None)}

    assert remote is not None
    fetched, failure, exit_code = _fetch(root, remote)
    if not fetched:
        return {
            "status": "refresh_failed",
            "reason": failure,
            "fetch_exit": exit_code,
            "repo_root": root,
            "branch": branch or "detached",
            "remote": remote,
        }

    return {"status": "refreshed", **_observe(root, branch, remote)}


def handle(payload: dict[str, Any], *, harness_root: str | Path | None = None) -> dict[str, Any]:
    cwd = payload.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        return _context(status="refresh_failed", reason="invalid_cwd")

    harness = Path(harness_root).resolve() if harness_root is not None else _canonical_harness_root()
    gate = _sync_harness(harness)
    if gate["harness_gate"] == "blocked":
        return _context(**gate)

    target_root, _ = _repo_root(cwd)
    if target_root is not None and Path(target_root).resolve() == harness:
        return _context(**gate, status="refreshed", **_observe(str(harness), _branch(harness), "origin"))

    return _context(**gate, **_refresh_target_repo(cwd))


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
