# Close

1. Issue ID、Description、Status、Labels、relations、全Commentsと、現在のRepository/worktreeを再取得する
2. canonical Plan本文から `plan-fingerprint-v1` のSHA-256を再計算し、最新Plan Reviewの `APPROVE`、Issue／mode／profile／Test判定／relations snapshot metadata、`plan_fingerprint` がすべて現在値と一致することを確認する。一致しない、Commentがない、または結果不明ならStatusを維持する
3. `In Implementation Review` の通常Issueは、現在の成果物fingerprintに一致する最新の `PASS` Review Commentを確認する。Spikeは `DECISION_READY` を確認する
4. 現在の依頼内に明示的なClose指示があることを確認する。Reviewの正判定だけで `Done` へ進めない
5. 対象scopeをRepository単位に分け、各Repositoryごとに `git-add-commit-push` へ対象範囲とクローズ指示を渡して委譲する
6. 全RepositoryでGit Skillが成功、または送信すべき変更なしを確認できた場合だけ `Done` へ更新する
7. いずれかのGit失敗・結果不明・Issue/Review state不一致ではStatusを維持する
8. `Done` 更新後に再取得確認する

Git操作の安全条件、staging、commit、remote選択、push、push後検証は `git-add-commit-push` をSource of Truthとします。
