---
name: initial-plan
description: BacklogのLinear IssueをRepositoryを見ずに整理し、必要な粒度の初期PlanをDescriptionへ保存してTodoへ進める任意の前処理。
---

# Linear 初期プラン

## 役割

Repository確認前にLinear上の情報だけでIssueを整理する任意のfrontendです。

- 主対象は `Backlog`
- Repository、ローカルファイル、コード上の事実は参照・推測しない
- 初期PlanをDescriptionへ保存し、`Backlog → Todo` に進める
- `Todo` 以降のRepository確認を伴うPlan作成・Reviewは `linear-issue-plan-review` に委ねる
- このSkillを使わず、後続workflowから直接 `Backlog → Todo` に進んでもよい

## 共通契約

- Issue IDで対象Issueを一意に取得し、Issue本体と全CommentsをSource of Truthとする。取得不能・競合・不一致は推測せず停止する
- 要件、制約、意思決定、受入条件、参考情報を保持し、仮定・未解決事項と区別する
- Linearへの書き込みは親Agentだけが行う。このSkillの起動は、本文で定義した対象IssueのDescription / Label / Status更新への承認を含む
- 書き込み直前に対象フィールドを再取得してbaseline一致を確認し、書き込み後も意図した差分だけが反映されたことを再取得確認する
- marker外のDescription、非対象Label、title、assignee、relations等を保持する

停止時は次の形式で報告する。

```text
結果: BLOCKED
停止箇所: <取得|検証|保存|再取得>
確認事項: <確認できた事実。原因未確定ならその旨>
推奨対応: <推奨する次の行動>
再開条件: <再開に必要な条件>
```

## Status

| 開始Status | 処理 | 終了Status |
| --- | --- | --- |
| `Backlog` | 初期Planを作成・保存 | `Todo` |
| `Todo` | 明示的に初期Plan更新を依頼された場合だけ更新 | `Todo` |
| `In Plan Review` 以降 | 処理しない | 変更なし |

## Canonical Description marker

管理領域は次のASCII marker 1組だけで囲む。

```text
CODEX_LINEAR_ISSUE_DESCRIPTION_START
...
CODEX_LINEAR_ISSUE_DESCRIPTION_END
```

- markerは単独行とする
- markerがなければ既存Descriptionを保持して末尾に1組追加する
- 正しい1組があれば内側だけを更新する
- 複数、片側欠落、逆順、境界不明なら書き換えず停止する
- marker内の既存重要情報を黙って削除しない

## 初期Plan

Issueの規模・性質に応じて粒度を変える。小規模な設定・文書変更・単純Taskは目的、要件、受入条件を中心に簡潔にし、空セクションを作らない。複雑IssueやSpikeは、後続Planningに必要な制約、検証論点、仮定、未解決事項まで保持する。

必要な範囲で次を整理する。

1. 目的
2. 背景・コンテキスト
3. 要件
4. 制約・対象外
5. 実装Plan
6. テスト / 検証方針
7. 受入条件
8. 仮定・未解決事項
9. 参考情報

実装PlanはCoding Agentが次に調査・判断できる程度まで具体化する。ただし、未確認のファイル、module、API、class、function、dependency、schema等を確定事項として書かない。Repository確認が必要なら「何を確認し、その結果で何を決めるか」を書く。

`Spike` labelがあるIssueは、完成品の実装手順より仮説、検証論点、観測方法、採用/不採用の判断基準を優先する。

## 保存

1. 保存直前にIssueを再取得し、Description / Status / Labelsがbaselineと一致することを確認する
2. marker内だけを更新し、既存Labelを保持する。Spike判定は `Spike` labelの有無だけで行い、このSkillでは自動付与しない
3. `Backlog` から開始した場合だけ `Todo` へ更新する
4. 保存後にmarker、marker外、Label、Statusを再取得確認する
5. 成功時はIssue IDとStatus遷移だけを簡潔に報告し、依頼されない限りDescription全文を再掲しない
