---
name: remote-implementation-loop
description: canonical implementation-loopをremote/Chat環境へbindingする薄いadapter。lightweight profileでcurrent phaseが要求するcapabilityを満たせる範囲を継続し、Reviewの独立性を維持する。
notion_sync: false
---

# Remote Implementation Loop

## 役割

最初に `../implementation-loop/SKILL.md` とLinear Statusに対応するcanonical referenceを読み、そのphase semanticsをそのまま適用します。このadapterが差し替えるのは、local worktreeを利用できない場合のGit executorと、remote環境で実行できないAcceptanceのhandoffだけです。Review semanticsはcanonicalを維持します。

## Eligibility gate

remote adapterは `lightweight` profileを対象とし、Issue modeではなく `current phase` が要求する `capability` をphase開始時に判定します。

- `Bug` / `Spike` label自体はEligibilityの除外条件にしない。canonical mode modifierとして対応referenceを選ぶ
- current phaseに必要なcapabilityをLinear、GitHub repository read/write、repository inspection、remote service、CIなど現在利用可能なremote capabilityで満たせる場合はcanonical workflowを継続して進める
- current phaseがremoteから利用できない `local-only` または `unavailable` capabilityを要求する場合は停止し、その観測・verification・Acceptanceを `未検証` のままhandoffする。必要なentry point、実行環境、期待結果、未確認理由をLinearへ残す
- `Strict profile` は対象外。Strict Reviewerをremote adapterで代替せずcanonical/local `implementation-loop` へhandoffする
- independent reviewer availabilityはEligibility条件にしない。Reviewを現在のremote実行から独立に実行できない場合はcanonicalのReview Statusでhandoffする
- local worktreeを利用できずGitHub repository read/writeが利用可能な場合だけremote Git executorを使う。local Gitが利用可能な環境のGit transportは置換しない

remote adapter固有のStatusやLabelは追加しません。停止時はIssue、Status、canonical Plan、Comments、Labels、relationsとrepository evidenceをreadbackし、停止理由と再開地点をdurableに残します。

## Review boundary

Plan Review / Test Review / Test-not-required Implementation Review / Spike Result Reviewなどcanonicalが要求するReviewは、成果物作成主体とは独立したread-only Reviewerで行います。remote adapterはReviewをskipしたり自己判定へ置換したりしません。

独立Reviewerを現在のremote実行から利用できない場合は、canonical referenceが要求するReview packetをLinear / repositoryに残し、該当Review Statusでhandoffします。別実行は最新Linear / Harness / repository evidenceをfresh readbackして、そのReview phaseだけを実行します。

## Git executor binding

local worktreeを利用できずGitHub repository read/writeが利用可能なeligible Issueでは、logical `checkpoint` / `publish checkpoint` のactive Git executorを [references/remote-git.md](references/remote-git.md) に差し替えます。`git-add-commit-push` のsemanticsは変更しません。

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
- Close時のpost-publish CI gateはcanonical `../implementation-loop/references/close.md` をSource of Truthとし、remote adapterはprovider/connector transportだけを担当する。requiredness、publish-trigger binding、PASS/stop条件をremote側へ複製しない
- remote環境でLocal Acceptanceを実行できない場合はcandidate SHA、entry point、必要environment/application、expected result、未確認理由をCompletion Commentへ残す
- Human Acceptanceは明示的人間確認まで未確認として維持する

Chat/Codex等の実行主体名をworkflow stateにしません。Linear Status、canonical Plan、Comments、candidate SHAをhandoff contractとします。
