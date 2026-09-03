# Test Implementation + Test Review

通常Issueかつ `Test required` の `Test Implementation` / `In Test Review` で読む。共通契約とReview作法は `../SKILL.md` に従う。

## Test Implementation

1. implementer（原則 Luna / medium）へ承認済みPlanを渡し、Planで許可されたTest成果物を変更させる
2. 承認済みPlanのRequirements / Acceptance Criteriaを公開動作単位で検証するTestを作る
3. 変更ファイル、検証command / result、成果物path/hash、未検証事項をCommentへ保存し `In Test Review` へ更新する

## Test Review

- lightweight Reviewer: `agents/reviewer-lightweight.toml`（Terra / high、read-only）
- strict: [strict-profile.md](strict-profile.md) を追加適用
- `review_phase: tests-only`
- 判定: `TESTS_APPROVED` / `TESTS_CHANGES_REQUIRED` / `PLAN_INCOMPLETE`

`PLAN_INCOMPLETE` はPlan不足がImplementation開始を妨げる場合に使います。

Canonical Review Resultのdecisionは `TESTS_APPROVED` / `TESTS_CHANGES_REQUIRED` / `PLAN_INCOMPLETE` / `BLOCKED` を使います。Test Implementationのpath / SHA-256 / 再実行command / 必要な手動確認を `approved_tests` 候補としてReviewerへ渡します。

- `TESTS_APPROVED` → approved-testsをbaselineとして固定し `Implementation` へ進む
- `TESTS_CHANGES_REQUIRED` → `Test Implementation` へ戻す
- `PLAN_INCOMPLETE` → 理由をCommentへ保存して `Todo` へ戻し停止する
