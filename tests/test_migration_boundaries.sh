#!/bin/bash

set -euo pipefail

ROOT=$(cd -- "$(dirname -- "$0")/.." && pwd)

/usr/bin/python3 - "$ROOT" <<'PY'
import json
import os
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1])
manifest = json.loads((root / "migration-manifest.json").read_text(encoding="utf-8"))
expected = set(manifest["tracked_files"])
tracked = set(subprocess.check_output(
    ["git", "-C", str(root), "ls-files"], text=True
).splitlines())
assert tracked == expected, (sorted(expected - tracked), sorted(tracked - expected))
for relative in sorted(expected):
    path = root / relative
    assert path.is_file() and not path.is_symlink(), relative

def sha256(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()

def sha256_bytes(value: bytes) -> str:
    import hashlib
    return hashlib.sha256(value).hexdigest()

source_roots = {}
for source_name in ("custom-instructions", "skills"):
    direct_root = root.parent / source_name
    source_roots[source_name] = (
        direct_root
        if direct_root.exists()
        else root.parent / manifest["source_archives"][source_name]
    )

for source_name, target_prefix in (
    ("custom-instructions", "custom-instructions"),
    ("skills", "skills"),
):
    source_root = source_roots[source_name]
    revision = subprocess.check_output(
        ["git", "-C", str(source_root), "rev-parse", "HEAD"], text=True
    ).strip()
    assert revision == manifest["source_revisions"][source_name], (source_name, revision)
    source_files = set(manifest["source_inventory"][source_name])
    actual_files = set(subprocess.check_output(
        ["git", "-C", str(source_root), "ls-files"], text=True
    ).splitlines())
    assert actual_files == source_files, (source_name, sorted(source_files - actual_files), sorted(actual_files - source_files))
    worktree = manifest.get("source_worktrees", {}).get(source_name, {})
    expected_status = worktree.get("status", [])
    actual_status = subprocess.check_output(
        ["git", "-C", str(source_root), "status", "--short", "--untracked-files=no"],
        text=True,
    ).splitlines()
    assert actual_status == expected_status, (source_name, actual_status, expected_status)
    if expected_status:
        diff_paths = worktree["tracked_files"]
        diff_blob = subprocess.check_output(
            ["git", "-C", str(source_root), "diff", "--binary", "HEAD", "--", *diff_paths]
        )
        assert sha256_bytes(diff_blob) == worktree["tracked_diff_sha256"], source_name
    for relative in sorted(source_files):
        target = root / target_prefix / relative
        source = source_root / relative
        if relative in worktree.get("tracked_files", []):
            blob = source.read_bytes()
        else:
            blob = subprocess.check_output(
                ["git", "-C", str(source_root), "show", f"{revision}:{relative}"]
            )
        assert source.is_file() and target.is_file()
        assert not target.is_symlink()
        assert sha256(target) == __import__("hashlib").sha256(blob).hexdigest(), relative

dotfiles_root = root.parent / "dotfiles"
dotfiles_revision = manifest["source_revisions"]["dotfiles"]
subprocess.run(
    ["git", "-C", str(dotfiles_root), "cat-file", "-e", f"{dotfiles_revision}^{{commit}}"],
    check=True,
)
for relative in manifest.get("dotfiles_setup_scripts", []):
    path = dotfiles_root / relative
    assert path.is_file() and not path.is_symlink(), relative

for relative in manifest.get("dotfiles_setup_tests", []):
    path = dotfiles_root / relative
    assert path.is_file() and not path.is_symlink(), relative

for relative in (
    "agents/agents-setup.sh",
    "hooks/install-hooks.py",
    "skills/skills-setup.sh",
):
    assert not (root / relative).exists(), relative

for relative in manifest["source_inventory"]["dotfiles-agents"]:
    name = Path(relative).name
    source = dotfiles_root / relative
    target = root / "agents" / name
    assert target.is_file() and not target.is_symlink()
    if metadata.get("source_removed"):
        assert not source.exists() and not source.is_symlink(), source
    else:
        assert source.is_file(), source
    blob = subprocess.check_output([
        "git", "-C", str(dotfiles_root), "show",
        f"{manifest['source_revisions']['dotfiles']}:{relative}",
    ])
    assert sha256(target) == __import__("hashlib").sha256(blob).hexdigest(), relative

for relative in manifest["source_inventory"]["dotfiles-hooks"]:
    name = Path(relative).name
    target = root / "hooks" / "runtime" / name
    assert target.is_file() and not target.is_symlink()
    blob = subprocess.check_output([
        "git", "-C", str(dotfiles_root), "show",
        f"{manifest['source_revisions']['dotfiles']}:{relative}",
    ])
    assert sha256(target) == __import__("hashlib").sha256(blob).hexdigest(), relative

for relative in manifest["source_inventory"].get("retired_source_files", []):
    source = dotfiles_root / relative
    assert not source.exists() and not source.is_symlink(), relative
    subprocess.check_output([
        "git", "-C", str(dotfiles_root), "show",
        f"{manifest['source_revisions']['dotfiles']}:{relative}",
    ])

for relative in manifest["ignored_overlay_files"]:
    source_relative = relative
    source_name = "custom-instructions" if relative.startswith("custom-instructions/") else "skills"
    source_root = source_roots[source_name]
    source = source_root / source_relative.split("/", 1)[1]
    target = root / relative
    assert source.is_file() and target.is_file() and not target.is_symlink(), relative
    subprocess.run(
        ["git", "-C", str(source_root), "check-ignore", "--no-index", "-q", source_relative.split("/", 1)[1]],
        check=True,
    )
    assert sha256(source) == manifest["ignored_overlay_sha256"][relative], relative
    assert sha256(target) == manifest["ignored_overlay_sha256"][relative], relative

def overlay_inventory(base: Path, prefix: str) -> set[str]:
    values = set()
    for path in base.rglob("*"):
        if path.is_file() and ".DS_Store" not in path.parts:
            values.add(f"{prefix}/{path.relative_to(base).as_posix()}")
    return values

actual_overlay = set()
actual_overlay.add("custom-instructions/user-profile.md")
for name in ("draft-proposal", "draft-press-release-qa", "notion-molcure", "notion-personal", "writing-references"):
    if name == "writing-references":
        actual_overlay.add("skills/writing-references/business-email.md")
        continue
    source_base = source_roots["skills"] / name
    actual_overlay |= overlay_inventory(source_base, f"skills/{name}")
assert actual_overlay == set(manifest["ignored_overlay_files"]), (
    sorted(actual_overlay - set(manifest["ignored_overlay_files"])),
    sorted(set(manifest["ignored_overlay_files"]) - actual_overlay),
)

for relative in manifest["ignored_overlays"]:
    path = root / relative
    assert path.exists() and not path.is_symlink(), relative
    subprocess.run(
        ["git", "-C", str(root), "check-ignore", "--no-index", "-q", relative],
        check=True,
    )
    assert relative not in tracked
    if path.is_dir():
        for child in path.rglob("*"):
            assert not child.is_symlink(), child

for target_relative, metadata in manifest["derived_artifacts"].items():
    source_relative = metadata["source"]
    source_relative = source_relative if source_relative.startswith("codex/") else f"codex/{source_relative}"
    source = dotfiles_root / source_relative
    blob = subprocess.check_output([
        "git", "-C", str(dotfiles_root), "show",
        f"{manifest['source_revisions']['dotfiles']}:{source_relative}",
    ])
    target = root / target_relative
    assert target.is_file() and not target.is_symlink()
    if metadata.get("source_removed"):
        assert not source.exists() and not source.is_symlink(), source
    else:
        assert source.is_file(), source
    assert blob, source_relative

for target_relative, metadata in manifest["hooks_artifact_integrity"].items():
    source_relative = metadata["source_path"]
    source = dotfiles_root / source_relative
    target = root / target_relative
    blob = subprocess.check_output([
        "git", "-C", str(dotfiles_root), "show",
        f"{manifest['source_revisions']['dotfiles']}:{source_relative}",
    ])
    assert target.is_file() and not target.is_symlink()
    if metadata.get("source_removed"):
        assert not source.exists() and not source.is_symlink(), source
    else:
        assert source.is_file(), source
    assert __import__("hashlib").sha256(blob).hexdigest() == metadata["source_blob_sha256"]
    assert sha256(target) == metadata["target_sha256"], target_relative

for relative in ("hooks/.runtime", "hooks/_archive", "skills/.system"):
    path = root / relative
    assert relative not in tracked
    if path.exists():
        subprocess.run(
            ["git", "-C", str(root), "check-ignore", "--no-index", "-q", relative],
            check=True,
        )
    if relative == "skills/.system":
        assert not path.exists(), relative
for path in root.rglob(".DS_Store"):
    relative = path.relative_to(root).as_posix()
    assert relative not in tracked
    subprocess.run(
        ["git", "-C", str(root), "check-ignore", "--no-index", "-q", relative],
        check=True,
    )
for path in root.rglob(".cogito-folder.json"):
    raise AssertionError(path)
PY

[ ! -e "$ROOT/hooks/runtime/textlint-stop-hook.py" ] || {
    printf '%s\n' '[FAIL] archived stop hook leaked into runtime' >&2
    exit 1
}

printf '%s\n' '[PASS] migration boundaries'
