# Spike

Spikeでは、実装ではなく観測結果・再現手順・判断を主な成果物にできます。

## 異常時の診断

SpikeでDiagnosticへ切り替えるのは、調査がループする、観測が矛盾する、調査範囲が制御不能に広がる、次の識別実験を設計できない、または調査がSpikeの目的から逸脱した場合に限ります。仮説が外れたことや単一の実験失敗だけではDiagnosticへエスカレーションしません。

Diagnosticは観測事実、矛盾、可能性の高い原因区分、原因を区別する最小の実験1〜3件、処置を返します。処置は現行Planで続行、Planningへ戻す、外部またはHuman対応、判断不能に分類します。親エージェントは結果を既存 `workflow.toml[phase_return]` とnext actorの規則に対応付けます。この処理の原因または戻り先が確定しない場合はStatusを推測せず停止し、新しいLinear Statusを作りません。

## Plan

Planには仮説、観測対象、識別条件、終了条件、必要な証拠を記載します。不要な本番変更を混ぜません。

### Implementation中のPlan改訂

承認済みPlanの実質変更が必要になった場合は、汎用 `binding_returns` ではなく、`workflow.toml[phase_return.spike_plan_return]` の専用条件を使います。候補が存在しないことを既知のIssue branch/ref/worktree、基準コミット、現在HEAD、作業差分、Linearの追記専用履歴から確認し、Result Reviewが未実施であることを現在approvalと全レビュー履歴から確認できる場合だけ `Todo` へ戻します。`candidate_sha: null` や記録の不在だけでは許可しません。候補・由来・Result Review状態が不明、Result Review済み、または後続の有効な承認・検証・受入がある場合は `BLOCKED` とし、一般規則へfallbackしません。

この処理では専用表の対象だけを失効させ、旧値・PlanコメントID・旧hashと判断根拠を `PHASE_RETURN` イベントに保持します。Planコメント、過去レビュー、baseline、診断観測記録は残します。読み戻しで整合を確認するまでStatusを変えません。改訂した同じPlanコメントの新hashについて独立Plan Reviewと人間確認を終えた後に作業を再開します。この例外はResult Review／Closeの既存条件を変えません。

## Result

詳細結果は `artifact_key: result` を持つ、更新可能な1件のコメントに保存します。Result本文を正規化してSHA-256を計算し、approvalへ `current_result_hash` を保存します。

結果が変わった場合は `workflow.toml` の `spike_result_hash` 失効規則を適用し、以前のResult Reviewの承認を無効化します。

## Result Review

成果物を作成した実行とは独立した読み取り専用のレビュー担当が、最新Plan、result、証拠、対象リポジトリを再取得します。

判定は `DECISION_READY`/`CHANGES_REQUIRED`/`BLOCKED`。

DECISION_READYではapprovalへ次を保存します。

- `reviewed_result_hash = current_result_hash`
- Result Review判定

変更要求とBLOCKEDの理由は、追記専用の履歴に保存します。

## Closeの開始条件

Spikeをcloseできるのは、現在のresultのhashとレビュー済みのresultのhashが一致し、その版に結び付いた `DECISION_READY` が存在する場合だけです。不一致なら再レビューします。
