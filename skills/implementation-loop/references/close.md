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

## Done

公開、必要CI、外部成果物の再取得確認が完了した場合だけ `CLOSE_COMPLETE` を `workflow.toml` へ適用しDoneへ進みます。
