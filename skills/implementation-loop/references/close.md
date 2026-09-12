# Close

## Post-publish CI gate

CloseのCI判定はGit transportではなくcanonical Close semanticsです。local Git executor / remote Git executorのどちらでpublishしても同じ判定を使い、provider固有の取得方法だけをbinding側へ委ねます。この追加gateは通常Issueのaccepted candidate publishへ適用し、Spikeまたはcandidateを持たない公開には新しいCI必須条件を追加しません。

CIのrequirednessはtarget refのconfiguration/contractから判定し、実行結果の観測とは分離します。

- provider側のrequired checks / ruleset等でrequired CI identityを一意に特定できる場合はそれをrequirednessのSource of Truthとする
- provider側にrequired designationがない場合はrepository-owned explicit declarationだけをrequirednessのSource of Truthとして認める。Harnessでは `.github/implementation-loop-ci.yml` をexplicit declarationとして使う
- workflow fileが存在するだけではrequiredへ昇格させない
- required CI contractがなく、target refへ適用されるCI-like automationも存在しないことをconfiguration readbackで確認できた場合だけ `ci_applicability=none` とする
- CI-like automationは存在するがrequirednessを一意に決められない、declarationが矛盾する、configuration取得不能・権限不足の場合は `ci_applicability=unknown` としてsafe-stopする
- required CI identityとpublish trigger contextを一意に確定できる場合は `ci_applicability=required` とする

`ci_applicability=required` の場合、execution observationを別軸で `not_observed` / `queued` / `pending` / `in_progress` / `completed` / `observation_unknown` として記録します。matching publish-trigger runがまだ見えない場合も `ci_applicability=required` のまま `not_observed` とし、`none` / `unknown` へ変換しません。`required + not_observed` は `Done` 不可で、matching publish-trigger runが観測可能になることを再開条件とします。

GitHub Actionsをrequired CIとして使う場合、repository/provider contractで指定したworkflow identity/pathに加え、`event=push`、`head_branch == target branch/ref`、`head_sha == published_sha` をすべて一致させます。同じSHA・同じworkflowでも `pull_request` eventのsuccessはpost-publish `push` CIの代替にしない。別branch、別SHA、別workflow、別eventの結果も流用しません。

GitHub ActionsのPASSは `status=completed && conclusion=success` のみです。`queued` / `pending` / `in_progress` / `not_observed` は未完了、`failure` / `cancelled` / `timed_out` / `action_required` はfailure、`neutral` / `skipped` / `stale` / unknown conclusion / provider result unknownはPASSへ昇格させません。固定delayだけを成功条件にせず、matching publish-trigger runの出現またはstatus/conclusion変化を再開条件にします。

Close Commentには最低限、`published_sha`、target remote/ref、`ci_applicability`、requiredness根拠、required CI identity、publish trigger context、execution observation、CI対象SHA、status/conclusion、run/check URLまたは識別子、停止時の再開条件を保存します。`ci_applicability=none` の場合も判定根拠を保存し、実行statusが空という事実だけをno-CIの根拠にしません。

1. Issue ID、Description、Status、Labels、relations、全Commentsと現在のRepository evidenceをactive Git bindingに従って再取得する。canonical/local bindingではRepository/worktree/適用されるlocal instructions、remote bindingではrepository identity、default/candidate ref、baselineをreadbackする
2. 最新Plan Reviewの `APPROVE`、Issue／mode／profile／Test判定／`blockedBy` snapshot metadata、レビュー対象のPlan・成果物・差分が現在値と整合することを確認する。要求・scope・受入条件に影響する変更、対象・差分が不明、Commentがない、または結果不明ならStatusを維持する。`relatedTo`／`blocks`の変更だけでは承認を失効させない
3. 通常Issueは、Statusが `In Implementation Review` で保存された最新のImplementation完了・検証記録とHuman Acceptance確認点に加え、`candidate_commit`、push先remote/refごとの到達記録、対象SHAを確認する。送信先を区別しないglobalな `push済み` / `未push` をClose判定の根拠にしない。`Test required` では Implementation ReviewをClose条件にしない。`Test not required` では最新のImplementation Review Commentについて、review対象candidate SHA (`candidate_commit`) が current candidate と一致し、そのdecisionが `APPROVE` であることを確認する。candidate変更時は旧Implementation Reviewの `APPROVE` は失効し、新しいcurrent candidateへのfresh Reviewが必要である。current candidate-bound `APPROVE` がない場合はHuman Acceptance済みでもCloseへ進めない。Spikeは `In Implementation Review` の最新Result Reviewが `DECISION_READY` で、対象・証拠・判断基準に意味のある変更がないことを確認する
4. 現在の依頼内に明示的なClose指示があることを確認する。Reviewの正判定だけで `Done` へ進めない
5. 通常IssueでHuman AcceptanceがPASSの場合、candidate safetyをactive Git bindingに従って再確認する。local bindingではcandidate SHAがcurrent HEADと一致し、対象pathにAcceptance後の未コミット変更がないことを確認する。remote bindingではcandidate SHAがcandidate refと一致し、Acceptance時に記録したcandidate ref/treeから変化していないことをreadbackする。remote pathにlocal worktreeや未コミット差分の存在を要求しない。Close先remote/refを確定し、Linearへ記録・readback済みの当該Issue checkpoint chainについて、そのtarget refからのlive reachabilityを確認する。target refから到達不能なcheckpointだけを古い順に並べ、今回の公開を許可する `allowed_checkpoint_shas` とする。別remote/refへ先行push済みでもClose先target refから未到達なら含め、target refから既に到達可能なら含めない。target candidate SHA、送信先とともにlogical `publish checkpoint` を **active Git executor** へ委譲する。canonical `implementation-loop` の既定bindingはlocal Git executorで、従来どおり `git-add-commit-push publish-checkpoint` を使用する。別entry pointがGit executorを差し替える場合も、target refからcandidateまでのprovenance、non-force fast-forward、candidate SHA保持、mutation後readbackを満たし、新しいcommitを作成しない。対象Issue外・由来不明・未承認commit、許可列の不足・余剰・順序不整合、候補SHA不一致、未確認差分、remote先行/分岐、publish失敗・結果不明では `Done` に進めない。Human AcceptanceがFAILならcandidateを保持して明示的な再開境界へ戻し、公開やDone化を行わない
6. Close時にAcceptance未実施の差分が残っている場合は、それを暗黙にcommitしない。Statusを `Implementation` または現行の再開境界へ戻して停止する
7. [case-signals.md](case-signals.md) の共通カタログを完全一致で参照し、Close時Case振り返りを一度実行する。単一シグナルに明確に一致し、必須証拠が揃った事象ごとに、次のlogical payloadを作成し、`add-case`へ渡す。CloseはNotion DB URL、data source、物理Property名、Relation、Page IDをpayloadへ含めない。

   | field | meaning / requiredness | Close value or rule |
   | --- | --- | --- |
   | `producer` | producer識別子。必須 | `implementation-loop` 固定 |
   | `case_name` | [case-signals.md](case-signals.md)の正式な単一シグナル。必須 | 完全一致。未知・複数候補ならpayloadを作成しない |
   | `subject` / `summary` / `occurred_at` | 事象の対象・要約・発生時点。すべて必須 | 確定した証拠から設定 |
   | `context` | 補足証拠。任意 | 証拠がある場合だけ設定 |
   | `case_intent` | 新規作成または既存Case再利用を制御。必須 | `new` 固定 |
   | `human_reindication` | Human feedback加算分岐を制御。必須 | `false` 固定 |

   必須証拠が不足・未知・複数候補の場合はpayloadを作成せず、現行Close停止／継続境界に従う。`add-case`はlogical payloadをNotion物理schemaへ境界写像し、schema readback、既存Case照合、保存後readbackを所有する。
8. 単一シグナルに明確に一致した後で必須証拠またはpayloadのtrigger contractが未確定、`add-case`保存またはreadbackが失敗・不明の場合はCase境界で停止し、成功済みcore作業をrollback・再実行せず、Git公開へ進めない。同一Closeの再実行は同一payloadで既存Case照合・再利用へ委ねる
9. `add-case`成功後、対象scopeをRepository単位に分け、各Repositoryごとにactive Git executorへ対象範囲とクローズ指示を渡して委譲する。通常Issueは前項のtarget candidate SHA、target remote/ref、target ref基準の `allowed_checkpoint_shas` を渡した `publish checkpoint`、Spikeまたはcandidateを持たない公開は既存の公開契約に従う。Policy生成・Relation設定・Feedback Count加算・Review完了はこの振り返りで行わない
10. 通常Issueでは、全Repositoryでactive Git executorが成功、または送信すべき変更なしを確認した後、各target refをreadbackして `published_sha` を確定する。各RepositoryについてPost-publish CI gateを評価し、`ci_applicability=required` ならmatching publish-trigger CIがPASSした場合だけClose継続、`ci_applicability=none` ならCI execution gateをskip、`ci_applicability=unknown` またはexecution observationが未完了・failure・不明ならCI evidenceと再開条件をCommentへ保存してStatusを維持する。Spikeまたはcandidateを持たない公開はこの追加gateを適用せず既存Close条件へ進む
11. 通常Issueは全RepositoryでGit処理が成功し、かつPost-publish CI gateが `required + PASS` または `none` であることを確認できた場合だけ `Done` へ更新する。Spikeは既存のGit/Case/Review条件を満たした場合だけ `Done` へ更新する
12. いずれかのCase処理・Git処理・通常IssueのPost-publish CI処理の失敗・結果不明・Issueまたは必要なReview/Acceptance記録の不一致ではStatusを維持する
13. `Done` 更新後に再取得確認する

Git操作の共通安全条件は `../SKILL.md` のlogical Git contractをSource of Truthとし、canonical/local bindingのworking tree、staging、commit、remote選択、push詳細は `git-add-commit-push` をSource of Truthとします。remote binding固有のGitHub API / connector semanticsはadapter側が所有します。
