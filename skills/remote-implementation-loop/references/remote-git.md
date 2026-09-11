# Remote Git executor

このreferenceは `remote-implementation-loop` のGitHub API / connector transportだけを所有します。workflow semanticsは `../../implementation-loop/` がSource of Truthです。

## checkpoint

1. Issueのcandidate branchを一意に決める
2. write直前にtarget/default branch、candidate branch（存在する場合）、base commitをreadbackし、Planで承認されたbaselineからstaleになっていないことを確認する
3. Plan scopeの変更だけをGitHubの `blob` → `tree` → `commit` で1 candidate commitへ固定する。approved-testsはTest Reviewで固定した内容とhashを維持する
4. candidate branchがなければ確認済みbaseから作成し、更新は **non-force** fast-forwardのref updateだけを使う
5. mutation後にbranch `ref`、candidate SHA、parent/base、変更path、scope/provenanceをreadbackする
6. candidate SHA / base SHA / remote/ref / verification結果をLinearへ保存してreadbackする

Human Acceptance前に`main`/default branchを更新しません。force update、history rewrite、PR merge、squash、rebaseで別SHAを作るfallbackは禁止です。

## publish checkpoint

Accepted **candidate SHA** を新しいcommitへ変換せず、Close先target refへnon-force fast-forwardします。

1. publish直前にtarget ref、candidate ref、candidate ancestry、Linearに記録されたcandidate/outgoing provenanceをreadbackする
2. targetがcandidateのancestorで、outgoing chainが許可checkpoint列と一致する場合だけ同じcandidate SHAへのnon-force ref updateを行う
3. 初回publishが拒否・失敗・結果不明でも、無条件retryせずtarget refをreadbackする
4. readbackでtargetが既にcandidateなら成功として扱い、retryしない
5. targetが未変更でcandidate/outgoing provenanceも不変、remote先行/分岐なしと再確認できた場合だけ、**同一non-force操作を1回だけretry**する
6. targetが進んだ、diverged、provenance不一致、readback不能ならretryせずBLOCKED
7. 1回だけretryしても失敗した場合はGit publication execution boundaryとしてlocal executorへhandoffし、candidate SHA、target ref、outgoing chain、publish operation、expected result、未完了理由をLinearへ残す

PR merge / squash / rebase等でAccepted candidateとは別SHAを生成して迂回しません。
