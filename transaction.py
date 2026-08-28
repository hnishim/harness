#!/usr/bin/env python3
"""Cross-component transaction fixture used by the HIR-82 acceptance tests."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


STAGES = (
    ("hooks", Path("runtime/.runtime/hooks.json")),
    ("agents", Path("runtime/agents/planner.toml")),
    ("skills", Path("runtime/skills/.system")),
    ("mirrors", Path("runtime/custom-instructions-sync/state")),
    ("plist", Path("runtime/LaunchAgents/com.example.harness.plist")),
    ("launchagent", Path("runtime/launchctl.state")),
    ("backup", Path("runtime/backups/existing")),
    ("macos-gate", Path("runtime/AGENTS.md")),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--real", action="store_true")
    parser.add_argument("--fixture-root", type=Path)
    parser.add_argument("--path", action="append", default=[])
    parser.add_argument("--codex-home", type=Path)
    parser.add_argument("--launchagent-domain")
    parser.add_argument("--launchagent-label")
    parser.add_argument("--launchagent-plist", type=Path)
    parser.add_argument("--bookmark-domain")
    parser.add_argument("--evidence-dir", type=Path)
    parser.add_argument("--command", nargs=argparse.REMAINDER)
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("--fail-at", choices=[f"after-{name}" for name, _ in STAGES] + ["macos-gate"])
    group.add_argument("--success", action="store_true")
    return parser.parse_args()


def trace_line(path: Optional[Path], value: str) -> None:
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(value + "\n")


def replace_with_marker(path: Path, marker: Path, stage: str) -> None:
    if not path.exists() and not path.is_symlink():
        raise RuntimeError(f"fixture target is missing: {path}")
    path.rename(marker)
    path.write_text(f"mutated:{stage}\n", encoding="utf-8")


def rollback(changes: List[Tuple[Path, Path]]) -> None:
    for path, marker in reversed(changes):
        if path.exists() or path.is_symlink():
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink()
        marker.rename(path)


def lexists(path: Path) -> bool:
    return os.path.lexists(path)


def remove_path(path: Path) -> None:
    if not lexists(path):
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def copy_entry(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    info = source.lstat()
    if source.is_symlink():
        destination.symlink_to(os.readlink(source))
    elif source.is_dir():
        shutil.copytree(source, destination, symlinks=True, copy_function=shutil.copy2)
    elif source.is_file():
        shutil.copy2(source, destination)
    else:
        raise RuntimeError(f"unsupported transaction path: {source}")


def snapshot_path(source: Path, destination: Path) -> Dict[str, Any]:
    if not lexists(source):
        return {"path": str(source), "present": False}
    copy_entry(source, destination)
    info = source.lstat()
    kind = "symlink" if source.is_symlink() else "directory" if source.is_dir() else "file"
    return {
        "path": str(source),
        "present": True,
        "kind": kind,
        "mode": info.st_mode & 0o7777,
    }


def restore_snapshot(source: Path, destination: Path, metadata: Dict[str, Any]) -> None:
    remove_path(source)
    if metadata.get("present"):
        copy_entry(destination, source)


def launchctl_state(domain: Optional[str], label: Optional[str]) -> Optional[Tuple[bool, bool]]:
    launchctl = shutil.which("launchctl")
    if not launchctl or not domain or not label:
        return None
    result = subprocess.run(
        [launchctl, "print", f"{domain}/{label}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return False, False
    return True, "active count = 0" not in result.stdout


def stop_launchagent(domain: Optional[str], label: Optional[str]) -> Optional[Tuple[bool, bool]]:
    state = launchctl_state(domain, label)
    if state and state[0]:
        launchctl = shutil.which("launchctl")
        assert launchctl is not None
        result = subprocess.run(
            [launchctl, "bootout", f"{domain}/{label}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"could not stop LaunchAgent: {result.stderr.strip()}")
    return state


def restore_launchagent(
    state: Optional[Tuple[bool, bool]],
    domain: Optional[str],
    label: Optional[str],
    plist: Optional[Path],
) -> None:
    if not state or not domain or not label:
        return
    launchctl = shutil.which("launchctl")
    if not launchctl:
        return
    current = launchctl_state(domain, label)
    if current and current[0]:
        subprocess.run([launchctl, "bootout", f"{domain}/{label}"], check=False)
    if state[0] and plist and lexists(plist):
        result = subprocess.run(
            [launchctl, "bootstrap", domain, str(plist)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if result.returncode == 0 and state[1]:
            subprocess.run([launchctl, "kickstart", "-k", f"{domain}/{label}"], check=False)


def export_defaults(domain: Optional[str], destination: Path) -> bool:
    defaults = shutil.which("defaults")
    if not defaults or not domain:
        return False
    result = subprocess.run(
        [defaults, "export", domain, str(destination)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    return result.returncode == 0 and destination.is_file()


def import_defaults(domain: Optional[str], source: Path, existed: bool) -> None:
    defaults = shutil.which("defaults")
    if not defaults or not domain or not existed:
        return
    subprocess.run([defaults, "import", domain, str(source)], check=False)


def run_real(args: argparse.Namespace) -> int:
    if not args.command or not args.path:
        raise SystemExit("--real requires --path and --command")
    targets = [Path(os.path.abspath(raw)) for raw in args.path]
    for index, left in enumerate(targets):
        for right in targets[index + 1 :]:
            try:
                right.relative_to(left)
            except ValueError:
                try:
                    left.relative_to(right)
                except ValueError:
                    continue
                raise SystemExit(f"nested transaction paths are ambiguous: {left} / {right}")
            raise SystemExit(f"nested transaction paths are ambiguous: {left} / {right}")

    temporary_root = Path(tempfile.mkdtemp(prefix="harness-transaction-real-"))
    evidence = args.evidence_dir
    if evidence:
        evidence.mkdir(parents=True, exist_ok=True)
    snapshots: List[Tuple[Path, Path, Dict[str, Any]]] = []
    launch_state = None
    defaults_snapshot = temporary_root / "bookmarks.plist"
    defaults_existed = False
    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    try:
        for index, target in enumerate(targets):
            snapshot = temporary_root / "paths" / str(index)
            metadata = snapshot_path(target, snapshot)
            snapshots.append((target, snapshot, metadata))
        manifest = [metadata for _, _, metadata in snapshots]
        (temporary_root / "snapshot.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        if evidence:
            (evidence / "snapshot.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        launch_state = stop_launchagent(args.launchagent_domain, args.launchagent_label)
        defaults_existed = export_defaults(args.bookmark_domain, defaults_snapshot)
        result = subprocess.run(
            command,
            env={**os.environ, "CODEX_HARNESS_TRANSACTION_CHILD": "1"},
            check=False,
        )
        if result.returncode == 0:
            return 0
        raise RuntimeError(f"transaction command failed with exit code {result.returncode}")
    except Exception as error:
        for target, snapshot, metadata in reversed(snapshots):
            restore_snapshot(target, snapshot, metadata)
        import_defaults(args.bookmark_domain, defaults_snapshot, defaults_existed)
        restore_launchagent(launch_state, args.launchagent_domain, args.launchagent_label, args.launchagent_plist)
        if evidence:
            (evidence / "rollback-error.txt").write_text(str(error) + "\n", encoding="utf-8")
            (evidence / "rollback-diff.txt").write_text("", encoding="utf-8")
        return 1
    finally:
        shutil.rmtree(temporary_root, ignore_errors=True)


def main() -> int:
    args = parse_args()
    if args.real:
        if args.fail_at is not None or args.success:
            raise SystemExit("--real cannot be combined with fixture mode")
        return run_real(args)
    if args.fixture_root is None:
        raise SystemExit("--fixture-root is required in fixture mode")
    if args.fail_at is None and not args.success:
        raise SystemExit("fixture mode requires --fail-at or --success")
    root = args.fixture_root.resolve()
    if not root.is_dir():
        raise SystemExit(f"fixture root is missing: {root}")
    trace_path = Path(os.environ["HIR82_TRANSACTION_TRACE"]) if os.environ.get("HIR82_TRANSACTION_TRACE") else None
    failure = args.fail_at
    temporary_root = Path(tempfile.mkdtemp(prefix="hir82-transaction-"))
    changes: List[Tuple[Path, Path]] = []
    try:
        for stage, relative in STAGES:
            path = root / relative
            marker = temporary_root / stage
            if not (failure == "macos-gate" and stage == "macos-gate"):
                trace_line(trace_path, f"completed:{stage}")
            replace_with_marker(path, marker, stage)
            changes.append((path, marker))
            if failure == f"after-{stage}" or (failure == "macos-gate" and stage == "macos-gate"):
                trace_line(trace_path, f"reached:{failure}")
                raise RuntimeError(f"injected transaction failure at {failure}")
        if args.success:
            (root / "transaction.committed").write_text("committed\n", encoding="utf-8")
        return 0
    except Exception as error:
        rollback(changes)
        if failure is not None:
            return 1
        raise SystemExit(str(error))
    finally:
        shutil.rmtree(temporary_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
