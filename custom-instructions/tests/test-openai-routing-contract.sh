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
    'CloseではローカルGitを必須' \
    'GitHub APIでCloseの公開は行わない' \
    'Bug/Spike' \
    'Strict profile' \
    '独立レビュー担当' \
    'Local-only検証' \
    'Git CLIを使用する' \
    'git-add-commit-push' \
    'GitHubプラグイン' \
    'remote Git backend' \
    'remote-only' \
    'local-origin'; do
    /usr/bin/grep -Fq -- "$required" "$SOURCE" || {
        printf '[ERROR] routing invariant is missing: %s\n' "$required" >&2
        exit 1
    }
done

retry_contract_line=$(/usr/bin/grep -F -- '実行環境側でGit操作が拒否された場合' "$SOURCE" || true)
[ -n "$retry_contract_line" ] || {
    printf '[ERROR] sandbox-originated Git retry contract is missing\n' >&2
    exit 1
}

for retry_required in \
    'Git自体の障害と判断して諦めず' \
    '通常のmacOS実行環境で同じ操作を一度だけ再試行' \
    '再試行が成功した場合は処理を続行' \
    '再試行後も失敗した場合に限り停止または `skip` します'; do
    printf '%s\n' "$retry_contract_line" | /usr/bin/grep -Fq -- "$retry_required" || {
        printf '[ERROR] Git retry contract is missing: %s\n' "$retry_required" >&2
        exit 1
    }
done

for forbidden in \
    'Local worktreeまたはローカルGitが利用できない場合は停止し、GitHubの読み書き権限へ切り替えない'; do
    if /usr/bin/grep -Fq -- "$forbidden" "$SOURCE"; then
        printf '[ERROR] canonical instructions still enforce the removed local-only route: %s\n' "$forbidden" >&2
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
