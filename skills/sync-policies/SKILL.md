---
name: sync-policies
description: 個人NotionのPolicies DBをreadbackし、Active Policyだけをruntime cacheへ同期する。
notion_sync: false
role: Main
tags: [notion, policy, decision-log, cache]
---

# Sync Policies

入力を受け取らず、固定された個人NotionのPolicies DBを読み取り、UserPromptSubmit Hookが読むruntime cacheを再生成します。Notion操作には標準の個人Notion接続（`mcp__codex_apps__notion`）だけを使用します。

## 固定リソース

- Policies DB page: `https://app.notion.com/p/eed9843aea2c44d6886738e111aeb08e`
- Policies data source: `collection://e226c613-a17a-4136-8b97-f880765abb84`
- cache: `$HOME/.cache/decision-log/policies.json`（`Path.home() / ".cache" / "decision-log" / "policies.json"`）

Linear Issue ID、環境変数、別の設定ファイル、別Notion workspace／DBで対象を解決しません。

## Procedure

1. 上記DB pageをfetchし、対象DBであることとdata source URLをreadbackします。data sourceをqueryし、schemaもreadbackします。
2. `Name`（title）、`Policy`（rich text）、`Context`（rich text）、`Status`（select）、`Feedback Count`（number）が存在し、型が一致することを確認します。DB、data source、schema、property、query結果が不成立または不明なら同期を失敗として終了します。
3. query結果から`Status=Active`のPageだけを選び、各要素を次の項目へ変換します。`Page ID`、`Name`、`Policy`、`Context`、`Feedback Count`、`Last Edited`、`Status: "Active"`。6項目またはStatusが欠落、null、空文字、またはActive以外のPageは同期を失敗として扱います。cacheのトップレベルはこの要素のJSON配列です。
4. Page IDなどの安定キーで並べ、完全な配列をJSON化してparseできることを確認します。取得、schema検証、変換、JSON化の途中で失敗した場合はcacheへ触れません。
5. cacheの親ディレクトリを作成し、同じディレクトリ内に一時ファイルを作成します。一時ファイルへ完全なJSONを書き、readbackしてparseと全要素の6項目および`Status: "Active"`を再検証した後、`os.replace`相当のatomic replaceを一度だけ実行します。
6. 失敗時は既存cacheのbyte、inode、mtimeを変更せず、Notion mutationを行わず、失敗箇所と理由を報告します。新規cacheがまだない場合も、空配列や不完全なcacheを作成しません。

## add-policyとの連携

`$add-policy`はPolicy mutation後の成功readbackを確認してから、入力なしでこのSkillを一度だけ呼びます。同期失敗はPolicy mutation自体を再実行せず、未完了として報告します。

## Output

成功時はreadbackしたDB/data source、Active件数、cache path、atomic replace完了を報告します。失敗時はNotion取得、schema検証、変換、JSON化、write、replaceのどこで失敗したか、既存cacheを保持したことを報告します。

## Hard constraints

- Active以外をcacheへ出力しません。HookからNotionを呼び出したりcacheを書き換えたりしません。
- cache更新前に完全な内容を検証し、partial JSONをcache本体として残しません。
- sync失敗時に既存cacheを削除、空化、上書きしません。
- Policy enforcement、優先度制御、Case自動生成、定期同期、手入力cacheを追加しません。
