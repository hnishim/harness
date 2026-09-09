# Planning + Plan Review

`Backlog`/`Todo`/`In Plan Review` で読む。共通契約とReview作法は `../SKILL.md` に従う。

`Spike` labelがある場合は [spike.md](spike.md) のPlanning差分も読む。

`Bug` labelがある場合は [bug.md](bug.md) のRoot-cause investigationとPlan handoffを先に読む。

## Profile

- `Backlog`/`Todo` でユーザーがこの依頼内にstrictを明示指定した場合は、承認済みとして `Strict profile` labelを追加できる
- `In Plan Review` から開始した場合は既存labelだけを使う

## Backlog / Todo: Planning

`Backlog` と `Todo` は同じ処理を行います。既存Planがあればbaselineとして保持し、なければ新規作成します。`Bug` labelがある場合は、Planの作成・更新前に [bug.md](bug.md) の原因調査を完了します。

1. `Bug` labelがある場合は、Issue・Repository・再現条件を調査し、`ROOT_CAUSE_CONFIRMED` の記録を保存・再取得確認する。未確定・結果不明ならPlanを変更せずStatusを維持してBLOCKEDで停止する
2. 既存Description、Issue、Status、Comments、Labels、relations、Repository事実を照合し、正しい部分を維持して誤り・曖昧さ・不足を修正する
3. 目的、scope、要件対応、Repository根拠、実施項目、受入条件、検証、未確認事項を必要な範囲でcanonical Planへまとめる。Bug modeでは最新のBug Investigation記録、確認済みの原因、原因に直接対応する最小scope、回帰Testを明記する
4. 通常Issueは専用Test成果物の要否を決め、TestグループLabelを判定と同じ1つにする。Bug modeの判定は常に `Test required` とし、TestグループLabelもそれに一致させる
5. Canonical Plan、レビュー対象のPlan・成果物・差分、Issue ID、mode、profile、Test判定、`blockedBy` snapshotをPlan Review packetへ渡す。あわせて親Agentが作成するReview Context候補（`approved_scope`、`review_targets`、`meaningful_diff_at_review`、`comparison_basis`、`unverified`）を渡す。Bug modeではBug Investigation記録とその根拠もレビュー対象へ含める。`blockedBy` snapshotは今回のPlanが依存する現在の `blockedBy` のIssue IDを昇順で格納した `relations_snapshot` JSON objectとする。`blocks`/`relatedTo` はこのmetadataに含めない
6. 書き込み直前にDescription/Status/Labels/Planが依存する `blockedBy` を再取得してbaseline一致を確認し、Description/Labelsを保存・再取得確認してから `In Plan Review` へ更新する

Markerがなければ既存Descriptionを保持して末尾に1組作成します。既存Planが未canonicalの場合は重要情報を保持したまま `## 承認済みPlan`/`## 参考情報` へ正規化します。

通常IssueのPlanには次を1つだけ持ちます。

```markdown
### テスト判定
- 判定: Test required | Test not required
- 理由: <理由>
```

`Test not required` は専用Testコードを追加せず、既存validatorや静的確認等で受入条件を十分に検証できる場合に使います。

Bug modeでは次を必ず満たします。

```markdown
### 原因調査
- 記録: <最新のBug Investigation Comment>
- 確認済み原因: <原因>
- 根拠: <原因を裏付ける証拠>

### テスト判定
- 判定: Test required
- 理由: <原因を再現し、修正による再発防止を検証する回帰Test>
```

### One-off

1回限りのmigration/cleanup/backfillは安全な手動手順を優先します。恒久script/flag/専用entry pointは、手作業が複雑・反復的で誤操作riskが高くscript化が明確に有利で、かつユーザーが承認した場合だけPlanへ含め、理由と承認を記録します。

Planning保存後はIssue、Description、Status、Labels、Planが依存する `blockedBy`、Commentsを再取得し、保存済みcanonical Plan、レビュー対象、mode/profile、`test_decision`、`blockedBy` snapshot、Review Context候補をReviewerへ渡して同一実行でPlan Reviewへ進みます。保存後のPlan Review Commentには、metadataとCanonical Review Resultとは別領域としてReview Contextの5項目を保存し、親Agentがreadbackして確認します。ReviewerはPlan本文と対象・差分を確認し、workflow metadataを変更せず返します。再取得値が保存前の意図と一致しない、または対象・差分を確認できない場合はBLOCKEDです。`relatedTo`／`blocks` の変更だけではBLOCKEDにしません。

## In Plan Review: 独立Review

- 親Agentはユーザーから見えるReviewer専用のtop-level task/threadを作成せず、現在の実行内で同期的な独立read-only subagentを起動します
- Lightweight Reviewer: `agents/plan-reviewer-lightweight.toml`（Terra/high、read-only）
- Strict: [strict-profile.md](strict-profile.md) を追加適用
- 判定： `APPROVE`/`CHANGES_REQUIRED`

Reviewerは要求適合、Repository整合、受入条件、検証可能性、未確認事項、レビュー対象のPlan・成果物・差分、mode/profile、Test判定、`blockedBy` snapshotと、PlanがIssue達成に必要な最小scopeであることを確認します。`relatedTo`／`blocks` はscope・受入条件への実質影響がある場合だけ確認対象にします。

One-off処理の恒久script/flag/専用entry pointは、Planに承認済み例外として記録されていない場合 `scope-removal` とします。

明示的な別要件がない限り、対象はsingle-userの個人Mac上で実行するlocal scriptまたは小規模automationのtrusted local environmentです。Planの抽象化、設定機構、framework、compatibility layer、依存追加、defensive infrastructure、将来対応は、現在のIssue要件、既存構成、安全性、データ保全、既存互換性の具体的な必要性と照合します。根拠のないscope外の複雑化は `scope-removal` とします。明示的なIssue要件や安全性・データ保全・互換性に必要な複雑さは受け入れ、将来の拡張性、一般論、industry best practice、style preferenceだけを理由にAcceptance-blockingにしません。

Spikeでは [spike.md](spike.md) のPlanning Review差分も適用します。Bugでは [bug.md](bug.md) の調査記録、原因とscopeの対応、回帰Testを確認します。

Canonical Review Resultのdecisionは `APPROVE`/`CHANGES_REQUIRED`/`BLOCKED` を使います。`APPROVE` では親Agentから渡された `test_decision`、`relations_snapshot` をそのまま返し、レビュー対象と結果をCommentへ保存します。

- `CHANGES_REQUIRED` → Comment保存後 `Todo` へ戻して停止
- `APPROVE` → `Test required` なら `Test Implementation`、`Test not required` なら `Implementation` へ更新して停止し、人間確認を待つ
- 判断不能 → 共通 `BLOCKED`
