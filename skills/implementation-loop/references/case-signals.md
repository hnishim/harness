# Close Case signal catalog

Close時のCase振り返りで参照する初期の共通カタログです。CloseはIssue固有の候補を再定義せず、このカタログとの完全一致で判定します。

## 初期カタログ

### `user_correction`

ユーザーがworkflowの行動またはルールの修正を明示した事象です。確認、承認、仕様のclarification、単なる質問は含めません。

判定条件は、ユーザー発言から修正前後のworkflowの行動またはルールと、その発生時刻を確認できることです。非該当条件は、確認、承認、仕様のclarification、単なる質問です。

必須証拠は、ユーザー発言、発生時刻、修正前後の行動またはルールです。

Logical payloadでは `case_name=user_correction` とし、Subject、Summary、Occurred At、Contextはこの証拠から構成します。

### `external_operation_failure`

外部書込みの失敗、結果不明、誤対象、意図しない副作用、外部操作を起因とするBLOCKEDです。通常の人間確認待ち、通常のTest失敗、内部phase停止は含めません。

判定条件は、外部操作の対象と、失敗・結果不明・誤対象・意図しない副作用または外部操作起因のBLOCKEDを確認できることです。非該当条件は、通常の人間確認待ち、通常のTest失敗、内部phase停止です。

必須証拠は、操作対象、エラーまたは結果不明の事実、readbackまたは停止記録です。

Logical payloadでは `case_name=external_operation_failure` とし、Subject、Summary、Occurred At、Contextはこの証拠から構成します。

### `workflow_contract_violation`

未修正状態を修正済みと報告した事象、誤ったStatus遷移、必須ゲートのスキップ、未承認scope変更です。Reviewerの通常の修正要求は含めません。

判定条件は、期待状態と実際の状態の差分、および未修正状態の修正済み報告、誤ったStatus遷移、必須ゲートのスキップまたは未承認scope変更を確認できることです。非該当条件は、Reviewerの通常の修正要求です。

必須証拠は、期待状態、実際の状態、Status履歴・Comment・Git差分です。

Logical payloadでは `case_name=workflow_contract_violation` とし、Subject、Summary、Occurred At、Contextはこの証拠から構成します。

## 判定境界

- Reviewerの指摘、採用、修正そのものはCase候補にしません。採用変更が別途このカタログの `workflow_contract_violation` に明確に一致する場合だけ、そのworkflow事実を候補にします
- 1つの発生が複数シグナルに見える場合は優先順位を付けず、判定不能としてCase化しません
- 単一シグナルに明確に一致して必須証拠が不足する場合だけ、Case境界でBLOCKEDにします
- カタログ外、未知、または候補なしはpayloadを作成せず、`add-case` を呼び出さずに通常Closeを継続します
- カタログの変更は既存シグナルの意味変更・削除を含めず、新規追加だけを明示的に承認されたPlanで行います。変更公開後のCloseから適用し、既存Issue/Caseへ遡及しません
