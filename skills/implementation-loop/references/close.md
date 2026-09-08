# Close

1. Issue ID、Description、Status、Labels、relations、全Commentsと、現在のRepository/worktreeを再取得する
2. 最新Plan Reviewの `APPROVE`、Issue／mode／profile／Test判定／`blockedBy` snapshot metadata、レビュー対象のPlan・成果物・差分が現在値と整合することを確認する。要求・scope・受入条件に影響する変更、対象・差分が不明、Commentがない、または結果不明ならStatusを維持する。`relatedTo`／`blocks`の変更だけでは承認を失効させない
3. 通常Issueは、Statusが `In Implementation Review` で保存された最新のImplementation完了・検証記録とHuman Acceptance確認点を確認する。AIの独立ReviewのPASSを前提にしない。Spikeは `In Implementation Review` の最新Result Reviewが `DECISION_READY` で、対象・証拠・判断基準に意味のある変更がないことを確認する
4. 現在の依頼内に明示的なClose指示があることを確認する。Reviewの正判定だけで `Done` へ進めない
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
7. `add-case`成功後、対象scopeをRepository単位に分け、各Repositoryごとに `git-add-commit-push` へ対象範囲とクローズ指示を渡して委譲する。Policy生成・Relation設定・Feedback Count加算・Review完了はこの振り返りで行わない
8. 全RepositoryでGit Skillが成功、または送信すべき変更なしを確認できた場合だけ `Done` へ更新する
9. いずれかのCase処理・Git処理の失敗・結果不明・Issueまたは必要なReview/Acceptance記録の不一致ではStatusを維持する
10. `Done` 更新後に再取得確認する

Git操作の安全条件、staging、commit、remote選択、push、push後検証は `git-add-commit-push` をSource of Truthとします。
