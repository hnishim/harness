# Close

通常IssueのHuman Acceptance PASS、またはSpikeの現在result版に対するDECISION_READYが揃った後、**人間から明示的なclose指示がある場合だけ**開始します。

## entry gate

close開始前に最新のIssue、approval、delivery、result（Spike）、candidate ref、対象refを再取得します。

normalでは少なくとも次を確認します。

- 現在candidate SHAとdeliveryのcandidate SHAが一致
- human acceptanceが現在candidateへbindingしてpass
- Test not requiredなら現在candidateに結び付いたImplementation Review APPROVE
- Test requiredならapproved tests manifestが現在も同一

Spikeでは現在result hashとreviewed result hashが一致し、DECISION_READYであることを確認します。

entry gate未達ではclose状態を将来許可として保存しません。

## close開始状態

gate通過後だけdeliveryへ `close_started: true` とentry gate対象candidate/resultを保存します。途中停止後は同じ対象と整合する場合だけ再開し、新しいclose指示を再要求しません。

## publish

選択済みGit backendで受理済みcandidate SHAを対象refへ公開します。remote backendでは [remote-git.md](remote-git.md) を使います。

公開後に対象refをreadbackし、同じcandidate SHAへ到達していることを確認します。別SHAを作るmerge/squash/rebaseは使いません。

## CI

リポジトリに必須CIがある場合は公開済みSHAへ結び付く結果だけを評価します。CI適用可否、実行観測、結果を分けて扱い、未観測を「CIなし」に変換しません。

必須CIがsuccessでない、または判定不能ならDoneへ進みません。

## ローカルclose後同期

公開、必要CI、外部成果物の再取得確認までをclose本体とします。local Git backendではclose本体が完了した後、`CLOSE_COMPLETE` 適用前に、公開済み対象refへ対応するローカルブランチの同期をbest-effortで試行します。この後処理の失敗やskipはclose本体を失効させず、Doneへの遷移を妨げません。remote Git backendではローカル環境へ触れず `not_applicable` とします。

local backendでは次の順序と安全条件を守ります。

1. 公開に使ったremoteをfetchし、公開済み対象refのSHAを再取得する。対象ref名を `main` に固定せず、公開済み対象refと対応するローカルブランチを使う
2. ローカル対象ブランチのSHA、remote対象refとの祖先関係、現在および他worktreeでのcheckout状態をreadbackする
3. SHAが同一なら `already_synced`
4. ローカル対象ブランチがremote対象refの祖先である場合だけ更新を許可する
   - 現在のworktreeで対象ブランチをcheckout中: index、tracked、untrackedを含めcleanな場合だけff-only更新する
   - 対象ブランチがどのworktreeでもcheckoutされていない: 現在のbranch、index、worktreeを変更せず、祖先確認後に `git update-ref refs/heads/<branch> <remote_sha> <local_sha>` 相当の旧SHA付きref更新を行う
   - 他worktreeでcheckout中: そのworktreeを変更せず `skipped`
5. local ahead、diverged、比較不能、dirtyな対象worktree、fetch失敗、更新前refの競合変更、更新失敗、更新後readback不一致は、stash、reset、rebase、force、branch切替や破壊的な再試行を行わず `skipped`
6. 更新後はローカル対象ブランチSHAが公開済み対象ref SHAと一致することをreadbackする

結果はdeliveryの `local_post_close_sync` に保存し、少なくとも `outcome`、skip時の `reason`、`target_ref`、観測した `local_sha` / `remote_sha` を残します。outcomeは `synced` / `already_synced` / `skipped` / `not_applicable` を使います。

## Done

公開、必要CI、外部成果物の再取得確認が完了した場合だけ `CLOSE_COMPLETE` を `workflow.toml` へ適用しDoneへ進みます。
