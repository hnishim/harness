---
name: implementation-loop
description: Linear IssueのStatusから必要なphaseを判定し、Planning、Test、Implementation、Spike、独立Review、明示的Closeまでを単一入口で進める。
---

# Implementation Loop

## 役割

入力はLinear Issue IDです。Statusから基準referenceを選びます。

| Status | 読むreference |
| --- | --- |
| `Backlog` / `Todo` / `In Plan Review` | [references/planning.md](references/planning.md) |
| `Test Implementation` / `In Test Review` | [references/test.md](references/test.md) |
| `Implementation` / `In Implementation Review` | [references/implementation.md](references/implementation.md) |
| `Done` | なし |

`Spike` labelはmode modifierです。Planningでは `planning.md` に [references/spike.md](references/spike.md) を追加し、`Implementation` / `In Implementation Review` では `spike.md` を `implementation.md` の代わりに使います。SpikeがTest Statusにある場合はBLOCKEDです。

`Strict profile` labelはReview profile modifierです。独立Review時だけ [references/strict-profile.md](references/strict-profile.md) を追加します。

Close待ちで明示的Close指示を受けた場合だけ [references/close.md](references/close.md) を読みます。

## 共通契約

- phaseのSource of TruthはStatus
- modeのSource of Truthは `Spike` label
- profileのSource of Truthは `Strict profile` label。あり=strict、なし=lightweight
- phase開始前にIssue、Status、Description、全Comments、Labels、Repository root / worktree / 適用されるlocal instructionsを再取得する
- Repositoryは明示パス、現在workspace、そこから一意に決まるGit rootの順で確定する
- Linearへの書き込みは親Agentが行う。このSkillの起動は、本文と各referenceで定義した対象IssueのDescription / Comment / TestグループLabel / Status更新への承認を含む。`Strict profile` labelの新規付与は明示的なユーザー承認を必要とする
- 書き込み直前に対象フィールドを再取得してbaseline一致を確認し、書き込み後も意図した差分だけを再取得確認する
- marker外のDescription、Testグループ以外のLabels、title、assignee、relations等を保持する
- Workflow Status、Review回数、Review結果はCommentへ残す
- 作業scopeは承認済みPlanの範囲・制約・受入条件に限定する
- 無関係なworktree変更を保持する

Repositoryやbaselineを一意に確認できない場合はBLOCKEDです。

開始時、Issue取得とStatus検証に成功したら、各chatで1回だけ `Issue概要: <Issue ID> — <title>` を表示します。

停止時は次の形式で報告します。

```text
結果: BLOCKED
停止箇所: <取得|canonical Plan|Repository|Agent|検証|保存|Git/外部>
確認事項: <確認できた事実。原因未確定ならその旨>
推奨対応: <推奨する次の行動>
再開条件: <再開に必要な条件>
```

## Canonical Description / Plan

Description管理領域は次のASCII marker 1組です。

```text
CODEX_LINEAR_ISSUE_DESCRIPTION_START
...
CODEX_LINEAR_ISSUE_DESCRIPTION_END
```

実装へ渡すPlanはmarker内の `## 承認済みPlan` から終端 `## 参考情報` の直前までです。両見出しは1つずつ、Plan内部の見出しは `###` 以下とします。

- `Backlog` / `Todo` でmarkerがない場合の作成・既存Planの正規化は `planning.md` に従う
- `In Plan Review` 以降は正しいmarkerとcanonical Planを必須とする
- 通常IssueはPlan内のTest判定とTestグループLabelが `Test required` / `Test not required` のどちらか1つで一致していることを必須とする
- Spikeは `Test not required`

markerの複数、片側欠落、逆順、境界不明はBLOCKEDです。

## Review共通契約

Planning、Test、Implementation、Resultの各独立Reviewに共通して次を適用します。

- Reviewerは成果物がIssue達成に必要な最小scopeかを確認する
- `scope-removal` は、残置cost / riskが除去・再検証costを上回る実質的なscope外複雑性に限る
- Reviewerはphaseを進める前に修正必須の指摘だけを出し、各指摘に `acceptance` / `safety` / `bug` / `scope-removal` の分類と具体的根拠を付ける
- Reviewer packetは、まずschema / phase / decision / 必須項目を検証する。不正なら形式訂正を1回だけ求め、再度不正ならBLOCKEDとする
- schema正常化後に各findingの分類と具体的根拠を確認し、根拠が欠けるfindingは実装要求にしない。valid findingが0なら各Reviewの正判定へ補正する
- 親AgentはReviewerの技術判断を再Reviewせず、packetの形式・分類・具体的根拠だけを検証する
- Reviewerはread-only
- 変更要求を保存したとき、直前の同phase Review Commentも同じ変更要求なら2回連続とみなす。通常のbackward transitionを行った後、その実行を停止する
- Reviewer利用不能または判断不能はBLOCKEDとする

Review Commentの共通項目:

```text
フェーズ: <review phase>
対象Issue: <issue-identifier>
プロファイル: lightweight | strict
判定: <phase-specific decision>
必須指摘: <各指摘を acceptance | safety | bug | scope-removal の分類と具体的根拠付きで記載。なければ なし>
```

## Routing / 停止境界

保存・再取得確認後のforward transitionは同じ実行内で継続できます。

次は停止境界です。

- Plan Review `APPROVE` 後: 次Statusへ更新して停止し、人間確認を待つ。以後の明示的な `implementation-loop` 実行を人間確認後の再開指示として扱う
- `CHANGES_REQUIRED` / `PLAN_INCOMPLETE` / `MATERIAL_DEVIATION` で `Todo` へ戻った場合
- 同一Review phaseで2回連続の変更要求になった場合
- `PASS` / `DECISION_READY` のClose待ち
- BLOCKED
- `Done`

Plan Review後の次回実行は、`Test required` なら `test.md`、`Test not required` なら `implementation.md` から開始します。`TESTS_APPROVED` 後は同一実行で `implementation.md` へ進めます。

## Test以降の開始ゲート

`Test Implementation` 以降はcanonical Plan、mode/profile、Test判定、Repository/worktreeを再検証します。変更予定pathと既存dirty pathが重なる場合、その変更が同一Issueの直前phase成果物として確認できなければBLOCKEDです。hunk単位の自動分離は行いません。

## `In Implementation Review` の共通substate

Review直前に、今回scopeの相対pathと各成果物のSHA-256（削除は `deleted`）をsortしてhash化した `成果物fingerprint` を作ります。

- 通常Issueで最新のImplementation Reviewが `PASS` かつfingerprint一致 → Close待ち
- Spikeで最新のResult Reviewが `DECISION_READY` かつfingerprint一致 → Close待ち
- fingerprintが変わっている、または有効な正判定Commentがない → 対応referenceのReviewを実行
- 明示的Close指示がある場合も、最新の正判定とfingerprint一致を確認してCloseへ進む

## 終了報告

必要な項目だけを日本語名で簡潔に報告します。

```text
実行フェーズ: <phase>
プロファイル: <lightweight | strict>
モード: <normal | spike>
テスト判定: <Test required | Test not required | 該当なし>
レビュー判定: <decision | 該当なし>
ステータス遷移: <before → after>
検証結果: <要約>
未確認事項: <なし | 内容>
クローズ待ち: <はい | いいえ>
```
