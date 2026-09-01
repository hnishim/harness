---
name: linear-issue-plan-review
description: Linear Statusに従い、BacklogまたはTodoでRepository確認を伴うPlan作成を実行し、成功時にIn Plan Reviewへ進める。In Plan Reviewでは独立Reviewを実行する。
---

# Linear Issue Plan Review

## 役割

Planning専用Skillです。**Linear Status = 現在実行すべきphase** とします。

| Status | phase | 成功時 |
| --- | --- | --- |
| `Backlog` | Plan作成 / Repository確認によるrefine | `In Plan Review` |
| `Todo` | Plan作成 / Repository確認によるrefine | `In Plan Review` |
| `In Plan Review` | 独立Plan Review | `APPROVE` → execution、`CHANGES_REQUIRED` → `Todo` |

その他のStatusでは変更せず停止します。`initial-plan` は任意であり、実行済みであることを前提にしません。

## 共通契約

- 入力はLinear Issue ID。Issue、全Comments、Labels、Status、Descriptionを取得し、Repositoryが必要なphaseではRepository root / worktreeも取得する
- Repositoryは明示パス、現在workspace、そこから一意に決まるGit rootの順で確定し、曖昧なら停止する
- phaseはStatusだけで決め、Commentや成果物から推測しない
- Linearへの書き込みは親Agentだけが行う。このSkillの起動は、本文で定義した対象IssueのDescription / Comment / Label / Status更新への承認を含む
- 書き込み直前に対象フィールドを再取得してbaseline一致を確認し、書き込み後も意図した差分だけを確認する。不一致時は上書きせず停止する
- marker外、Testグループ以外のLabels、title、assignee、relations等を保持する
- Workflow Status、Review回数、Review結果はDescriptionに保存しない
- Issueにない仕様、不要な抽象化・設定化・依存追加・将来対応をPlanへ追加しない

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

ProfileはLinear labelを永続的なSource of Truthとし、PlanningからImplementationまで共通で使う。

- `Strict profile` あり → strict
- なし → lightweight
- `Backlog` / `Todo` のPlanning時だけ新規判定できる
- 共有サービス、本番・機密データ、認証・権限、security/privacy、不可逆な外部副作用、データ損失、stateful/high-risk変更、または明示的なstrict/test-first要求がある場合は `Strict profile` を追加する
- 自動では `Strict profile` を削除しない。`Todo` へ戻った場合は再評価し、必要ならlightweightからstrictへ昇格する
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
2. Profileを判定し、Spike modeは `Spike` labelの有無だけで確定する
3. 既存DescriptionとRepository事実を照合し、正しい部分を維持して誤り・曖昧さ・不足だけを修正する
4. 必要な範囲で目的、スコープ、要件対応、Repository根拠、実施項目、受入条件、検証、未確認事項をcanonical Planへまとめる
5. 通常Issueは専用テスト成果物の要否を決める。Spikeは `Test not required` とする
6. TestグループLabelをPlan判定と同じ1つへ置換し、他Labelを保持する
7. Description / Labelsを保存・再取得確認し、その後 `In Plan Review` へ更新する

`Test not required` は専用テストコードを追加しなくても既存validator、静的確認、シナリオ確認、またはSpikeのExperiment / PoCで受入条件を十分に検証できる場合に使う。

**PlanningではReviewerを起動しない。**

成功時はDescription / Labelsを保存・再取得確認し、`Backlog` / `Todo` のどちらから開始しても `In Plan Review` へ更新して終了する。

## In Plan Review: 独立Review

1. Issue、Comments、Labels、Repositoryを再取得し、canonical Plan、mode、Test判定、Test Labelを検証する
2. Profileは `Strict profile` labelだけで決める。ReviewerはPlanを修正しない
3. まずPlanそのものがIssue達成に必要な最小限かを確認する。Issueにない作業、不要なArchitecture・抽象化・一般化・設定化・依存追加・将来対応、過剰な検証範囲があれば指摘する。より単純なPlanで同じ受入条件を満たせる場合はその差分を示す
4. 続いて要求適合、Repository整合、受入条件、検証可能性、未確認事項をread-onlyで確認する。Spikeでは仮説・観測・判断基準がDecisionに十分かも確認する
5. 判定候補を `APPROVE` / `CHANGES_REQUIRED` から決める。Planにすでにscope外の実質的な複雑性が含まれている場合、その除去は必須指摘になり得る。ただし、残置による複雑性・保守負荷・riskより、修正と再検証のコストが大きいだけのcleanupでは再ループさせない
6. `CHANGES_REQUIRED` でPlanningをもう一巡させる前に、各指摘がIssueの明示要件・受入条件・安全性・Repository制約、または前項の実質的な過剰部分の除去に必要かを再確認する。任意改善や「さらに簡潔にできる」程度の指摘は除外し、必須指摘が残らなければ `APPROVE` にする
7. 判断不能なら `PLAN_BLOCKED` として停止する
8. 親AgentがReview Commentを1件保存・再取得確認する
9. `APPROVE` なら `Test required → Test Implementation`、`Test not required → Implementation` へ更新する
10. `CHANGES_REQUIRED` なら `Todo` へ戻す

Review Comment:

```text
フェーズ: Plan Review
対象Issue: <issue-identifier>
プロファイル: lightweight | strict
モード: normal | spike
判定: APPROVE | CHANGES_REQUIRED
指摘事項: <具体的な指摘。なければ なし>
```

## 終了報告

保存・再取得を確認できていない場合は成功扱いにしない。成功時は必要な項目だけを日本語名で簡潔に報告する。

```text
実行フェーズ: <Planning | Plan Review>
プロファイル: <lightweight | strict>
モード: <normal | spike>
テスト判定: <Test required | Test not required>
レビュー判定: <APPROVE | CHANGES_REQUIRED | 該当なし>
ステータス遷移: <before → after>
未確認事項: <なし | 内容>
```
