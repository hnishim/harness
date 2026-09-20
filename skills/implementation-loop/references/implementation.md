# Implementation / Acceptance

## Implementation

開始時にPlan、approval、Git候補、基準Harnessを再取得します。Test requiredでは `approved_tests_manifest` のpathsと各内容SHA-256をGit上で再計算し、承認版と完全一致することを確認します。不一致なら実装せずTest Review承認を失効させます。

実装ではapproved testsを変更対象から除外し、Planで承認された範囲だけを変更します。実装中に未承認の仕様変更が必要になった場合は継続せず、証跡と現bindingに基づき受理済み `workflow.toml[phase_return]` でPlanningへの差戻しを判断します。原因と戻り先が確定しない場合はStatusを推測して変更しません。

実装後は次を確認します。

- Planとの対応
- 変更パスと対象範囲
- approved testsが不変であること
- 実行可能な自動検証
- CI対象／候補SHA
- local-only検証とhuman acceptanceの未確認事項
- 実利用経路、仕様影響、診断、基準文書同期の成立項目

未実行の検証をPASSにしません。

## 汎用的な前フェーズへの差戻し

通常の完了・Acceptance・Close判断に先立ち、差戻しの必要性と既存Review/Acceptanceの専用遷移で扱えるかを評価します。汎用差戻しは未完了normal/bugの `workflow.toml[phase_return]` が認める元Statusと前方ではない戻り先に限定します。レビューStatusからの差戻しは既存のレビュー判定を適用し、Doneやclose開始済みの公開を伴う状態は本契約で巻き戻しません。

テスト欠陥・Plan変更・本体欠陥を混同せず、CIログ、期待値、実装・外部模擬境界、承認Plan hash、テストmanifest／ファイルhash、candidate SHAと許可済みcheckpoint履歴で原因・影響範囲を確認します。根拠不足、Plan変更の要否不明、binding矛盾、Git候補の由来不明、必要能力不足なら停止します。正常な承認と影響しない成果物・candidate ref／履歴を保持し、対象のPlan Review、Test Review、Implementation Review、CI、local/human acceptanceだけをTOMLの失効規則により無効化します。状態を戻した事実から旧承認を復活させません。

一意な差戻しID、元Statusと対象Status、理由・証跡、現Plan/test manifest/candidate SHA、失効・保持する対象、再レビューと再検証の要求を不変イベントへ記録します。既存approvalとdeliveryを同一IDと版bindingで更新し、両者とイベントを再取得して整合を確認してからのみStatusを更新します。途中書込みからは既存イベントを再利用して不足分だけ継続し、二重イベント、矛盾するID・版、必要な失効の未反映を検出したら停止します。差戻し先では通常のPlan Review／Test Review／Implementationのゲートを改めて適用し、実装の影響しない部分は現在の承認と照合して再利用します。candidate SHAが変われば旧CIと受入結果を新版のPASSにしません。

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
