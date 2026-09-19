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

## Close起点とGit backend選択

entry gateと明示close指示を確認した後、backendを選択する**前**にdeliveryへ `close_origin` とその根拠を保存してreadbackします。値は `local_origin` / `remote_only` / `unknown` とし、現在の端末にworktreeがないことだけをremote-onlyの根拠にしません。ローカルで開始したCloseが別の環境で再開されても記録済み起点を維持します。既存のdeliveryから一意に復元できない場合は `unknown` とし、根拠を確認するまで停止します。Chat等の実行主体名を起点の代わりに保存しません。

`local_origin` ではlocal Git backendを原則とします。Gitメタデータ権限制約・worktree利用不能等によりlocal Gitを使用できない場合、GitHub操作が可能でもremoteへ自動切替せず、deliveryへ理由、観測した能力、停止地点、必要なローカル後続操作を記録します。既存の `close_started`、承認済みcandidate、公開済みSHAのbindingは維持します。停止は既存のclose指示を無効にしません。

remoteへ続行するには、元のclose指示とは区別した、当該Close対象に対する明示的な切替許可が必要です。許可の事実と対象candidateをdeliveryの `remote_close_authorized` に保存・readbackしてからremote backendを選択します。元からremote-onlyで開始したことが根拠付きで確認できる場合は、従来どおりremote backendを利用できます。

## publish

選択済みGit backendで受理済みcandidate SHAを対象refへ公開します。remote backendでは [remote-git.md](remote-git.md) を使います。

公開後に対象refをreadbackし、同じcandidate SHAへ到達していることを確認します。別SHAを作るmerge/squash/rebaseは使いません。

## CI

リポジトリに必須CIがある場合は公開済みSHAへ結び付く結果だけを評価します。CI適用可否、実行観測、結果を分けて扱い、未観測を「CIなし」に変換しません。

必須CIがsuccessでない、または判定不能ならDoneへ進みません。

## ローカルclose後同期

公開、必要CI、外部成果物の再取得確認までをclose本体とします。local Git backendではclose本体が完了した後、`CLOSE_COMPLETE` 適用前に、公開済み対象refへ対応するローカルブランチの同期をbest-effortで試行します。この後処理の失敗やskipはclose本体を失効させず、Doneへの遷移を妨げません（HIR-277の通常local backend経路）。remote-only起点のremote Git backendはローカル環境へ触れず `not_applicable` とします。一方、ローカル起点から明示的にremoteへ切り替えたCloseは以下の未同期判定を適用し、`not_applicable` を同期完了として扱いません。

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

## ローカル起点からremoteへ切り替えたCloseの再開

明示的に切り替えたremote backendで公開した場合も、受理済みcandidate SHAをそのまま対象refへnon-forceで公開し、必要CIとreadbackまでをclose本体として記録します。ただしremote環境からローカル対象ブランチを同期済みとみなすことはできません。deliveryの `local_origin_close_sync` に `AWAIT_LOCAL_SYNC`、理由、公開した対象ref/SHA、観測できたローカルSHA（未観測なら未観測と明記）、利用者が行う必要のあるローカル後続操作を保存して通知します。ローカル同期が確認されるまでStatusは `Awaiting Acceptance` のままとし、`CLOSE_COMPLETE` は適用しません。

ローカル環境から再開した際は、記録済みの `close_started` と承認済みcandidateへのbinding、公開済み対象ref/SHA、必要CIを再取得します。すでに対象refが同じcandidate SHAであれば重複公開せず、ローカル同期の再開だけを行います。公開済みrefが進行・分岐した場合やreadback不能なら推測で再公開せず停止します。ローカル対象ブランチの安全な追従は前節の非破壊Git条件に従いますが、この経路では `skipped` や同期不能を完了へ昇格しません。公開済みSHAとローカル対象ブランチSHAが一致し、両方のreadbackを確認したときだけ `synced` / `already_synced` と記録して `CLOSE_COMPLETE` に進めます。dirty、ahead、diverged、別worktree、権限制約等では現在のローカル状態を破壊せず未同期のまま停止し、必要な手動対応を残します。

## Done

公開、必要CI、外部成果物の再取得確認が完了した場合だけ `CLOSE_COMPLETE` を `workflow.toml` へ適用しDoneへ進みます。
