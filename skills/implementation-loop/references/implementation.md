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
5. Verificationが完了したら、Statusを変更する前にlogical `checkpoint` を **active Git executor** へ委譲し、対象Issueの変更だけをcandidate commitへ固定する。canonical `implementation-loop` の既定bindingはlocal Git executorで、従来どおり `git-add-commit-push checkpoint` を使用する。別entry pointがGit executorを差し替える場合もcandidate SHA、scope/provenance、non-force/no history rewrite、mutation後readbackの共通契約を満たす。Checkpointが失敗・結果不明・scope混在の場合は `In Implementation Review` へ進めず、`Implementation` で停止する
6. Checkpoint後のCompletion Commentに、Implementation完了、`test_decision`、`candidate_commit`（candidate SHA）、push状態またはremote/ref到達状態、Human Acceptance対象が当該SHAであることを保存する。検証は **Automated Tests/Verification**、**CI Verification**、**Remaining Local Acceptance**、**Remaining Human Acceptance** を区別する。CI evidenceをAcceptanceに使う場合はcandidate SHAとCI対象SHAの一致を確認し、CI PASSだけでLocal/Human AcceptanceをPASS扱いしない。Local Acceptanceを別環境へhandoffする場合はcandidate SHA、command/entry point、必要environment/application、expected result、未確認理由を残す。Statusを `In Implementation Review` へ更新する。`Test required` はここで **Implementation Reviewを実行しない** ままHuman Acceptance待ちとする。`Test not required` はここから **Implementation Reviewを実行する** 独立Review待ちとする。送信先を区別しないglobalな `push済み` / `未push` だけを後続Closeの判断根拠にしない。Runtime path、diagnostic、contractに関する記録はそれぞれ該当する場合だけ含め、非該当Issueに `N/A` 項目を埋めるschemaを要求しない。`Current / Verified`、`Proposed / Target`、`Unverified` を混同せず、未実行をPASSと表現しない

`candidate_commit` はIssueの完了を意味せず、Human Acceptanceで確認するcandidateを識別する。canonical/local bindingで既存の未コミット変更が今回Issueの対象pathと混在して分離不能な場合は、hunk単位で推測せずcheckpointを実行しない。remote bindingではlocal worktreeや未コミット差分の存在を要求せず、candidate ref/treeのreadbackで対象scopeを確認する。

Candidate safetyはactive Git bindingごとに維持する。local bindingでは `candidate_commit == current HEAD` をCloseまで維持し、対象pathにAcceptance後の未コミット差分がないことを確認する。remote bindingでは `candidate_commit == candidate ref` を維持し、Acceptance後にcandidate ref/treeが変化していないことをreadbackする。同一Repository・同一branch/refではHuman Acceptance待ちcandidateの後に別Issueでcandidateを進めない。Human Acceptance FAILで同じIssueを再Implementationする場合は旧candidateを保持して新candidate checkpointを積めます。最終CloseではClose先remote/refを先に確定し、Linear記録済みの同一Issue checkpoint chainのうち、そのtarget refからliveに到達不能なcheckpointだけを古い順に `allowed_checkpoint_shas` として渡します。別remote/refへ先行push済みでもClose先から未到達なら含め、Close先から既に到達可能なら除外し、outgoing commit chain全体との完全一致を確認してから公開します。

## `In Implementation Review`: durable substate

通常Issueではまず最新のCompletion Commentから `test_decision` と current candidate (`candidate_commit`) を再取得し、candidate ref/treeと一致することを確認します。

### `Test required`: Human Acceptance待ち

`Test required` はImplementation Reviewを実行しない。Completion CommentのImplementation完了、Automated Tests/Verification、CI Verification、Remaining Local Acceptance、Remaining Human Acceptance、current candidate SHAを人間が確認する。問題が見つかった場合は、明示的な再開指示を受けて `Implementation` へ戻し、修正・再検証する。問題がなければ、明示的なClose指示を受けて [close.md](close.md) に進む。Human Acceptanceの完了だけで `Done` へ進めない。

### `Test not required`: Implementation Review待ち / Human Acceptance待ち

`Test not required` ではcurrent candidateに対する最新のpositive Implementation Reviewが存在するかでsubstateを判定する。

- current candidateにbindingされた `APPROVE` がない場合は独立Implementation Review待ち
- review対象candidate SHA (`candidate_commit`) がcurrent candidateと一致する最新 `APPROVE` がある場合だけHuman Acceptance待ち
- candidate変更時は旧candidateへbindingされた `APPROVE` は失効し、新candidateをfresh Reviewする

Implementation Reviewは成果物作成主体とは**独立**したread-only Reviewerが行う。成果物作成主体は同一実行コンテキストでpositive decisionまたは `APPROVE` を確定しない。Implementation Review開始時は **fresh** に current candidate (`candidate_commit`) を確認し、その後Linear Issue / Status / canonical Plan /全Comments / Labels / relationsとrepository evidence、current candidateに対するdiff/artifact、Verification evidence、未確認事項を再取得する。過去chatの説明や結論をReview根拠にしない。

Review責務はAcceptance Criteria、current candidateのdiff/artifact、Verification evidence、未確認事項の独立確認に限定し、旧来の広範なコード品質Reviewを全面復活させない。Reviewは成果物修正へ越境しない。

Canonical decisionは次を使い、Review Commentへreview対象 `candidate_commit` とともに保存する。

- `APPROVE` → Statusは `In Implementation Review` のまま維持し、current candidate-bound positive ReviewとしてHuman Acceptance待ちへ移る
- `CHANGES_REQUIRED` → findingを保存しStatusを `Implementation` へ戻して停止する
- `BLOCKED` → blockerを保存しStatusを維持して停止する

独立Reviewerを現在の実行から利用できない場合は、Reviewに必要なcurrent candidate / diff / Verification evidence /未確認事項をLinearとrepositoryから再構築できる状態にして `In Implementation Review` でdurable stopし、別Chat等の独立実行へhandoffする。

Human Acceptance待ちではcompletion Commentとcurrent candidate-bound `APPROVE` を確認する。問題が見つかった場合は、明示的な再開指示を受けて `Implementation` へ戻し、candidateを更新して修正・再検証する。問題がなければ、明示的なClose指示を受けて [close.md](close.md) に進む。Human AcceptanceまたはImplementation Reviewの正判定だけで `Done` へ進めない。
