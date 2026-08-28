# macOS統合受入チェック

このチェックは通常のmacOSユーザーコンテキストで実施します。証跡は
`.local-state/evidence/`へ保存し、秘密情報やsecurity-scoped bookmarkの生値は
保存しません。

以下のコマンドは`HARNESS_ROOT=/Users/hnishim/Library/Mobile Documents/com~apple~CloudDocs/Dev/harness`
を設定して、`cd "$HARNESS_ROOT"`した状態で実行する。各コマンドのexit codeが
受入れ判定であり、証跡ファイルが生成されない場合はPASSにしない。

1. 担当: ローカル実装担当。`CustomInstructionsSync --status`を実行し、
   `source=.../Dev/harness/custom-instructions`、`skills=.../Dev/harness/skills`、
   `output=$HOME/.codex`を期待する。次を実行し、stdoutと時刻を
   `.local-state/evidence/status.txt`へ保存する（exit code 0）。bookmarkの生値は保存しない。
   `HELPER="$HOME/Applications/Custom Instructions Sync.app/Contents/MacOS/CustomInstructionsSync"; { date -u +%FT%TZ; "$HELPER" --status; } | tee .local-state/evidence/status.txt`
2. 担当: ローカル実装担当。次の3つについて、存在、種別、permission、SHA-256を
   `.local-state/evidence/local-state.txt`へ記録する: `AGENTS.md`、
   `custom-instructions-sync`、`skills-notion-sync`。次を実行し、SHA-256の期待値を
   `shasum -a 256`でharness内の対応ファイルから計算して、実行結果と一致比較する。
   `CODEX_HOME="$HOME/.codex"; for p in "$CODEX_HOME/AGENTS.md" "$CODEX_HOME/custom-instructions-sync" "$CODEX_HOME/skills-notion-sync"; do stat -f '%N|%HT|%Mp%Lp|%i' "$p"; find -P "$p" -type f -print0 | xargs -0 -n1 shasum -a 256; done | tee .local-state/evidence/local-state.txt`
   `user-profile.md`、MOLCURE、draft、business-emailのoverlayはregular file/directoryであり、
   symlinkでないことも同じ証跡へ記録する。
3. 担当: macOS runtime担当。`readlink`で`~/.codex/hooks`、`hooks.json`、5つの
   `~/.codex/agents/*.toml`、Skillsの各managed child linkがharness内の対応先を
   指すことを確認し、`.local-state/evidence/runtime-links.txt`へ保存する。次のコマンドでHooks 2本、Agents 5本、
   Skills全managed childのtargetを列挙し、各`readlink`が対応する絶対pathでexit code 0になることを期待する。
   `for p in hooks hooks.json agents/planner.toml agents/plan-reviewer.toml agents/implementer.toml agents/reviewer.toml agents/git-actions.toml; do case "$p" in hooks) expected="$HARNESS_ROOT/hooks/runtime";; hooks.json) expected="$HARNESS_ROOT/hooks/.runtime/hooks.json";; agents/*) expected="$HARNESS_ROOT/$p";; esac; test "$(readlink "$HOME/.codex/$p")" = "$expected"; done; find -P "$HARNESS_ROOT/skills" -mindepth 1 -maxdepth 1 ! -name .system ! -name .DS_Store -exec basename {} \; | while read -r p; do test "$(readlink "$HOME/.codex/skills/$p")" = "$HARNESS_ROOT/skills/$p"; done > .local-state/evidence/runtime-links.txt`
   `.system`はharnessへコピーされず、plugin提供先を指すことを期待する。
4. 担当: macOS runtime担当。固定payloadを
   `.local-state/evidence/hooks-payload.json`へ保存してHookに渡す。
   `printf '%s\n' '{"tool_name":"Bash","tool_input":{"command":"gh auth status -h github.com"}}' | tee .local-state/evidence/hooks-payload.json | /usr/bin/python3 "$HARNESS_ROOT/hooks/runtime/gh_normal_context_guard.py" > .local-state/evidence/hooks-restricted.json`
   とし、`jq -e '.hookSpecificOutput.hookEventName == "PreToolUse" and .hookSpecificOutput.permissionDecision == "deny"' .local-state/evidence/hooks-restricted.json`がexit code 0になることを期待する。同じpayloadに
   `permission_mode=bypassPermissions`を加えた通常macOS contextではstdoutが空、exit code 0を期待する。具体的には`printf '%s\n' '{"permission_mode":"bypassPermissions","tool_name":"Bash","tool_input":{"command":"gh auth status -h github.com"}}' | /usr/bin/python3 "$HARNESS_ROOT/hooks/runtime/gh_normal_context_guard.py" > .local-state/evidence/hooks-normal.json`を実行し、ファイルが空であることを確認する。Hooks JSONの`jq -e`検査では、PreToolUseのmatcherが先に`^Bash$`、続いて`.*`、PostToolUseが`.*`、各hookのtypeが`command`であること、停止Hookが存在しないことを確認する。textlintのPostToolUse一回処理は`python3 -m unittest hooks.tests.test_textlint_boundaries`のexit code 0で確認する。
5. 担当: macOS runtime担当。5つのAgent TOMLについて、recognition、read-only指定
   （planner/plan-reviewer/reviewer）、起動結果を
   `HARNESS_ROOT="$HARNESS_ROOT" python3 -c 'import os, pathlib, tomllib; ps=list(pathlib.Path(os.environ["HARNESS_ROOT"], "agents").glob("*.toml")); assert len(ps)==5; ds=[tomllib.loads(p.read_text()) for p in ps]; assert all(d["name"] and d["description"] and d["model"] and d["model_reasoning_effort"] and d["developer_instructions"] for d in ds); assert all(d.get("sandbox_mode")=="read-only" for d in ds if d["name"] in {"planner","plan-reviewer","reviewer"})'`のexit code 0と、5定義をCodexのAgent選択画面から1つずつ起動した結果を`.local-state/evidence/agents.txt`へ保存する。LaunchAgent plistのWatchPathsが
   harnessを指すこと、`for p in hooks hooks.json agents/planner.toml agents/plan-reviewer.toml agents/implementer.toml agents/reviewer.toml agents/git-actions.toml; do printf '%s|' "$p"; readlink "$HOME/.codex/$p"; done | tee .local-state/evidence/runtime-links.txt`で全6リンクのtargetがharness内の対応先となること、`plutil -extract WatchPaths xml1 -o - "$HOME/Library/LaunchAgents/com.hnishim.custom-instructions-sync.plist"`の2値が
   `.../Dev/harness/custom-instructions`と`.../Dev/harness/skills`であることを確認する。
   `launchctl print gui/$(id -u)/com.hnishim.custom-instructions-sync | tee .local-state/evidence/launchagent.txt`でloaded/running/
   `last exit code = 0`を保存する。可逆確認中は`launchctl bootout gui/$(id -u)/com.hnishim.custom-instructions-sync`を実行し、local-only syncのexit code 0を記録した後、`launchctl bootstrap gui/$(id -u) "$HOME/Library/LaunchAgents/com.hnishim.custom-instructions-sync.plist"`で復元する。
6. 担当: 実装担当。Notion remote syncの前に、bookmark、AGENTS、両mirror、plist、
   launchctl state、旧runtime、`.system`、既存backup、生成物、non-target stateを
   snapshotし、`.local-state/evidence/pre-notion-snapshot.txt`へ内容、permission、
   inode、symlink targetを保存する。local/macOS gateの故障注入を1箇所ずつ行い、
   `rollback-diff.txt`が空であることを確認する。自動fixtureは
   `mkdir -p .local-state/evidence; HIR82_TRANSACTION_EVIDENCE_DIR="$HARNESS_ROOT/.local-state/evidence" /bin/bash "$HARNESS_ROOT/tests/test_hir82_transaction.sh"`を実行し、
   `after-hooks`、`after-agents`、`after-skills`、`after-mirrors`、`after-plist`、
   `after-launchagent`、`after-backup`、`macos-gate`の全8故障点が内部traceで指定点へ到達し、exit code非0かつsnapshot一致、`rollback-diff.txt`が空になることを期待する。1件でも不一致ならNotionへ進まず`BLOCKED`とし、
   runtime・旧Repository・Notionを変更しない。
7. 担当: 実装担当。local/macOS gateが全てPASSした後、LaunchAgentを一度だけ有効化し、
   通常起動または一度だけのkickstartのどちらか一方だけを実行する。
   `.local-state/evidence/launchagent-run.txt`にrun countが1回だけ増えたこと、local
   syncとNotion syncのexit code 0を保存する。
8. 担当: Notion連携担当。本文、metadata、対象ページ識別子をreadbackし、実行前に
   `jq -S -c '{body,metadata}' .local-state/evidence/notion-input.json | shasum -a 256`で
   算出した期待hashと、readbackから同じcanonical serializationを作ったhashが一致することを
   `.local-state/evidence/notion-readback.json`へ保存する。部分更新、readback不一致、
   失敗時は自動rollbackせず`BLOCKED`とし、cleanup/archiveを実行しない。
9. 担当: リポジトリ管理担当。Notion readback成功後のみ、dotfilesのmigrated source
   filesを別cleanup commitで除去し、旧custom-instructions/skills RepositoryをGit
   メタデータ（`.git/info/exclude`を含む）ごと、Devルートからの相対パス
   `Archives/git-reorg/2026-08-28/custom-instructions` と
   `Archives/git-reorg/2026-08-28/skills` へ移動して保持する。旧Repositoryは削除しない。
   archive locationとretentionが未決定なら、この最終手順を実行しない。
