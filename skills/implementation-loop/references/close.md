# Close

## Close entry / resume boundary

Closeは、初回Close entryと開始済みCloseのresumeを別経路として扱います。Close stateが存在しないことだけを理由にstateを作成してはいけません。まずIssue、Description、Status、Labels、relations、全Comments、canonical Plan、Review / Acceptance state、current candidate、active Git bindingのRepository evidenceをfresh readbackし、現在のClose経路を判定します。

- 有効な開始済みClose stateが存在しない場合だけ初回Close entryとして扱う
- 既存Close stateがある場合は、そのstateが初回entry gate通過後に作成された開始済みstateであることをdurable metadataと参照先のfresh readbackから確認できる場合だけresumeとして扱う
- `entry_gate: passed` / `close_started: true` 等の開始済みmetadataが欠けるlegacy／誤作成state、参照先やaccepted candidateとの整合を確認できないstateは、resumeやClose許可の根拠にしない。既存stateを更新しない。新しいClose stateも追加作成しないままBLOCKEDで停止する

### 初回Close entry

初回entryでは、Close stateを初回作成する**前**に次をすべて確認します。

1. 最新Plan Reviewが `APPROVE` で、Issue／mode／profile／Test判定／`blockedBy` snapshot、レビュー対象のPlan・成果物・差分が現在値と整合する
2. 通常IssueはStatusが `Awaiting Acceptance` で、最新 `implementation-completion` stateのImplementation完了、検証記録、Human AcceptanceがPASS、`candidate_commit` / candidate SHA、candidate branchまたはremote/ref到達状態が現在値と一致する。`Test required` ではImplementation ReviewをClose条件にしない。`Test not required` では最新のImplementation Reviewについて、review対象candidate SHA (`candidate_commit`) が current candidate と一致し、そのdecisionが `APPROVE` であることを必須とする。candidate変更時は、旧candidateにbindingされた過去の `APPROVE` は失効する。Spikeは最新 `spike-result` stateのResult Reviewが `DECISION_READY` であることを確認する
3. Plan／scope／Acceptance条件、current candidate、必要なReview / Acceptance evidenceに不整合・不明・未完了がない
4. **現在の依頼内に新しい明示的Close指示がある**

いずれかが未達・不整合・不明なら `BLOCKED` で停止します。この初回entry未達ではClose stateを作成しない・更新しない。明示的Close指示・Close許可もdurable stateへ保存しません。必要なblocker evidenceをimmutable eventへ残す場合も、拒否済みClose指示そのものを将来の許可として保存・再掲しません。後続実行で前提条件が満たされても、**拒否済み／過去のClose指示を再利用しない**。前提条件が揃った後の**新しい明示的Close指示**を改めて要求します。

初回entry gateをすべて通過した場合だけClose phaseを開始し、Close stateを**初回作成**します。初回stateには少なくとも `entry_gate: passed`、`close_started: true`、accepted candidateまたはSpike Resultへの参照、受理した現在のClose指示を識別できるmetadataを保存し、保存後に同じCommentをfresh readbackしてから後続処理へ進みます。

### 開始済みCloseのresume

開始済みCloseのresumeでは、既存Close stateをfresh readbackし、`entry_gate: passed` / `close_started: true` とaccepted candidateまたはSpike Resultへの参照が現在値と整合することを確認します。有効な開始済みstateと確認できた場合は、現在の依頼に新しい明示的Close指示を**再要求しない**。Notion保存失敗、GitHub操作失敗、CI待ち等の停止点から、同じClose state Comment IDを更新して再開します。

開始済みと確認できないlegacy／誤作成state、entry通過済みmetadataや参照整合を確認できないstateは、resume・Close許可の根拠にせず更新しません。

## Close state

`state_key: close` のmutable phase stateは、初回Close entry gate通過後のClose開始からDone直前までのcurrent durable stateとして使います。stateが存在しない初回entryでgateを通過した場合だけ新規Commentを作成してstable Comment IDを保持します。有効な開始済みstateではpre-publish、publish結果、CI待ち、Case処理、final Statusを同じCommentへupdateし、別のClose state Commentは追加しない・作成しない。

Close stateはCompletion / Result / Acceptance本文を再掲せず、通常Issueではaccepted `candidate_commit` / accepted candidate SHA、`implementation-completion` state Comment ID、必要なら`implementation-review` state Comment ID、Spikeでは`spike-result` state Comment IDとDecision event Comment IDを参照します。初回entry通過済みを識別するdurable metadataとして `entry_gate: passed`、`close_started: true`、受理したClose指示の識別情報を保持します。Close固有のcurrent deltaとして、target remote/ref、`published_sha`、allowed checkpoint provenance、Case処理、`ci_applicability`、required CI identity、publish trigger context、execution observation、CI対象SHA、status/conclusion、run/check URLまたは識別子、`unverified`、停止時の再開条件、final Statusを保持します。

CIが `not_observed` / `queued` / `pending` / `in_progress` 等で待機する場合は、pre-publishやCI待ち専用の新規Commentを増やさず、**同じ close Commentを更新**してcurrent observationと再開条件を保存します。再開時もfresh readback後に同じ `state_key: close` Commentをupdateします。

## Post-publish CI gate

CloseのCI判定はGit transportではなくcanonical Close semanticsです。local Git executor / remote Git executorのどちらでpublishしても同じ判定を使い、provider固有の取得方法だけをbinding側へ委ねます。この追加gateは通常Issueのaccepted candidate publishへ適用し、Spikeまたはcandidateを持たない公開には新しいCI必須条件を追加しません。

CIのrequirednessはtarget refのconfiguration/contractから判定し、execution observationとは分離します。

### Requiredness

provider側のrequired checks / ruleset等を最優先でreadbackし、一意なrequired CI identityがあればprovider設定をrequirednessのSource of Truthとします。provider required configurationが取得不能・readback不能でrequired designationなしと証明できない場合は、requiredなしと推測しないで `ci_applicability=unknown` としてsafe-stopします。provider readbackでrequired designationがないことを確認できた場合だけ、target ref上のrepository-owned `.github/workflows/*.yml` / `.github/workflows/*.yaml` をworkflow discoveryします。

各workflowは、version管理され、`push` eventがtarget branch/refへ適用され、published SHAへrunをbindingできることを確認します。複雑なtriggerまたはtarget refへの適用を一意に判定できない場合は `ci_applicability=unknown` とします。`paths` / `paths-ignore` によりpublished changeへの適用が判定不能な場合もautomatic判定を行わず `ci_applicability=unknown` とします。

workflow `name` または filename stem を正規化し、validation用途のpositive token `ci`, `test`, `tests`, `check`, `checks`, `validate`, `validation`, `verify`, `verification`, `lint` と、非validation用途のnegative token `release`, `deploy`, `deployment`, `publish`, `publishing`, `docs`, `documentation`, `maintenance`, `cleanup`, `sync` で分類します。positive tokenだけならautomatic validation candidate、negative tokenだけなら明確なnon-validationです。positive / negativeが混在する、またはどちらにも分類できない場合はambiguousとして `ci_applicability=unknown` とします。

Namingだけで分類できない例外はworkflow自身のco-located override `# implementation-loop-ci: validation` / `# implementation-loop-ci: ignore` で指定できます。overrideは `push` がtarget refへ適用される条件を満たさなければrequiredへ昇格できません。override metadataが重複する場合は `ci_applicability=unknown`、override metadataが競合する場合は `ci_applicability=unknown`、override metadataに未知の値 / unknown valueがある場合は `ci_applicability=unknown` とします。

automatic validation candidateが1件以上あり、ambiguousがない場合はvalidation candidate全体をrequired setとして `ci_applicability=required` とします。target refへapplicableなworkflowが存在しない場合、またはapplicable workflowが明確なnon-validationのみで、CI-like automationが存在しないことをconfiguration readbackできた場合は `ci_applicability=none` とします。CI-like automationが存在するがrequirednessを確定できない場合は `ci_applicability=unknown` とします。

`ci_applicability=required` の場合、execution observationを別軸で `not_observed` / `queued` / `pending` / `in_progress` / `completed` / `observation_unknown` として記録します。matching publish-trigger runがまだ見えない場合も `ci_applicability=required` のまま `not_observed` とし、`none` / `unknown` へ変換しません。`required + not_observed` は `Done` 不可で、matching publish-trigger runが観測可能になることを再開条件とします。

GitHub Actionsをrequired CIとして使う場合、required setの各workflow identity/pathに加え、`event=push`、`head_branch == target branch/ref`、`head_sha == published_sha` をすべて一致させます。同じSHA・同じworkflowでも `pull_request` eventのsuccessはpost-publish `push` CIの代替にしない。別branch、別SHA、別workflow、別eventの結果も流用しません。

GitHub ActionsのPASSは `status=completed && conclusion=success` のみです。`queued` / `pending` / `in_progress` / `not_observed` は未完了、`failure` / `cancelled` / `timed_out` / `action_required` はfailure、`neutral` / `skipped` / `stale` / unknown conclusion / provider result unknownはPASSへ昇格させません。固定delayだけを成功条件にせず、matching publish-trigger runの出現またはstatus/conclusion変化を再開条件にします。

Close stateには最低限、`published_sha`、target remote/ref、`ci_applicability`、requiredness根拠、required CI identity、publish trigger context、execution observation、CI対象SHA、status/conclusion、run/check URLまたは識別子、停止時の再開条件を保存します。`ci_applicability=none` の場合も判定根拠を保存し、実行statusが空という事実だけをno-CIの根拠にしません。

## Close procedure

1. [Close entry / resume boundary](#close-entry--resume-boundary) に従ってfresh readbackを行い、初回entryまたは有効な開始済みresumeを一意に判定する。初回entry未達、legacy／誤作成state、開始済みstateの整合不明ではClose stateを作成しない・更新しないまま停止する
2. 初回entryではgate通過後に作成したClose state、resumeではfresh readbackした有効な開始済みClose stateについて、最新Plan Review、Implementation / Result、Acceptance、candidateまたはSpike Resultの参照が現在値と整合することを再確認する。`relatedTo`／`blocks`の変更だけでは承認を失効させない
3. 通常IssueでHuman AcceptanceがPASSの場合、candidate safetyをactive Git bindingに従って再確認する。local bindingではcandidate SHAがcurrent HEADと一致し、対象pathにAcceptance後の未コミット変更がないことを確認する。remote bindingではcandidate SHAがcandidate refと一致し、Acceptance時に記録したcandidate ref/treeから変化していないことをreadbackする。remote pathにlocal worktreeや未コミット差分の存在を要求しない。Close先remote/refを確定し、Linearへ記録・readback済みの当該Issue checkpoint chainについて、そのtarget refからのlive reachabilityを確認する。target refから到達不能なcheckpointだけを古い順に並べ、今回の公開を許可する `allowed_checkpoint_shas` とする。別remote/refへ先行push済みでもClose先target refから未到達なら含め、Close先target refから既に到達可能なら含めない。target candidate SHA、送信先とともにlogical `publish checkpoint` を **active Git executor** へ委譲する。canonical `implementation-loop` の既定bindingはlocal Git executorで、従来どおり `git-add-commit-push publish-checkpoint` を使用する。別entry pointがGit executorを差し替える場合も、target refからcandidateまでのprovenance、non-force fast-forward、candidate SHA保持、mutation後readbackを満たし、新しいcommitを作成しない。対象Issue外・由来不明・未承認commit、許可列の不足・余剰・順序不整合、候補SHA不一致、未確認差分、remote先行/分岐、publish失敗・結果不明では `Done` に進めない。Human AcceptanceがFAILならcandidateを保持して明示的な再開境界へ戻し、公開やDone化を行わない
4. Close時にAcceptance未実施の差分が残っている場合は、それを暗黙にcommitしない。Statusを `Implementation` または現行の再開境界へ戻して停止する
5. [case-signals.md](case-signals.md) の共通カタログを完全一致で参照し、Close時Case振り返りを一度実行する。単一シグナルに明確に一致し、必須証拠が揃った事象ごとに、次のlogical payloadを作成し、`add-case`へ渡す。CloseはNotion DB URL、data source、物理Property名、Relation、Page IDをpayloadへ含めない。

   | field | meaning / requiredness | Close value or rule |
   | --- | --- | --- |
   | `producer` | producer識別子。必須 | `implementation-loop` 固定 |
   | `case_name` | [case-signals.md](case-signals.md)の正式な単一シグナル。必須 | 完全一致。未知・複数候補ならpayloadを作成しない |
   | `subject` / `summary` / `occurred_at` | 事象の対象・要約・発生時点。すべて必須 | 確定した証拠から設定 |
   | `context` | 補足証拠。任意 | 証拠がある場合だけ設定 |
   | `case_intent` | 新規作成または既存Case再利用を制御。必須 | `new` 固定 |
   | `human_reindication` | Human feedback加算分岐を制御。必須 | `false` 固定 |

   必須証拠が不足・未知・複数候補の場合はpayloadを作成せず、現行Close停止／継続境界に従う。`add-case`はlogical payloadをNotion物理schemaへ境界写像し、schema readback、既存Case照合、保存後readbackを所有する。
6. 単一シグナルに明確に一致した後で必須証拠またはpayloadのtrigger contractが未確定、`add-case`保存またはreadbackが失敗・不明の場合はCase境界で停止し、成功済みcore作業をrollback・再実行せず、Git公開へ進めない。同一Closeの再実行は同一payloadで既存Case照合・再利用へ委ねる
7. `add-case`成功後、対象scopeをRepository単位に分け、各Repositoryごとにactive Git executorへ対象範囲とクローズ指示を渡して委譲する。通常Issueは前項のtarget candidate SHA、target remote/ref、target ref基準の `allowed_checkpoint_shas` を渡した `publish checkpoint`、Spikeまたはcandidateを持たない公開は既存の公開契約に従う。Policy生成・Relation設定・Feedback Count加算・Review完了はこの振り返りで行わない
8. 通常Issueでは、全Repositoryでactive Git executorが成功、または送信すべき変更なしを確認した後、各target refをreadbackして `published_sha` を確定する。各RepositoryについてPost-publish CI gateを評価し、`ci_applicability=required` ならmatching publish-trigger CIがPASSした場合だけClose継続、`ci_applicability=none` ならCI execution gateをskip、`ci_applicability=unknown` またはexecution observationが未完了・failure・不明ならCI evidenceと再開条件を同じ `close` stateへ更新してStatusを維持する。Spikeまたはcandidateを持たない公開はこの追加gateを適用せず既存Close条件へ進む
9. 通常Issueは全RepositoryでGit処理が成功し、かつPost-publish CI gateが `required + PASS` または `none` であることを確認できた場合だけ `close` stateのfinal Statusを更新して `Done` へ更新する。Spikeは既存のGit/Case/Review条件を満たした場合だけ `Done` へ更新する
10. いずれかのCase処理・Git処理・通常IssueのPost-publish CI処理の失敗・結果不明・Issueまたは必要なReview/Acceptance記録の不一致ではStatusを維持し、current evidenceと再開条件を同じ `close` stateへ更新する
11. `Done` 更新後にIssueと `close` stateを再取得確認する

Git操作の共通安全条件は `../SKILL.md` のlogical Git contractをSource of Truthとし、canonical/local bindingのworking tree、staging、commit、remote選択、push詳細は `git-add-commit-push` をSource of Truthとします。remote binding固有のGitHub API / connector semanticsはadapter側が所有します。
