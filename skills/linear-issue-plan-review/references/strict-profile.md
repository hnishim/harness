# Strict Profile

ユーザーの確認・承認後だけ読みます。共通契約は `SKILL.md` に従い、ここではstrict固有の契約だけを追加します。

## 開始ゲート

- Strict適用が必要な根拠を示して承認を得ます。承認なしは `PLAN_BLOCKED` または `BLOCKED` で停止します
- 承認後、Issue、全Comments、Repository、ローカル指示、既存Planを確認し、3つのbaselineを固定します。Statusが `Backlog`/`Todo` でなく、`In Plan Review` のhandoff回復条件にも該当しない場合、入力を一意に特定できない場合、または取得不能なら停止します
- 通常modeではIssueにない仕様を確定しません。Spike modeの暫定判断には、根拠、影響範囲、検証方法、変更可能性を記録します
- 情報・方針不足は推測で補わず、Reviewer判定ではなく親Agentの `PLAN_BLOCKED` とします

## Agent契約

- Plannerは `gpt-5.6-luna`/`xhigh`、Reviewerは `gpt-5.6-sol`/`high` を原則とします。名前付きAgentは実効設定が完全一致する場合だけ使い、不一致・不明時は `default` にモデルと推論設定を明示します。実効設定を確認できなければ `BLOCKED` です
- PlannerとReviewerは別Agentとして直列起動し、同じRepository root、ローカル指示、対象codebase、Issue、全Comments、既存Planを渡します。SubagentにLinear、ファイル、外部システムを書き込ませません
- Agent利用不能時の `default` 置換はCycle 1–2だけ、実効設定を確認できる場合に限ります。それ以外は `BLOCKED` です

## Cycle

- `REVISE`/`REPLAN` は `Todo` へ戻し、Cycle 1–2だけ同じPlannerで同じcanonical Planを更新します。保存・再取得確認後、別Reviewerで再確認します。保存契約に失敗した場合は再投稿・Status更新をせず `BLOCKED` とします
- 各Commentには共通形式に加えて `Cycle n/3` を記載します

```text
Issue ID: <issue-identifier>
Cycle n/3
Decision: APPROVE|REVISE|REPLAN
Findings: reviewerの指摘全文
```

- Cycle 3で非承認なら `REVIEW_LIMIT_REACHED` として停止し、Agentを起動せずPlanを承認しません

## 終了報告

`APPROVED`、`PLAN_BLOCKED`、`REVIEW_LIMIT_REACHED`、`BLOCKED` のいずれか、Issue ID/title、実効Agent・モデル・推論設定、各Cycle判定、Description/Comment/Statusの再取得結果、最終Plan、未確認事項を含めます。実Linearやクラウド側を実行していない場合は `UNVERIFIED` と明記します。
