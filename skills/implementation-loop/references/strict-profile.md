# Strict Profile

`Strict profile` labelのReviewで適用します。work 範囲、評価基準、必要な根拠はlightweightと同一です。

- Plan Review: `agents/plan-reviewer.toml`（Sol / high、read-only）
- Test / Implementation / Result Review: `agents/reviewer.toml`（Sol / high、read-only）

Strict Reviewerを確保できなければBLOCKEDとし、lightweightへfallbackしません。
