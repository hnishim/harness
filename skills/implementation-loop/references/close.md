# Close

1. Issue ID、Description、Status、Labels、relations、全Commentsと、現在のRepository/worktreeを再取得する
2. canonical Plan本文から `plan-fingerprint-v1` のSHA-256を再計算し、最新Plan Reviewの `APPROVE`、Issue／mode／profile／Test判定／relations snapshot metadata、`plan_fingerprint` がすべて現在値と一致することを確認する。一致しない、Commentがない、または結果不明ならStatusを維持する
3. 通常Issueは、Statusが `Implementation` のまま保存された最新のImplementation完了・検証記録とHuman Acceptance確認点を確認する。Implementation ReviewのPASSやfingerprintを前提にしない。Spikeは `In Implementation Review` の最新成果物fingerprintに一致する `DECISION_READY` Result Reviewを確認する
4. 現在の依頼内に明示的なClose指示があることを確認する。Reviewの正判定だけで `Done` へ進めない
5. Close時Case振り返りを一度実行する。Planで人間が確定した候補シグナルに一致する事象ごとに、`producer=implementation-loop`、`case_name`、`subject`、`summary`、`occurred_at`、任意の`context`、`case_intent=new`、`human_reindication=false`からなるNotion物理schema非依存のlogical payloadを作成し、`add-case`へ渡す。候補がない場合は呼び出さず継続する
6. 候補の必須事実またはtrigger contractが未確定、payload作成、`add-case`保存またはreadbackが失敗・不明の場合はCase境界で停止し、成功済みcore作業をrollback・再実行せず、Git公開へ進めない。同一Closeの再実行は同一payloadで既存Case照合・再利用へ委ねる
7. `add-case`成功後、対象scopeをRepository単位に分け、各Repositoryごとに `git-add-commit-push` へ対象範囲とクローズ指示を渡して委譲する。Policy生成・Relation設定・Feedback Count加算・Review完了はこの振り返りで行わない
8. 全RepositoryでGit Skillが成功、または送信すべき変更なしを確認できた場合だけ `Done` へ更新する
9. いずれかのCase処理・Git処理の失敗・結果不明・Issueまたは必要なReview/Acceptance記録の不一致ではStatusを維持する
10. `Done` 更新後に再取得確認する

Git操作の安全条件、staging、commit、remote選択、push、push後検証は `git-add-commit-push` をSource of Truthとします。
