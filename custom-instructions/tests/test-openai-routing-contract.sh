#!/bin/bash
set -euo pipefail
SCRIPT_DIR=$(cd -- "$(dirname -- "$0")" && pwd)
SOURCE="$SCRIPT_DIR/../openai-instructions.md"
[ -f "$SOURCE" ] || { printf '[ERROR] source file is missing: %s\n' "$SOURCE" >&2; exit 1; }

/usr/bin/grep -Fqx '## 実装ワークフローの振り分け' "$SOURCE"
/usr/bin/grep -Fqx '## Git / GitHub操作' "$SOURCE"

for required in \
    'implementation-loop' \
    '唯一の実行入口' \
    'workflow.toml' \
    'Local worktree' \
    'local Git' \
    'ローカルGitが利用できない場合は停止' \
    'Bug/Spike' \
    'Strict profile' \
    '独立レビュー担当' \
    'Local-only検証' \
    'Git CLIを使用する' \
    'git-add-commit-push' \
    'GitHubプラグイン'; do
    /usr/bin/grep -Fq -- "$required" "$SOURCE" || {
        printf '[ERROR] routing invariant is missing: %s\n' "$required" >&2
        exit 1
    }
done

for forbidden in \
    'remote Git backend' \
    'GitHub API／コネクタでcandidate refを操作'; do
    if /usr/bin/grep -Fq -- "$forbidden" "$SOURCE"; then
        printf '[ERROR] canonical instructions still authorize remote Git: %s\n' "$forbidden" >&2
        exit 1
    fi
done

obsolete='remote-implementation-loop'
if /usr/bin/grep -Fq -- "$obsolete" "$SOURCE"; then
    printf '[ERROR] obsolete separate remote entry remains\n' >&2
    exit 1
fi

if /usr/bin/grep -Fq -- 'Strict profile はリモート環境向け差し替え層の対象外' "$SOURCE"; then
    printf '[ERROR] obsolete environment-based strict exclusion remains\n' >&2
    exit 1
fi

printf '%s\n' '[PASS] openai-instructions single canonical implementation-loop routing contract'
