# Spike

`Spike` labelのIssueで読む。共通契約とReview作法は `../SKILL.md` に従う。

Spikeは `Test not required` とし、専用Test phaseを使いません。

## Planning差分

Planは完成品の実装手順ではなく、仮説、検証論点、観測方法、採用/不採用の判断基準を中心に作ります。

- Experiment/PoCはDecisionに必要な最小コード・計測・fixtureに限定する
- 受入条件は各検証点を成功・失敗・未検証に分類でき、次のDecisionを導けること
- 本番データ、認証情報、課金、権限、security/privacy、不可逆変更など安全に暫定判断できない事項は共通 `BLOCKED`
- 実験対象がwrapper、launcher、symlink、generated config、installed/copied artifactなどを介する場合は、Decisionに必要な範囲でactual entry point、関連execution context、Repository artifactとruntime artifactの対応を固定する。Sourceやcommandの存在だけでruntime有効・実行成功とは扱わない
- 実験で失敗を観測する場合は、genericな結果だけでなく必要なexit status、stderr/safe error、error code、failure phase、operation識別子、timeout条件を残す。常設loggerや不要な秘密・個人情報は追加しない

Planning Reviewではコード品質より、仮説・観測・判断基準がDecisionに十分かを確認します。

## Bug `investigation` child

親に `Bug` labelが付いた調査子Issueでは、Spikeをroot-cause `investigation` として使います。専用Status、Bug専用Agent、専用Test phaseは追加しません。親Bugの実行から再帰的に呼び出さず、子Issue自身を独立したimplementation-loop入力として実行します。

- 親Bugの症状を再現・観測し、期待動作と実際の動作を分けて記録する
- 1件以上の仮説を列挙し、plausible alternativesが存在する場合だけ各仮説の予測とそれらを識別するdiscriminating testを記録する
- 検証結果、直接的なEvidence、Rejected hypotheses、未確認事項を保存する
- 修正が成功したことだけを原因の証拠にしない
- Result Commentは `BUG_INVESTIGATION_RESULT` 契約（[bug.md](bug.md)）を使い、結論を `ROOT_CAUSE_CONFIRMED`、`ROOT_CAUSE_UNCONFIRMED`、`BLOCKED` のいずれかで明示する
- `ROOT_CAUSE_CONFIRMED` は、症状を説明する因果関係を直接観測できるEvidenceがあり、plausible alternativesがある場合はそれらも識別できる場合だけ使う。明白な原因で合理的なalternativeがない場合に架空の第二仮説を作らない

調査子Issueの結論が `ROOT_CAUSE_CONFIRMED` でない場合、親BugはPlanへ進まず、親のStatusを維持します。親Bugが調査結果を再取得してから、通常のFix Planと回帰Testへ接続します。

## Baseline and diagnostic cleanup

Implementation途中の親IssueからSpikeまたは別Issueへ分岐する場合、未完成のproduction変更はhandoff前にlogical `checkpoint` を **active Git executor** へ委譲して固定します。canonical/local bindingでは従来どおり `git-add-commit-push` の `checkpoint` を使用し、remote bindingではremote Git executorのcheckpoint contractを使用します。完成候補でないため、local bindingでは `WIP(<Issue ID>): checkpoint before <child Issue ID> investigation` のようなmessageを使えます。

Checkpoint結果のSHAを `baseline_commit` として親Issueと子IssueのCommentへ記録し、active Git bindingに対応するtarget ref / provenanceもreadbackします。子Spikeはその `baseline_commit` を基点に開始し、SHAとbinding情報の記録・readbackが完了する前に子Issueへ制御を移しません。Remote共有が必要なhandoffでは、送信先remote/refを先に確定し、親AgentがLinearへ記録・readback済みの親Issue checkpoint chainについて、そのtarget refからのlive reachabilityを確認します。Target refから到達不能で今回の通常pushに含めることを許可するcheckpointだけを古い順に `allowed_checkpoint_shas` とし、target `baseline_commit`、理由、送信先とともに `publish-checkpoint` へ渡します。別remote/refへ先行push済みでも今回のtarget refから未到達なら含め、target refから既に到達可能なら含めません。Git executorがtarget refからcandidateまでのoutgoing commit chain全体と許可列の完全一致を確認できた場合だけ通常pushし、対象Issue外・由来不明・未承認commit、許可列の不足・余剰・順序不整合、remote先行/分岐があればpushせずBLOCKEDとします。先行push結果をCommentへ保存する場合は送信先remote/refと対応づけます。

一時diagnosticの追加とCleanupは親Issueのproduction変更と別の差分として扱います。Cleanupはdiagnostic差分だけを除去し、親baselineのproduction scopeを巻き戻しません。Cleanup後は **active Git binding** で `baseline_commit`、candidate/ref、対象pathの差分をreadbackし、diagnostic差分だけが除去され、親production scopeがbaselineから意図せず変化していないことを確認します。local bindingでは必要に応じてlocal Git stateを確認し、remote bindingではcandidate ref/treeを確認します。cleanupまたはruntime verificationに必要なcapabilityがremoteで利用できない場合は未検証としてhandoffし、確認済みとは扱いません。

## `Implementation`: Experiment / PoC

1. Implementer（原則Luna/medium）へ承認済みExperiment Planを渡す
2. Decisionに必要な最小のPoC、計測、fixture、実験を行う。親Issueまたは別Issueへのhandoffが発生する場合は、前節のcheckpointと `baseline_commit` 記録を先に完了する
3. 各検証論点について条件、観測結果、再現手順、成功/失敗/未検証を記録する。Source/static evidenceとruntime evidenceを分け、`Current / Verified`、`Proposed / Target`、`Unverified` を必要な主張ごとに明示する
4. 実験結果をCommentへ保存し `In Implementation Review` へ更新する

## `In Implementation Review`: Result Review

- Lightweight Reviewer: `agents/reviewer-lightweight.toml`（Terra/high、read-only）
- Strict: [strict-profile.md](strict-profile.md) を追加適用
- 判定： `DECISION_READY`/`CHANGES_REQUIRED`/`MATERIAL_DEVIATION`

証拠の十分性、偏り、再現性、Planの判断基準との対応を確認します。

Canonical Review Resultのdecisionは `DECISION_READY`/`CHANGES_REQUIRED`/`MATERIAL_DEVIATION`/`BLOCKED` を使います。親Agentは実験結果、対象成果物、検証観測、Planの判断基準をReviewerへ渡します。成果物Fingerprintは算出・受渡し・照合しません。

- `DECISION_READY` → 採用方式、制約、未対応範囲、追加Spikeの要否をCommentへ保存してClose待ち
- `CHANGES_REQUIRED` → `Implementation` へ戻す
- `MATERIAL_DEVIATION` → Planや仮説の再設計が必要な理由をCommentへ保存して `Todo` へ戻し停止する
