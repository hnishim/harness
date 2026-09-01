# Strict Profile

`Strict profile` labelが付いたIssueでのみ適用します。Status routing、Linear書き込み、canonical Plan、Test判定は `SKILL.md` をSource of Truthとし、ここではstrict固有の差分だけを定義します。

## Todo: Planner

- 原則としてPlannerは `gpt-5.6-luna` / `xhigh` を使う
- Issue、全Comments、Repository root、ローカル指示、既存Planを渡す
- shared/stateful/high-riskな挙動、compatibility、security/privacy、error handling、data loss、external side effectのうちIssueに関係する観点を明示的に確認する
- Issueにない仕様や「念のため」のArchitectureを追加しない
- PlannerはLinearへ書き込まない

## In Plan Review: Reviewer

- 原則として `agents/plan-reviewer.toml`（Sol / high、read-only）を使う
- Plannerとは独立したAgentとして、PlanとRepository事実の対応を確認する
- blockerは要求不一致、重大なRepository誤認、検証不能な受入条件、未処理のsecurity/privacy/data-loss risk、実装を開始できない未確定事項に限定する
- style preferenceや任意改善は `REVISE` / `REPLAN` の理由にしない

利用不能なAgentを代替する場合は、同等の役割・独立性を維持し、実効model/reasoning設定と代替理由を報告する。routingやLinear stateを変更して代替しない。
