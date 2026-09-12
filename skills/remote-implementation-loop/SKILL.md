---
name: remote-implementation-loop
description: canonical implementation-loopをremote/Chat環境で実行する薄いadapter。normal + lightweight Issueに限りremote Git executorとAcceptance handoffを提供し、Reviewはcanonicalの独立実行契約を維持する。
notion_sync: false
---

# Remote Implementation Loop

## 役割

このSkillは独立したmethodologyではありません。最初に `../implementation-loop/SKILL.md` を読み、Linear Statusに対応する `../implementation-loop/references/` のcanonical ruleをそのまま適用します。差し替えるのはGit executorと、remote環境で実行不能なAcceptanceのhandoffだけです。Review executorは差し替えず、canonicalの独立Review contractをそのまま使います。

## Eligibility gate

remote adapterの実行対象は **normal + lightweight** のIssueだけです。

- `Bug` labelがあるIssueは対象外。部分実行、remote resumeを行わず、canonical/local `implementation-loop` へhandoffする
- `Spike` labelがあるIssueは対象外。Experiment/PoCやResult Reviewをremote化せず、canonical/local `implementation-loop` へhandoffする
- `Strict profile` labelがあるIssueは対象外。Strict Reviewerをremote adapterで代替せず、canonical/local `implementation-loop` へhandoffする
- independent reviewer availabilityはEligibility条件にしない。mode=`normal`、profile=`lightweight` ならReview可否にかかわらずadapter自体はeligibleとする
- local worktreeを利用できずGitHub repository read/writeが利用可能な場合だけremote Git executorを使う。local Gitが利用できる環境のGit transportをGitHub APIへ置換しない

Eligibilityを満たさない場合はIssue、Status、canonical Plan、Comments、Labels、relationsをreadbackし、handoff理由と必要なentry pointを記録して停止します。remote adapter固有のStatus/Labelは追加しません。

## Review boundary

Plan Review / Test Review / Test-not-required Implementation Reviewなどcanonicalが要求するReviewは、成果物作成主体とは独立した実行コンテキストで実施します。remote adapterはReviewをskipしたり、成果物作成主体自身の判定へ置換したりしません。

Review phaseへ到達した時点で現在のremote実行から独立Reviewerを利用できない場合は、canonical referenceが要求するReview packetをLinear / repositoryにdurableに残し、該当 **Review Status** で **handoff** して停止します。別Chat等の独立実行は最新のLinear Issue / Status / canonical Plan / Comments / Labels / relations、最新Harness reference、repository evidenceをfresh readbackし、そのReview phaseだけを実行します。Review完了後の元実装側は過去chat contextへ依存せず、最新Linear / repository stateからresumeします。

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
