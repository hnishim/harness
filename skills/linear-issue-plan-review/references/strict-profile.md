# Strict Profile

`Strict profile` labelが付いたIssueでのみ適用します。Labelの新規付与はユーザーの明示承認後に限ります。

Strictはscopeを広げるProfileではありません。Planning内容、要件、Test scopeはlightweightと同じ基準で決め、Strictであることだけを理由にfailure path、manual check、追加要件、追加Testを増やしません。

Plan Reviewでは `agents/plan-reviewer.toml`（Sol / high、read-only）を使います。承認済みPlanとRepository事実を独立に確認し、Planに含まれる受入条件・riskについてlightweightより強い検証根拠を求めます。新しいmaterialな問題を発見した場合も、その場でscopeを拡張せず、`SKILL.md` の通常のReview判定に従います。

Strict Reviewerが利用不能・timeout・実行状態不明の場合は、同等のstrict設定と独立性を確認できるReviewerにだけ再委譲できます。lightweight Reviewerへ降格しません。同等Reviewerを確保できなければ `BLOCKED` として停止します。
