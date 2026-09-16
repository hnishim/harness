# Planning + Plan Review

`Backlog`/`Todo`/`In Plan Review` で読む。共通契約とReview作法は `../SKILL.md` に従う。

`Spike` labelがある場合は [spike.md](spike.md) のPlanning差分も読む。

`Bug` labelがある場合は [bug.md](bug.md) の症状確認、`investigation` child、Root Cause Gate、Planの引き継ぎを先に読む。

## Profile

- `Backlog`/`Todo` でユーザーがこの依頼内にstrictを明示指定した場合は、承認済みとして `Strict profile` labelを追加できる
- `In Plan Review` から開始した場合は既存labelだけを使う

## Backlog / Todo: Planning

`Backlog` と `Todo` は同じ処理を行います。既存Planがあればbaselineとして保持し、なければ新規作成します。`Bug` labelがある場合は、Planの作成・更新前に [bug.md](bug.md) の症状確認、調査子Issue、Root Cause Gateを完了します。

1. `Bug` labelがある場合は、親Bugの症状確認、調査子Issueの存在・`Spike` label・親子関係、調査結果とResult Reviewを再取得し、`ROOT_CAUSE_CONFIRMED` の記録を保存・再取得確認する。未確定・結果不明ならPlanを変更せずStatusを維持してBLOCKEDで停止する
2. 既存Description、Issue、Status、Comments、Labels、relations、Repositoryの事実を照合し、正しい部分を維持して誤り・曖昧さ・不足を修正する
3. 目的、範囲、要件対応、Repositoryの根拠、実施項目、受入条件、検証、未確認事項を必要な範囲でcanonical Planへまとめる。`Test required` の場合はテスト戦略もまとめる。Issueの範囲またはAcceptanceに関係する条件だけ、下記の実行時・仕様・診断・canonical確認を独立にPlanへ含める。Bug modeでは調査子Issueの最新結果、確認済みの原因、原因に直接対応する最小範囲、bug caseと隣接正常caseの回帰Testを明記する
4. 通常Issueは専用Test成果物の要否を決め、TestグループLabelを判定と同じ1つにする。`Test required` の場合は主test layer、失敗発生境界、bug case/隣接regression、mock/検証用データ/static assertionの未検証範囲をPlanで決める。`Test not required` の場合は、`### テスト判定` の理由に既存validator・静的確認等で十分な根拠を記載し、失敗発生境界等がその判断に重要な場合だけ必要項目を追加する。Bug modeの判定は常に `Test required` とし、TestグループLabelもそれに一致させる
5. Canonical Plan、レビュー対象のPlan・成果物・差分、Issue ID、mode、profile、Test判定、`blockedBy` snapshotをPlan Reviewのレビュー資料へ渡す。あわせて親Agentが作成するReview Context候補（`approved_scope`、`review_targets`、`meaningful_diff_at_review`、`comparison_basis`、`unverified`）を渡す。Bug modeでは調査子Issue、`BUG_INVESTIGATION_RESULT`、その根拠とResult Reviewもレビュー対象へ含める。`blockedBy` snapshotは今回のPlanが依存する現在の `blockedBy` のIssue IDを昇順で格納した `relations_snapshot` JSON objectとする。`blocks`/`relatedTo` はこのmetadataに含めない
6. 書き込み直前にDescription/Status/Labels/Planが依存する `blockedBy` を再取得してbaseline一致を確認し、Description/Labelsを保存・再取得確認してから `In Plan Review` へ更新する

### Descriptionの管理範囲 / canonical Planの境界

Descriptionの管理範囲はAgentの管理領域ではなく、必要な場合に人間が明示する保護範囲を正本とします。

```text
HUMAN_AUTHORED_START
...
HUMAN_AUTHORED_END
```

Agent / AIは自動で `HUMAN_AUTHORED_START/END` を付けない・作成しない。marker内の内容は変更・削除せず保持します。markerがないDescriptionはAgent管理領域という意味ではなく、既存の意味内容を踏まえて整理可能な通常Descriptionです。

旧 `CODEX_LINEAR_ISSUE_DESCRIPTION_START/END` はlegacy互換入力としてだけ認識し、新規には作成しません。legacy markerの内外にある既存テキストと意味内容を失わないよう保持しながら現行layoutへ正規化し、CODEX markerをAgent / AIの管理範囲や人間による保護の根拠にしません。`HUMAN_AUTHORED_*` またはlegacy CODEX markerが複数、片側欠落、逆順、入れ子等の不正・不整合で境界を一意に決められない場合はDescriptionを書き換えずBLOCKEDです。

canonical PlanはDescription内に次のtop-level見出しを**1つずつ**持ち、`## 承認済みPlan` から `## 参考情報` の直前までを一意なtop-level範囲の境界とします。Plan内部の見出しは `###` 以下です。

```markdown
## 承認済みPlan
...
## 参考情報
...
```

canonical Planは元Descriptionの背景・目的・要件を不要に全文複製しません。既存内容との重複をしない形で、実装・Reviewに必要な追加整理と決定だけを保持します。legacy CODEX layoutを正規化するときも既存の意味内容は保持します。

通常IssueのPlanには次を1つだけ持ちます。

```markdown
### テスト判定
- 判定: Test required | Test not required
- 理由: <理由>
```

`Test not required` は専用Testコードを追加せず、既存validatorや静的確認等で受入条件を十分に検証できる場合に使います。

## 条件付きの実行時・仕様・診断・canonical確認

### Effective Runtime / Entry-point

Repository上のソースと実利用経路が1段以上分離する場合だけ、Acceptanceに必要な範囲で次を記載します。

- Userが実際に起動するentry point
- Entry pointから変更対象までの関連chain
- Repositoryで編集する成果物/path
- Runtimeが参照する成果物/pathと、両者の同一性・対応を確認する方法

対象はhotkey/launcher、wrapper、symlink、generated config、installed/copied script、plugin/extensionなどです。Repository内で直接実行する純粋関数・単純CLI・Markdown-only変更にはruntime-chain確認を追加しません。ソースを直接実行した成功は、分離したentry pointの成功と同義にしません。

### Actual Contract Impact

CLI引数、stdout/stderr、exit status、entry point、hotkey、script path、config形式、入出力形式、event、実callerが利用するlocal APIなどの取り決めを変更する場合だけ、actual caller/consumer、取り決めを維持するか、同じ範囲でcallerを更新できるかを記載します。Plan外のconsumer変更が必要ならcompatibility layerを追加せずreplanします。

### Diagnostic Evidence Fidelity

失敗調査または実行時検証で診断の根拠が必要な場合だけ、必要な範囲でexit status、stderr/safe error、OS/API error、failure phase、operation識別子、timeout条件などを記載します。取り決め変更の有無とは独立して判定し、常設loggerやcorrelation IDなどの基盤は追加しません。

### Canonical Synchronization

既存canonicalのcomponent responsibility、lifecycle/state、mode/profile、model assignment、永続的な停止境界、major SoT ownershipなどを変更する場合だけ、`agent-development-workflow.md` の同期を実施項目に含めます。Issue進捗、test result、temporary instrumentation、one-off detailはcanonicalへ複製しません。

`Test required` の通常IssueのPlanには、次のテスト戦略を1つだけ持ちます。`Test not required` のIssueにはこのschemaをN/A埋めのためだけに追加せず、`### テスト判定` の理由で受入条件を十分に検証できる根拠を示します。失敗発生境界等がTest不要の判断に重要な場合だけ、関係する項目を記載します。

```markdown
### テスト戦略
- 主test layer: Unit | Integration | E2E / Acceptance | Static assertion | Manual check | 組み合わせ
- 失敗発生境界: <不具合または受入条件が発生する実境界>
- bug case: <対象Bugでの再現ケース | 該当なし>
- 隣接regression: <維持する既存正常case | 該当なしと理由>
- mock / テスト用データ / static assertionの未検証範囲: <内容 | なし>
- 状態待ち: <観測可能な状態変化 | 固定delayと理由 | 該当なし>
```

Bug modeでは次を必ず満たします。

```markdown
### 原因調査
- 調査子Issue: <root-cause `investigation` 用のSpike子Issue>
- 記録: <最新のBUG_INVESTIGATION_RESULT Comment>
- Root Cause Gate: PASS
- 確認済み原因: <原因>
- 根拠: <原因を裏付ける証拠>

### テスト判定
- 判定: Test required
- 理由: <原因を再現し、修正前FAIL・隣接正常caseの維持・修正後PASSを検証する回帰Test>
```

### One-off

1回限りのmigration/cleanup/backfillは安全な手動手順を優先します。恒久script/flag/専用entry pointは、手作業が複雑・反復的で誤操作riskが高くscript化が明確に有利で、かつユーザーが承認した場合だけPlanへ含め、理由と承認を記録します。

## Plan Review state

Plan保存後はIssue、Description、Status、Labels、Planが依存する `blockedBy`、Commentsを再取得し、保存済みcanonical Plan、レビュー対象、mode/profile、`test_decision`、`blockedBy` snapshot、Review Context候補をReviewの引き継ぎ情報として固定します。

`state_key: plan-review` の可変フェーズ状態CommentをPlan Review状態の唯一の現在スナップショットとして使います。state Commentが存在しない初回だけ新規Commentを作成し、そのComment IDを保持します。既存の同じ `state_key` Commentがある場合は、レビュー資料、Review Context、`unverified`、現在のPlan/review targetsを**同じComment IDへ更新**します。同じ論理状態について別のCommentは追加しない・作成しない。追記だけのスナップショットを増やしません。

レビュー資料を保存した後、独立Reviewerは同じフェーズ状態Commentを読み、Review Resultを**同じCommentへ更新**します。レビュー資料とReview Resultを別Commentへ全文複製しません。`APPROVE` のような指摘事項のない承認Reviewは現在の判定と必要metadataをこのstateへ更新します。`CHANGES_REQUIRED` / 具体的な `BLOCKED` 等の重要なイベントは共通immutable eventの取り決めに従い別のイベントCommentへ追記し、フェーズ状態は必要ならそのComment IDを参照します。

独立Reviewerを現在の実行から利用できる場合は同一top-level実行内の別read-only subagentへ渡してよい。利用できない場合は `In Plan Review` のまま永続的に停止し、`plan-review` stateのレビュー資料から別Chat等の独立実行へ引き継ぎます。再取得値が保存前の意図と一致しない、または対象・差分を確認できない場合はBLOCKEDです。`relatedTo`／`blocks` の変更だけではBLOCKEDにしません。

## In Plan Review: Review

Plan Reviewは常に成果物作成主体とは**独立**したread-only Reviewerが実行します。executorの種類をワークフローmetadataへ保存せず、entry pointにかかわらずレビュー資料、判定の語彙、Status transition、永続的な停止を同じ取り決めで使います。

Review開始時は過去chatの結論を前提にせず、Issue / Status / Description / canonical Plan /全Comments / Labels / relations、最新Harnessのcanonical reference、リポジトリの根拠とレビュー対象差分を最新状態として再取得します。Plan作成主体と同一contextで承認判定を確定しません。

canonical/localで利用可能な既定Reviewerは次です。

- Lightweight Reviewer: `agents/plan-reviewer-lightweight.toml`（Terra/high、read-only）
- Strict: [strict-profile.md](strict-profile.md) を追加適用
- 判定： `APPROVE`/`CHANGES_REQUIRED`/`BLOCKED`

Reviewerは要求適合、Repository整合、受入条件、テスト戦略、失敗発生境界、検証可能性、未確認事項、レビュー対象のPlan・成果物・差分、mode/profile、Test判定、`blockedBy` snapshotと、PlanがIssue達成に必要な最小範囲であることを確認します。Effective Runtime/Entry-point、Actual Contract Impact、Diagnostic Evidence Fidelity、Canonical Synchronizationの4条件を独立に判定し、成立した条件に対応する範囲だけを確認します。存在確認や静的な根拠だけでruntime成功を認定しません。Bugでは調査子IssueのResult、Root Cause Gate、原因と範囲の対応、回帰Testを確認します。`relatedTo`／`blocks` は範囲・受入条件への実質影響がある場合だけ確認対象にします。

execution binding / adapter / context一般化を含む変更では、旧binding固有の暗黙前提がcanonical全体に残っていないか、新contextから旧context固有capabilityを除いた反例でも成立するか、既存context側の安全条件を弱めていないか、変更ファイルだけでなく間接的なcanonical referencesが整合するかも確認します。

One-off処理の恒久script/flag/専用entry pointは、Planに承認済み例外として記録されていない場合 `scope-removal` とします。

明示的な別要件がない限り、対象はsingle-userの個人Mac上で実行するlocal scriptまたは小規模automationのtrusted local environmentです。Planの抽象化、設定機構、framework、compatibility layer、依存追加、defensive infrastructure、将来対応は、現在のIssue要件、既存構成、安全性、データ保全、既存互換性の具体的な必要性と照合します。根拠のないscope外の複雑化は `scope-removal` とします。明示的なIssue要件や安全性・データ保全・互換性に必要な複雑さは受け入れ、将来の拡張性、一般論、industry best practice、style preferenceだけを理由にAcceptance-blockingにしません。

Spikeでは [spike.md](spike.md) のPlanning Review差分も適用します。Bugでは [bug.md](bug.md) の調査記録、原因とscopeの対応、回帰Testを確認します。

Canonical Review Resultのdecisionは `APPROVE`/`CHANGES_REQUIRED`/`BLOCKED` を使います。`APPROVE` では親Agentから渡された `test_decision`、`relations_snapshot` をそのまま返し、`plan-review` stateのReview Resultとして更新します。

- `CHANGES_REQUIRED` → immutable event保存とphase state更新後 `Todo` へ戻して停止
- `APPROVE` → phase state更新後、`Test required` なら `Test Implementation`、`Test not required` なら `Implementation` へ更新して停止し、人間確認を待つ
- 判断不能 → 共通 `BLOCKED`
