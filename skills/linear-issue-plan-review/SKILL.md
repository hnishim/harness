---
name: linear-issue-plan-review
description: "指定されたLinear Issueのinitial-planをRepository上の事実で検証・具体化し、既存Planをrefineするか新規Planを作成して保存する。承認済みPlanの実装は扱わない。"
---

# Linear Issue Plan Review

Linear IssueをSource of TruthとしてRepositoryを確認し、canonical Planを作成またはRepository-awareにrefineします。Planの実装は行いません。

## プロファイル

- Plan保存、読み取り専用Review、レビューComment、限定的なworkflow Status handoffは標準処理です
- IssueとRepositoryから、単一ユーザーの短いローカルスクリプトで、共有サービス・本番データ・機密情報・権限・不可逆な外部副作用・データ損失リスクがなく、厳格なレビューやテスト先行の指定もないと確認できる場合は軽量プロファイルを使います
- それ以外は、厳格プロファイルが必要な根拠を示してユーザーの確認・承認を得ます。承認なしにstrictのAgent起動、Plan保存、Comment保存、Status変更を行いません。承認後は [references/strict-profile.md](references/strict-profile.md) を読みます
- タイトルが `Spike:` で始まる、または `Spike` ラベルがある場合は、選択したプロファイルに加えて [references/spike-mode.md](references/spike-mode.md) を読みます

## 共通契約

- 対象はStatusが `Backlog` または `Todo` のIssueです。`In Plan Review` は、canonical Description blockがありレビューComment保存前のhandoffを回復する場合だけ対象にします。`Backlog` はblockなし、`Todo` の既存blockは未検証baselineです
- Issue IDが一意でない、Description blockを安全に特定できない、入力取得に失敗・競合がある場合はLinearを変更せず `BLOCKED` とします。推測で補いません
- Repositoryは、明示パス、現在workspace、workspaceから一意に決まるGit rootの順で決めます。不明・複数候補・検証不能なら書き込み前に停止します
- Issueは `linear_get_issue`、Commentsは `linear_list_comments`（Cursorで最後まで）、保存は `linear_save_issue`、Commentは `linear_save_comment` を使います
- 開始時にIssue、Description、Status、identifier、labels、project/team、全Commentsを取得し、`description_baseline`、`status_baseline`、`comments_baseline` を固定します
- 外部書き込みは対象IssueのDescription、レビューComment、workflow Statusだけです。実行するのは親Agentだけで、Subagentは読み取り専用です。タイトル、担当者、ラベル、関連付け、marker外のDescriptionは保持します
- Description block本文にStatus、Review cycle、終端状態を保存しません。Workflow Statusを唯一の状態管理とします
- 新しいcanonical markerは、Linearが変換しないASCII単独行の1組です。完全な1組以外（複数、片側欠落、逆順、境界不明）は `BLOCKED` とします
- Description markerがない場合はcanonical Description blockなしとして扱います。Descriptionの見出しだけから範囲を推測しません
- 実装へ引き渡すcanonical Planは、marker内の単独な `## 承認済みPlan` から、その後に置く単独な同レベル `## 参考情報` の直前までとします。Plan本文の見出しは `###` 以下にし、Plan範囲内に同レベルの `##` 見出しを置きません。`承認済みPlan` または終端 `参考情報` の欠落・複数・順序不正・Plan内の同レベル見出しは `BLOCKED` とします
- `承認済みPlan` は実装ループがPlan範囲を識別するための構造名であり、レビュー判定やWorkflow Statusを表しません。承認状況はReviewerのCommentとWorkflow Statusで管理します
- 既存blockをrefineするときにこの構造がなければ、内容を削除せず、既存の末尾単独 `## 参考情報` は終端として再利用し、それ以外の見出しを相対階層ごと1段下げたうえで `## 承認済みPlan` 配下に置きます（`##` は `###`、`###` は `####`）。終端がなければmarker内末尾に追加します。marker外の内容は保持します

```text
CODEX_LINEAR_ISSUE_DESCRIPTION_START
## 承認済みPlan

### 目的

（標準Description。要件、実施内容、受入条件、検証、未確認事項を必要に応じて含める）
### 参考情報

（Planに含める参考情報）
## 参考情報

（Plan外の参考情報。なければ空欄）
CODEX_LINEAR_ISSUE_DESCRIPTION_END
```

- Description blockの由来を見出し名や内容から推測せず、initial-planとCodex Planningは同じcanonical Description blockを段階的に更新します。Planの内容は `## 承認済みPlan` 配下へ集約し、REVISE/REPLANでもmarkerを追加しません
- Initial-planのクラウド側Skillを修正する必要がある場合は、既存版を先に取得して内容を変えずRepositoryへ取り込み、修正・検証後に利用可能な経路で反映し、再取得して一致を確認します。経路がなければ捏造せず `PLAN_BLOCKED` とします

## Plan作成とReview

1. Issue、全Comments、確定Repository、ローカル指示、対象codebase、既存Description blockを確認します。Descriptionが空なら、通常modeでは停止し、Spike modeでは検証目的が明確な場合だけ最小Planを作成します
2. 既存block内の正しい部分は維持し、Repositoryの事実で誤り・曖昧さ・不足だけを該当箇所へ反映します。新規Planには目的、範囲、要求との対応、Repositoryの根拠、実施項目、受入条件、検証、未確認事項を含め、これらは `## 承認済みPlan` 配下の `###` 以下に記載します。Issueにない仕様を発明しません
3. 軽量プロファイルではCycle管理をせず、親Agentが別AgentのReviewerを1つ起動します。Reviewerは要求適合、範囲、Repositoryの根拠、検証可能性、未確認事項を読み取り専用で確認し、`APPROVE`、`REVISE`、`REPLAN` とFindingsを1回返します。具体的な問題だけDescription blockを修正し、同じReviewerに1回だけ再確認させます。好みや任意改善はブロッカーにせず、情報・方針不足は `PLAN_BLOCKED` とします
4. 厳格プロファイルでは [references/strict-profile.md](references/strict-profile.md) のPlanner、Reviewer、Cycle契約を適用します

## Description保存とStatus handoff

- Description markerがなければ最新Description末尾に1組追加し、あればその内側だけを置換します。保存するblockには `## 承認済みPlan` と終端 `## 参考情報` を1組だけ含めます。保存直前にIssueを再取得し、DescriptionとStatusがbaselineに一致することを確認します。不一致・取得不能は `BLOCKED` です
- 保存後にIssueを再取得し、意図したDescription block、`承認済みPlan` の範囲、Plan内の見出しレベル、終端、marker外の保持、保存前の期待Statusを確認します。初回保存が未達で、再取得値が保存前baselineと完全一致する場合だけ1回再試行します。それ以外の未達、差分、取得不能、検証不能は `BLOCKED` とします
- Description block保存と再取得確認が成功し、開始Statusが `Backlog` または `Todo` なら、親Agentだけが `In Plan Review` へ更新します。更新前後にStatus、Description block、marker外を再取得確認します。中断後にすでに同じblockで `In Plan Review` なら再更新しません
- `In Plan Review` へのhandoff確認後、親Agentが次のCommentを1件保存します。保存直前に全CommentsとIssue（Status、Description block、marker外）のbaselineを再固定し、保存後に完全一致するCommentが1件だけ増えたことを確認します。重複・不明・取得不能なら再投稿やStatus更新をしません

```text
Issue ID: <issue-identifier>
Decision: APPROVE|REVISE|REPLAN
Findings: reviewerの指摘全文
```

- Comment確認後、`APPROVE` は `Test Implementation`、`REVISE`/`REPLAN` は `Todo` へ更新します。Status更新前後にComment、Plan、marker外を再取得します。期待するCommentとStatusがすでに存在する場合は再投稿・再更新しません。それ以外のStatusや矛盾するCommentは `BLOCKED` とします

## 終了報告

軽量プロファイルではReviewer判定、Plan保存・各再取得、Status handoff、レビューComment、未確認事項を報告します。厳格プロファイルではstrict参照の形式に従います。実Linearやクラウド側を実行していない場合は `UNVERIFIED` と明記し、成功扱いしません。
