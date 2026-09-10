# Implementation

通常Issueの `Implementation`/`In Implementation Review` で読む。共通契約と検証記録は `../SKILL.md` に従う。Spikeの `Implementation`/`In Implementation Review` は [spike.md](spike.md) のExperiment/Result Reviewとして扱う。

## Implementation

1. `Test required` は最新 `TESTS_APPROVED` と `approved-tests`、`Test not required` はPlan記載の検証方法をbaselineとする
2. `Test required` は開始前にapproved-testsのpath/hash一致を確認し、Implementationではapproved-testsを変更対象から除外する。不一致はBLOCKEDとする
3. Implementer（原則Luna/medium）へPlanとbaselineを渡し、Plan範囲を実装させる
4. 実装後にPlan traceability、変更ファイル、Automated Tests/Verificationの結果、未検証事項を確認する。実利用経路がsourceと分離する場合は、可能なら実entry pointまたは同等のruntime経路で確認し、Repository artifactとruntime artifactの対応を確認する。Sourceを直接実行した成功だけでruntime成功と扱わない。外部contractを変更した場合はactual caller/consumerの影響を確認し、wrapperやcatchがexit status、stderr/safe error、error code、failure phaseなど必要なdiagnostic evidenceを失っていないか確認する
5. Completion CommentにImplementation完了、Automated Tests/Verificationの結果、runtime pathがVerifiedかUnverifiedか、diagnostic/contract確認結果、未確認事項、Human Acceptanceで確認する点を保存し、Statusを `In Implementation Review` へ更新して人間レビュー待ちとする。`Current / Verified`、`Proposed / Target`、`Unverified` を混同せず、未実行をPASSと表現しない。通常IssueではAIの独立Reviewを実行しない

## `In Implementation Review`: Human Review

1. 人間がcompletion CommentのImplementation完了、Automated Tests/Verificationの結果、未確認事項、Human Acceptance確認点を確認する
2. 問題が見つかった場合は、明示的な再開指示を受けて `Implementation` へ戻し、修正・再検証する
3. 問題がなければ、明示的なClose指示を受けて [close.md](close.md) に進む。人間レビューの完了だけで `Done` へ進めない
