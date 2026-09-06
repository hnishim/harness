# Implementation

通常Issueの `Implementation` で読む。共通契約と検証記録は `../SKILL.md` に従う。Spikeの `In Implementation Review` は [spike.md](spike.md) のResult Reviewとして扱う。

## Implementation

1. `Test required` は最新 `TESTS_APPROVED` と `approved-tests`、`Test not required` はPlan記載の検証方法をbaselineとする
2. `Test required` は開始前にapproved-testsのpath / hash一致を確認し、Implementationではapproved-testsを変更対象から除外する。不一致はBLOCKEDとする
3. implementer（原則 Luna / medium）へPlanとbaselineを渡し、Plan範囲を実装させる
4. 実装後にPlan traceability、変更ファイル、Automated Tests/Verificationの結果、未検証事項を確認する
5. completion CommentにImplementation完了、Automated Tests/Verificationの結果、未確認事項、Human Acceptanceで確認する点を保存し、Statusは `Implementation` のままHuman Acceptance待ちとする
6. Human Acceptanceで問題が見つかった場合は、明示的な再開指示を受けて `Implementation` で修正・再検証する。通常Issueを `In Implementation Review` へ遷移させない
