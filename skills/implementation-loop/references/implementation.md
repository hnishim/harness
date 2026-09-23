# Implementation / Acceptance

## Implementation

開始時にPlan、approval、Gitの候補コミット、現在有効な受入済みHarnessを再取得します。Test requiredでは `approved_tests_manifest` のpathsと各内容SHA-256をGit上で再計算し、承認版と完全一致することを確認します。不一致なら実装せずTest Review承認を失効させます。

実装ではapproved testsを変更対象から除外し、Planで承認された範囲だけを変更します。実装中に未承認の仕様変更が必要になった場合は継続せず、確認結果と現在の承認・対象の版の対応に基づき受理済み `workflow.toml[phase_return]` でPlanningへの差戻しを判断します。原因と戻り先が確定しない場合はStatusを推測して変更しません。

実装後は次を確認します。

- Planとの対応
- 変更パスと対象範囲
- Approved testsが不変であること
- 実行可能な自動検証
- CIで検証したコミットと今回の候補コミットのSHA
- ローカル環境でしかできない検証と人間による受入確認で未確認の事項
- 実際に利用する手順・呼び出し経路、仕様への影響、原因の調査、関連する基準文書の更新について、Planで必要とされた項目

未実行の検証をPASSにしません。

## 前の作業工程へ戻す共通手順

通常の完了・Acceptance・Close判断に先立ち、差戻しの必要性と既存Review/Acceptanceの専用遷移で扱えるかを評価します。汎用差戻しは未完了normal/bugの `workflow.toml[phase_return]` が認める元Statusと前方ではない戻り先に限定します。レビューStatusからの差戻しは既存のレビュー判定を適用し、Doneやclose開始済みの公開を伴う状態は本契約で巻き戻しません。

テスト欠陥・Plan変更・本体欠陥を混同せず、CIログ、期待値、実装・外部模擬境界、承認Plan hash、テストmanifest／ファイルhash、candidate SHAと許可済みcheckpoint履歴で原因・影響範囲を確認します。根拠が不足する場合、Planの変更が必要か判断できない場合、承認と対象の版が一致しない場合、Git候補の作成元・変更履歴を確認できない場合、必要な操作・確認を実行できない場合は停止します。正常な承認と影響しない成果物・candidate ref／履歴を保持し、対象のPlan Review、Test Review、Implementation Review、CI、local/human acceptanceだけをTOMLの失効規則により無効化します。状態を戻した事実から旧承認を復活させません。

一意な差戻しID、元Statusと対象Status、理由・証跡、現Plan/test manifest/candidate SHA、失効・保持する対象、再レビューと再検証の要求を不変イベントへ記録します。既存approvalとdeliveryを同一IDと版bindingで更新し、両者とイベントを再取得して整合を確認してからのみStatusを更新します。途中書込みからは既存イベントを再利用して不足分だけ継続し、二重イベント、矛盾するID・版、必要な失効の未反映を検出したら停止します。差戻し先では通常のPlan Review／Test Review／Implementationのゲートをあらためて適用し、実装の影響しない部分は現在の承認と照合して再利用します。Candidate SHAが変われば旧CIと受入結果を新版のPASSにしません。

## 候補コミットの保存

検証後、対象Issue専用の作業ブランチに候補コミットを作成します。ローカルでは他の作業を妨げないworktree／作業領域を使い、remote-only環境では同じGitHub candidate refを使います。公開先を未受入候補にせず、候補コミットの保存は受入確認の対象を確定する操作であり、Doneへの変更やデフォルトブランチへの公開ではありません。

deliveryに少なくとも次を保存し、保存後に再取得して内容を確認します。

- Baseline SHA
- Candidate SHA/candidate ref
- 自動検証結果
- CI結果、または結果を確認できていないこと
- Local acceptance: pending/pass
- Human acceptance: pending/pass
- 未検証事項
- Close開始状態

Candidate SHAが変わった場合は `workflow.toml` の失効規則を適用します。

## Implementation Review

Normal + Test not requiredだけ独立Implementation Reviewを要求します。レビュー担当は現在の候補コミットのSHA、差分、検証結果、Planを再取得し、`APPROVE`/`CHANGES_REQUIRED`/`BLOCKED` を判定します。

APPROVEは現在の候補コミットのSHAと対応付けてapprovalに保存します。Candidate変更で旧承認は失効します。

Test requiredではImplementation Reviewを行わず、実装完了判定を `workflow.toml` へ適用します。

## Awaiting Acceptance

このStatusでは現在の候補コミットに対するローカル環境での検証と人間による受入確認を待ちます。

- Local-only検証を現在環境で実行できなければ、候補SHA、必要なコマンド／起動方法、環境、期待結果、未確認理由をdeliveryへ残す
- CIが成功しただけでは、ローカル環境での検証や人間による受入確認を完了したとは扱わない
- 人間による受入確認のPASSは、確認対象の候補コミットのSHAと対応付ける
- FAILの理由を追記専用の履歴に保存し、再開時にImplementationへ戻す

Human Acceptance PASSだけではDoneにしません。明示的close指示を受けた後 [close.md](close.md) を適用します。
