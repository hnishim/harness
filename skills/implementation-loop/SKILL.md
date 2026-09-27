---
name: implementation-loop
description: Linear Issueを起点に、ローカル環境とリモート環境で共通の状態遷移を使い、利用できる操作に応じて実装を進めるワークフロー。
metadata:
  notion_sync: "false"
---

# Implementation Loop

## 各情報の正規の参照先

ローカル環境・リモート環境のどちらから実装を始める場合も、このSkillを使用します。各情報の正規の参照先は次のとおりです。

- Linear: Issue、Status、Label、Plan、approval、delivery、result、追記専用の履歴
- 対象Gitリポジトリ：ソースコード、テスト、候補コミット
- このHarness: `workflow.toml` と各参照文書
- CI: 再現可能な自動検証
- ローカル環境：OS／アプリ／認証情報など、ローカル環境でしか実行できない検証
- 人間：明示的な最終受入確認

実行主体名はワークフロー状態へ保存しません。

## 実行時に適用するルール

各実行の開始時にLinear Issue、全コメント、Status、Label、依存関係、対象リポジトリを再取得した後、**現在有効な受入済みHarness**にある `skills/implementation-loop/workflow.toml` を読みます。

ローカル実行では、SessionStartが受入済みHarnessの実行用設定を `ready` または `updated` と確認できることを開始条件とします。`harness_gate=blocked` の場合は古いHarnessへフォールバックせず、その実装ワークフローを開始しません。リモート実行では、GitHub上の受入済みHarnessを直接取得する従来のルールを維持します。

1. `routes` を参照し、Statusに対応するactionを決める
2. `actions` と `profiles` を参照し、必要な操作・確認を実行できるか判断する
3. Mode制約を確認する
4. 各参照文書に従い、対象Issueの状況と成果物の内容を判断する
5. 判断が確定したら、`transitions`、`bindings`、`invalidation` に従い、次のStatusと無効にする承認を決める
6. 書込み直前に受入済みHarnessを再取得し、開始時と同じルールが適用されることを確認する
7. 決定した承認状態と次StatusをLinearへ保存し、書込み結果をreadbackして期待どおり永続化されたことを確認する
8. 一致したtransitionの `continue_in_same_run` は未指定なら `true` と解釈する。`false` なら同一実行を停止し、新しいStatusに対応する次actionは開始しない
9. Plan ReviewのAPPROVEによる停止では、readback後かつ実行終了前にチャットへ「設計判断の要点」を出力する。Planning開始時の重要な未確定・不明事項、判断の根拠、確定した内容を主情報とし、重要な代替案を採用しなかった理由や残る未解決事項があれば併記する。最後にTest decisionと次Status／actionを簡潔に示す。説明は人間に分かりやすい言葉で行い、内部のStatus名・field名・hash等をそのまま羅列するだけで済ませない

当該Issue自身が `workflow.toml` を変更していても、候補上の未受理TOMLをそのIssue自身の制御へ使いません。現在有効な受入済みHarnessの設定で実行を制御し、変更中の候補はレビュー対象の成果物として扱います。新しい契約は公開後の次回実行から有効です。

Markdownへ同じ状態遷移表・失効表を複製しません。Markdownでは判断する内容を定義し、TOMLでは判断後の機械的な処理を定義します。

## Assigneeとnext actor

Assigneeは履歴上の担当者ではなく、**次に状態を進めるためのアクションを実行できる主体**を表します。Statusは工程、Assigneeはnext actorとして別に扱い、local / remoteで同じ意味を使います。具体的なactor identityと機械条件は `workflow.toml[next_actor]` を正規仕様とします。

各フェーズで停止または再開地点を確定するときは、次の順で処理します。

1. 停止理由と再開条件を確定する
2. 現在の事実からnext actorを判定する
3. approval / delivery等の永続状態を保存する
4. Assigneeをnext actorへ更新する
5. Status・Assignee・永続状態をreadbackし、停止理由と矛盾しないことを確認する
6. Assigneeと期待actorが一致しなければ `workflow.toml[next_actor].on_assignee_mismatch` に従って停止する

人間の仕様判断、確認、操作トリガーが必要ならHumanへassignして停止します。人間の操作が完了しAgentだけで継続可能になったらAgentへ戻します。ローカル作業であること自体をHuman待ちの理由にはせず、ローカルAgentが継続可能ならAgentをnext actorとします。Awaiting AcceptanceはHumanをnext actorとし、Done / CanceledではAssigneeを解除します。

Review actionが `workflow.toml[next_actor.review_confirmation].actions` に含まれる場合、独立Reviewerの判定を対象版へbindingして保存しただけでは既存transitionを適用しません。Reviewer判定保存後は同じReview StatusのままHumanへassignしてdurable stopし、人間確認を現在のreview対象版へ対応付けて確認した後にだけ既存transitionを適用します。遷移後の同一実行継続可否は従来どおりtransitionの `continue_in_same_run` に従い、Review確認gateと二重化しません。

`workflow.toml[next_actor.subscription]` が適用され、永続状態の `subscription_bootstrapped` が未完了なら、Assigneeを一度Humanへ変更してreadbackした後、本来のnext actorへ戻して再度readbackします。両方の更新を確認した後だけ `subscription_bootstrapped: true` をdeliveryへ保存します。完了済みIssueではこの往復を繰り返しません。Linear connectorからsubscriber一覧を直接確認できない場合、その未確認範囲は明示し、Assignee更新の成功だけをSubscription表示の検証済みとは扱いません。

## Mode / profile

- `Bug` Label: bug mode。原因確定前は親Issueを実装へ進めません。常に `Test required`
- `Spike` Label: spike mode。主成果物はresult
- 両方ある場合： BLOCKED
- どちらもない場合： normal
- `Strict profile`: strict。必要なstrict Reviewer能力がなければレビューStatusを維持して停止
- それ以外： lightweight

## 利用可能な操作とGitの実行方法

フェーズ開始時に、現在の環境で実行できる操作・確認を実際に調べます。

- 通常の候補コミットの保存では、ローカルのworktreeとGitを使える場合は `git_backends.local` を使う。それらを使えずGitHubの読取り・書込みが可能な場合は `git_backends.remote` を使う
- **Closeでは** `workflow.toml[actions.close]` の共通能力を判定し、local Gitまたはremote-only環境で利用可能な `git_backends.remote` のGitHub／Pull Request操作で公開する。公開できるかどうかを作業開始時の環境だけでは決めません
- 通常IssueではHuman Acceptance PASSと明示Close指示前、Spikeでは現在result版への有効なDECISION_READYと明示Close指示前は公開先を更新しない。公開対象の変更が実在する場合は承認済みIssueの差分と統合結果を照合し、統合後のコミットSHAが異なるだけでは承認を無効にしません
- 必要なローカル反映を実行できない場合は公開済みであることと、未完了の同期・設定適用・利用確認をdeliveryへ記録し、Doneにはしません
- 独立したレビュー担当を確保できない場合：現在のレビューステータスを維持し、再開に必要な資料をLinearへ保存して停止します
- ローカル環境でしかできない検証を実行できない場合：未検証事項としてdeliveryへ記録して引き継ぎます
- 厳格プロファイルのレビュー担当を確保できない場合：プロファイルを緩和せずに停止します

必要な操作・確認ができないことをPASSとして扱いません。`remote Git` の操作ルールは [references/remote-git.md](references/remote-git.md) を使います。

## Linearへの記録形式

新形式では、通常Issueで更新する情報を次の3件のコメントに集約します。

- `artifact_key: plan`: 詳細Plan本文
- `state_key: approval`: Plan Review、approved tests manifest、Implementation Review、Spike Result Reviewなどの承認と、承認対象の版との対応付け
- `state_key: delivery`: baseline/candidate、検証、CI、local/human acceptance、close進行

Spikeだけ `artifact_key: result` を追加します。

各論理キーは1件だけです。改訂時は同じコメントIDを更新し、同じ現在状態のスナップショットを追加しません。重要な変更要求、具体的なBLOCKEDの理由、受入FAIL、Bugの原因を示す根拠、Spikeの最終判断は、既存記録を上書きせず履歴として追記します。

### Hash

PlanとresultはUTF-8、改行LF、各行末の空白除去、末尾改行1個へ正規化してSHA-256を計算します。

Approved tests manifestは、リポジトリ相対パスを辞書順に並べ、各ファイルSHA-256、再実行コマンド、手動確認、未検証範囲、各新規・変更テストの維持・削除条件に関する情報を含む決定的な表現からmanifest hashを計算します。寿命情報にはテスト識別子、分類、終了条件、恒久保持理由を含め、分類・終了条件・恒久保持理由の変更もmanifest hashを変化させます。Test Review承認はmanifestの特定版へ結び付けます。

## フェーズ

### 必要な前フェーズへの差戻し

未完了Issueの進行中に前の作業フェーズへ戻る必要が確定した場合は、既存のReview判定と通常進行を優先し、それだけでは扱えない差戻しに限り、受理済み `workflow.toml[phase_return]` を適用します。差戻し先は原因と影響した成果物から決め、任意のStatusへ変更してよいという意味ではありません。原因の調査・承認の無効化・候補の保持・途中で停止した書込みの再開は [references/implementation.md](references/implementation.md)、[references/planning.md](references/planning.md)、[references/test.md](references/test.md) を使います。Close開始済み、原因未確定、承認と対象の版が一致しない場合、候補の作成元・変更履歴が不明な場合は停止します。新しい契約は当該HarnessのHuman Acceptanceと公開後の次回実行から適用します。


Statusに対応するactionを `workflow.toml` から選び、次の意味判断文書を適用します。

- Planning/Plan Review: [references/planning.md](references/planning.md)
- Test Implementation/Test Review: [references/test.md](references/test.md)
- Implementation/Acceptance: [references/implementation.md](references/implementation.md)
- Bug: [references/bug.md](references/bug.md)
- Spike: [references/spike.md](references/spike.md)
- Close: [references/close.md](references/close.md)
- Strict profile: [references/strict-profile.md](references/strict-profile.md)

## 独立レビュー

Plan Review、Test Review、normal + Test not requiredのImplementation Review、Spike Result Reviewは、成果物を作成した実行から独立した読み取り専用Reviewerが行います。同一実行内での自己レビューは禁止します。対象成果物と作成した実行を特定できない場合は、レビュー担当の独立性を推定せず、当該レビューStatusを維持して停止します。レビュアーの環境別選定順序と停止条件は `workflow.toml[independent_reviewer]` に従います。既存のStrict profile追加能力要件は維持します。

レビュー判定は各参照文書の語彙だけを使います。承認する場合は指摘事項がないこと、変更を要求する場合は具体的な指摘事項があること、BLOCKEDの場合は判断できない具体的な理由があることを必要とします。

## 失効

対象の内容を判断した後、承認と対象の版の対応が変更されていれば `workflow.toml[invalidation]` を適用します。

- Planの版が変わった場合：Plan Reviewと後続工程の承認を無効化
- 承認済みテストのmanifestが変わった場合：Test Reviewの承認を無効化
- 候補コミットのSHAが変わった場合：その候補へのImplementation Reviewの承認と受入確認を無効化
- Spikeのresultの版が変わった場合：Result Reviewの承認を無効化

Statusが以前と同じになっただけでは、無効化した承認を復活させません。

## Gitへの候補コミットの保存

実装・テスト成果物は、現在選択されたGit backendで候補へ固定します。

- Local: local Git executor
- Remote: GitHub candidate ref executor

共通条件は、Issue専用作業ブランチ、候補SHA、基準SHA、変更対象範囲と変更元の確認、強制更新をしないこと、履歴を書き換えないこと、更新後にGitの状態を再取得して確認することです。受入確認前の候補を公開先ブランチに作らず、ローカルでは他の作業を壊さない別作業領域を使います。ローカル／リモートでは同じ作業ブランチを継続します。人間受入前に既定ブランチへ公開しません。

## 停止条件

次では安全側で停止します。

- 必要な操作・確認を実行できない
- 独立レビュー待ち
- 変更要求
- Binding不一致
- 候補コミットの保存や外部への書込みが成功したか確認できない
- ローカル環境でしかできない検証が未実施
- 人間による受入確認待ち
- 明示close待ち
- Done

停止時は再開に必要なStatus、候補コミットのSHA、承認と対象の版の対応、未検証事項をLinearに記録します。
