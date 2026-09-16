# Implementation

通常Issueの `Implementation` / `In Implementation Review` / `Awaiting Acceptance` で読む。共通契約と検証記録は `../SKILL.md` に従う。Spikeの `Implementation`/`In Implementation Review` は [spike.md](spike.md) のExperiment/Result Reviewとして扱う。

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
5. Verificationが完了したら、Statusを変更する前にlogical `checkpoint` を **active Git executor** へ委譲し、対象Issueの変更だけをcandidate commitへ固定する。canonical `implementation-loop` の既定bindingはlocal Git executorで、従来どおり `git-add-commit-push checkpoint` を使用する。別entry pointがGit executorを差し替える場合もcandidate SHA、scope/provenance、non-force/no history rewrite、mutation後readbackの共通契約を満たす。Checkpointが失敗・結果不明・scope混在の場合は後続Statusへ進めず、`Implementation` で停止する
6. Checkpoint後は後述の `state_key: implementation-completion` をcurrent candidateへ更新してreadbackする。`Test required` は **Implementation Reviewを実行せず** Statusを `Awaiting Acceptance` へ更新する。`Test not required` はStatusを `In Implementation Review` へ更新し、current candidateに対する独立Implementation Review待ちとする

## Implementation Completion / Acceptance state

`state_key: implementation-completion` のmutable phase stateをImplementation完了からAcceptanceまでのcurrent durable stateとして使います。stateが存在しない初回だけ新規Commentを作成し、そのComment IDを保持します。既存stateがある再Implementation、candidate revision、Acceptance待ちでは同じComment IDをupdateし、別のCompletion / Acceptance state Commentは追加しない・作成しない。

このstateは少なくともImplementation完了、`test_decision`、current `candidate_commit` / candidate SHA、candidate branchまたはremote/ref到達状態、Automated Tests/Verification、CI Verification、verification boundary、`unverified`、Remaining Local Acceptance、Remaining Human Acceptance、Acceptance state（pending / pass）をcurrent valueとして保持します。Human Acceptance対象はcurrent candidate SHAへbindingします。必要なprior state / material eventの参照はComment IDで保持します。

CI evidenceをAcceptanceに使う場合はcandidate SHAとCI対象SHAの一致を確認し、CI PASSだけでLocal/Human AcceptanceをPASS扱いしません。Local Acceptanceを別環境へhandoffする場合はcandidate SHA、command/entry point、必要environment/application、expected result、未確認理由をcurrent stateへ残します。送信先を区別しないglobalな `push済み` / `未push` だけを後続Closeの判断根拠にしません。Runtime path、diagnostic、contractに関する記録はそれぞれ該当する場合だけ含め、非該当Issueに `N/A` 項目を埋めるschemaを要求しません。`Current / Verified`、`Proposed / Target`、`Unverified` を混同せず、未実行をPASSと表現しません。

Human Acceptance PASSは`implementation-completion` stateのAcceptance stateを同じCommentへ更新します。Local Acceptance FAIL / Human Acceptance FAILは理由追跡が必要なため共通immutable eventとして新規Commentへappendし、current phase stateはそのevent Comment IDと再開条件を参照します。FAIL時はcandidateを保持して明示的な再開指示後に `Implementation` へ戻します。

`candidate_commit` はIssueの完了を意味せず、Human Acceptanceで確認するcandidateを識別します。canonical/local bindingで既存の未コミット変更が今回Issueの対象pathと混在して分離不能な場合は、hunk単位で推測せずcheckpointを実行しません。remote bindingではlocal worktreeや未コミット差分の存在を要求せず、candidate ref/treeのreadbackで対象scopeを確認します。

Candidate safetyはactive Git bindingごとに維持します。local bindingでは `candidate_commit == current HEAD` をCloseまで維持し、対象pathにAcceptance後の未コミット差分がないことを確認します。remote bindingでは `candidate_commit == candidate ref` を維持し、Acceptance時に記録したcandidate ref/treeから変化していないことをreadbackします。同一Repository・同一branch/refではHuman Acceptance待ちcandidateの後に別Issueでcandidateを進めません。Human Acceptance FAILで同じIssueを再Implementationする場合は旧candidateを保持して新candidate checkpointを積めます。最終CloseではClose先remote/refを先に確定し、Linear記録済みの同一Issue checkpoint chainのうち、そのtarget refからliveに到達不能なcheckpointだけを古い順に `allowed_checkpoint_shas` として渡します。別remote/refへ先行push済みでもClose先から未到達なら含め、Close先から既に到達可能なら除外し、outgoing commit chain全体との完全一致を確認してから公開します。

## `In Implementation Review`: Implementation Review

通常Issueで `In Implementation Review` にある場合は、`implementation-completion` stateから `test_decision` と current candidate (`candidate_commit`) を再取得し、candidate ref/treeと一致することを確認します。通常IssueのこのStatusは `Test not required` の独立Implementation Review中だけを表します。`Test required` がこのStatusにある場合は旧契約または不整合として推測せずBLOCKEDし、durable stateを確認します。

`state_key: implementation-review` のmutable phase stateをcurrent candidateのReview packet / Review Resultに使います。stateが存在しない初回だけ新規Commentを作成し、そのComment IDを保持します。既存の同じstateではReview packet、candidate、verification evidence、Review Resultを同じCommentへupdateし、別のImplementation Review state Commentは追加しない・作成しない。

`Test not required` ではcurrent candidateに対する最新positive Implementation Reviewが存在するかでReview stateを判定します。

- current candidateにbindingされた `APPROVE` がない場合は独立Implementation Review待ち
- review対象candidate SHA (`candidate_commit`) がcurrent candidateと一致する `implementation-review` stateの最新 `APPROVE` がある場合はStatusを `Awaiting Acceptance` へ更新する
- candidate変更時は旧candidateへbindingされた `APPROVE` は失効し、新candidateのReview packet / Resultへstateを更新してfresh Reviewする

Implementation Reviewは成果物作成主体とは**独立**したread-only Reviewerが行います。成果物作成主体は同一実行コンテキストでpositive decisionまたは `APPROVE` を確定しない。Implementation Review開始時は **fresh** に current candidate (`candidate_commit`) を確認し、その後Linear Issue / Status / canonical Plan /全Comments / Labels / relationsとrepository evidence、current candidateに対するdiff/artifact、Verification evidence、未確認事項を再取得します。過去chatの説明や結論をReview根拠にしません。

Review責務はAcceptance Criteria、current candidateのdiff/artifact、Verification evidence、未確認事項の独立確認に限定し、旧来の広範なコード品質Reviewを全面復活させません。Reviewは成果物修正へ越境しません。

`implementation-review` stateにはfresh executionやCloseがReview packetを再構築できるminimum durable metadataとして、`issue`、`phase`=`Implementation Review`、`test_decision`=`Test not required`、`candidate_commit`、`review_targets`（current candidateのdiff/artifact）、`verification_evidence`、`unverified`、`decision`、`findings`、`blocker` をcurrent valueとして保持します。`review_targets` と `verification_evidence` はCanonical Review Resultの `review_context` に保持し、本文中の説明だけで代替しません。Review packetとReview Resultは同じCommentへ更新します。

Canonical decisionは次を使います。

- `APPROVE` → findingなしpositive Reviewとして `implementation-review` stateを更新し、Statusを `Awaiting Acceptance` へ更新してcurrent candidate-bound Human Acceptance待ちへ進む
- `CHANGES_REQUIRED` → findingを共通immutable eventへappendし、current stateを更新してStatusを `Implementation` へ戻して停止する
- `BLOCKED` → concrete blockerをimmutable eventへappendし、current stateを更新してStatusを維持して停止する

独立Reviewerを現在の実行から利用できない場合は、Reviewに必要なcurrent candidate / diff / Verification evidence /未確認事項を `implementation-review` stateから再構築できる状態にして `In Implementation Review` でdurable stopし、別Chat等の独立実行へhandoffします。

## `Awaiting Acceptance`: Local / Human Acceptance待ち

通常Issueの `Awaiting Acceptance` はAIによるImplementation Reviewの完了有無ではなく、current candidateに対するLocal Acceptance / Human Acceptanceの未確認事項を保持する受入待ちStatusです。

- `Test required`: Implementation Reviewは実行しない。candidate checkpoint後に直接 `Awaiting Acceptance` へ進む
- `Test not required`: current candidateにbindingされた最新 `implementation-review` stateの `APPROVE` が存在し、review対象candidate SHAとcurrent candidateが一致する場合だけ `Awaiting Acceptance` に到達できる。candidate変更時は旧 `APPROVE` を失効させる

`implementation-completion` stateのImplementation完了、Automated Tests/Verification、CI Verification、Remaining Local Acceptance、Remaining Human Acceptance、current candidate SHAを確認します。Local Acceptanceを現在の環境で実行できない場合はcandidate SHA、command/entry point、必要environment/application、expected result、未確認理由を同じstateへ残し、`Awaiting Acceptance` のままhandoffします。

問題が見つかった場合は、Local Acceptance FAIL / Human Acceptance FAILをimmutable eventへ残し、candidateを保持して明示的な再開指示後に `Implementation` へ戻します。問題がなければHuman Acceptance PASSを同じstateへ更新し、明示的なClose指示を受けて [close.md](close.md) に進みます。Human AcceptanceまたはImplementation Reviewの正判定だけで `Done` へ進めません。
