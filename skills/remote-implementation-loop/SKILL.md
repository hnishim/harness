---
name: remote-implementation-loop
description: canonical implementation-loopをremote/Chat環境で実行する薄いadapter。normal + lightweight Issueに限りself-reviewとGitHub remote Git executorへ差し替える。
notion_sync: false
---

# Remote Implementation Loop

## 役割

このSkillは独立したmethodologyではありません。最初に `../implementation-loop/SKILL.md` を読み、Linear Statusに対応する `../implementation-loop/references/` のcanonical ruleをそのまま適用します。差し替えるのはReview executor、Git executor、remote環境で実行不能なAcceptanceのhandoffだけです。

## Eligibility gate

remote adapterの実行対象は **normal + lightweight** のIssueだけです。

- `Bug` labelがあるIssueは対象外。部分実行、self-review fallback、remote resumeを行わず、canonical/local `implementation-loop` へhandoffする
- `Spike` labelがあるIssueは対象外。Experiment/PoCやResult Reviewをremote化せず、canonical/local `implementation-loop` へhandoffする
- `Strict profile` labelがあるIssueは対象外。Strict Reviewerをself-reviewへ置換せず、canonical/local `implementation-loop` へhandoffする
- mode=`normal`、profile=`lightweight` で、独立read-only reviewerを現在環境から利用できない場合だけ `review_mode: self` を使う
- local worktreeを利用できずGitHub repository read/writeが利用可能な場合だけremote Git executorを使う。local Gitが利用できる環境のGit transportをGitHub APIへ置換しない

Eligibilityを満たさない場合はIssue、Status、canonical Plan、Comments、Labels、relationsをreadbackし、handoff理由と必要なentry pointを記録して停止します。remote adapter固有のStatus/Labelは追加しません。

## Review executor binding

normal + lightweightかつindependent reviewerを利用できない場合、canonical Plan Review / Test Reviewの **active Review executor** をself-reviewへ差し替えます。判定語彙、Review packet、Status transition、durable stopはcanonical referenceを変更しません。

Self-review開始時は直前のPlanning/Test推論を根拠に追認せず、最低限次をfresh readbackします。

- Linear `Issue / Status / canonical Plan / Comments / Labels / relations`
- repository evidenceとreview対象差分
- Test Reviewではtest artifactのpath/hashと再実行結果
- candidate/closeに関係する確認ではcandidate SHA、ref、provenance、利用可能なCI evidence

再取得した要求、Plan、repository evidenceからReviewer roleとして再判定し、Review記録に `review_mode: self` を保存します。同一phaseで修正→再Reviewを許す場合も、`*_CHANGES_REQUIRED` が **2回連続** した時点で未解決点を保存して停止し、無限反復しません。

Plan Review APPROVE後のHuman confirmation stop、Test Review TESTS_APPROVED後の同一実行内Implementation継続、Implementation完了後の `In Implementation Review` stopはcanonicalと同一です。

## Git executor binding

local worktreeを利用できずGitHub repository writeが利用可能なeligible Issueでは、logical `checkpoint` / `publish checkpoint` の **active Git executor** を [references/remote-git.md](references/remote-git.md) に差し替えます。`git-add-commit-push` にremote modeを追加しません。

Workflowへ返すlogical resultはlocal executorと同じです。

- candidate SHA / base SHA
- remote/ref
- scope / provenance確認結果
- published / not published
- verification結果またはBLOCKED reason

Human Acceptance前はcandidate branchだけを更新し、default branchを更新しません。CloseではAccepted candidate SHAを変えずにtarget refへ公開します。

## Verification / handoff binding

Automated verification、CI Verification、Local Acceptance、Human Acceptanceの意味はcanonical `test.md` / `implementation.md` に従います。

- CI evidenceをAcceptanceへ使う場合はcandidate SHAとCI対象SHAを一致させる
- CI PASSをLocal AcceptanceまたはHuman AcceptanceのPASSへ昇格しない
- remote環境でLocal Acceptanceを実行できない場合はcandidate SHA、command/entry point、必要environment/application、expected result、未確認理由をCompletion Commentへ残す
- Human Acceptanceは明示的人間確認まで未確認として維持する

Chat/Codex等の実行主体名をworkflow stateにしません。Linear Status、canonical Plan、Comments、candidate SHAをhandoff contractとします。
