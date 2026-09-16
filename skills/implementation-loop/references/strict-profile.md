# Strict Profile

`Strict profile` labelのReviewで適用します。作業範囲、評価基準、必要な根拠はlightweightと同一です。

- Plan Review: `agents/plan-reviewer.toml`（Sol / high、read-only）
- Test / Implementation / Result Review: `agents/reviewer.toml`（Sol / high、read-only）

Strict Reviewerを確保できなければBLOCKEDとし、lightweightへ切り替えません。
