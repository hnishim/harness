---
name: linear-issue-plan-review
description: Linear Statusに従い、BacklogまたはTodoではRepository確認を伴うPlan作成後、そのまま独立Plan Reviewまで実行する。In Plan Reviewからの開始時は独立Reviewを実行する。
---

# Linear Issue Plan Review

## 役割

Planning専用Skillです。**Linear Status = 現在実行すべきphase** とします。

| Status | phase | 成功時 |
| --- | --- | --- |
| `Backlog` | Plan作成 / Repository確認によるrefine | `In Plan Review` へ更新し、同一実行でPlan Reviewを続行 |
| `Todo` | Plan作成 / Repository確認によるrefine | `In Plan Review` へ更新し、同一実行でPlan Reviewを続行 |
| `In Plan Review` | 独立Plan Review | `APPROVE` → execution、`CHANGES_REQUIRED` → `Todo` |

その他のStatusでは変更せず停止します。`initial-plan` は任意であり、実行済みであることを前提にしません。

## 共通契約

- 入力はLinear Issue ID。Issue、全Comments、Labels、Status、Descriptionを取得し、Repositoryが必要なphaseではRepository root / worktreeも取得する
- Repositoryは明示パス、現在workspace、そこから一意に決まるGit rootの順で確定し、曖昧なら停止する
- phaseはStatusだけで決め、Commentや成果物から推測しない
- Linearへの書き込みは親Agentだけが行う。このSkillの起動は、本文で定義した対象IssueのDescription / Comment / Label / Status更新への承認を含む。ただし `Strict profile` labelの新規付与だけは例外とし、明示的なユーザー承認を別途必要とする
- 書き込み直前に対象フィールドを再取得してbaseline一致を確認し、書き込み後も意図した差分だけを確認する。不一致時は上書きせず停止する
- marker外、Testグループ以外のLabels、title、assignee、relations等を保持する
- Workflow Status、Review回数、Review結果はDescriptionに保存しない
- Issueにない仕様、不要な抽象化・設定化・依存追加・将来対応をPlanへ追加しない
- 一回限りのmigration / cleanup / backfillでは、恒久的なscript・flag・専用entry pointを原則追加せず、安全な手動手順で実行可能なら手動操作を優先する
- 手作業が複雑・反復的で誤操作riskが高くscript化が明確に有利な場合だけ、理由を示してユーザー承認を求める。承認された場合は例外理由と承認済みであることをPlanに記録し、恒久保存がIssue達成に必要でなければ一時的な実行手段として扱う

開始時、Issue取得とStatus検証に成功したら `Issue概要: <Issue ID> — <title>` を1行だけ表示する。同じチャットのAssistant出力ですでに同一行を表示済みなら再掲しない。`implementation-loop` から `issue_summary_displayed=true` を受け取った場合も表示しない。

停止時は次の形式で報告する。

```text
結果: BLOCKED
停止箇所: <取得|canonical Plan|Repository|Agent|検証|保存|再取得>
確認事項: <確認できた事実。原因未確定ならその旨>
推奨対応: <推奨する次の行動>
再開条件: <再開に必要な条件>
```

## Profile

ProfileはLinear labelを永続的なSource of Truthとし、PlanningからImplementationまで共通で使う。Strictはscope拡張ではなくReview assuranceの差として扱い、Planning自体はlightweightと同じ基準で行う。

- `Strict profile` あり → strict。既存Labelはユーザー承認済みとして扱い、再確認しない
- なし → lightweight
- `Backlog` / `Todo` のPlanning時にstrictの必要性を評価してよいが、自動では発動しない
- 共有サービス、本番・機密データ、認証・権限、security/privacy、不可逆な外部副作用、データ損失、stateful/high-risk変更、または明示的なstrict/test-first要求がある場合はstrictを推奨する
- strictを推奨し、`Strict profile` labelがない場合は、理由を簡潔に示してユーザーへ承認を求める。承認前はLabel追加、strict Reviewer起動、Status更新を行わず停止する
- ユーザーが承認した場合だけ `Strict profile` labelを追加して再開する。ユーザーが明示的に拒否した場合はlightweightで続行する
- ユーザーがSkill起動時または同一依頼内で明示的にstrictを指定した場合は、その指定を承認として扱いLabelを追加できる
- 自動では `Strict profile` を削除しない。`Todo` へ戻った場合に再評価してstrictを推奨することはできるが、lightweightからstrictへの昇格には毎回ユーザー承認を必要とする
- `In Plan Review` 以降はlabelだけを参照し、再判定しない

lightweight Reviewerは `agents/plan-reviewer-lightweight.toml`（Terra / high、read-only）、strictは [references/strict-profile.md](references/strict-profile.md) を適用し `agents/plan-reviewer.toml`（Sol / high、read-only）を使う。

`Spike` labelがあるIssueでは [references/spike-mode.md](references/spike-mode.md) も適用する。Spike判定はtitleや本文から推測せず、labelだけで行う。このSkillでは `Spike` labelを自動付与・削除しない。

## Canonical Description / Plan

Description管理領域は次のmarker 1組だけとする。

```text
CODEX_LINEAR_ISSUE_DESCRIPTION_START
...
CODEX_LINEAR_ISSUE_DESCRIPTION_END
```

- markerはASCIIの単独行
- 複数、片側欠落、逆順、境界不明は停止する
- `Backlog` / `Todo` ではmarkerがなければ既存Descriptionを保持して末尾に作成できる
- `In Plan Review` では正しいmarkerとcanonical Planを必須とし、推測・migrationしない

実装へ渡すPlanはmarker内の `## 承認済みPlan` から終端 `## 参考情報` の直前までとする。両見出しは1つずつ、Plan内部の見出しは `###` 以下に限定する。`Backlog` / `Todo` でinitial-plan形式など未canonicalの場合は、既存情報を落とさず同じPlanへ正規化する。

通常IssueはPlan内にテスト判定を1つ持ち、TestグループLabelは `Test required` / `Test not required` のどちらか1つだけとする。

```markdown
### テスト判定
- 判定: Test required | Test not required
- 理由: <理由>
```

Spikeは専用Test phaseを使わないため `Test not required` とし、判断に必要な検証はExperiment / PoCの受入条件・検証項目としてPlanに記載する。

## Backlog / Todo: Plan作成 / Repository確認によるrefine

`Backlog` と `Todo` は同じPlanning処理を行う。既存Planがあればbaselineとして保持し、Planがなければ新規作成する。

1. Issue、Comments、Description、Labels、Repository、ローカル指示を取得する
2. Profileを判定する。strict推奨かつ `Strict profile` labelがなければユーザー承認ゲートで停止し、承認後に再開する。Spike modeは `Spike` labelの有無だけで確定する
3. 既存DescriptionとRepository事実を照合し、正しい部分を維持して誤り・曖昧さ・不足だけを修正する
4. 必要な範囲で目的、スコープ、要件対応、Repository根拠、実施項目、受入条件、検証、未確認事項をcanonical Planへまとめる
5. 通常Issueは専用テスト成果物の要否を決める。Spikeは `Test not required` とする
6. TestグループLabelをPlan判定と同じ1つへ置換し、他Labelを保持する
7. Description / Labelsを保存・再取得確認し、その後 `In Plan Review` へ更新する

`Test not required` は専用テストコードを追加しなくても既存validator、静的確認、シナリオ確認、またはSpikeのExperiment / PoCで受入条件を十分に検証できる場合に使う。

**Planning phase中はReviewerを起動しない。**

Planning成功時はDescription / Labelsを保存・再取得確認し、`In Plan Review` へ更新する。そこで終了せずIssueを再取得し、Statusが `In Plan Review`、canonical Plan / Labelsが保存済みであることを確認して、同一実行で次の「In Plan Review: 独立Review」へ進む。Plan Review完了までをこのSkillの1回の実行範囲とする。

## In Plan Review: 独立Review

`Backlog` / `Todo` からPlanningを完了して到達した場合も、最初から `In Plan Review` で開始した場合も同じReview処理を行う。Planning直後であっても保存済みPlanを必ず再取得し、Planning時のin-memory内容をそのままReview入力に使わない。

1. Issue、Comments、Labels、Repositoryを再取得し、canonical Plan、mode、Test判定、Test Labelを検証する
2. Profileは `Strict profile` labelだけで決める。ReviewerはPlanを修正しない
3. まずPlanそのものがIssue達成に必要な最小限かを確認する。Issueにない作業、不要なArchitecture・抽象化・一般化・設定化・依存追加・将来対応、過剰な検証範囲があれば指摘する。one-off処理のための恒久的なscript・flag・専用entry pointは、Planに承認済み例外として記録されていない限り不要scopeとして扱う。より単純なPlanで同じ受入条件を満たせる場合はその差分を示す
4. 続いて要求適合、Repository整合、受入条件、検証可能性、未確認事項をread-onlyで確認する。Spikeでは仮説・観測・判断基準がDecisionに十分かも確認する
5. Reviewerは実装必須の指摘だけを出し、各指摘に `acceptance`（受入条件不足）/ `safety`（security・権限・データ損失等の実質risk）/ `bug`（Repository事実との不整合・回帰）/ `scope-removal`（実質的な過剰scopeの除去）の分類と具体的根拠を付ける。任意改善はユーザーが求めた場合を除きReview結果へ残さない
6. 親Agentは各必須指摘に分類と具体的根拠があることだけを確認し、技術的なReviewをやり直さない。根拠が欠ける指摘は実装要求にせず、必須指摘が残らなければ最終判定を `APPROVE` にする
7. scope外の実質的な複雑性の除去は必須指摘になり得るが、残置による複雑性・保守負荷・riskより修正と再検証のコストが大きいだけのcleanupでは再ループさせない
8. `CHANGES_REQUIRED` ならReview Commentを保存して `Todo` へ戻す。直前の同phase Review Commentも `CHANGES_REQUIRED` なら2回連続とみなし、その実行では必ず停止してユーザー判断を待つ
9. 判断不能なら `PLAN_BLOCKED` として停止する
10. 親AgentがReview Commentを1件保存・再取得確認する
11. `APPROVE` なら `Test required → Test Implementation`、`Test not required → Implementation` へ更新する

Review Comment:

```text
フェーズ: Plan Review
対象Issue: <issue-identifier>
プロファイル: lightweight | strict
モード: normal | spike
判定: APPROVE | CHANGES_REQUIRED
必須指摘: <各指摘を acceptance | safety | bug | scope-removal の分類と具体的根拠付きで記載。なければ なし>
```

## 終了報告

保存・再取得を確認できていない場合は成功扱いにしない。成功時は必要な項目だけを日本語名で簡潔に報告する。

```text
実行フェーズ: <Planning + Plan Review | Plan Review>
プロファイル: <lightweight | strict>
モード: <normal | spike>
テスト判定: <Test required | Test not required>
レビュー判定: <APPROVE | CHANGES_REQUIRED | 該当なし>
ステータス遷移: <before → after>
未確認事項: <なし | 内容>
```
