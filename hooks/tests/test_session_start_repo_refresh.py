#!/usr/bin/env python3
"""Contract tests for SessionStart repository remote refresh."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "runtime" / "session_start_repo_refresh.py"
TEMPLATE = ROOT / "hooks.json.tmpl"


def run(*args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(args), cwd=cwd, text=True, capture_output=True, check=check)


def git(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run("git", *args, cwd=cwd, check=check)


def init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    git("init", "-b", "main", cwd=path)
    git("config", "user.name", "HIR-230 Test", cwd=path)
    git("config", "user.email", "hir-230@example.invalid", cwd=path)
    (path / "README.md").write_text("base\n", encoding="utf-8")
    git("add", "README.md", cwd=path)
    git("commit", "-m", "base", cwd=path)


def clone_repo(remote: Path, path: Path) -> None:
    run("git", "clone", str(remote), str(path))
    git("config", "user.name", "HIR-230 Test", cwd=path)
    git("config", "user.email", "hir-230@example.invalid", cwd=path)


class SessionStartRepoRefreshTests(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.assertTrue(HOOK.is_file(), f"missing runtime hook: {HOOK}")

    def run_hook(self, cwd: Path) -> tuple[subprocess.CompletedProcess[str], str]:
        result = subprocess.run(
            ["/usr/bin/python3", str(HOOK)],
            input=json.dumps({
                "session_id": "test-session",
                "cwd": str(cwd),
                "hook_event_name": "SessionStart",
                "source": "startup",
            }),
            text=True,
            capture_output=True,
            env=os.environ.copy(),
        )
        payload = json.loads(result.stdout)
        hook_output = payload["hookSpecificOutput"]
        self.assertEqual(hook_output["hookEventName"], "SessionStart")
        return result, hook_output["additionalContext"]

    def make_remote_pair(self, root: Path) -> tuple[Path, Path, Path]:
        seed = root / "seed"
        init_repo(seed)
        remote = root / "remote.git"
        run("git", "init", "--bare", str(remote))
        git("remote", "add", "origin", str(remote), cwd=seed)
        git("push", "-u", "origin", "main", cwd=seed)
        clone = root / "clone"
        clone_repo(remote, clone)
        return seed, remote, clone

    def test_template_registers_bounded_startup_resume_hook(self) -> None:
        template = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        entries = template["hooks"]["SessionStart"]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["matcher"], "startup|resume")
        hook = entries[0]["hooks"][0]
        self.assertEqual(hook["type"], "command")
        self.assertEqual(hook["timeout"], 15)
        self.assertIn("session_start_repo_refresh.py", hook["command"])

    def test_non_git_directory_is_safe_noop(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            result, context = self.run_hook(Path(temp))
        self.assertEqual(result.returncode, 0)
        self.assertIn("status=not_git", context)

    def test_repository_without_remote_is_safe_noop(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            init_repo(repo)
            before = git("status", "--porcelain=v1", cwd=repo).stdout
            result, context = self.run_hook(repo)
            after = git("status", "--porcelain=v1", cwd=repo).stdout
        self.assertEqual(result.returncode, 0)
        self.assertIn("status=no_remote", context)
        self.assertEqual(after, before)

    def test_same_and_dirty_state_are_reported_without_worktree_change(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            _, _, repo = self.make_remote_pair(Path(temp))
            (repo / "dirty.txt").write_text("dirty\n", encoding="utf-8")
            before_head = git("rev-parse", "HEAD", cwd=repo).stdout.strip()
            result, context = self.run_hook(repo)
            after_head = git("rev-parse", "HEAD", cwd=repo).stdout.strip()
        self.assertEqual(result.returncode, 0)
        self.assertIn("status=refreshed", context)
        self.assertIn("sync=same", context)
        self.assertIn("dirty=true", context)
        self.assertEqual(after_head, before_head)

    def test_remote_ahead_local_ahead_and_diverged_are_observed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            seed, _, repo = self.make_remote_pair(root)
            (seed / "remote.txt").write_text("remote\n", encoding="utf-8")
            git("add", "remote.txt", cwd=seed)
            git("commit", "-m", "remote", cwd=seed)
            git("push", cwd=seed)
            _, context = self.run_hook(repo)
            self.assertIn("sync=remote_ahead", context)
            git("merge", "--ff-only", "@{upstream}", cwd=repo)
            (repo / "local.txt").write_text("local\n", encoding="utf-8")
            git("add", "local.txt", cwd=repo)
            git("commit", "-m", "local", cwd=repo)
            _, context = self.run_hook(repo)
            self.assertIn("sync=local_ahead", context)
            (seed / "remote-2.txt").write_text("remote-2\n", encoding="utf-8")
            git("add", "remote-2.txt", cwd=seed)
            git("commit", "-m", "remote-2", cwd=seed)
            git("push", cwd=seed)
            _, context = self.run_hook(repo)
            self.assertIn("sync=diverged", context)

    def test_single_non_origin_remote_without_upstream_is_selected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, _, repo = self.make_remote_pair(root)
            git("branch", "--unset-upstream", cwd=repo)
            git("remote", "rename", "origin", "mirror", cwd=repo)
            result, context = self.run_hook(repo)
        self.assertEqual(result.returncode, 0)
        self.assertIn("status=refreshed", context)
        self.assertIn("remote=mirror", context)

    def test_multiple_remotes_without_upstream_prefers_origin(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, remote, repo = self.make_remote_pair(root)
            git("branch", "--unset-upstream", cwd=repo)
            git("remote", "add", "backup", str(remote), cwd=repo)
            result, context = self.run_hook(repo)
        self.assertEqual(result.returncode, 0)
        self.assertIn("status=refreshed", context)
        self.assertIn("remote=origin", context)

    def test_multiple_remotes_without_upstream_or_origin_is_ambiguous(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, remote, repo = self.make_remote_pair(root)
            git("branch", "--unset-upstream", cwd=repo)
            git("remote", "rename", "origin", "one", cwd=repo)
            git("remote", "add", "two", str(remote), cwd=repo)
            result, context = self.run_hook(repo)
        self.assertEqual(result.returncode, 0)
        self.assertIn("status=refresh_failed", context)
        self.assertIn("reason=remote_ambiguous", context)

    def test_upstream_remote_wins_over_origin(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, _, repo = self.make_remote_pair(root)
            git("remote", "rename", "origin", "upstream", cwd=repo)
            git("remote", "add", "origin", str(root / "missing.git"), cwd=repo)
            result, context = self.run_hook(repo)
        self.assertEqual(result.returncode, 0)
        self.assertIn("status=refreshed", context)
        self.assertIn("remote=upstream", context)

    def test_fetch_failure_exits_zero_and_returns_model_visible_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            init_repo(repo)
            git("remote", "add", "origin", str(Path(temp) / "missing.git"), cwd=repo)
            result, context = self.run_hook(repo)
        self.assertEqual(result.returncode, 0)
        self.assertIn("status=refresh_failed", context)
        self.assertIn("reason=fetch_failed", context)
        self.assertNotIn("status=refreshed", context)

    def test_fetch_timeout_is_caught_and_model_visible(self) -> None:
        spec = importlib.util.spec_from_file_location("session_start_repo_refresh", HOOK)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            init_repo(repo)
            git("remote", "add", "origin", str(Path(temp) / "remote.git"), cwd=repo)
            real_run = module.subprocess.run
            def fake_run(args, *pargs, **kwargs):
                if "fetch" in args:
                    raise subprocess.TimeoutExpired(args, kwargs.get("timeout", 10))
                return real_run(args, *pargs, **kwargs)
            with mock.patch.object(module.subprocess, "run", side_effect=fake_run):
                response = module.handle({"cwd": str(repo), "hook_event_name": "SessionStart"})
        context = response["hookSpecificOutput"]["additionalContext"]
        self.assertIn("status=refresh_failed", context)
        self.assertIn("reason=fetch_timeout", context)

    def test_fetch_only_touches_current_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            seed_a, _, repo_a = self.make_remote_pair(root / "a")
            seed_b, _, repo_b = self.make_remote_pair(root / "b")
            (seed_a / "a.txt").write_text("a\n", encoding="utf-8")
            git("add", "a.txt", cwd=seed_a)
            git("commit", "-m", "a", cwd=seed_a)
            git("push", cwd=seed_a)
            (seed_b / "b.txt").write_text("b\n", encoding="utf-8")
            git("add", "b.txt", cwd=seed_b)
            git("commit", "-m", "b", cwd=seed_b)
            git("push", cwd=seed_b)
            before_b = git("rev-parse", "refs/remotes/origin/main", cwd=repo_b).stdout.strip()
            self.run_hook(repo_a)
            after_b = git("rev-parse", "refs/remotes/origin/main", cwd=repo_b).stdout.strip()
        self.assertEqual(after_b, before_b)

    def test_pruned_upstream_is_reported_without_crash(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            seed, _, repo = self.make_remote_pair(root)
            git("checkout", "-b", "topic", cwd=seed)
            (seed / "topic.txt").write_text("topic\n", encoding="utf-8")
            git("add", "topic.txt", cwd=seed)
            git("commit", "-m", "topic", cwd=seed)
            git("push", "-u", "origin", "topic", cwd=seed)
            git("fetch", cwd=repo)
            git("checkout", "-b", "topic", "--track", "origin/topic", cwd=repo)
            git("push", "origin", "--delete", "topic", cwd=seed)
            result, context = self.run_hook(repo)
        self.assertEqual(result.returncode, 0)
        self.assertIn("status=refreshed", context)
        self.assertIn("upstream=missing", context)


if __name__ == "__main__":
    unittest.main()
