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
    'Closeでは受入・明示指示・公開先の実状態を照合' \
    'ローカル反映が必要なら実利用まで確認' \
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

git_execution_contract=$(/usr/bin/sed -n '/^## Git \/ GitHub操作/,/^## Linear操作/p' "$SOURCE")
[ -n "$git_execution_contract" ] || {
    printf '[ERROR] preflight Git execution-environment contract is missing\n' >&2
    exit 1
}

for readonly_required in \
    '読み取り専用Git操作' \
    '既定のsandbox経路'; do
    printf '%s\n' "$git_execution_contract" | /usr/bin/grep -Fq -- "$readonly_required" || {
        printf '[ERROR] read-only Git routing contract is missing: %s\n' "$readonly_required" >&2
        exit 1
    }
done

metadata_contract_line=$(printf '%s\n' "$git_execution_contract" | /usr/bin/grep -F -- 'メタデータを書き込む可能性があるGit操作' || true)
[ -n "$metadata_contract_line" ] || {
    printf '[ERROR] metadata-writing Git routing contract is missing\n' >&2
    exit 1
}

for metadata_required in \
    'sandboxで試す前に' \
    '`sandbox_permissions: "require_escalated"`' \
    '通常macOS実行環境を要求' \
    '利用できない場合は' \
    '広い `.rules` のallowを追加せず停止'; do
    printf '%s\n' "$metadata_contract_line" | /usr/bin/grep -Fq -- "$metadata_required" || {
        printf '[ERROR] preflight Git execution-environment contract is missing: %s\n' "$metadata_required" >&2
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

email_account_contract=$(/usr/bin/sed -n '/^## メールアカウントの使い分け$/,/^## /p' "$SOURCE")
[ -n "$email_account_contract" ] || {
    printf '[ERROR] email account routing contract section is missing\n' >&2
    exit 1
}

for email_required in \
    'nishimiyahirotaka.agent@gmail.com' \
    'AIエージェント専用アカウント' \
    '本人用アカウント' \
    'AIによる受信・整理・処理' \
    '本人名義' \
    '読み取り・検索・送信・下書き作成' \
    '明示的に選択' \
    '暗黙に別アカウントへフォールバックしない' \
    '個別指定を優先'; do
    printf '%s\n' "$email_account_contract" | /usr/bin/grep -Fq -- "$email_required" || {
        printf '[ERROR] email account routing invariant is missing: %s\n' "$email_required" >&2
        exit 1
    }
done

printf '%s\n' '[PASS] openai-instructions single canonical implementation-loop routing contract'
