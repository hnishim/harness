# Spike

Spikeは実装候補ではなく、観測・再現手順・判断を主成果物にできます。

## Plan

Planには仮説、観測対象、識別条件、終了条件、必要な証拠を記載します。不要な本番変更を混ぜません。

## result

詳細結果は `artifact_key: result` の単一可変コメントへ保存します。result本文を正規化してSHA-256を計算し、approvalへ `current_result_hash` を保存します。

結果が変わった場合は `workflow.toml` の `spike_result_hash` 失効規則を適用し、旧Result Reviewを無効化します。

## Result Review

成果物作成主体とは独立した読み取り専用Reviewerが、最新Plan、result、証拠、対象リポジトリを再取得します。

判定は `DECISION_READY` / `CHANGES_REQUIRED` / `BLOCKED`。

DECISION_READYではapprovalへ次を保存します。

- `reviewed_result_hash = current_result_hash`
- Result Review判定

変更要求とBLOCKEDは不変イベントへ保存します。

## close条件

Spikeをcloseできるのは、現在result hashとreviewed result hashが一致し、その版に結び付いた `DECISION_READY` が存在する場合だけです。不一致なら再レビューします。
