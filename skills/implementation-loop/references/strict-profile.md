# Strict Profile

`Strict profile` labelのIssueでのみ適用します。Labelの新規付与はPlanning側でユーザー承認済みであることを前提とします。

Strictはscopeを広げるProfileではありません。Worker、Test設計、Implementation、Spikeの作業範囲はlightweightと同じです。Strictであることだけを理由にfailure path、edge case、manual check、fixture、Test、production codeを追加しません。

Reviewでは `agents/reviewer.toml`（Sol / high、read-only）を使い、承認済みPlan、approved-testsまたはverification baselineに含まれる受入条件・riskについてlightweightより強い検証根拠を求めます。新しいmaterialな問題を発見した場合も、その場でscopeを拡張せず、`SKILL.md` の通常のReview判定に従います。

Strict Reviewerが利用不能・timeout・実行状態不明の場合は、同等のstrict設定と独立性を確認できるReviewerにだけ再委譲できます。lightweight Reviewerへ降格しません。同等Reviewerを確保できなければ `BLOCKED` とします。
