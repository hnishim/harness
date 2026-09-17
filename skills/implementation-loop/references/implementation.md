# Implementation / Acceptance

## Implementation

開始時にPlan、approval、Git候補、基準Harnessを再取得します。Test requiredでは `approved_tests_manifest` のpathsと各内容SHA-256をGit上で再計算し、承認版と完全一致することを確認します。不一致なら実装せずTest Review承認を失効させます。

実装ではapproved testsを変更対象から除外し、Planで承認された範囲だけを変更します。実装中に未承認の仕様変更が必要になった場合は継続せずPlanningへ戻します。

実装後は次を確認します。

- Planとの対応
- 変更パスと対象範囲
- approved testsが不変であること
- 実行可能な自動検証
- CI対象／候補SHA
- local-only検証とhuman acceptanceの未確認事項
- 実利用経路、仕様影響、診断、基準文書同期の成立項目

未実行の検証をPASSにしません。

## candidate checkpoint

検証後、現在のGit backendで候補checkpointを作成します。候補は受入確認対象を固定するだけで、Doneや既定ブランチ公開を意味しません。

deliveryへ少なくとも次を保存しreadbackします。

- baseline SHA
- candidate SHA / candidate ref
- 自動検証結果
- CI結果または未観測
- local acceptance: pending / pass
- human acceptance: pending / pass
- unverified
- close開始状態

candidate SHAが変わった場合は `workflow.toml` の失効規則を適用します。

## Implementation Review

normal + Test not requiredだけ独立Implementation Reviewを要求します。Reviewerは現在candidate SHA、差分、検証根拠、Planを最新状態から再取得し、`APPROVE` / `CHANGES_REQUIRED` / `BLOCKED` を判定します。

APPROVEはapprovalへ現在candidate SHAと結び付けて保存します。candidate変更で旧承認は失効します。

Test requiredではImplementation Reviewを行わず、実装完了判定を `workflow.toml` へ適用します。

## Awaiting Acceptance

このStatusは現在candidateに対するlocal / human acceptance待ちです。

- local-only検証を現在環境で実行できなければ、候補SHA、必要コマンド／実行入口、環境、期待結果、未確認理由をdeliveryへ残す
- CI PASSをlocal / human acceptance PASSへ昇格しない
- human acceptance PASSは現在candidate SHAへbindingする
- FAILは不変イベントへ理由を保存し、再開時にImplementationへ戻す

Human Acceptance PASSだけではDoneにしません。明示的close指示を受けた後 [close.md](close.md) を適用します。
