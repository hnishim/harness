# Implementation + Implementation Review

通常Issueの `Implementation` / `In Implementation Review` で読む。共通契約、Review作法、fingerprintは `../SKILL.md` に従う。

## Implementation

1. `Test required` は最新 `TESTS_APPROVED` と `approved-tests`、`Test not required` はPlan記載の検証方法をbaselineとする
2. `Test required` は開始前にapproved-testsのpath / hash一致を確認し、Implementationではapproved-testsを変更対象から除外する。不一致はBLOCKEDとする
3. implementer（原則 Luna / medium）へPlanとbaselineを渡し、Plan範囲を実装させる
4. 実装後にPlan traceability、変更ファイル、検証結果、未検証事項を確認する
5. completion Commentを保存し `In Implementation Review` へ更新する

## Implementation Review

- lightweight Reviewer: `agents/reviewer-lightweight.toml`（Terra / high、read-only）
- strict: [strict-profile.md](strict-profile.md) を追加適用
- `review_phase: implementation`
- 判定: `PASS` / `CHANGES_REQUIRED` / `MATERIAL_DEVIATION`

`MATERIAL_DEVIATION` は承認済みPlanへ戻らないと解決できない実質的な乖離に使います。

Canonical Review Resultのdecisionは `PASS` / `CHANGES_REQUIRED` / `MATERIAL_DEVIATION` / `BLOCKED` を使います。親Agentが算出した `artifact_fingerprint` をReviewerへ渡します。

- `PASS` → Review結果、変更・検証結果、残作業、未検証事項をCommentへ保存してClose待ち
- `CHANGES_REQUIRED` → `Implementation` へ戻す
- `MATERIAL_DEVIATION` → 期待値・観測値・影響範囲をCommentへ保存して `Todo` へ戻し停止する
