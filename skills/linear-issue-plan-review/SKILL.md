---
name: linear-issue-plan-review
description: "指定されたLinear Issueのinitial-planをRepository上の事実で検証・具体化し、既存Planをrefineするか新規Planを作成して保存する。承認済みPlanの実装は扱わない。"
---

# Linear Issue Plan Review

Linear IssueをSource of TruthとしてRepositoryを確認し、canonical Planを作成またはRepository-awareにrefineします。Planの実装は行いません。

## プロファイル

- Plan保存、読み取り専用Review、レビューComment、限定的なworkflow Status handoffは標準処理です
- IssueとRepositoryから、単一ユーザーの短いローカルスクリプトで、共有サービス・本番データ・機密情報・権限・不可逆な外部副作用・データ損失リスクがなく、厳格なレビューやテスト先行の指定もないと確認できる場合は軽量プロファイルを使い、`agents/plan-reviewer-lightweight.toml`（Terra/high、read-only）を選びます
- それ以外は、厳格プロファイルが必要な根拠を示してユーザーの確認・承認を得ます。Skill起動による対象Issueへの明示されたLinear操作の承認とは別に、厳格プロファイルの確認が必要な場合は、その確認なしにstrictのAgentを起動しません。承認後は [references/strict-profile.md](references/strict-profile.md) を読み、`agents/plan-reviewer.toml`（Sol/high、read-only）を選びます
- タイトルが `Spike:` で始まる、または `Spike` ラベルがある場合は、選択したプロファイルに加えて [references/spike-mode.md](references/spike-mode.md) を読みます

## 共通契約

- 開始時概要表示は、Issue取得、入力検証、Status検証がすべて成功した後、最初の進行メッセージで行います。現在チャットの過去のアシスタント出力だけを確認し、同じIssue IDの同一形式の概要行が既にあれば表示しません。ユーザー発言や引用中の文字列は表示済み判定に使いません。未表示の場合は、次の1行だけを追加します: `Issue概要: <Issue ID> — <Issue title>`。Issue取得失敗、Issue ID不一致、StatusまたはDescription検証による `BLOCKED` 時は概要を推測表示しません。Planning委譲から `current_issue_id` と `issue_summary_displayed=true|false` を受けた場合は、その値をチャット履歴より優先し、Issue IDが一致するとき `true` なら表示しません。
- 対象はStatusが `Backlog`、`Todo`、または `In Plan Review` のIssueです。`Backlog` は `Todo` へhandoffし、`Todo` だけが `plan-create-or-replan` を1回実行してPlan作成または再Planを行います。`In Plan Review` は、Issue IDと明示的な `mode=plan-review` を受けた場合に限り、canonical Description block内の既存PlanだけをReviewし、新規Planは作成しません
- `Backlog` ではPlan作成・再Plan処理を起動しません
- `Backlog` はblockなし、`Todo` の既存blockは未検証baselineです。`In Plan Review` はcanonical Description blockがあり、既存PlanのReviewまたは保存後のhandoffを回復する場合だけ対象にします
- Issue IDが一意でない、Description blockを安全に特定できない、入力取得に失敗・競合がある場合はLinearを変更せず `BLOCKED` とします。推測で補いません
- Repositoryは、明示パス、現在workspace、workspaceから一意に決まるGit rootの順で決めます。不明・複数候補・検証不能なら書き込み前に停止します
- Issueは `linear_get_issue`、Commentsは `linear_list_comments`（Cursorで最後まで）、保存は `linear_save_issue`、Commentは `linear_save_comment` を使います
- 開始時にIssue、Description、Status、identifier、labels、project/team、全Commentsを取得し、`description_baseline`、`status_baseline`、`comments_baseline` を固定します
- 外部書き込みは対象IssueのDescription、レビューComment、workflow Status、およびTestグループのLabel 1つの置換だけです。いずれも対象Issueに限り、親Agentだけが実行します。Subagentは読み取り専用です。Testグループ以外のLabel、タイトル、担当者、関連付け、marker外のDescriptionは保持し、Label置換を含む保存前後にbaselineと再取得結果を検証します
- このSkillの起動は、本文に明示された対象IssueのDescription保存、レビューComment保存、workflow Status handoff、およびTestグループLabel 1つの置換の承認を含みます。Label置換は対象Issueに限り親Agentだけが行い、Testグループ以外のLabelを保持し、保存前baselineと保存後再取得結果を検証します。この対象範囲のLinear操作について起動後に追加承認を求めません。ただし、対象外Issue・対象外Comment/Status/Label・親Agent以外による更新、baseline・marker・取得結果の不一致、その他本文の安全停止条件に該当する場合は実行せず停止します
- 複雑化チェックでは、抽象化・設定化・依存追加・将来対応がIssueの受入条件、既存構成、安全性、互換性のいずれかに根拠と寄与を持つか確認します。4観点のいずれにも必要な根拠と寄与がない複雑化だけをAcceptance-blockingとし、いずれかの観点に根拠と寄与がある必要な複雑さ、style preference、Issue外の要求はブロッカーにしません
- Description block本文にStatus、Review cycle、終端状態を保存しません。Workflow Statusを唯一の状態管理とします
- 新しいcanonical markerは、Linearが変換しないASCII単独行の1組です。完全な1組以外（複数、片側欠落、逆順、境界不明）は `BLOCKED` とします
- Description markerがない場合はcanonical Description blockなしとして扱います。Descriptionの見出しだけから範囲を推測しません
- 実装へ引き渡すcanonical Planは、marker内の単独な `## 承認済みPlan` から、その後に置く単独な同レベル `## 参考情報` の直前までとします。Plan本文の見出しは `###` 以下にし、Plan範囲内に同レベルの `##` 見出しを置きません。`承認済みPlan` または終端 `参考情報` の欠落・複数・順序不正・Plan内の同レベル見出しは `BLOCKED` とします
- `承認済みPlan` は実装ループがPlan範囲を識別するための構造名であり、レビュー判定やWorkflow Statusを表しません。承認状況はReviewerのCommentとWorkflow Statusで管理します
- 既存blockをrefineするときにこの構造がなければ、内容を削除せず、既存の末尾単独 `## 参考情報` は終端として再利用し、それ以外の見出しを相対階層ごと1段下げたうえで `## 承認済みPlan` 配下に置きます（`##` は `###`、`###` は `####`）。終端がなければmarker内末尾に追加します。marker外の内容は保持します
- marker内のユーザー記述と生成領域を安全に区別できない既存blockは、推測で置換せず `BLOCKED` とし、marker外の保持と保存前後の差分を確認してから再開します

## 停止・再開報告（共通形式）

入力・取得、canonical marker/Plan、Agent/packet、検証、保存・再取得、権限/外部/remote状態、終了報告のいずれかで停止するときは、次の最小形式を使います。既存の停止名やStatusを置き換えず、該当する停止点を明記します。

```text
STATUS: BLOCKED
STOP POINT: <入力/取得|canonical marker/Plan|Agent/packet|検証|保存・再取得|権限/外部/remote状態|終了報告>
INPUT / STOP CONDITION: <入力、前提、または停止条件>
OBSERVED FACTS OR REQUIRED CONFIRMATION: <確定原因なら観測事実、未確定なら確認事項>
CAUSE CERTAINTY: CONFIRMED | UNCONFIRMED
IMPACT OR RESTART CONDITION: <影響、または再開に必要な条件>
RECOMMENDATION: <推奨する次の行動>
STATUS / COMMENT / RETRY: <Status、Comment保存の扱い、再試行可否>
```

- `CONFIRMED` は観測事実から原因を確定できる場合だけ使い、原因・観測事実・影響を記載します。`UNCONFIRMED` では原因を推測せず、必要な確認事項・再開条件・推奨行動を記載します
- `STATUS / COMMENT / RETRY` には既存Statusを維持するか既存遷移を行うか、Commentを保存したか保存しないか、既存契約上許される再試行だけを記載します。自動再試行、新しいStatus、停止履歴のDescription追加は行いません
- 以下の既存契約にあるすべての停止条件と終了報告へこの形式を適用し、入力/取得から外部書き込み後の再取得まで、観測事実と未確認事項を混在させません

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

## `mode=plan-review` 分岐

この分岐は、一般のPlan作成・再PlanおよびDescription保存手順より先に選択します。Issue IDと明示的な `mode=plan-review` を受けた `In Plan Review` では、最新Issue、canonical Description、全Comments、Repositoryを再取得し、canonical marker内の既存Planだけを読み取り専用でReviewします。新規Planの作成、既存Planの拡張・再解釈、Description保存は行いません。Review結果が `APPROVE` の場合だけ、Planのテスト要否が `Test required` なら `Test Implementation`、`Test not required` なら `Implementation` へ返し、`REVISE` または `REPLAN` の場合は `Todo` へ返します。mode不在、Issue ID不一致、canonical Plan不備、テスト要否の不一致・判定不能、またはReview対象の不一致は、一般のPlan作成へフォールバックせず `BLOCKED` とします。

## Plan作成とReview

1. Issue、全Comments、確定Repository、ローカル指示、対象codebase、既存Description blockを確認します。Descriptionが空なら、通常modeでは停止し、Spike modeでは検証目的が明確な場合だけ最小Planを作成します
2. 既存block内の正しい部分は維持し、Repositoryの事実で誤り・曖昧さ・不足だけを該当箇所へ反映します。新規Planには目的、範囲、要求との対応、Repositoryの根拠、実施項目、受入条件、検証、未確認事項を含め、これらは `## 承認済みPlan` 配下の `###` 以下に記載します。Issueにない仕様を発明しません
3. 軽量プロファイルではCycle管理をせず、親Agentが `agents/plan-reviewer-lightweight.toml` の別Agent Reviewerを1つ起動します。Reviewerは要求適合、範囲、Repositoryの根拠、検証可能性、未確認事項を読み取り専用で確認し、`APPROVE`、`REVISE`、`REPLAN` とFindingsを1回返します。具体的な問題だけDescription blockを修正し、同じReviewerに1回だけ再確認させます。好みや任意改善はブロッカーにせず、情報・方針不足は `PLAN_BLOCKED` とします
4. 厳格プロファイルでは [references/strict-profile.md](references/strict-profile.md) のPlanner、Reviewer、Cycle契約を適用します

### テスト要否の確定

- Plan確定時に、実装に専用テスト成果物が必要かを単一の判定値 `Test required` または `Test not required` として決めます。判定理由と、対象ファイル・検証方法との対応をPlanの受入条件または検証に記載します。`Test not required` は、Skill定義などを専用テストコードなしで既存のSkill検証、静的確認、意味のあるシナリオ確認により検証する場合に限ります
- LabelはTestグループ（`Test required`、`Test not required`）を判定値に一致する1つへ置換し、Testグループ以外のLabelは保持します。TestグループLabelの不一致・重複、判定不能、Label取得不能は、Plan保存や実装へのhandoffを行わず `BLOCKED` とします
- Plan保存後のIssue再取得で、判定値、判定理由、TestグループLabelが一致し、非Test Labelが保持されていることを確認します。確認できない場合はStatusを進めず停止します

## Description保存とStatus handoff

- Description markerがなければ最新Description末尾に1組追加し、あればその内側だけを置換します。保存するblockには `## 承認済みPlan` と終端 `## 参考情報` を1組だけ含めます。保存直前にIssueを再取得し、DescriptionとStatusがbaselineに一致することを確認します。不一致・取得不能は `BLOCKED` です
- 保存後にIssueを再取得し、意図したDescription block、`承認済みPlan` の範囲、Plan内の見出しレベル、終端、marker外の保持、保存前の期待Statusを確認します。初回保存が未達で、再取得値が保存前baselineと完全一致する場合だけ1回再試行します。それ以外の未達、差分、取得不能、検証不能は `BLOCKED` とします
- Description block保存と再取得確認が成功し、開始Statusが `Todo` の場合だけ、親Agentが `In Plan Review` へ更新します。更新前後にStatus、Description block、marker外を再取得確認します。中断後にすでに同じblockで `In Plan Review` なら再更新しません
- 開始Statusが `Backlog` の場合は、親Agentが `Todo` へ変更するだけで、Description保存や `In Plan Review` への直接遷移は行いません。`Backlog` から `In Plan Review` へ進むには、Todoへの変更後に改めて `Todo` 開始としてPlan作成・再Planを実行する必要があります
- `In Plan Review` へのhandoff確認後、親Agentが次のCommentを1件保存します。保存直前に全CommentsとIssue（Status、Description block、marker外）のbaselineを再固定し、保存後に完全一致するCommentが1件だけ増えたことを確認します。重複・不明・取得不能なら再投稿やStatus更新をしません

```text
Issue ID: <issue-identifier>
Decision: APPROVE|REVISE|REPLAN
Findings: reviewerの指摘全文
```

- Comment確認後、`APPROVE` はPlanのテスト要否に従い、`Test required` なら `Test Implementation`、`Test not required` なら `Implementation` へ更新します。`REVISE`/`REPLAN` は `Todo` へ更新します。Status更新前後にComment、Plan、marker外、判定値、Labelを再取得します。期待するCommentとStatusがすでに存在する場合は再投稿・再更新しません。それ以外のStatusや矛盾するCommentは `BLOCKED` とします

## 終了報告

軽量プロファイルではReviewer判定、Plan保存・各再取得、Status handoff、レビューComment、未確認事項を報告します。厳格プロファイルではstrict参照の形式に従います。実Linearやクラウド側を実行していない場合は `UNVERIFIED` と明記し、成功扱いしません。
