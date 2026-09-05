# sync-policies / UserPromptSubmit scenario verification

このシナリオは、`$sync-policies` と UserPromptSubmit Hook の公開動作を、実装後に既存のSkill／Hook実行経路で確認するためのTest Implementation成果物です。Policies DBの実体確認には個人Notion接続を使用します。テスト用のfake adapter、モックDB、新しいテスト基盤は追加しません。Notionへのmutationは行わず、readbackと一時cacheを使った失敗系確認を分離します。

## 共通前提と実行方法

- Repository rootで実行する。`pwd` と `git rev-parse --show-toplevel` が同じRepositoryを示すことを確認する。
- 対象DBはHIR-137で確定したPolicies DB page URL `https://app.notion.com/p/eed9843aea2c44d6886738e111aeb08e` と、readbackで確認したdata source URL `collection://e226c613-a17a-4136-8b97-f880765abb84` である。Linear Issue IDからDBを解決しない。
- cache pathは `$HOME/.cache/decision-log/policies.json` に固定する。テストでは通常のcacheを破壊せず、必要な失敗系は一時HOMEを使う。
- 各シナリオの開始前後にcacheの存在、内容、mtimeまたはinodeを記録する。既存cacheの保持を確認するシナリオでは、sentinel JSONを事前にatomic replaceで配置する。
- 各シナリオの結果を `PASS` / `FAIL` / `MANUAL-UNVERIFIED` / `BLOCKED` で記録し、Notion readback結果、cache差分、Hook出力、終了ステータスを証跡に残す。

実装後に実行する基本command:

```sh
cd "$(git rev-parse --show-toplevel)"
sh -n skills/sync-policies/*.sh 2>/dev/null || true
python3 -m compileall -q skills hooks/runtime
```

上記に加え、実装が提供する公式のsync／Hook実行commandを、Skill本文およびHook登録定義から再確認して各シナリオで実行する。実装がPython entrypointを提供する場合は、例として次を使う（実際のentrypointに置換する）。

```sh
SYNC_CMD="python3 skills/sync-policies/sync.py"
HOOK_CMD="python3 hooks/runtime/<UserPromptSubmit-hook>.py"
```

## S1 Policies DB・schema・data sourceのreadbackと固定path

`$sync-policies`を入力なしで実行する。

期待結果:

- 固定Policies DB page URLをfetchして対象DBを確認する。
- `Name`（title）、`Policy`（rich text）、`Context`（rich text）、`Status`（select）、`Feedback Count`（number）の存在と型を確認する。
- data source `collection://e226c613-a17a-4136-8b97-f880765abb84` をquery対象として使用する。
- Linear Issue ID、環境変数、専用設定ファイル、別DBへのフォールバックを使用しない。
- 成功時だけ `$HOME/.cache/decision-log/policies.json` を生成または更新する。

検証command:

```sh
$SYNC_CMD
rc=$?
test "$rc" -eq 0
test -f "$HOME/.cache/decision-log/policies.json"
python3 -m json.tool "$HOME/.cache/decision-log/policies.json" >/dev/null
```

## S2 Active filteringと必要項目

Policies DBのreadback結果とcacheを比較する。DB上の全Pageを取得し、`Status=Active`のPageだけがcacheに含まれることを確認する。

期待結果:

- cacheのトップレベルはJSON配列である。`{"policies": [...]}`などのwrapper objectは許容しない。
- Active以外のPolicyはcacheに出力しない。
- Active各要素には、次の6項目がすべて存在する。`Page ID`、`Name`、`Policy`、`Context`、`Feedback Count`、`Last Edited`。値が空、null、または項目名だけが存在する状態は欠落として扱う。
- DBの表示順に依存せず、同じreadback結果から安定したJSONを生成する。
- DBまたは必須Propertyのreadbackが不成立の場合はcacheを更新しない。

検証command:

```sh
python3 - <<'PYTEST'
import json, os
p = os.path.expanduser('~/.cache/decision-log/policies.json')
data = json.load(open(p))
assert isinstance(data, list), 'top-level JSON must be an array'
required = {'Page ID', 'Name', 'Policy', 'Context', 'Feedback Count', 'Last Edited'}
for item in data:
    assert isinstance(item, dict)
    assert item.get('Status') == 'Active'
    assert required <= item.keys(), (required - item.keys())
    assert all(item[key] not in (None, '') for key in required)
PYTEST
```

DB側の件数・Status・6項目は個人Notion接続のreadback結果と突合する。cache要素のキー名が実装上JSON向けに別名へ正規化される場合は、Planで確定した対応関係をTest Review前に明示し、6項目の欠落検査を弱めない。

## S3 atomic replace成功

正常なsyncを実行し、更新前後のcacheを記録する。

期待結果:

- JSON全体の取得・schema検証・JSON化が完了した後に一度だけreplaceされる。
- 書込み途中のpartial JSONをHookが観測しない。
- 成功後のcacheはparse可能で、Active Policyだけを含む。
- 一時ファイルや一時ディレクトリをcache本体として残さない。

検証command:

```sh
before=$(stat -f '%i %m %z' "$HOME/.cache/decision-log/policies.json" 2>/dev/null || true)
$SYNC_CMD
python3 -m json.tool "$HOME/.cache/decision-log/policies.json" >/dev/null
after=$(stat -f '%i %m %z' "$HOME/.cache/decision-log/policies.json")
test -n "$after"
find "$HOME/.cache/decision-log" -maxdepth 1 -type f -name '*.tmp' -print | (! grep .)
```

## S4 sync失敗時の既存cache保持

一時HOMEごとに既存cacheへ同じsentinelを配置し、次の失敗点を個別に誘発してsyncを実行する。Notion取得、schema検証、JSON化、書込み、replaceの順序ごとに別実行とし、実装が提供する公式の障害再現手段または実際の失敗条件を使う。fake adapterや新しいテスト基盤は作らない。

失敗点:

1. `notion-fetch`: 固定Policies DB page fetchまたはdata source queryを失敗させる。
2. `schema-validation`: DBまたは必須Propertyのschema検証を失敗させる。
3. `json-serialization`: readback結果のJSON化を失敗させる。
4. `write`: 一時ファイルへの書込みを失敗させる。
5. `replace`: 完成した一時ファイルからcache本体へのatomic replaceを失敗させる。

各失敗点の期待結果:

- syncは非0または定義済みエラー状態を返す。
- sentinel cacheのバイト列、inode、mtimeをすべて保持する。
- 不完全なJSONや新しい空cacheを作成しない。
- 成功と報告せず、失敗点と理由を出力する。

検証command（`FAILURE_TRIGGER`は実装が提供する公式の失敗誘発手段へ置換し、5つを別々に実行する）:

```sh
run_sync_failure_case() {
  stage="$1"
  TMP_HOME=$(mktemp -d)
  mkdir -p "$TMP_HOME/.cache/decision-log"
  printf '%s\n' '{"sentinel":true}' > "$TMP_HOME/.cache/decision-log/policies.json"
  cp "$TMP_HOME/.cache/decision-log/policies.json" "$TMP_HOME.before"
  stat -f '%i %m' "$TMP_HOME/.cache/decision-log/policies.json" > "$TMP_HOME.stat.before"
  FAILURE_TRIGGER="$stage" HOME="$TMP_HOME" $SYNC_CMD
  rc=$?
  test "$rc" -ne 0
  cmp "$TMP_HOME.before" "$TMP_HOME/.cache/decision-log/policies.json"
  stat -f '%i %m' "$TMP_HOME/.cache/decision-log/policies.json" > "$TMP_HOME.stat.after"
  cmp "$TMP_HOME.stat.before" "$TMP_HOME.stat.after"
  rm -rf "$TMP_HOME"
}
run_sync_failure_case notion-fetch
run_sync_failure_case schema-validation
run_sync_failure_case json-serialization
run_sync_failure_case write
run_sync_failure_case replace
```

## S5 Hookのread-only・Activeのみ注入・Notionアクセスなし

有効なcacheを一時HOMEへ配置し、UserPromptSubmit Hookを実行する。実行前後のcache byte、inode、mtimeを比較し、Notion接続の呼出しがないことをHookの実行経路・ログで確認する。

期待結果:

- Hookはcacheだけをreadする。
- Active Policyだけをプロンプトへ注入する。
- Notion API、認証情報、sync処理、cache書込みを実行しない。
- cacheの内容・inode・mtimeを変更しない。
- Policyが複数ある場合も、定義された安定順で注入する。

検証command:

```sh
TMP_HOME=$(mktemp -d)
mkdir -p "$TMP_HOME/.cache/decision-log"
printf '%s\n' '[{"Page ID":"page-active","Name":"Active A","Policy":"A","Context":"test","Status":"Active","Feedback Count":1,"Last Edited":"2026-09-05T00:00:00Z"},{"Page ID":"page-inactive","Name":"Inactive B","Policy":"B","Context":"test","Status":"Inactive","Feedback Count":1,"Last Edited":"2026-09-05T00:00:00Z"}]' > "$TMP_HOME/.cache/decision-log/policies.json"
cp "$TMP_HOME/.cache/decision-log/policies.json" "$TMP_HOME.before"
stat -f '%i %m %z' "$TMP_HOME/.cache/decision-log/policies.json" > "$TMP_HOME.stat.before"
HOME="$TMP_HOME" $HOOK_CMD <<< '{"prompt":"test"}' > "$TMP_HOME.output"
cmp "$TMP_HOME.before" "$TMP_HOME/.cache/decision-log/policies.json"
stat -f '%i %m %z' "$TMP_HOME/.cache/decision-log/policies.json" > "$TMP_HOME.stat.after"
cmp "$TMP_HOME.stat.before" "$TMP_HOME.stat.after"
rg 'A' "$TMP_HOME.output"
! rg 'B' "$TMP_HOME.output"
rm -rf "$TMP_HOME"
```

## S6 Hookの欠落・malformed時fail-open

cacheが存在しない場合、JSONが壊れている場合、schemaまたは必須項目が不正な場合を個別に実行する。

期待結果:

- Hookはターンを停止させない（終了status 0または既存契約のfail-open status）。
- エラーを明示する場合も、入力プロンプトを失わせず、Notionへのアクセスやcache修復を行わない。
- malformed cacheを自動修正・削除・再同期しない。

検証command:

```sh
TMP_HOME=$(mktemp -d)
mkdir -p "$TMP_HOME/.cache/decision-log"
HOME="$TMP_HOME" $HOOK_CMD <<< '{"prompt":"keep-going"}' > "$TMP_HOME.missing.output"
test "$?" -eq 0
printf '%s\n' '{broken' > "$TMP_HOME/.cache/decision-log/policies.json"
HOME="$TMP_HOME" $HOOK_CMD <<< '{"prompt":"keep-going"}' > "$TMP_HOME.malformed.output"
test "$?" -eq 0
rg 'keep-going' "$TMP_HOME.missing.output" "$TMP_HOME.malformed.output"
rm -rf "$TMP_HOME"
```

## S7 `$sync-policies`入口とadd-policy連携

入力なしの`$sync-policies`入口が実装されていることをSkill定義から確認し、`add-policy`でPolicy変更を成功readbackした後に一度だけsyncが呼ばれることを、実際の個人Notion接続とreadback証跡で確認する。実行対象のPolicyと変更内容は人間が事前に確定する。テスト用Policyのmutationが必要な場合は、add-policy既存シナリオの人間承認手順に従い、終了後に元の状態をreadbackする。

期待結果:

- `$sync-policies`は入力を要求せず起動できる。
- add-policyはNotion mutation成功だけで完了せず、対象Pageの成功readback後にsyncを1回呼ぶ。
- syncは同じ固定Policies DBを読み、固定cacheを更新する。
- readback不成立時にはsyncを呼ばない。
- add-policyの呼出し側はNotion schemaやcache pathを重複定義しない。

検証command:

```sh
rg -n '\$sync-policies|sync-policies' skills/add-policy skills/sync-policies hooks
# 実装が提供するadd-policy公式commandと$SYNC_CMDを順に実行し、Notion Pageとcacheをreadbackする
```

## S8 sync errorの未完了伝播とNotion変更の再実行なし

add-policyのNotion変更が成功readbackした後、syncだけが失敗する条件で実行する。実装が提供する接続障害・検証失敗の再現手順を使い、Notion mutation回数とPage状態をreadbackする。fake adapterは追加しない。

期待結果:

- add-policyは未完了またはエラーとして返す。成功・Doneとは報告しない。
- Notionの変更済みPageは実際のreadback結果として記録する。
- sync errorを理由に、同じNotion mutation、Page作成、Feedback Count加算を再実行しない。
- cacheが既存の場合はS4と同じく保持される。
- 再開時は人間が対象Pageと状態を確認してから行う。

検証command:

```sh
# 実装が提供するadd-policy公式commandを実行し、終了statusと出力を保存
# Notion側で対象Pageのmutation回数・Property・readbackを確認
rg -n 'sync|未完了|error|retry' /tmp/add-policy-run.log
```

## 手動確認・未検証事項

- 個人Notion接続によるPolicies DB page fetch、data source query、schema/property型、Active件数、対象Pageのreadbackは実clientで確認する。接続・認証・権限が利用できない場合は`MANUAL-UNVERIFIED`とし、成功扱いにしない。
- UserPromptSubmit Hookが実際のエージェントターンで注入した内容と、Notionへアクセスしていないことは、Hookの通常実行コンテキストで確認する。静的parseやmock出力だけではPASSにしない。
- atomic replaceの競合時に読者がpartial JSONを観測しないことは、実装が提供する公式実行経路で確認する。単なるファイル存在確認はこの受入条件を満たさない。
- add-policyのNotion mutation成功readback後のsync呼出し、およびsync error時の再実行なしは、実Notionの対象Pageをreadbackして確認する。

## 判定記録

| 項目 | 記録内容 |
| --- | --- |
| Scenario | S1〜S8 |
| DB／data source | 固定URL、schema、data source readback |
| cache | path、Active件数、必須項目、byte／inode／mtime差分 |
| Hook | 注入内容、read-only、Notionアクセス有無、終了status |
| add-policy | 成功readback、sync呼出し回数、sync error伝播、Notion mutation回数 |
| 結果 | PASS／FAIL／MANUAL-UNVERIFIED／BLOCKED |
| 証跡 | command output、Notion Page URL、readback内容、停止理由 |
