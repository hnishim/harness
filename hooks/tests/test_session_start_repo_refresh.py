#!/usr/bin/env python3
"""Contract tests for SessionStart repository remote refresh."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
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


def load_hook_module():
    spec = importlib.util.spec_from_file_location("session_start_repo_refresh", HOOK)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SessionStartRepoRefreshTests(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.assertTrue(HOOK.is_file(), f"missing runtime hook: {HOOK}")

    def make_harness(self, root: Path) -> Path:
        _, remote, harness = self.make_remote_pair(root / "harness-control-plane")
        canonical = "git@github.com:hnishim/harness.git"
        git("remote", "set-url", "origin", canonical, cwd=harness)
        git("config", f"url.{remote}.insteadOf", canonical, cwd=harness)
        return harness.resolve()

    def run_hook(self, cwd: Path) -> tuple[subprocess.CompletedProcess[str], str]:
        with tempfile.TemporaryDirectory() as harness_temp:
            harness = self.make_harness(Path(harness_temp))
            result = subprocess.run(
                ["/usr/bin/python3", "-c", (
                    "import importlib.util,json,sys;"
                    f"spec=importlib.util.spec_from_file_location('session_start_repo_refresh',{str(HOOK)!r});"
                    "module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);"
                    f"payload=json.loads(sys.stdin.read());print(json.dumps(module.handle(payload,harness_root={str(harness)!r})))"
                )],
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
        run("git", "--git-dir", str(remote), "symbolic-ref", "HEAD", "refs/heads/main")
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

    def test_git_root_command_failure_is_not_misclassified_as_not_git(self) -> None:
        module = load_hook_module()
        failure = subprocess.CompletedProcess(
            ["git", "rev-parse", "--show-toplevel"],
            2,
            stdout="",
            stderr="fatal: simulated git command failure\n",
        )
        with tempfile.TemporaryDirectory() as temp:
            harness = self.make_harness(Path(temp))
            real_git = module._git

            def fail_target_root(cwd, *args, **kwargs):
                if str(cwd) == "/tmp/repo" and args[:2] == ("rev-parse", "--show-toplevel"):
                    return failure
                return real_git(cwd, *args, **kwargs)

            with mock.patch.object(module, "_git", side_effect=fail_target_root):
                response = module.handle(
                    {"cwd": "/tmp/repo", "hook_event_name": "SessionStart"},
                    harness_root=harness,
                )
        context = response["hookSpecificOutput"]["additionalContext"]
        self.assertIn("status=refresh_failed", context)
        self.assertIn("reason=git_root_failed", context)
        self.assertNotIn("status=not_git", context)

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

    def test_same_and_dirty_state_are_reported_without_worktree_index_or_branch_change(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            _, _, repo = self.make_remote_pair(Path(temp))
            (repo / "dirty.txt").write_text("dirty\n", encoding="utf-8")
            before_head = git("rev-parse", "HEAD", cwd=repo).stdout.strip()
            before_branch = git("symbolic-ref", "--quiet", "--short", "HEAD", cwd=repo).stdout.strip()
            before_status = git("status", "--porcelain=v1", cwd=repo).stdout
            result, context = self.run_hook(repo)
            after_head = git("rev-parse", "HEAD", cwd=repo).stdout.strip()
            after_branch = git("symbolic-ref", "--quiet", "--short", "HEAD", cwd=repo).stdout.strip()
            after_status = git("status", "--porcelain=v1", cwd=repo).stdout
        self.assertEqual(result.returncode, 0)
        self.assertIn("status=refreshed", context)
        self.assertIn("sync=same", context)
        self.assertIn("dirty=true", context)
        self.assertEqual(after_head, before_head)
        self.assertEqual(after_branch, before_branch)
        self.assertEqual(after_status, before_status)

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

    def test_fetch_failure_with_existing_upstream_does_not_report_stale_sync_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, _, repo = self.make_remote_pair(root)
            git("remote", "set-url", "origin", str(root / "missing.git"), cwd=repo)
            result, context = self.run_hook(repo)
        self.assertEqual(result.returncode, 0)
        self.assertIn("status=refresh_failed", context)
        self.assertIn("reason=fetch_failed", context)
        self.assertNotIn("status=refreshed", context)
        self.assertNotIn("sync=", context)
        self.assertNotIn("ahead=", context)
        self.assertNotIn("behind=", context)

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

    def test_fetch_timeout_uses_bounded_noninteractive_subprocess_contract(self) -> None:
        module = load_hook_module()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            harness = self.make_harness(root)
            repo = root / "repo"
            init_repo(repo)
            git("remote", "add", "origin", str(root / "remote.git"), cwd=repo)
            real_run = module.subprocess.run
            captured: dict[str, object] = {}

            def fake_run(args, *pargs, **kwargs):
                if "fetch" in args and "-C" in args:
                    repo_arg = Path(args[args.index("-C") + 1]).resolve()
                    if repo_arg == repo.resolve():
                        captured["timeout"] = kwargs.get("timeout")
                        captured["env"] = kwargs.get("env")
                        raise subprocess.TimeoutExpired(args, kwargs.get("timeout", 10))
                return real_run(args, *pargs, **kwargs)

            with mock.patch.object(module.subprocess, "run", side_effect=fake_run):
                response = module.handle(
                    {"cwd": str(repo), "hook_event_name": "SessionStart"},
                    harness_root=harness,
                )
        context = response["hookSpecificOutput"]["additionalContext"]
        self.assertIn("status=refresh_failed", context)
        self.assertIn("reason=fetch_timeout", context)
        self.assertNotIn("sync=", context)
        self.assertEqual(captured["timeout"], 5)
        env = captured["env"]
        self.assertIsInstance(env, dict)
        assert isinstance(env, dict)
        self.assertEqual(env["GIT_TERMINAL_PROMPT"], "0")
        self.assertEqual(env["GCM_INTERACTIVE"], "Never")

    def test_timeout_main_returns_zero_with_model_visible_failure(self) -> None:
        module = load_hook_module()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            harness = self.make_harness(root)
            repo = root / "repo"
            init_repo(repo)
            git("remote", "add", "origin", str(root / "remote.git"), cwd=repo)
            stdin = io.StringIO(json.dumps({"cwd": str(repo), "hook_event_name": "SessionStart"}))
            stdout = io.StringIO()
            original_handle = module.handle
            real_fetch = module._fetch

            def timeout_target(root, remote):
                if Path(root).resolve() == repo.resolve():
                    return False, "fetch_timeout", None
                return real_fetch(root, remote)

            def handle_with_harness(payload):
                return original_handle(payload, harness_root=harness)

            with mock.patch.object(module, "_fetch", side_effect=timeout_target), \
                 mock.patch.object(module, "handle", side_effect=handle_with_harness), \
                 mock.patch.object(module.sys, "stdin", stdin), \
                 mock.patch.object(module.sys, "stdout", stdout):
                exit_code = module.main()
        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        context = payload["hookSpecificOutput"]["additionalContext"]
        self.assertIn("status=refresh_failed", context)
        self.assertIn("reason=fetch_timeout", context)
        self.assertNotIn("sync=", context)

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


class HarnessControlPlaneSyncTests(unittest.TestCase):
    """Acceptance tests for the Harness-only SessionStart fast-forward gate."""

    def make_remote_pair(self, root: Path) -> tuple[Path, Path, Path]:
        seed = root / "seed"
        init_repo(seed)
        remote = root / "remote.git"
        run("git", "init", "--bare", str(remote))
        git("remote", "add", "origin", str(remote), cwd=seed)
        git("push", "-u", "origin", "main", cwd=seed)
        run("git", "--git-dir", str(remote), "symbolic-ref", "HEAD", "refs/heads/main")
        clone = root / "clone"
        clone_repo(remote, clone)
        return seed, remote, clone

    def mark_as_canonical_harness(self, harness: Path, remote: Path) -> None:
        canonical = "git@github.com:hnishim/harness.git"
        git("remote", "set-url", "origin", canonical, cwd=harness)
        git("config", f"url.{remote}.insteadOf", canonical, cwd=harness)

    def make_registered_harness(self, root: Path) -> tuple[Path, Path, Path]:
        seed = root / "seed"
        init_repo(seed)
        registered_hook = seed / "hooks" / "runtime" / HOOK.name
        registered_hook.parent.mkdir(parents=True)
        shutil.copy2(HOOK, registered_hook)
        git("add", str(registered_hook.relative_to(seed)), cwd=seed)
        git("commit", "-m", "install registered SessionStart hook", cwd=seed)

        remote = root / "remote.git"
        run("git", "init", "--bare", str(remote))
        git("remote", "add", "origin", str(remote), cwd=seed)
        git("push", "-u", "origin", "main", cwd=seed)
        run("git", "--git-dir", str(remote), "symbolic-ref", "HEAD", "refs/heads/main")
        clone = root / "clone"
        clone_repo(remote, clone)
        return seed, remote, clone

    def run_registered_hook(self, harness: Path, target: Path) -> dict[str, object]:
        registered_hook = harness / "hooks" / "runtime" / HOOK.name
        result = subprocess.run(
            ["/usr/bin/python3", str(registered_hook)],
            input=json.dumps(
                {
                    "session_id": "test-session",
                    "cwd": str(target),
                    "hook_event_name": "SessionStart",
                    "source": "startup",
                }
            ),
            text=True,
            capture_output=True,
            check=True,
        )
        return json.loads(result.stdout)

    def handle_with_harness(self, module, target: Path, harness: Path):
        return module.handle(
            {"cwd": str(target), "hook_event_name": "SessionStart"},
            harness_root=harness,
        )

    def context(self, response) -> str:
        return response["hookSpecificOutput"]["additionalContext"]

    def test_fetch_budget_leaves_margin_inside_outer_hook_timeout(self) -> None:
        module = load_hook_module()
        template = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        outer_timeout = template["hooks"]["SessionStart"][0]["hooks"][0]["timeout"]
        self.assertEqual(module.FETCH_TIMEOUT_SECONDS, 5)
        self.assertLessEqual(module.FETCH_TIMEOUT_SECONDS * 2, outer_timeout - 5)

    def test_same_harness_is_ready_without_moving_head(self) -> None:
        module = load_hook_module()
        with tempfile.TemporaryDirectory() as temp:
            _, harness_remote, harness = self.make_remote_pair(Path(temp) / "harness")
            self.mark_as_canonical_harness(harness, harness_remote)
            before = git("rev-parse", "HEAD", cwd=harness).stdout.strip()
            response = self.handle_with_harness(module, harness, harness)
            after = git("rev-parse", "HEAD", cwd=harness).stdout.strip()
        self.assertIn("harness_gate=ready", self.context(response))
        self.assertEqual(after, before)

    def test_clean_main_remote_ahead_fast_forwards_only_harness(self) -> None:
        module = load_hook_module()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            seed, harness_remote, harness = self.make_remote_pair(root / "harness")
            self.mark_as_canonical_harness(harness, harness_remote)
            _, _, target = self.make_remote_pair(root / "target")
            (seed / "remote.txt").write_text("remote\n", encoding="utf-8")
            git("add", "remote.txt", cwd=seed)
            git("commit", "-m", "remote", cwd=seed)
            git("push", cwd=seed)
            target_before = git("rev-parse", "HEAD", cwd=target).stdout.strip()
            response = self.handle_with_harness(module, target, harness)
            harness_head = git("rev-parse", "HEAD", cwd=harness).stdout.strip()
            harness_remote = git("rev-parse", "origin/main", cwd=harness).stdout.strip()
            target_after = git("rev-parse", "HEAD", cwd=target).stdout.strip()
        self.assertIn("harness_gate=updated", self.context(response))
        self.assertEqual(harness_head, harness_remote)
        self.assertEqual(target_after, target_before)

    def test_dirty_non_harness_target_does_not_block_ready_gate(self) -> None:
        module = load_hook_module()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, harness_remote, harness = self.make_remote_pair(root / "harness")
            self.mark_as_canonical_harness(harness, harness_remote)
            target_seed, _, target = self.make_remote_pair(root / "target")
            (target / "uncommitted.txt").write_text("keep\n", encoding="utf-8")
            target_before = git("rev-parse", "HEAD", cwd=target).stdout.strip()
            target_status_before = git("status", "--porcelain=v1", cwd=target).stdout

            (target_seed / "later.txt").write_text("later\n", encoding="utf-8")
            git("add", "later.txt", cwd=target_seed)
            git("commit", "-m", "later", cwd=target_seed)
            git("push", cwd=target_seed)

            response = self.handle_with_harness(module, target, harness)
            target_after = git("rev-parse", "HEAD", cwd=target).stdout.strip()
            target_status_after = git("status", "--porcelain=v1", cwd=target).stdout
            target_remote_after = git(
                "rev-parse", "refs/remotes/origin/main", cwd=target
            ).stdout.strip()
            target_seed_head = git("rev-parse", "HEAD", cwd=target_seed).stdout.strip()

        context = self.context(response)
        self.assertIn("harness_gate=ready", context)
        self.assertIn("status=refreshed", context)
        self.assertIn("dirty=true", context)
        self.assertEqual(target_after, target_before)
        self.assertEqual(target_status_after, target_status_before)
        self.assertEqual(target_remote_after, target_seed_head)

    def test_registered_clean_execution_harness_allows_dirty_development_harness(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, execution_remote, execution_harness = self.make_registered_harness(
                root / "execution-harness"
            )
            self.mark_as_canonical_harness(execution_harness, execution_remote)
            _, development_remote, development_harness = self.make_registered_harness(
                root / "development-harness"
            )
            self.mark_as_canonical_harness(development_harness, development_remote)
            _, _, target = self.make_remote_pair(root / "target")
            (development_harness / "uncommitted.txt").write_text(
                "keep development work\n", encoding="utf-8"
            )
            development_head = git(
                "rev-parse", "HEAD", cwd=development_harness
            ).stdout.strip()
            development_status = git(
                "status", "--porcelain=v1", cwd=development_harness
            ).stdout

            response = self.run_registered_hook(execution_harness, target)

            self.assertIn("harness_gate=ready", self.context(response))
            self.assertIn("status=refreshed", self.context(response))
            self.assertEqual(
                git("rev-parse", "HEAD", cwd=development_harness).stdout.strip(),
                development_head,
            )
            self.assertEqual(
                git("status", "--porcelain=v1", cwd=development_harness).stdout,
                development_status,
            )

    def test_registered_clean_execution_harness_allows_local_ahead_development_harness(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, execution_remote, execution_harness = self.make_registered_harness(
                root / "execution-harness"
            )
            self.mark_as_canonical_harness(execution_harness, execution_remote)
            _, development_remote, development_harness = self.make_registered_harness(
                root / "development-harness"
            )
            self.mark_as_canonical_harness(development_harness, development_remote)
            _, _, target = self.make_remote_pair(root / "target")
            (development_harness / "local.txt").write_text(
                "keep local development commit\n", encoding="utf-8"
            )
            git("add", "local.txt", cwd=development_harness)
            git("commit", "-m", "local development work", cwd=development_harness)
            development_head = git(
                "rev-parse", "HEAD", cwd=development_harness
            ).stdout.strip()

            response = self.run_registered_hook(execution_harness, target)

            self.assertIn("harness_gate=ready", self.context(response))
            self.assertIn("status=refreshed", self.context(response))
            self.assertEqual(
                git("rev-parse", "HEAD", cwd=development_harness).stdout.strip(),
                development_head,
            )

    def test_registered_dirty_development_harness_blocks_start(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, development_remote, development_harness = self.make_registered_harness(
                root / "development-harness"
            )
            self.mark_as_canonical_harness(development_harness, development_remote)
            _, _, target = self.make_remote_pair(root / "target")
            (development_harness / "uncommitted.txt").write_text(
                "keep development work\n", encoding="utf-8"
            )
            development_head = git(
                "rev-parse", "HEAD", cwd=development_harness
            ).stdout.strip()
            target_remote_before = git(
                "rev-parse", "refs/remotes/origin/main", cwd=target
            ).stdout.strip()

            response = self.run_registered_hook(development_harness, target)

            self.assertIn("harness_gate=blocked", self.context(response))
            self.assertIn("harness_reason=dirty", self.context(response))
            self.assertEqual(
                git("rev-parse", "HEAD", cwd=development_harness).stdout.strip(),
                development_head,
            )
            self.assertEqual(
                git("rev-parse", "refs/remotes/origin/main", cwd=target).stdout.strip(),
                target_remote_before,
            )

    def test_registered_local_ahead_development_harness_blocks_start(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, development_remote, development_harness = self.make_registered_harness(
                root / "development-harness"
            )
            self.mark_as_canonical_harness(development_harness, development_remote)
            _, _, target = self.make_remote_pair(root / "target")
            (development_harness / "local.txt").write_text(
                "keep local development commit\n", encoding="utf-8"
            )
            git("add", "local.txt", cwd=development_harness)
            git("commit", "-m", "local development work", cwd=development_harness)
            development_head = git(
                "rev-parse", "HEAD", cwd=development_harness
            ).stdout.strip()
            target_remote_before = git(
                "rev-parse", "refs/remotes/origin/main", cwd=target
            ).stdout.strip()

            response = self.run_registered_hook(development_harness, target)

            self.assertIn("harness_gate=blocked", self.context(response))
            self.assertIn("harness_reason=local_ahead", self.context(response))
            self.assertEqual(
                git("rev-parse", "HEAD", cwd=development_harness).stdout.strip(),
                development_head,
            )
            self.assertEqual(
                git("rev-parse", "refs/remotes/origin/main", cwd=target).stdout.strip(),
                target_remote_before,
            )

    def test_dirty_target_preserves_index_and_other_worktree_during_refresh(self) -> None:
        module = load_hook_module()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, harness_remote, harness = self.make_remote_pair(root / "harness")
            self.mark_as_canonical_harness(harness, harness_remote)
            target_seed, _, target = self.make_remote_pair(root / "target")

            (target / "README.md").write_text("tracked edit\n", encoding="utf-8")
            (target / "staged.txt").write_text("staged\n", encoding="utf-8")
            git("add", "staged.txt", cwd=target)
            (target / "untracked.txt").write_text("untracked\n", encoding="utf-8")
            secondary = root / "target-secondary"
            git("worktree", "add", "-b", "secondary", str(secondary), cwd=target)
            (secondary / "secondary.txt").write_text("secondary\n", encoding="utf-8")

            before_head = git("rev-parse", "HEAD", cwd=target).stdout.strip()
            before_branch = git(
                "symbolic-ref", "--quiet", "--short", "HEAD", cwd=target
            ).stdout.strip()
            before_status = git("status", "--porcelain=v1", cwd=target).stdout
            before_diff = git("diff", cwd=target).stdout
            before_cached_diff = git("diff", "--cached", cwd=target).stdout
            before_secondary_head = git("rev-parse", "HEAD", cwd=secondary).stdout.strip()
            before_secondary_status = git(
                "status", "--porcelain=v1", cwd=secondary
            ).stdout

            (target_seed / "later.txt").write_text("later\n", encoding="utf-8")
            git("add", "later.txt", cwd=target_seed)
            git("commit", "-m", "later", cwd=target_seed)
            git("push", cwd=target_seed)

            response = self.handle_with_harness(module, target, harness)
            target_remote_after = git(
                "rev-parse", "refs/remotes/origin/main", cwd=target
            ).stdout.strip()
            target_seed_head = git("rev-parse", "HEAD", cwd=target_seed).stdout.strip()

            self.assertIn("harness_gate=ready", self.context(response))
            self.assertIn("status=refreshed", self.context(response))
            self.assertEqual(git("rev-parse", "HEAD", cwd=target).stdout.strip(), before_head)
            self.assertEqual(
                git("symbolic-ref", "--quiet", "--short", "HEAD", cwd=target).stdout.strip(),
                before_branch,
            )
            self.assertEqual(git("status", "--porcelain=v1", cwd=target).stdout, before_status)
            self.assertEqual(git("diff", cwd=target).stdout, before_diff)
            self.assertEqual(git("diff", "--cached", cwd=target).stdout, before_cached_diff)
            self.assertEqual(target_remote_after, target_seed_head)
            self.assertEqual(
                git("rev-parse", "HEAD", cwd=secondary).stdout.strip(),
                before_secondary_head,
            )
            self.assertEqual(
                git("status", "--porcelain=v1", cwd=secondary).stdout,
                before_secondary_status,
            )

    def test_target_remote_ref_lock_failure_preserves_local_state(self) -> None:
        module = load_hook_module()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, harness_remote, harness = self.make_remote_pair(root / "harness")
            self.mark_as_canonical_harness(harness, harness_remote)
            target_seed, _, target = self.make_remote_pair(root / "target")
            (target_seed / "later.txt").write_text("later\n", encoding="utf-8")
            git("add", "later.txt", cwd=target_seed)
            git("commit", "-m", "later", cwd=target_seed)
            git("push", cwd=target_seed)
            (target / "README.md").write_text("keep\n", encoding="utf-8")
            (target / "staged.txt").write_text("staged\n", encoding="utf-8")
            git("add", "staged.txt", cwd=target)
            (target / "untracked.txt").write_text("untracked\n", encoding="utf-8")
            before_head = git("rev-parse", "HEAD", cwd=target).stdout.strip()
            before_status = git("status", "--porcelain=v1", cwd=target).stdout
            before_diff = git("diff", cwd=target).stdout
            before_cached_diff = git("diff", "--cached", cwd=target).stdout
            ref_path = Path(
                git("rev-parse", "--git-path", "refs/remotes/origin/main", cwd=target).stdout.strip()
            )
            if not ref_path.is_absolute():
                ref_path = target / ref_path
            lock_path = ref_path.with_name(f"{ref_path.name}.lock")
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            lock_path.write_text("held by test\n", encoding="utf-8")

            response = self.handle_with_harness(module, target, harness)
            context = self.context(response)

            self.assertIn("status=refresh_failed", context)
            self.assertIn("reason=fetch_failed", context)
            self.assertEqual(git("rev-parse", "HEAD", cwd=target).stdout.strip(), before_head)
            self.assertEqual(git("status", "--porcelain=v1", cwd=target).stdout, before_status)
            self.assertEqual(git("diff", cwd=target).stdout, before_diff)
            self.assertEqual(git("diff", "--cached", cwd=target).stdout, before_cached_diff)
            self.assertTrue(lock_path.is_file())

    def test_dirty_harness_is_blocked_and_target_fetch_is_short_circuited(self) -> None:
        module = load_hook_module()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, harness_remote, harness = self.make_remote_pair(root / "harness")
            self.mark_as_canonical_harness(harness, harness_remote)
            _, _, target = self.make_remote_pair(root / "target")
            (harness / "dirty.txt").write_text("dirty\n", encoding="utf-8")
            before_head = git("rev-parse", "HEAD", cwd=harness).stdout.strip()
            before_status = git("status", "--porcelain=v1", cwd=harness).stdout
            target_remote_before = git("rev-parse", "refs/remotes/origin/main", cwd=target).stdout.strip()
            target_seed = root / "target" / "seed"
            (target_seed / "later.txt").write_text("later\n", encoding="utf-8")
            git("add", "later.txt", cwd=target_seed)
            git("commit", "-m", "later", cwd=target_seed)
            git("push", cwd=target_seed)
            response = self.handle_with_harness(module, target, harness)
            target_remote_after = git("rev-parse", "refs/remotes/origin/main", cwd=target).stdout.strip()
            after_head = git("rev-parse", "HEAD", cwd=harness).stdout.strip()
            after_status = git("status", "--porcelain=v1", cwd=harness).stdout
        self.assertIn("harness_gate=blocked", self.context(response))
        self.assertIn("harness_reason=dirty", self.context(response))
        self.assertEqual(target_remote_after, target_remote_before)
        self.assertEqual(after_head, before_head)
        self.assertEqual(after_status, before_status)

    def test_local_ahead_and_diverged_harness_never_move_head(self) -> None:
        module = load_hook_module()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            seed, harness_remote, harness = self.make_remote_pair(root / "harness")
            self.mark_as_canonical_harness(harness, harness_remote)
            (harness / "local.txt").write_text("local\n", encoding="utf-8")
            git("add", "local.txt", cwd=harness)
            git("commit", "-m", "local", cwd=harness)
            local_head = git("rev-parse", "HEAD", cwd=harness).stdout.strip()
            response = self.handle_with_harness(module, harness, harness)
            self.assertIn("harness_reason=local_ahead", self.context(response))
            self.assertEqual(git("rev-parse", "HEAD", cwd=harness).stdout.strip(), local_head)

            (seed / "remote.txt").write_text("remote\n", encoding="utf-8")
            git("add", "remote.txt", cwd=seed)
            git("commit", "-m", "remote", cwd=seed)
            git("push", cwd=seed)
            response = self.handle_with_harness(module, harness, harness)
            self.assertIn("harness_reason=diverged", self.context(response))
            self.assertEqual(git("rev-parse", "HEAD", cwd=harness).stdout.strip(), local_head)

    def test_detached_non_main_no_origin_and_unexpected_origin_are_blocked(self) -> None:
        module = load_hook_module()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, harness_remote, harness = self.make_remote_pair(root / "detached")
            self.mark_as_canonical_harness(harness, harness_remote)
            git("checkout", "--detach", cwd=harness)
            response = self.handle_with_harness(module, harness, harness)
            self.assertIn("harness_reason=detached", self.context(response))

            _, harness_remote, harness = self.make_remote_pair(root / "topic")
            self.mark_as_canonical_harness(harness, harness_remote)
            git("checkout", "-b", "topic", cwd=harness)
            response = self.handle_with_harness(module, harness, harness)
            self.assertIn("harness_reason=non_main_branch", self.context(response))

            repo = root / "no-origin"
            init_repo(repo)
            response = self.handle_with_harness(module, repo, repo)
            self.assertIn("harness_reason=no_origin", self.context(response))

            _, _, harness = self.make_remote_pair(root / "unexpected")
            git(
                "remote",
                "set-url",
                "origin",
                "git@github.com:someone-else/harness.git",
                cwd=harness,
            )
            before_head = git("rev-parse", "HEAD", cwd=harness).stdout.strip()
            before_status = git("status", "--porcelain=v1", cwd=harness).stdout
            response = self.handle_with_harness(module, harness, harness)
            after_head = git("rev-parse", "HEAD", cwd=harness).stdout.strip()
            after_status = git("status", "--porcelain=v1", cwd=harness).stdout
            self.assertIn("harness_reason=unexpected_origin", self.context(response))
            self.assertEqual(after_head, before_head)
            self.assertEqual(after_status, before_status)

    def test_harness_fetch_failure_is_blocked_and_target_fetch_is_short_circuited(self) -> None:
        module = load_hook_module()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, harness_remote, harness = self.make_remote_pair(root / "harness")
            self.mark_as_canonical_harness(harness, harness_remote)
            target_seed, _, target = self.make_remote_pair(root / "target")
            target_remote_before = git("rev-parse", "refs/remotes/origin/main", cwd=target).stdout.strip()
            (target_seed / "later.txt").write_text("later\n", encoding="utf-8")
            git("add", "later.txt", cwd=target_seed)
            git("commit", "-m", "later", cwd=target_seed)
            git("push", cwd=target_seed)
            real_fetch = module._fetch

            def fail_harness(repo, remote):
                if Path(repo).resolve() == harness.resolve():
                    return False, "fetch_failed", 128
                return real_fetch(repo, remote)

            with mock.patch.object(module, "_fetch", side_effect=fail_harness):
                response = self.handle_with_harness(module, target, harness)
            target_remote_after = git("rev-parse", "refs/remotes/origin/main", cwd=target).stdout.strip()
        context = self.context(response)
        self.assertIn("harness_gate=blocked", context)
        self.assertIn("harness_reason=fetch_failed", context)
        self.assertEqual(target_remote_after, target_remote_before)

    def test_harness_fetch_timeout_is_blocked_and_model_visible(self) -> None:
        module = load_hook_module()
        with tempfile.TemporaryDirectory() as temp:
            _, harness_remote, harness = self.make_remote_pair(Path(temp) / "harness")
            self.mark_as_canonical_harness(harness, harness_remote)
            real_fetch = module._fetch

            def timeout_harness(root, remote):
                if Path(root).resolve() == harness.resolve():
                    return False, "fetch_timeout", None
                return real_fetch(root, remote)

            with mock.patch.object(module, "_fetch", side_effect=timeout_harness):
                response = self.handle_with_harness(module, harness, harness)
        self.assertIn("harness_gate=blocked", self.context(response))
        self.assertIn("harness_reason=fetch_timeout", self.context(response))

    def test_target_fetch_timeout_remains_model_visible_after_ready_harness(self) -> None:
        module = load_hook_module()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, harness_remote, harness = self.make_remote_pair(root / "harness")
            self.mark_as_canonical_harness(harness, harness_remote)
            _, _, target = self.make_remote_pair(root / "target")
            real_fetch = module._fetch

            def timeout_target(repo, remote):
                if Path(repo).resolve() == target.resolve():
                    return False, "fetch_timeout", None
                return real_fetch(repo, remote)

            with mock.patch.object(module, "_fetch", side_effect=timeout_target):
                response = self.handle_with_harness(module, target, harness)
        context = self.context(response)
        self.assertIn("harness_gate=ready", context)
        self.assertIn("status=refresh_failed", context)
        self.assertIn("reason=fetch_timeout", context)

    def test_fast_forward_failure_and_post_readback_mismatch_are_blocked(self) -> None:
        module = load_hook_module()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            seed, harness_remote, harness = self.make_remote_pair(root / "ff-failure")
            self.mark_as_canonical_harness(harness, harness_remote)
            (seed / "remote.txt").write_text("remote\n", encoding="utf-8")
            git("add", "remote.txt", cwd=seed)
            git("commit", "-m", "remote", cwd=seed)
            git("push", cwd=seed)
            with mock.patch.object(module, "_fast_forward_harness", return_value=(False, "fast_forward_failed")):
                response = self.handle_with_harness(module, harness, harness)
            self.assertIn("harness_reason=fast_forward_failed", self.context(response))

            seed, harness_remote, harness = self.make_remote_pair(root / "readback")
            self.mark_as_canonical_harness(harness, harness_remote)
            (seed / "remote.txt").write_text("remote\n", encoding="utf-8")
            git("add", "remote.txt", cwd=seed)
            git("commit", "-m", "remote", cwd=seed)
            git("push", cwd=seed)
            with mock.patch.object(module, "_verify_harness_readback", return_value=False):
                response = self.handle_with_harness(module, harness, harness)
            self.assertIn("harness_reason=post_readback_mismatch", self.context(response))

    def test_blocked_context_explicitly_prohibits_implementation_loop_start(self) -> None:
        module = load_hook_module()
        with tempfile.TemporaryDirectory() as temp:
            _, harness_remote, harness = self.make_remote_pair(Path(temp) / "harness")
            self.mark_as_canonical_harness(harness, harness_remote)
            (harness / "dirty.txt").write_text("dirty\n", encoding="utf-8")
            response = self.handle_with_harness(module, harness, harness)
        context = self.context(response)
        self.assertIn("harness_gate=blocked", context)
        self.assertIn("implementation_loop_start=prohibited", context)


if __name__ == "__main__":
    unittest.main()
