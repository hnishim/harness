# Close

通常IssueのHuman Acceptance PASS、またはSpikeの現在result版に対するDECISION_READYが揃った後、**人間から明示的なclose指示がある場合だけ**開始します。

## 前フェーズへの差戻しとの関係

`close_started: true` を記録したCloseは汎用 `phase_return` の対象外です。公開済みSHAやClose起点・権限の契約を差戻し名目で取り消さず、Close内の既存の停止・再開契約を適用します。未着手のAwaiting Acceptanceからの差戻しは、原因と影響を確認したうえで通常のAcceptance FAIL経路または汎用差戻しを選択します。

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

Gate通過後だけdeliveryへ `close_started: true` とentry gate対象candidate/resultを保存します。途中停止後は同じ対象と整合する場合だけ再開し、新しいclose指示を再要求しません。

## Close起点とlocal Git選択

Entry gateと明示close指示を確認した後、local Gitを選択する**前**にdeliveryへ `close_origin` とその根拠を保存してreadbackします。値は `local_origin`/`remote_only`/`unknown` とし、現在の端末にworktreeがないことだけを `remote_only` の根拠にしません。ローカルで開始したCloseが別の環境で再開されても記録済み起点を維持します。既存のdeliveryから一意に復元できない場合は `unknown` とし、根拠を確認するまで停止します。Chat等の実行主体名を起点の代わりに保存しません。

`local_origin` ではlocal Gitを使います。Gitメタデータ権限制約・worktree利用不能等によりlocal Gitを使用できない場合、GitHub操作が可能でも切り替えず、deliveryへ理由、観測した能力、停止地点、必要なローカル後続操作を記録します。`remote_only` は旧deliveryの履歴として読めますが、canonical loop内の公開は許可しません。既存の `close_started`、承認済みcandidate、公開済みSHAのbindingは維持します。停止は既存のclose指示を無効にしません。

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
