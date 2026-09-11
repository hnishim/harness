# Close

1. Issue ID、Description、Status、Labels、relations、全Commentsと、現在のRepository/worktreeを再取得する
2. 最新Plan Reviewの `APPROVE`、Issue／mode／profile／Test判定／`blockedBy` snapshot metadata、レビュー対象のPlan・成果物・差分が現在値と整合することを確認する。要求・scope・受入条件に影響する変更、対象・差分が不明、Commentがない、または結果不明ならStatusを維持する。`relatedTo`／`blocks`の変更だけでは承認を失効させない
3. 通常Issueは、Statusが `In Implementation Review` で保存された最新のImplementation完了・検証記録とHuman Acceptance確認点に加え、`candidate_commit`、push先remote/refごとの到達記録、対象SHAを確認する。送信先を区別しないglobalな `push済み` / `未push` をClose判定の根拠にしない。AIの独立ReviewのPASSを前提にしない。Spikeは `In Implementation Review` の最新Result Reviewが `DECISION_READY` で、対象・証拠・判断基準に意味のある変更がないことを確認する
4. 現在の依頼内に明示的なClose指示があることを確認する。Reviewの正判定だけで `Done` へ進めない
5. 通常IssueでHuman AcceptanceがPASSの場合、candidate SHAが現在の対象HEADと一致し、対象pathにAcceptance後の未コミット変更がないことを確認する。Close先remote/refを確定し、Linearへ記録・readback済みの当該Issue checkpoint chainについて、そのtarget refからのlive reachabilityを確認する。target refから到達不能なcheckpointだけを古い順に並べ、今回の公開を許可する `allowed_checkpoint_shas` とする。別remote/refへ先行push済みでもClose先target refから未到達なら含め、target refから既に到達可能なら含めない。target candidate SHA、送信先とともにlogical `publish checkpoint` を **active Git executor** へ委譲する。canonical `implementation-loop` の既定bindingはlocal Git executorで、従来どおり `git-add-commit-push publish-checkpoint` を使用する。別entry pointがGit executorを差し替える場合も、target refからcandidateまでのprovenance、non-force fast-forward、candidate SHA保持、mutation後readbackを満たし、新しいcommitを作成しない。対象Issue外・由来不明・未承認commit、許可列の不足・余剰・順序不整合、候補SHA不一致、未確認差分、remote先行/分岐、publish失敗・結果不明では `Done` に進めない。Human AcceptanceがFAILならcandidateを保持して明示的な再開境界へ戻し、公開やDone化を行わない
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
10. 全Repositoryでactive Git executorが成功、または送信すべき変更なしを確認できた場合だけ `Done` へ更新する
11. いずれかのCase処理・Git処理の失敗・結果不明・Issueまたは必要なReview/Acceptance記録の不一致ではStatusを維持する
12. `Done` 更新後に再取得確認する

Git操作の共通安全条件は `../SKILL.md` のlogical Git contractをSource of Truthとし、canonical/local bindingのworking tree、staging、commit、remote選択、push詳細は `git-add-commit-push` をSource of Truthとします。remote binding固有のGitHub API / connector semanticsはadapter側が所有します。
