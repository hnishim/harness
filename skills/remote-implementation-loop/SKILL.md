---
name: remote-implementation-loop
description: canonical implementation-loopをremote/Chat環境へbindingする薄いadapter。lightweight profileで現在のphaseが必要とする機能を満たせる範囲を継続し、Reviewの独立性を維持する。
notion_sync: false
---

# Remote Implementation Loop

## 役割

最初に `../implementation-loop/SKILL.md` とLinear Statusに対応するcanonical referenceを読み、そのphaseの意味をそのまま適用します。このadapterが差し替えるのは、local worktreeを利用できない場合のGit executorと、remote環境で実行できないAcceptanceの引き継ぎだけです。Reviewの意味づけはcanonicalを維持します。

## 対象判定

remote adapterは `lightweight` profileを対象とし、Issue modeではなく現在のphaseが要求する機能をphase開始時に判定します。

- `Bug` / `Spike` label自体は対象判定の除外条件にしない。canonicalのモード判定を補助するラベルとして対応referenceを選ぶ
- 現在のフェーズに必要な機能をLinear、GitHub Repositoryの読み書き、リポジトリ確認、外部サービス、CIなど現在利用可能なremote側の機能で満たせる場合はcanonical workflowを継続して進める
- 現在のフェーズがremoteから利用できない `local-only` または `unavailable` の機能を要求する場合は停止し、その観測・検証・Acceptanceを `未検証` のまま引き継ぐ。必要なentry point、実行環境、期待結果、未確認理由をLinearへ残す
- `Strict profile` は対象外。Strict Reviewerをremote adapterで代替せずcanonical/local `implementation-loop` へ引き継ぐ
- 独立Reviewerの利用可否は対象判定の条件にしない。Reviewを現在のremote実行から独立に実行できない場合はcanonicalのReview Statusで引き継ぐ
- local worktreeを利用できずGitHub Repositoryの読み書きが利用可能な場合だけremote Git executorを使う。local Gitが利用可能な環境のGit転送は置換しない

remote adapter固有のStatusやLabelは追加しません。停止時はIssue、Status、canonical Plan、Comments、Labels、relationsとrepositoryの証跡を再取得確認し、停止理由と再開地点を永続的に残します。

## Reviewの境界

Plan Review / Test Review / Test-not-required Implementation Review / Spike Result Reviewなどcanonicalが要求するReviewは、成果物作成主体とは独立したread-only Reviewerで行います。remote adapterはReviewを省略したり自己判定へ置換したりしません。

独立Reviewerを現在のremote実行から利用できない場合は、canonical referenceが要求するレビュー資料をLinear / repositoryに残し、該当Review Statusで引き継ぎます。別実行は最新Linear / Harness / repositoryの証跡を再取得確認して、そのReview phaseだけを実行します。

## Git executor binding

local worktreeを利用できずGitHub Repositoryの読み書きが利用可能な対象Issueでは、論理的な `checkpoint` / `publish checkpoint` のactive Git executorを [references/remote-git.md](references/remote-git.md) に差し替えます。`git-add-commit-push` の意味づけは変更しません。

Workflowへ返す論理的な結果はlocal executorと同じです。

- 候補SHA / base SHA
- remote/ref
- scope / provenance確認結果
- published / not published
- verification結果またはBLOCKEDの理由

Human Acceptance前は候補ブランチだけを更新し、既定ブランチを更新しません。Closeでは受理済み候補SHAを変えずにtarget refへ公開します。

## 検証 / 引き継ぎの条件

Automated verification、CI Verification、Local Acceptance、Human Acceptanceの意味はcanonical `test.md` / `implementation.md` に従います。

- CIの根拠をAcceptanceへ使う場合は候補SHAとCI対象SHAを一致させる
- CI PASSをLocal AcceptanceまたはHuman AcceptanceのPASSへ昇格しない
- Close時の公開後CI判定はcanonical `../implementation-loop/references/close.md` を正本とし、remote adapterはprovider/connectorの通信だけを担当する。必須性、publish-trigger binding、PASS/停止条件をremote側へ複製しない
- remote環境でLocal Acceptanceを実行できない場合は、通常Issueを `Awaiting Acceptance` のまま維持し、候補SHA、entry point、必要environment/application、expected result、未確認理由を `implementation-completion` stateへ残す。Local Acceptance未実行をPASSへ昇格せず、local/canonical環境または人間へ引き継ぐ
- Human Acceptanceは `Awaiting Acceptance` で明示的人間確認まで未確認として維持する

Chat/Codex等の実行主体名をワークフロー状態にしません。Linear Status、canonical Plan、Comments、候補SHAを引き継ぎの条件とします。
