# Planning + Plan Review

`Backlog` / `Todo` / `In Plan Review` で読む。共通契約とReview作法は `../SKILL.md` に従う。

`Spike` labelがある場合は [spike.md](spike.md) のPlanning差分も読む。

## Profile

- `Backlog` / `Todo` でユーザーがこの依頼内にstrictを明示指定した場合は、承認済みとして `Strict profile` labelを追加できる
- `In Plan Review` から開始した場合は既存labelだけを使う

## Backlog / Todo: Planning

`Backlog` と `Todo` は同じ処理を行います。既存Planがあればbaselineとして保持し、なければ新規作成します。

1. 既存Description、Issue、Status、Comments、Labels、relations、Repository事実を照合し、正しい部分を維持して誤り・曖昧さ・不足を修正する
2. 目的、scope、要件対応、Repository根拠、実施項目、受入条件、検証、未確認事項を必要な範囲でcanonical Planへまとめる
3. 通常Issueは専用Test成果物の要否を決め、TestグループLabelを判定と同じ1つにする
4. canonical Plan本文から `plan-fingerprint-v1` のSHA-256を算出し、Issue ID、mode、profile、Test判定、relations snapshotとともにPlan Review packetへ渡す。relations snapshotは現在のLinear relationをIssue IDの昇順で `blocks` / `blockedBy` / `relatedTo` に格納したJSON objectとする
5. 書き込み直前にDescription / Status / Labels / relationsを再取得してbaseline一致を確認し、Description / Labelsを保存・再取得確認してから `In Plan Review` へ更新する

markerがなければ既存Descriptionを保持して末尾に1組作成します。既存Planが未canonicalの場合は重要情報を保持したまま `## 承認済みPlan` / `## 参考情報` へ正規化します。

通常IssueのPlanには次を1つだけ持ちます。

```markdown
### テスト判定
- 判定: Test required | Test not required
- 理由: <理由>
```

`Test not required` は専用Testコードを追加せず、既存validator、静的確認、シナリオ確認等で受入条件を十分に検証できる場合に使います。

### One-off

一回限りのmigration / cleanup / backfillは安全な手動手順を優先します。恒久script / flag / 専用entry pointは、手作業が複雑・反復的で誤操作riskが高くscript化が明確に有利で、かつユーザーが承認した場合だけPlanへ含め、理由と承認を記録します。

Planning保存後はIssue、Description、Status、Labels、relations、Commentsを再取得し、保存済みcanonical Plan、`plan_fingerprint`、mode/profile、`test_decision`、relations snapshotをReviewerへ渡して同一実行でPlan Reviewへ進みます。Reviewerはこれら二つのmetadataを変更せず返し、再取得値が保存前の意図と一致しない場合はBLOCKEDです。

## In Plan Review: 独立Review

- lightweight Reviewer: `agents/plan-reviewer-lightweight.toml`（Terra / high、read-only）
- strict: [strict-profile.md](strict-profile.md) を追加適用
- 判定: `APPROVE` / `CHANGES_REQUIRED`

Reviewerは要求適合、Repository整合、受入条件、検証可能性、未確認事項、Plan fingerprint、mode/profile、Test判定、relations snapshotと、PlanがIssue達成に必要な最小scopeであることを確認します。

one-off処理の恒久script / flag / 専用entry pointは、Planに承認済み例外として記録されていない場合 `scope-removal` とします。

Spikeでは [spike.md](spike.md) のPlanning Review差分も適用します。

Canonical Review Resultのdecisionは `APPROVE` / `CHANGES_REQUIRED` / `BLOCKED` を使います。`APPROVE` では親Agentから渡された `plan_fingerprint`、`test_decision`、`relations_snapshot` をそのまま返し、結果をCommentへ保存します。

- `CHANGES_REQUIRED` → Comment保存後 `Todo` へ戻して停止
- `APPROVE` → `Test required` なら `Test Implementation`、`Test not required` なら `Implementation` へ更新して停止し、人間確認を待つ
- 判断不能 → 共通 `BLOCKED`
