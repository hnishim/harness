#!/bin/bash
set -euo pipefail
SCRIPT_DIR=$(cd -- "$(dirname -- "$0")" && pwd)
SOURCE="$SCRIPT_DIR/../openai-instructions.md"
[ -f "$SOURCE" ] || { printf '[ERROR] source file is missing: %s\n' "$SOURCE" >&2; exit 1; }
/usr/bin/grep -Fqx '## Git / GitHub操作' "$SOURCE"
for required in \
    'ローカルRepositoryのstatus' \
    'Git CLIを使用する' \
    'git-add-commit-push' \
    'GitHub pluginを使用する' \
    '`gh` CLIは' \
    '認証エラーだけを根拠にGitHub認証が無効と判断しない' \
    'Browser Useへ切り替えない' \
    'Git transportとして扱うため、GitHub pluginへ置換しない' \
    'remote-implementation-loop' \
    'lightweight' \
    'current phase' \
    'capability' \
    'Bug' \
    'Spike' \
    'Strict profile' \
    '独立Reviewer availability'; do
    /usr/bin/grep -Fq -- "$required" "$SOURCE" || { printf '[ERROR] routing invariant is missing: %s\n' "$required" >&2; exit 1; }
done
for forbidden in \
    'Bug / Spike / Strict profile` はremote adapterで部分実行・remote resumeを行わず' \
    'normal + lightweight かつLinear/GitHub connector'; do
    if /usr/bin/grep -Fq -- "$forbidden" "$SOURCE"; then
        printf '[ERROR] obsolete remote hard-exclusion routing remains: %s\n' "$forbidden" >&2
        exit 1
    fi
done
if /usr/bin/grep -Fq -- '## 責務境界' "$SOURCE" || /usr/bin/grep -Fq -- '| 操作 | 原則経路 |' "$SOURCE"; then
    printf '%s\n' '[ERROR] routing responsibility table remains duplicated' >&2
    exit 1
fi
printf '%s\n' '[PASS] openai-instructions capability-based remote routing contract'
