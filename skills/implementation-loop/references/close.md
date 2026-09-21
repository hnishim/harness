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

## Local Gitと公開先

新規実行のCloseは常に `git_backends.local` を使います。旧deliveryの `close_origin`、remote-only起点、旧許可フラグは履歴として読めますが、backend選択や公開権限には使いません。Local Gitが利用できない場合はGitHubへ切り替えず、現在Statusと停止理由を残します。

候補refは検証成果物の場所であり、公開先remote実体と公開先refとは別です。公開先を一意に解決できない、または候補の由来・対象を確認できない場合は停止します。

## Publish

Local Gitで受理済みcandidate SHAを対象refへ公開します。

公開後に対象refをreadbackし、同じcandidate SHAへ到達していることを確認します。別SHAを作るmerge/squash/rebaseは使いません。

## CI

リポジトリに必須CIがある場合は公開済みSHAへ結び付く結果だけを評価します。CI適用可否、実行観測、結果を分けて扱い、未観測を「CIなし」に変換しません。

必須CIがsuccessでない、または判定不能ならDoneへ進みません。

## ローカルclose後同期

公開、必要CI、外部成果物の再取得確認までをclose本体とします。Local Gitではclose本体が完了した後、`CLOSE_COMPLETE` 適用前に、公開済み対象refへ対応するローカルブランチの同期をbest-effortで試行します。この後処理の失敗やskipはclose本体を失効させず、Doneへの遷移を妨げません（HIR-277の通常local Git経路）。

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
