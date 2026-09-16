# Implementation

通常Issueの `Implementation`/`In Implementation Review` で読む。共通契約と検証記録は `../SKILL.md` に従う。Spikeの `Implementation`/`In Implementation Review` は [spike.md](spike.md) のExperiment/Result Reviewとして扱う。

## Implementation

1. `Test required` は最新 `TESTS_APPROVED` と `approved-tests`、`Test not required` はPlan記載の検証方法をbaselineとする
2. `Test required` は開始前にapproved-testsのpath/hash一致を確認し、Implementationではapproved-testsを変更対象から除外する。不一致はBLOCKEDとする
3. Implementer（原則Luna/medium）へPlanとbaselineを渡し、Plan範囲を実装させる
4. 実装後にPlanとの対応関係、変更ファイル、Automated Tests/Verificationの結果、未検証事項を確認する。次の4条件を独立に判定する
   - Effective Runtime/Entry-point：ソースと実利用経路が分離する場合だけ、必要な範囲を確認する
   - Actual Contract Impact：外部の取り決めを変更する場合だけ、actual caller/consumerの影響を確認する
   - Diagnostic Evidence Fidelity：失敗調査または実行時検証で必要な場合だけ、診断の根拠の保持を確認する
   - Canonical Synchronization：既存canonicalが管轄する取り決めを変更する場合だけ、必要な同期を確認する
   ソースを直接実行した成功だけで実行時の成功と扱わない。Diagnostic Evidence Fidelityの条件が成立する場合は、Wrapperやcatchが必要な診断の根拠を失っていないか確認する
5. Verificationが完了したら、Statusを変更する前に論理的な `checkpoint` を **active Git executor** へ委譲し、対象Issueの変更だけを候補commitへ固定する。canonical `implementation-loop` の既定bindingはlocal Git executorで、従来どおり `git-add-commit-push checkpoint` を使用する。別entry pointがGit executorを差し替える場合も候補SHA、scope/provenance、non-force/no history rewrite、変更後の再取得確認に関する共通の取り決めを満たす。Checkpointが失敗・結果不明・scope混在の場合は `In Implementation Review` へ進めず、`Implementation` で停止する
6. Checkpoint後は後述の `state_key: implementation-completion` を現在の候補へ更新し、再取得確認後にStatusを `In Implementation Review` へ更新する。`Test required` はここで **Implementation Reviewを実行しない** ままHuman Acceptance待ちとする。`Test not required` はここから **Implementation Reviewを実行する** 独立Review待ちとする

## Implementation Completion / Acceptance state

`state_key: implementation-completion` の可変フェーズ状態をImplementation完了からAcceptanceまでの現在の永続状態として使います。stateが存在しない初回だけ新規Commentを作成し、そのComment IDを保持します。既存stateがある再Implementation、候補の改訂、Acceptance待ちでは同じComment IDを更新し、別のCompletion / Acceptance state Commentは追加しない・作成しない。

このstateは少なくともImplementation完了、`test_decision`、現在の `candidate_commit` / 候補SHA、候補branchまたはremote/ref到達状態、Automated Tests/Verification、CI Verification、検証境界、`unverified`、Remaining Local Acceptance、Remaining Human Acceptance、Acceptance state（pending / pass）を現在値として保持します。Human Acceptance対象は現在の候補SHAへbindingします。必要な過去のstate / 重要なイベントの参照はComment IDで保持します。

CIの根拠をAcceptanceに使う場合は候補SHAとCI対象SHAの一致を確認し、CI PASSだけでLocal/Human AcceptanceをPASS扱いしません。Local Acceptanceを別環境へ引き継ぐ場合は候補SHA、command/entry point、必要なenvironment/application、expected result、未確認理由を現在状態へ残します。送信先を区別しないglobalな `push済み` / `未push` だけを後続Closeの判断根拠にしません。Runtime path、diagnostic、contractに関する記録はそれぞれ該当する場合だけ含め、非該当Issueに `N/A` 項目を埋めるschemaを要求しません。`Current / Verified`、`Proposed / Target`、`Unverified` を混同せず、未実行をPASSと表現しません。

Human Acceptance PASSは`implementation-completion` stateのAcceptance stateを同じCommentへ更新します。Local Acceptance FAIL / Human Acceptance FAILは理由追跡が必要なため共通immutable eventとして新規Commentへ追記し、現在のフェーズ状態はそのイベントComment IDと再開条件を参照します。FAIL時は候補を保持して明示的な再開指示後に `Implementation` へ戻します。

`candidate_commit` はIssueの完了を意味せず、Human Acceptanceで確認する候補を識別します。canonical/local bindingで既存の未コミット変更が今回Issueの対象pathと混在して分離不能な場合は、hunk単位で推測せずcheckpointを実行しません。remote bindingではlocal worktreeや未コミット差分の存在を要求せず、candidate ref/treeの再取得確認で対象範囲を確認します。

候補の安全条件はactive Git bindingごとに維持します。local bindingでは `candidate_commit == current HEAD` をCloseまで維持し、対象pathにAcceptance後の未コミット差分がないことを確認します。remote bindingでは `candidate_commit == candidate ref` を維持し、Acceptance時に記録したcandidate ref/treeから変化していないことを再取得確認します。同一Repository・同一branch/refではHuman Acceptance待ち候補の後に別Issueで候補を進めません。Human Acceptance FAILで同じIssueを再Implementationする場合は旧候補を保持して新しい候補checkpointを積めます。最終CloseではClose先remote/refを先に確定し、Linear記録済みの同一Issue checkpoint chainのうち、そのtarget refからliveに到達不能なcheckpointだけを古い順に `allowed_checkpoint_shas` として渡します。別remote/refへ先行push済みでもClose先から未到達なら含め、Close先から既に到達可能なら除外し、outgoing commit chain全体との完全一致を確認してから公開します。

## `In Implementation Review`: durable substate

通常Issueではまず `implementation-completion` stateから `test_decision` と現在の候補 (`candidate_commit`) を再取得し、候補ref/treeと一致することを確認します。

### `Test required`: Human Acceptance待ち

`Test required` はImplementation Reviewを実行しません。`implementation-completion` stateのImplementation完了、Automated Tests/Verification、CI Verification、Remaining Local Acceptance、Remaining Human Acceptance、現在の候補SHAを人間が確認します。問題が見つかった場合は、明示的な再開指示を受けて `Implementation` へ戻し、修正・再検証します。問題がなければ、Human Acceptance PASSを同じstateへ更新したうえで、明示的なClose指示を受けて [close.md](close.md) に進みます。Human Acceptanceの完了だけで `Done` へ進めません。

### `Test not required`: Implementation Review待ち / Human Acceptance待ち

Implementation ReviewのReview Commentには、`issue`、`phase`=`Implementation Review`、`test_decision`=`Test not required`、`candidate_commit`、`review_targets`、`verification_evidence`、`decision`、`findings`、`blocker`を保存します。

`state_key: implementation-review` の可変フェーズ状態を現在の候補のレビュー資料 / Review Resultに使います。stateが存在しない初回だけ新規Commentを作成し、そのComment IDを保持します。既存の同じstateではレビュー資料、候補、検証の根拠、Review Resultを同じCommentへ更新し、別のImplementation Review state Commentは追加しない・作成しない。

`Test not required` では現在の候補に対する最新positive Implementation Reviewが存在するかで下位状態を判定します。

- 現在の候補にbindingされた `APPROVE` がない場合は独立Implementation Review待ち
- review対象候補SHA (`candidate_commit`) が現在の候補と一致する `implementation-review` stateの最新 `APPROVE` がある場合だけHuman Acceptance待ち
- 候補変更時は旧候補へbindingされた `APPROVE` は失効し、新しい候補のレビュー資料 / Resultへstateを更新して最新のReviewを行う

Implementation Reviewは成果物作成主体とは**独立**したread-only Reviewerが行います。成果物作成主体は同一実行コンテキストで承認判定または `APPROVE` を確定しない。Implementation Review開始時は **最新状態として** 現在の候補 (`candidate_commit`) を確認し、その後Linear Issue / Status / canonical Plan /全Comments / Labels / relationsとリポジトリの根拠、現在の候補に対するdiff/成果物、検証の根拠、未確認事項を再取得します。過去chatの説明や結論をReview根拠にしません。

Review責務はAcceptance Criteria、現在の候補のdiff/成果物、検証の根拠、未確認事項の独立確認に限定し、旧来の広範なコード品質Reviewを全面復活させません。Reviewは成果物修正へ越境しません。

`implementation-review` stateには最新の実行やCloseでレビュー資料を再構築できる最小限の永続metadataとして、`issue`、`phase`=`Implementation Review`、`test_decision`=`Test not required`、`candidate_commit`、`review_targets`（現在の候補のdiff/成果物）、`verification_evidence`、`unverified`、`decision`、`findings`、`blocker` を現在値として保持します。`review_targets` と `verification_evidence` はCanonical Review Resultの `review_context` に保持し、本文中の説明だけで代替しません。レビュー資料とReview Resultは同じCommentへ更新します。

Canonical decisionは次を使います。

- `APPROVE` → 指摘事項のない承認Reviewとして `implementation-review` stateを更新し、Statusは `In Implementation Review` のまま維持して現在の候補に紐付くHuman Acceptance待ちへ移る
- `CHANGES_REQUIRED` → 指摘事項を共通immutable eventへ追記し、現在状態を更新してStatusを `Implementation` へ戻して停止する
- `BLOCKED` → 具体的なblockerをimmutable eventへ追記し、現在状態を更新してStatusを維持して停止する

独立Reviewerを現在の実行から利用できない場合は、Reviewに必要な現在の候補 / diff /検証の根拠 /未確認事項を `implementation-review` stateから再構築できる状態にして `In Implementation Review` で永続的に停止し、別Chat等の独立実行へ引き継ぎます。

Human Acceptance待ちでは`implementation-completion` stateと現在の候補に紐付く `APPROVE` を確認します。問題が見つかった場合は、明示的な再開指示を受けて `Implementation` へ戻し、候補を更新して修正・再検証します。問題がなければ、Acceptance stateを更新して明示的なClose指示を受けて [close.md](close.md) に進みます。Human AcceptanceまたはImplementation Reviewの正判定だけで `Done` へ進めません。
