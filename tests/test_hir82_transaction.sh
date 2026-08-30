#!/bin/bash

set -euo pipefail

ROOT=$(cd -- "$(dirname -- "$0")/.." && pwd)
TRANSACTION="$ROOT/transaction.py"
TMP_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/harness-transaction-test.XXXXXX")
trap 'rm -rf -- "$TMP_ROOT"' EXIT
EVIDENCE_DIR="${HIR82_TRANSACTION_EVIDENCE_DIR:-}"
if [ -n "$EVIDENCE_DIR" ]; then
    mkdir -p "$EVIDENCE_DIR"
fi

make_fixture() {
    local state="$1"
    mkdir -p \
        "$state/bookmarks" \
        "$state/runtime/custom-instructions-sync" \
        "$state/runtime/skills-notion-sync" \
        "$state/runtime/LaunchAgents" \
        "$state/runtime/agents" \
        "$state/runtime/backups" \
        "$state/runtime/.runtime" \
        "$state/runtime/non-target" \
        "$state/legacy/old-runtime" \
        "$state/legacy/agents" \
        "$state/plugin-system/skills"
    printf '%s\n' source-bookmark >"$state/bookmarks/source"
    printf '%s\n' skills-bookmark >"$state/bookmarks/skills"
    printf '%s\n' output-bookmark >"$state/bookmarks/output"
    chmod 600 "$state/bookmarks"/*
    printf '%s\n' old-agents >"$state/legacy/AGENTS.md"
    ln -s ../legacy/AGENTS.md "$state/runtime/AGENTS.md"
    printf '%s\n' custom-sync >"$state/runtime/custom-instructions-sync/state"
    printf '%s\n' notion-sync >"$state/runtime/skills-notion-sync/state"
    printf '%s\n' launch-agent >"$state/runtime/LaunchAgents/com.example.harness.plist"
    printf '%s\n' launchctl-stopped >"$state/runtime/launchctl.state"
    printf '%s\n' old-runtime >"$state/legacy/old-runtime/hooks"
    ln -s ../legacy/old-runtime "$state/runtime/old-runtime"
    for name in planner plan-reviewer implementer reviewer git-actions; do
        printf '%s\n' "$name" >"$state/legacy/agents/$name.toml"
        ln -s "../../legacy/agents/$name.toml" "$state/runtime/agents/$name.toml"
    done
    printf '%s\n' plugin-system >"$state/plugin-system/marker"
    ln -s ../../plugin-system/skills "$state/runtime/skills"
    printf '%s\n' existing-backup >"$state/runtime/backups/existing"
    printf '%s\n' generated-hooks >"$state/runtime/.runtime/hooks.json"
    printf '%s\n' preserve >"$state/runtime/non-target/keep"
}

snapshot() {
    local state="$1"
    /usr/bin/python3 - "$state" <<'PY'
import hashlib
import os
import stat
import sys
from pathlib import Path

root = Path(sys.argv[1])
rows = []
for path in sorted(root.rglob("*")):
    relative = path.relative_to(root).as_posix()
    info = path.lstat()
    mode = stat.S_IMODE(info.st_mode)
    if stat.S_ISLNK(info.st_mode):
        value = "link:" + os.readlink(path)
        kind = "symlink"
    elif stat.S_ISREG(info.st_mode):
        value = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        kind = "file"
    elif stat.S_ISDIR(info.st_mode):
        value = ""
        kind = "directory"
    else:
        raise SystemExit(f"unsupported fixture entry: {path}")
    rows.append(f"{relative}|{kind}|{mode:o}|{info.st_ino}|{value}")
print("\n".join(rows))
PY
}

snapshot_semantic() {
    local state="$1"
    /usr/bin/python3 - "$state" <<'PY'
import hashlib
import os
import stat
import sys
from pathlib import Path

root = Path(sys.argv[1])
rows = []
for path in sorted(root.rglob("*")):
    relative = path.relative_to(root).as_posix()
    info = path.lstat()
    mode = stat.S_IMODE(info.st_mode)
    if stat.S_ISLNK(info.st_mode):
        value = "link:" + os.readlink(path)
        kind = "symlink"
    elif stat.S_ISREG(info.st_mode):
        value = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        kind = "file"
    elif stat.S_ISDIR(info.st_mode):
        value = ""
        kind = "directory"
    else:
        raise SystemExit(f"unsupported fixture entry: {path}")
    rows.append(f"{relative}|{kind}|{mode:o}|{value}")
print("\n".join(rows))
PY
}

for failure in after-hooks after-agents after-skills after-mirrors after-plist after-launchagent after-backup macos-gate; do
    state="$TMP_ROOT/$failure"
    make_fixture "$state"
    before=$(snapshot "$state")
    trace="$TMP_ROOT/$failure.trace"
    set +e
    HIR82_TRANSACTION_TRACE="$trace" /usr/bin/python3 "$TRANSACTION" --fixture-root "$state" --fail-at "$failure" >"$TMP_ROOT/$failure.log" 2>&1
    status=$?
    set -e
    [ "$status" -ne 0 ]
    case "$failure" in
        after-hooks) expected_trace=$'completed:hooks\nreached:after-hooks\n' ;;
        after-agents) expected_trace=$'completed:hooks\ncompleted:agents\nreached:after-agents\n' ;;
        after-skills) expected_trace=$'completed:hooks\ncompleted:agents\ncompleted:skills\nreached:after-skills\n' ;;
        after-mirrors) expected_trace=$'completed:hooks\ncompleted:agents\ncompleted:skills\ncompleted:mirrors\nreached:after-mirrors\n' ;;
        after-plist) expected_trace=$'completed:hooks\ncompleted:agents\ncompleted:skills\ncompleted:mirrors\ncompleted:plist\nreached:after-plist\n' ;;
        after-launchagent) expected_trace=$'completed:hooks\ncompleted:agents\ncompleted:skills\ncompleted:mirrors\ncompleted:plist\ncompleted:launchagent\nreached:after-launchagent\n' ;;
        after-backup) expected_trace=$'completed:hooks\ncompleted:agents\ncompleted:skills\ncompleted:mirrors\ncompleted:plist\ncompleted:launchagent\ncompleted:backup\nreached:after-backup\n' ;;
        macos-gate) expected_trace=$'completed:hooks\ncompleted:agents\ncompleted:skills\ncompleted:mirrors\ncompleted:plist\ncompleted:launchagent\ncompleted:backup\nreached:macos-gate\n' ;;
    esac
    [ "$(cat "$trace")"$'\n' = "$expected_trace" ]
    after=$(snapshot "$state")
    if [ -n "$EVIDENCE_DIR" ]; then
        printf '%s\n' "$before" >"$EVIDENCE_DIR/$failure.before"
        printf '%s\n' "$after" >"$EVIDENCE_DIR/$failure.after"
        printf '%s\n' "$expected_trace" >"$EVIDENCE_DIR/$failure.trace"
        diff -u "$EVIDENCE_DIR/$failure.before" "$EVIDENCE_DIR/$failure.after" >"$EVIDENCE_DIR/$failure.rollback-diff.txt" || true
    fi
    [ "$after" = "$before" ] || {
        printf '[FAIL] transaction rollback changed state at %s\n' "$failure" >&2
        diff -u <(printf '%s\n' "$before") <(printf '%s\n' "$after") >&2 || true
        exit 1
    }
done
if [ -n "$EVIDENCE_DIR" ]; then
    : >"$EVIDENCE_DIR/rollback-diff.txt"
fi

success="$TMP_ROOT/success"
make_fixture "$success"
/usr/bin/python3 "$TRANSACTION" --fixture-root "$success" --success >/dev/null
[ -f "$success/transaction.committed" ]

real="$TMP_ROOT/real"
mkdir -p "$real"
printf '%s\n' before >"$real/state"
before=$(snapshot_semantic "$real")
set +e
/usr/bin/python3 "$TRANSACTION" \
    --real \
    --path "$real/state" \
    --command /bin/sh -c 'printf "%s\\n" after >"$1"; exit 7' sh "$real/state" \
    >"$TMP_ROOT/real.log" 2>&1
status=$?
set -e
[ "$status" -ne 0 ]
after=$(snapshot_semantic "$real")
[ "$after" = "$before" ] || {
    printf '%s\n' '[FAIL] real transaction rollback changed state' >&2
    exit 1
}

printf '%s\n' before >"$real/state"
/usr/bin/python3 "$TRANSACTION" \
    --real \
    --path "$real/state" \
    --command /bin/sh -c 'printf "%s\\n" after >"$1"' sh "$real/state" \
    >"$TMP_ROOT/real-success.log" 2>&1
[ "$(cat "$real/state")" = after ]

printf '%s\n' '[PASS] HIR-82 transaction rollback scenarios'
