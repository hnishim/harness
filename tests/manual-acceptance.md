# macOS統合受入チェック

このチェックは通常のmacOSユーザーコンテキストで実施します。証跡は
`.local-state/evidence/`へ保存し、秘密情報やsecurity-scoped bookmarkの生値は
保存しません。

以下のコマンドは`HARNESS_ROOT=/Users/hnishim/Library/Mobile Documents/com~apple~CloudDocs/Dev/harness`
を設定して、`cd "$HARNESS_ROOT"`した状態で実行する。各コマンドのexit codeが
受入れ判定であり、証跡ファイルが生成されない場合はPASSにしない。

1. 担当: ローカル実装担当。`CustomInstructionsSync --status`を実行し、
   `source=.../Dev/harness/custom-instructions`、`skills=.../Dev/harness/skills`、
   `output=$HOME/.codex`、`mirror=$HOME/Library/Application Support/com.hnishim.custom-instructions-sync/mirrors`
   を期待する。次を実行し、stdoutと時刻を
   `.local-state/evidence/status.txt`へ保存する（exit code 0）。bookmarkの生値は保存しない。
   `HELPER="$HOME/Applications/Custom Instructions Sync.app/Contents/MacOS/CustomInstructionsSync"; { date -u +%FT%TZ; "$HELPER" --status; } | tee .local-state/evidence/status.txt`
2. 担当: ローカル実装担当。次の3つについて、存在、種別、permission、SHA-256を
   `.local-state/evidence/local-state.txt`へ記録する: `AGENTS.md`、
   `mirrors/custom-instructions-sync`、`mirrors/skills-notion-sync`。次を実行し、SHA-256の期待値を
   `shasum -a 256`でharness内の対応ファイルから計算して、実行結果と一致比較する。
   `CODEX_HOME="$HOME/.codex"; MIRROR_ROOT="$HOME/Library/Application Support/com.hnishim.custom-instructions-sync/mirrors"; for p in "$CODEX_HOME/AGENTS.md" "$MIRROR_ROOT/custom-instructions-sync" "$MIRROR_ROOT/skills-notion-sync"; do stat -f '%N|%HT|%Mp%Lp|%i' "$p"; find -P "$p" -type f -print0 | xargs -0 -n1 shasum -a 256; done | tee .local-state/evidence/local-state.txt`
   記録だけでPASSにせず、次の簡易検証がexit code 0になることも確認する。
   ```bash
   set -euo pipefail
   CODEX_HOME="$HOME/.codex"
   MIRROR_ROOT="$HOME/Library/Application Support/com.hnishim.custom-instructions-sync/mirrors"
   for p in "$MIRROR_ROOT/custom-instructions-sync" "$MIRROR_ROOT/skills-notion-sync"; do
       test -d "$p" && test ! -L "$p"
       test -z "$(find -P "$p" -type l -print -quit)"
       test -z "$(find -P "$p" -type d ! -perm 700 -print -quit)"
       test -z "$(find -P "$p" -type f ! -perm 600 -print -quit)"
   done
   test ! -L "$CODEX_HOME/AGENTS.md" && test -f "$CODEX_HOME/AGENTS.md"
   ```
   `user-profile.md`、MOLCURE、draft、business-emailのoverlayはregular file/directoryであり、
   symlinkでないことも同じ証跡へ記録する。再実行では認可ダイアログが表示されないことを目視確認し、
   `--status`の4行が前後一致すること、LaunchAgentが正常終了することを
   `.local-state/evidence/idempotent-rerun.txt`へ記録する。Notion remote syncの成否とreadbackは後続のNotion担当で確認する。
3. 担当: macOS runtime担当。`readlink`で`~/.codex/hooks`、`hooks.json`、6つの
   `~/.codex/agents/*.toml`、`~/.codex/skills`のtargetを確認し、
   `.local-state/evidence/runtime-links.txt`へ保存する。Skillsはchild linkではなく
   `test "$(readlink "$HOME/.codex/skills")" = "$HARNESS_ROOT/skills"`を期待する。
   `harness/skills/.system`はopaqueなplugin管理stateとして前後一致をread-only確認し、作成・コピー・link・cleanupしない。
4. 担当: macOS runtime担当。固定payloadを
   `.local-state/evidence/hooks-payload.json`へ保存してHookに渡す。
   `printf '%s\n' '{"tool_name":"Bash","tool_input":{"command":"gh auth status -h github.com"}}' | tee .local-state/evidence/hooks-payload.json | /usr/bin/python3 "$HARNESS_ROOT/hooks/runtime/gh_normal_context_guard.py" > .local-state/evidence/hooks-restricted.json`
   とし、`jq -e '.hookSpecificOutput.hookEventName == "PreToolUse" and .hookSpecificOutput.permissionDecision == "deny"' .local-state/evidence/hooks-restricted.json`がexit code 0になることを期待する。同じpayloadに
   `permission_mode=bypassPermissions`を加えた通常macOS contextではstdoutが空、exit code 0を期待する。具体的には`printf '%s\n' '{"permission_mode":"bypassPermissions","tool_name":"Bash","tool_input":{"command":"gh auth status -h github.com"}}' | /usr/bin/python3 "$HARNESS_ROOT/hooks/runtime/gh_normal_context_guard.py" > .local-state/evidence/hooks-normal.json`を実行し、ファイルが空であることを確認する。Hooks JSONの`jq -e`検査では、PreToolUseのmatcherが先に`^Bash$`、続いて`.*`、PostToolUseが`.*`、各hookのtypeが`command`であること、停止Hookが存在しないことを確認する。textlintのPostToolUse一回処理は`python3 -m unittest hooks.tests.test_textlint_boundaries`のexit code 0で確認する。
5. 担当: macOS runtime担当。`$HARNESS_ROOT/agents/*.toml` にあるすべてのAgent TOMLについて、ファイル名と `name` の一致、必須項目、各定義に記載されたsandbox設定、recognition、起動結果を確認する。
   `HARNESS_ROOT="$HARNESS_ROOT" python3 -c 'import os, pathlib, tomllib; ps=sorted(pathlib.Path(os.environ["HARNESS_ROOT"], "agents").glob("*.toml")); assert ps; ds=[tomllib.loads(p.read_text()) for p in ps]; assert all(p.stem == d["name"] and d["description"] and d["model"] and d["model_reasoning_effort"] and d["developer_instructions"] for p,d in zip(ps,ds))'`のexit code 0と、列挙された各定義をCodexのAgent選択画面から起動した結果を`.local-state/evidence/agents.txt`へ保存する。LaunchAgent plistのWatchPathsが
   harnessを指すこと、`for p in hooks hooks.json agents/*.toml; do printf '%s|' "$p"; readlink "$HOME/.codex/$p"; done | tee .local-state/evidence/runtime-links.txt`で列挙された全リンクのtargetがharness内の対応先となること、`plutil -extract WatchPaths xml1 -o - "$HOME/Library/LaunchAgents/com.hnishim.custom-instructions-sync.plist"`の2値が
   `.../Dev/harness/custom-instructions`と`.../Dev/harness/skills`であることを確認する。
   `launchctl print gui/$(id -u)/com.hnishim.custom-instructions-sync | tee .local-state/evidence/launchagent.txt`でloaded/running/
   `last exit code = 0`を保存する。可逆確認中は`launchctl bootout gui/$(id -u)/com.hnishim.custom-instructions-sync`を実行し、local-only syncのexit code 0を記録した後、`launchctl bootstrap gui/$(id -u) "$HOME/Library/LaunchAgents/com.hnishim.custom-instructions-sync.plist"`で復元する。
6. 担当: 実装担当。Notion remote syncの前に、bookmark、AGENTS、両mirror、plist、
   launchctl state、旧runtime、`.system`、既存backup、生成物、non-target stateを
   確認する。Codex setupのAgents → Skills → Custom Instructions → Hooksの直接委譲が
   維持され、子setupの非0終了で後続処理へ進まないことを確認する。失敗原因を修正した後、
   同じentrypointを再実行して全componentが収束することを確認する。1件でも不一致なら
   Notionへ進まず`BLOCKED`とし、runtime・旧Repository・Notionを変更しない。
7. 担当: 実装担当。local/macOS gateが全てPASSした後、LaunchAgentを一度だけ有効化し、
   通常起動または一度だけのkickstartのどちらか一方だけを実行する。
   `.local-state/evidence/launchagent-run.txt`にrun countが1回だけ増えたこと、local
   syncとNotion syncのexit code 0を保存する。
8. 担当: Notion連携担当。本文、metadata、対象ページ識別子をreadbackし、実行前に
   `jq -S -c '{body,metadata}' .local-state/evidence/notion-input.json | shasum -a 256`で
   算出した期待hashと、readbackから同じcanonical serializationを作ったhashが一致することを
   `.local-state/evidence/notion-readback.json`へ保存する。部分更新、readback不一致、
   失敗時は自動rollbackせず`BLOCKED`とし、cleanup/archiveを実行しない。
