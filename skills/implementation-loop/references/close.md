# Close

1. Issue ID / Statusと、現在の成果物fingerprintに一致する最新の `PASS` / `DECISION_READY` Review Commentを再取得確認する
2. 対象scopeをRepository単位に分け、各Repositoryごとに `git-add-commit-push` へ対象範囲とクローズ指示を渡して委譲する
3. 全RepositoryでGit Skillが成功、または送信すべき変更なしを確認できた場合だけ `Done` へ更新する
4. いずれかのGit失敗・結果不明・Issue/Review state不一致ではStatusを維持する
5. `Done` 更新後に再取得確認する

Git操作の安全条件、staging、commit、remote選択、push、push後検証は `git-add-commit-push` をSource of Truthとします。
