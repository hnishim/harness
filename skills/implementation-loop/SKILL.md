---
name: implementation-loop
description: Linear Issue IDを入力としてStatusを読み、Backlog/Todo/In Plan ReviewのPlanning handoffをlinear-issue-plan-reviewへ委譲・統括し、HIR-42で承認されたImplementation Planの後段を、テスト専用ゲート・実装・独立レビュー・明示的なクローズ処理付きで実行する。Planの作成・レビュー・承認そのものは担当しない。
---

# Implementation Loop

## 役割と入力

- 入力はLinear Issue IDです。最初に親Agentが対象IssueのStatus、Description、全Comments、対象Repositoryのcommon directory/rootとworktree状態を取得します。各phaseの開始前にも同じ取得を行います
- Statusだけでphaseを選びます。Comment、成果物、過去の実行記録からphaseを推測しません
- Canonical Description blockを正本とします。既存の単独行 `CODEX_LINEAR_ISSUE_DESCRIPTION_START` と `CODEX_LINEAR_ISSUE_DESCRIPTION_END` の完全な1組を検証し、開始が終了より前であることを確認します。欠落、複数、順序不正、単独行でないmarkerはworker・reviewer起動とStatus更新を行わず停止します
- Marker間だけをcanonical blockとして扱い、marker外のDescriptionは保持します。Review履歴・実行時Status・回数・結果をmarker内へ追加せず、Plan専用markerも追加しません。Marker検証後に限り、canonical block内の `承認済みPlan` 見出しから同レベルの次の見出しの直前までをPlan範囲とし、marker欠落や見出しの曖昧さから推測しません
- implementation-loopはStatusを読み、Backlog/Todo/In Plan ReviewのPlanning handoffを`linear-issue-plan-review`へ委譲・統括するオーケストレーターです。HIR-42のPlanning入口とPlan作成・Plan Review・承認前処理を自ら実行せず、承認済みPlanの後段だけをこのSkill内で担当します。Planを作成・拡張・再解釈・承認しません
- Planの変更対象、制約、受入条件、保持すべき既存変更を固定し、範囲外の実装・テスト基盤・依存関係・専用Agent・別Skillを追加しません
- このSkillの起動は、本文に明示された対象IssueへのComment保存とWorkflow Status更新の承認を含みます。この対象範囲のLinear操作について起動後に追加承認を求めません。ただし、Status・Description・Plan・全Comments・成果物の再取得と一致確認、親Agent限定、phase gate、Plan範囲、安全停止条件を満たさない場合は書き込みやStatus更新を行わず停止します。既存の`git-add-commit-push`への委譲はこの承認範囲を拡張せず、同Skillの対象範囲・安全ゲート・有効なクローズ指示に従います。クローズ処理では、ユーザーの有効なクローズ指示を、外部リモートのdefaultブランチである`origin/main`への通常のfast-forward pushについて、宛先を明示した許可を明示的に与えたものとして扱います。この例外は`origin/main`以外の宛先、force push、その他の安全停止条件には適用しません
- 複雑化チェックでは、抽象化・設定化・依存追加・将来対応がIssueの受入条件、既存構成、安全性、互換性のいずれかに根拠と寄与を持つか確認します。4観点のいずれにも必要な根拠と寄与がない複雑化だけをAcceptance-blockingとし、いずれかの観点に根拠と寄与がある必要な複雑さ、style preference、Issue外の要求はブロッカーにしません。Plan、テスト、実装、レビューの同じ判断に適用します
- marker内のユーザー記述と生成領域を安全に区別できない既存blockは、推測で読み替え・上書きせず停止し、marker外の保持と保存前後の差分を確認してから再開します

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
- 以下の既存契約にあるすべての停止条件と終了報告へこの形式を適用し、入力/取得から権限・remote状態、外部書き込み後の再取得まで、観測事実と未確認事項を混在させません

## Phase routing

Statusを次のphaseへ対応づけます。親AgentだけがStatusを更新し、各遷移の前後にIssue、Description、全Comments、成果物を再取得します。

| Status | phase | 実行 | 成功時のStatus |
| --- | --- | --- | --- |
| `Backlog` | Planning | 親Agentが`Todo`へhandoffし、`plan-create-or-replan`は起動しない | `Todo` |
| `Todo` | Planning | `linear-issue-plan-review`の`plan-create-or-replan` | `In Plan Review` |
| `In Plan Review` | Plan Review | Issue ID + 明示的な`mode=plan-review`で既存PlanだけをReview | `APPROVE` + `Test required` → `Test Implementation`、`APPROVE` + `Test not required` → `Implementation`、`REVISE`/`REPLAN` → `Todo` |
| `Test Implementation` | Test Implementation | 既存implementer（Luna / medium） | `In Test Review` |
| `In Test Review` | Test Review | lightweight: `agents/reviewer-lightweight.toml`（Terra / high、read-only）；strict: `agents/reviewer.toml`（Sol / high、read-only） | `TESTS_APPROVED` → `Implementation`、`TESTS_CHANGES_REQUIRED` → `Test Implementation`、`PLAN_INCOMPLETE` → 停止 |
| `Implementation` | Implementation | 既存implementer（Luna / medium） | `In Implementation Review` |
| `In Implementation Review` | Implementation Review / Close | lightweight: `agents/reviewer-lightweight.toml`（Terra / high、read-only）；strict: `agents/reviewer.toml`（Sol / high、read-only）。PASS後は完了報告を保存してクローズ指示を待つ | `PASS` → `In Implementation Review` に留める。クローズ成功 → `Done`、`CHANGES_REQUIRED` → `Implementation`、material deviation → `Todo` |

その他のStatus、Issue ID・Description・Planの不一致、必要情報の欠落は書き込みなしで停止します。

- Plan Reviewのhandoffでは、Planに単一の判定値 `Test required` または `Test not required`、判定理由、対応するLabelがあり、TestグループLabelが判定値と一致して1つだけで、非Test Labelが保持されていることを確認します。不一致・重複・判定不能・取得不能は実装へ進めず停止します
- `Test required` は `In Plan Review → Test Implementation → In Test Review → Implementation` を維持し、`approved-tests` の固定ベースラインを使います。`Test not required` は `In Plan Review → Implementation` とし、Test Implementation、In Test Review、専用テストコード、`approved-tests` 固定ベースラインを要求しません

## Test Implementation

1. Worker起動前に、親AgentはStatus、canonical Descriptionと承認済みPlan、全Comments、Label、Repository/worktreeを再取得します。canonical Planにテスト要否判定がちょうど1つだけあり、その値が `Test required` で、TestグループLabelがちょうど1つだけ存在し同じ `Test required` に一致することを確認した場合だけ、implementerを開始します
2. 判定が `Test not required`、PlanとLabelの不一致・重複・判定不能・取得不能、または必要情報のStatus不一致・取得不能の場合は、workerを起動せず、外部書き込みも行わず、現在Statusを維持して共通の `STATUS: BLOCKED` 形式で停止します。明示的に再開されたときだけ同じphaseの開始ゲートを再適用します
3. 承認済みPlanを唯一の基準に、Requirements、Plan、Acceptance Criteriaから公開動作単位のテストを作ります。成功経路、該当する失敗・境界・異常終了・外部副作用を扱い、単なるキーワード有無や脆い正規表現で意味検証を代用しません
4. テスト、fixture、helper、依存関係、生成物の追加がPlanにない場合は追加しません。Skill定義の意味検証など一時的なチェックは対象ファイルを変更せず実行できます
5. Implementerの出力は既存契約の `STATUS / CHANGES / TESTS / RISKS / BLOCKER` を検証します。`STATUS: BLOCKED` は妥当な停止として、BLOCKERを親AgentがCommentへ記録します。Completion Commentと成功側Status更新は行わず、現在Statusを維持し、自動再実行しません
6. 成功時は、テスト結果、成果物の相対パス・SHA-256、検証コマンド、Repository common directory/root、未検証事項をcompletion Commentへ記録し、保存前後の再取得で確認できた場合だけ `In Test Review` へ遷移します

## Test Review

1. Reviewer起動前に、親AgentはStatus、canonical Descriptionと承認済みPlan、全Comments、Label、Repository/worktreeを再取得します。canonical Planにテスト要否判定がちょうど1つだけあり、その値が `Test required` で、TestグループLabelがちょうど1つだけ存在し同じ `Test required` に一致することを確認した場合だけ、reviewerを開始します
2. 判定が `Test not required`、PlanとLabelの不一致・重複・判定不能・取得不能、または必要情報のStatus不一致・取得不能の場合は、reviewerを起動せず、外部書き込みも行わず、現在Statusを維持して共通の `STATUS: BLOCKED` 形式で停止します。`Test not required` は承認済みPlanのhandoff後に直接 `Implementation` を開始し、このTest Reviewを経由しません
3. Reviewerには `review_phase: tests-only` を渡します。lightweightは`agents/reviewer-lightweight.toml`、strictは既存の`agents/reviewer.toml`を選びます。判定は `TESTS_APPROVED`、`TESTS_CHANGES_REQUIRED`、`PLAN_INCOMPLETE` だけです。Reviewerはread-onlyで、Linearやworktreeを変更しません
4. `TESTS_APPROVED` の場合、Planで要求された専用テスト成果物がすべて存在することを確認し、各テストの相対パス、SHA-256、再実行コマンド、テストマトリクス、手動確認をapproved-tests固定ベースラインとしてCommentに記録します。`Test required` の専用テスト成果物が1つでも不足している場合は `TESTS_APPROVED` にせず、`TESTS_CHANGES_REQUIRED` として不足内容を記録します。`Test required` のapproved-testsでは、相対パス・SHA-256に `N/A` を使用しません
5. `Test required` の `TESTS_APPROVED` では、保存前後にapproved-testsの相対path・SHA-256・再実行commandを再取得して一致確認し、確認できた場合だけ親Agentが `Implementation` へStatusを更新します。一致しなければStatusを変えず停止します。`Test required` の `Implementation` は `TESTS_APPROVED` の確認済みで、`In Test Review` からだけ進めます。以後、`Test required` のapproved-testsの削除、弱体化、skip、無断変更はできません。`Test not required` はこのゲートおよびapproved-tests契約の対象外で、承認済みPlanのhandoff後に直接 `Implementation` を開始します。`Test not required` の検証ベースラインに限り、専用テスト成果物の相対パス・SHA-256を `N/A` とできます
6. `TESTS_CHANGES_REQUIRED` では指摘をCommentへ記録して `Test Implementation` へStatusを戻します。Strict-profileの最大2回を適用し、2回目も必要なら `TEST_DESIGN_BLOCKED` として停止します
7. `PLAN_INCOMPLETE` では不足・矛盾をCommentへ記録し、Statusを変更せず停止します。必要なら `PLAN_BLOCKED` として扱いますが、新しいLinear Statusは追加しません。いずれもDoneへ進めません

## Implementation

1. `Test required` の場合、このphaseは `In Test Review` で `TESTS_APPROVED` を確認して `Implementation` へ遷移した場合だけ開始します。`Test not required` の場合はPlan Reviewの承認後に直接開始できます。いずれも親Agentが開始時にStatus、Description、全Comments、Label、Repository/worktreeを再取得し、対象Planの判定値とLabelを確認します。`Test required` ではapproved-tests固定ベースラインも再取得し、`TESTS_APPROVED` とテスト相対パス・SHA-256・再実行コマンドが一致しない場合は実装しません
2. `Test required` では同じimplementerに承認済みPlanとapproved-testsを渡します。`Test not required` では承認済みPlanだけを渡し、専用テスト成果物を要求しません。後者では、検証ベースラインとして検証コマンド、対象ファイル、テスト成果物がN/Aである判定理由を固定します。いずれもPlanの範囲だけを実装し、既存変更を保持します。Workerが必要な成果物または検証を完了できない場合は `STATUS: BLOCKED` として扱います
3. 成功時は、RequirementsからImplementationまでのtraceability、scope、変更ファイル、成果物相対パス・SHA-256（`Test not required` の専用テスト成果物は `N/A`）、検証ベースライン（検証コマンド・対象ファイル・テスト成果物N/Aの判定理由）、common directory/root、Status transition（from/to/phase）、未検証事項をcompletion Commentへ記録し、保存前後の再取得で確認できた場合だけ `In Implementation Review` へ遷移します。実際のLinear handoff記録の追補・保存は親Agentだけが行います

## Implementation Review

- Reviewerには `review_phase: implementation` を渡します。lightweightは`agents/reviewer-lightweight.toml`、strictは既存の`agents/reviewer.toml`を選びます。`Test required` ではRequirements → Plan → Tests → Implementationの対応とapproved-testsの弱体化を、`Test not required` ではRequirements → Plan → 検証ベースライン → Implementationの対応とテスト成果物N/Aの妥当性を確認させます。いずれも正確性、回帰、hack、edge、error、不要な複雑化、無関係変更、security・privacyを確認させます。判定は `PASS` または `CHANGES_REQUIRED` だけです
- `PASS` の場合、親Agentは `Done` へStatus更新せず、Issue ID、`PASS`、承認済みPlanの識別情報、変更・検証結果、Agentが抽出した残作業（`残作業: なし` または具体的な項目）、未検証事項、次の定型文を含むcompletion Commentを保存します。保存前後にIssue、Description、全Comments、Repository/worktreeを再取得し、対象Issueに一意に保存できたことを確認した場合だけ `In Implementation Review` に留めます。定型文は次のとおりです: `結果を確認し、問題がなければ「クローズ処理してください」または「クローズ処理」と返信してください`
- completion Comment直後の同一会話における対象ユーザーの次の発話だけをクローズ指示の候補にします。前後の空白と末尾句読点を除いた最後の文節が `クローズ処理してください` または `クローズ処理` と完全一致する場合だけ有効とし、`OK`、絵文字、「完了」だけ、質問、否定、引用、説明中の文言、別実行への指示は無効としてGit処理・Done化を行いません。runtimeが同一会話の直後の発話を確実に識別できない場合も採用せず、`In Implementation Review` で停止します
- クローズ指示を採用する直前に、対象Issue ID、現在のStatus、同じIssueに保存された一意のImplementation Review `PASS` completion Commentを再取得して照合します。対象Issue IDがcompletion Commentと一致しない場合、または現在のStatusが `In Implementation Review` 以外（`Done`、`In Test Review`、`Implementation` など）の場合は、クローズ指示を許可として扱わず、Git処理・Done化を行いません。次の確認プロンプトを表示して停止します: `確認が必要です。<Issue ID> は現在 <Status> で、クローズ可能な In Implementation Review ではありません。対象Issue IDと実行フェーズを確認し、必要なら In Implementation Review へ戻してから、もう一度クローズ処理を指示してください。`
- 有効なクローズ指示を受けた場合、親AgentはIssue、Description、Status、全Comments、completion Comment、Repository/worktreeを再取得し、対象・保存済みPASS記録・ベースラインが一致した場合だけ既存の `git-add-commit-push` Skillを `git-actions`（またはSkill記載の代替Agent）へ委譲します。新しいGit操作、snapshot、結果packetは設計せず、Git executorはLinearへ書き込みません
- Git executorの結果を親Agentがresult receiptとして保存・再取得確認します。Git処理の成功または変更なしを確認できた場合だけ `Done` へStatus更新します。secret、競合、Git途中状態、remote先行・分岐、force push要求、失敗、部分成功、timeout、receipt不備、状態不明ではDone化せず、結果を記録して `In Implementation Review` で停止します。自動再試行・自動復旧は行いません
- `Done` 更新後、親AgentはIssue、Description、全Comments、result receipt、Repository/remote同期状態を再取得し、Statusが `Done` で、completion Comment・receipt・既存記録が維持されていることを確認します。確認できない場合は状態不明として追加操作を停止します
- `CHANGES_REQUIRED` は指摘をCommentへ記録して `Implementation` へ戻し、3回目になった時点で `REVIEW_LIMIT_REACHED` として停止します。非PASSをDone扱いにしません
- Material deviationは通常修正せず、期待値、観測値、対象成果物、影響範囲、未承認であることをCommentへ記録し、成果物と既存記録を保持したまま親Agentが `Todo` へ戻します。HIR-42で再Planningした後、新しいTest Reviewを行います

## Packet、再開、Linear更新

- Workerの見出し欠落・STATUS不一致・必要成果物やCommentの欠落、reviewerのJSON不正・phase不一致・想定外判定は不正packetです。親Agentは通常Reviewと区別して、同じagent（Reviewer packetは同じreviewer）へschemaまたはStatusの訂正を1回だけ求められます。訂正後も不正ならStatusを変えず、事実と停止理由をCommentへ記録して停止します
- LinearのCommentとStatusを更新できるのは親Agentだけです。Comment保存前後、Status更新前後にIssue、Description、全Comments、成果物を再取得し、対象・phase・from/to Status・成果物相対パス・hashが期待値と一致した場合だけ次へ進みます
- 保存済みtransition Comment、from/to Status、phase、成果物相対パス・hashが一致する場合だけ同じphaseを再開できます。欠落、重複、不一致、hash不一致なら再実行せず停止します。すでにto StatusならStatusを再更新しません
- CommentにはTest/Implementationのcompletion、Review、Status遷移、traceability、Repository common directory/root、成果物相対パス・SHA-256、検証コマンドを記録します。Review履歴、実行時Status、回数、結果はDescriptionへ書きません

## 共通方針と安全策

- 内容と実装は目的達成に必要な最小限とし、要件のない抽象化、設定化、依存関係、リファクタリングを追加しません
- 無関係な既存変更を保持します。Planが明示的に許可しない限り、リセット、破棄、上書き、ステージ、コミット、プッシュ、PR作成、別IssueやHIR-42への書き込み、破壊的操作をしません。許可されたIssueのComment・Status更新は親Agentだけが行います
- 権限不足、継続する検証失敗、指示の衝突、重大なPlan逸脱があれば停止します。`PLAN_BLOCKED`、`TEST_DESIGN_BLOCKED`、`REVIEW_LIMIT_REACHED`、invalid packetはDoneへ進めません
- 厳格プロファイルの開始ゲート、scenario数、agent契約、レビュー回数、完了・非PASS報告は [references/strict-profile.md](references/strict-profile.md) に従います。Implementerとreviewerが利用できない場合だけ、同等の実装担当・独立reviewerへ代替し、実効種別・モデル・推論設定と理由を記録します
