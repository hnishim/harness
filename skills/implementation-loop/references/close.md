# Close

通常IssueのHuman Acceptance PASS、またはSpikeの現在result版に対するDECISION_READYが揃った後、**人間から明示的なclose指示がある場合だけ**開始します。

## 前フェーズへの差戻しとの関係

Closeの途中停止・再開は、現在の候補、受入証跡、明示Close指示、公開先の実状態から判断します。過去の `close_started` やBLOCKED記録だけを固定的な停止条件にはしません。未着手のAwaiting Acceptanceからの差戻しは、原因と影響を確認したうえで通常のAcceptance FAIL経路または汎用差戻しを選択します。

## Entry gate

Close開始前に最新のIssue、approval、delivery、result（Spike）、candidate ref、対象refを再取得します。

Normalでは少なくとも次を確認します。

- 現在candidate SHAとdeliveryのcandidate SHAが一致
- Human acceptanceが現在candidateへbindingしてpass
- Test not requiredなら現在candidateに結び付いたImplementation Review APPROVE
- Test requiredならapproved tests manifestが現在も同一

Spikeでは現在result hashとreviewed result hashが一致し、DECISION_READYであることを確認します。

Entry gate未達ではclose状態を将来許可として保存しません。

## Close開始状態

Gate通過後は、現在のcandidate/result、明示Close指示、公開先とCIの観測結果をdeliveryへ保存します。途中停止後は、現在の証跡が同じ対象へ結び付く場合だけ再開します。初回entry前に拒否された古いClose指示は再利用せず、新しい明示指示を要求します。

## Git backendと引継ぎ

Closeは常に `git_backends.local` を使い、`local_git` を必須とします。remote-only環境で作成した候補も同じcandidate SHA/refを保持したまま、ローカルGitでCloseします。GitHub APIで公開しません。

ローカルGitが利用できない場合、GitHub read/write能力や旧 `remote_close_authorized` があっても、現在Statusを維持して停止します。既存deliveryへ候補SHA/ref、承認・Human Acceptance・CI、公開先、能力不足理由、必要なローカル操作を残してreadbackし、ローカル環境へ引き継ぎます。旧 `close_origin`、`remote_close_authorized`、`local_origin_close_sync` は履歴として照合するだけで、公開権限に変換せず、新規作成も要求しません。

再開時には候補ref/SHA、承認・受入証跡、公開先の実状態と祖先関係・許可コミット列を照合します。既に同一candidate SHAが対象refへ公開済みなら重複公開せず、現証跡に基づきローカルCloseを継続します。公開先や候補の由来が不明・不一致の場合は停止します。

## Publish

Local Gitで受理済みcandidate SHAを対象refへ公開します。

公開後に対象refをreadbackし、同じcandidate SHAへ到達していることを確認します。別SHAを作るmerge/squash/rebaseは使いません。

## CI

リポジトリに必須CIがある場合は公開済みSHAへ結び付く結果だけを評価します。CI適用可否、実行観測、結果を分けて扱い、未観測を「CIなし」に変換しません。

必須CIがsuccessでない、または判定不能ならDoneへ進みません。

## ローカルclose後同期

公開、必要CI、外部成果物の再取得確認までをclose本体とします。Close本体が完了した後、`CLOSE_COMPLETE` 適用前に公開済み対象refへ対応するローカルブランチの同期をbest-effortで試行します。この後処理の失敗やskipはclose本体を失効させず、Doneへの遷移を妨げません（HIR-277）。候補をリモートで作成した場合も同じローカルClose後同期を適用します。

Local backendでは次の順序と安全条件を守ります。

1. 公開に使ったremoteをfetchし、公開済み対象refのSHAを再取得する。対象ref名を `main` に固定せず、公開済み対象refと対応するローカルブランチを使う
2. ローカル対象ブランチのSHA、remote対象refとの祖先関係、現在および他worktreeでのcheckout状態をreadbackする
3. SHAが同一なら `already_synced`
4. ローカル対象ブランチがremote対象refの祖先である場合だけ更新を許可する
   - 現在のworktreeで対象ブランチをcheckout中： index、tracked、untrackedを含めcleanな場合だけff-only更新する
   - 対象ブランチがどのworktreeでもcheckoutされていない： 現在のbranch、index、worktreeを変更せず、祖先確認後に `git update-ref refs/heads/<branch> <remote_sha> <local_sha>` 相当の旧SHA付きrefを更新する
   - 他worktreeでcheckout中： そのworktreeを変更せず `skipped`
5. Local ahead、diverged、比較不能、dirtyな対象worktree、fetch失敗、更新前refの競合変更、更新失敗、更新後readback不一致は、stash、reset、rebase、force、branch切替や破壊的な再試行をせず `skipped`
6. 更新後はローカル対象ブランチSHAが公開済み対象ref SHAと一致することをreadbackする

結果はdeliveryの `local_post_close_sync` に保存し、少なくとも `outcome`、skip時の `reason`、`target_ref`、観測した `local_sha`/`remote_sha` を残します。Outcomeは `synced`/`already_synced`/`skipped`/`not_applicable` を使います。

## Done

公開、必要CI、外部成果物の再取得確認が完了した場合だけ、`workflow.toml` に `CLOSE_COMPLETE` を適用してDoneへ進みます。
