# Implementation

通常Issueの `Implementation`/`In Implementation Review` で読む。共通契約と検証記録は `../SKILL.md` に従う。Spikeの `Implementation`/`In Implementation Review` は [spike.md](spike.md) のExperiment/Result Reviewとして扱う。

## Implementation

1. `Test required` は最新 `TESTS_APPROVED` と `approved-tests`、`Test not required` はPlan記載の検証方法をbaselineとする
2. `Test required` は開始前にapproved-testsのpath/hash一致を確認し、Implementationではapproved-testsを変更対象から除外する。不一致はBLOCKEDとする
3. Implementer（原則Luna/medium）へPlanとbaselineを渡し、Plan範囲を実装させる
4. 実装後にPlan traceability、変更ファイル、Automated Tests/Verificationの結果、未検証事項を確認する。次の4条件を独立に判定する
   - Effective Runtime/Entry-point：sourceと実利用経路が分離する場合だけ、必要な範囲を確認する
   - Actual Contract Impact：外部contractを変更する場合だけ、actual caller/consumerの影響を確認する
   - Diagnostic Evidence Fidelity：failure調査またはruntime verificationで必要な場合だけ、diagnostic evidenceの保持を確認する
   - Canonical Synchronization：既存canonicalのowned contractを変更する場合だけ、必要な同期を確認する
   Sourceを直接実行した成功だけでruntime成功と扱わない。Diagnostic Evidence Fidelityの条件が成立する場合は、Wrapperやcatchが必要なdiagnostic evidenceを失っていないか確認する
5. Completion CommentにImplementation完了、Automated Tests/Verificationの結果、未確認事項、Human Acceptanceで確認する点を保存し、Statusを `In Implementation Review` へ更新して人間レビュー待ちとする。Runtime path、diagnostic、contractに関する記録はそれぞれ該当する場合だけ含め、非該当Issueに `N/A` 項目を埋めるschemaを要求しない。`Current / Verified`、`Proposed / Target`、`Unverified` を混同せず、未実行をPASSと表現しない。通常IssueではAIの独立Reviewを実行しない

## `In Implementation Review`: Human Review

1. 人間がcompletion CommentのImplementation完了、Automated Tests/Verificationの結果、未確認事項、Human Acceptance確認点を確認する
2. 問題が見つかった場合は、明示的な再開指示を受けて `Implementation` へ戻し、修正・再検証する
3. 問題がなければ、明示的なClose指示を受けて [close.md](close.md) に進む。人間レビューの完了だけで `Done` へ進めない
