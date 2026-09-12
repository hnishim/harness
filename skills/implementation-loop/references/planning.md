# Planning + Plan Review

`Backlog`/`Todo`/`In Plan Review` で読む。共通契約とReview作法は `../SKILL.md` に従う。

`Spike` labelがある場合は [spike.md](spike.md) のPlanning差分も読む。

`Bug` labelがある場合は [bug.md](bug.md) のSymptom confirmation、`investigation` child、Root Cause Gate、Plan handoffを先に読む。

## Profile

- `Backlog`/`Todo` でユーザーがこの依頼内にstrictを明示指定した場合は、承認済みとして `Strict profile` labelを追加できる
- `In Plan Review` から開始した場合は既存labelだけを使う

## Backlog / Todo: Planning

`Backlog` と `Todo` は同じ処理を行います。既存Planがあればbaselineとして保持し、なければ新規作成します。`Bug` labelがある場合は、Planの作成・更新前に [bug.md](bug.md) の症状確認、調査子Issue、Root Cause Gateを完了します。

1. `Bug` labelがある場合は、親Bugの症状確認、調査子Issueの存在・`Spike` label・親子関係、調査結果とResult Reviewを再取得し、`ROOT_CAUSE_CONFIRMED` の記録を保存・再取得確認する。未確定・結果不明ならPlanを変更せずStatusを維持してBLOCKEDで停止する
2. 既存Description、Issue、Status、Comments、Labels、relations、Repository事実を照合し、正しい部分を維持して誤り・曖昧さ・不足を修正する
3. 目的、scope、要件対応、Repository根拠、実施項目、受入条件、検証、未確認事項を必要な範囲でcanonical Planへまとめる。`Test required` の場合はテスト戦略もまとめる。IssueのscopeまたはAcceptanceに関係する条件だけ、下記のruntime/contract/diagnostic/canonical確認を独立にPlanへ含める。Bug modeでは調査子Issueの最新結果、確認済みの原因、原因に直接対応する最小scope、bug caseと隣接正常caseの回帰Testを明記する
4. 通常Issueは専用Test成果物の要否を決め、TestグループLabelを判定と同じ1つにする。`Test required` の場合は主test layer、failure boundary、bug case/隣接regression、mock/fixture/static assertionの未検証範囲をPlanで決める。`Test not required` の場合は、`### テスト判定` の理由に既存validator・静的確認等で十分な根拠を記載し、failure boundary等がその判断に重要な場合だけ必要項目を追加する。Bug modeの判定は常に `Test required` とし、TestグループLabelもそれに一致させる
5. Canonical Plan、レビュー対象のPlan・成果物・差分、Issue ID、mode、profile、Test判定、`blockedBy` snapshotをPlan Review packetへ渡す。あわせて親Agentが作成するReview Context候補（`approved_scope`、`review_targets`、`meaningful_diff_at_review`、`comparison_basis`、`unverified`）を渡す。Bug modeでは調査子Issue、`BUG_INVESTIGATION_RESULT`、その根拠とResult Reviewもレビュー対象へ含める。`blockedBy` snapshotは今回のPlanが依存する現在の `blockedBy` のIssue IDを昇順で格納した `relations_snapshot` JSON objectとする。`blocks`/`relatedTo` はこのmetadataに含めない
6. 書き込み直前にDescription/Status/Labels/Planが依存する `blockedBy` を再取得してbaseline一致を確認し、Description/Labelsを保存・再取得確認してから `In Plan Review` へ更新する

Markerがなければ既存Descriptionを保持して末尾に1組作成します。既存Planが未canonicalの場合は重要情報を保持したまま `## 承認済みPlan`/`## 参考情報` へ正規化します。

通常IssueのPlanには次を1つだけ持ちます。

```markdown
### テスト判定
- 判定: Test required | Test not required
- 理由: <理由>
```

`Test not required` は専用Testコードを追加せず、既存validatorや静的確認等で受入条件を十分に検証できる場合に使います。

## 条件付きのruntime・contract・diagnostic・canonical確認

### Effective Runtime / Entry-point

Repository上のsourceと実利用経路が1段以上分離する場合だけ、Acceptanceに必要な範囲で次を記載します。

- Userが実際に起動するentry point
- Entry pointから変更対象までの関連chain
- Repositoryで編集するartifact/path
- Runtimeが参照するartifact/pathと、両者の同一性・対応を確認する方法

対象はhotkey/launcher、wrapper、symlink、generated config、installed/copied script、plugin/extensionなどです。Repository内で直接実行する純粋関数・単純CLI・Markdown-only変更にはruntime-chain確認を追加しません。Sourceを直接実行した成功は、分離したentry pointの成功と同義にしません。

### Actual Contract Impact

CLI引数、stdout/stderr、exit status、entry point、hotkey、script path、config形式、入出力形式、event、実callerが利用するlocal APIなどのcontractを変更する場合だけ、actual caller/consumer、contractを維持するか、同じscopeでcallerを更新できるかを記載します。Plan外のconsumer変更が必要ならcompatibility layerを追加せずreplanします。

### Diagnostic Evidence Fidelity

Failure調査またはruntime verificationでdiagnostic evidenceが必要な場合だけ、必要な範囲でexit status、stderr/safe error、OS/API error、failure phase、operation識別子、timeout条件などを記載します。Contract変更の有無とは独立して判定し、常設loggerやcorrelation IDなどの基盤は追加しません。

### Canonical Synchronization

既存canonicalのcomponent responsibility、lifecycle/state、mode/profile、model assignment、durable stop boundary、major SoT ownershipなどを変更する場合だけ、`agent-development-workflow.md` の同期を実施項目に含めます。Issue進捗、test result、temporary instrumentation、one-off detailはcanonicalへ複製しません。

`Test required` の通常IssueのPlanには、次のテスト戦略を1つだけ持ちます。`Test not required` のIssueにはこのschemaをN/A埋めのためだけに追加せず、`### テスト判定` の理由で受入条件を十分に検証できる根拠を示します。Failure boundary等がTest不要の判断に重要な場合だけ、関係する項目を記載します。

```markdown
### テスト戦略
- 主test layer: Unit | Integration | E2E / Acceptance | Static assertion | Manual check | 組み合わせ
- failure boundary: <不具合または受入条件が発生する実境界>
- bug case: <対象Bugでの再現ケース | 該当なし>
- 隣接regression: <維持する既存正常case | 該当なしと理由>
- mock / fixture / static assertionの未検証範囲: <内容 | なし>
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

Planning保存後はIssue、Description、Status、Labels、Planが依存する `blockedBy`、Commentsを再取得し、保存済みcanonical Plan、レビュー対象、mode/profile、`test_decision`、`blockedBy` snapshot、Review Context候補をReview handoffへ固定します。独立Reviewerを現在の実行から利用できる場合は同一top-level実行内の別read-only subagentへ渡してよい。利用できない場合は `In Plan Review` のままdurable stopし、別Chat等の独立実行へhandoffします。保存後のPlan Review Commentには、metadataとCanonical Review Resultとは別領域としてReview Contextの5項目を保存し、親Agentがreadbackして確認します。ReviewerはPlan本文と対象・差分を確認し、workflow metadataを変更せず返します。再取得値が保存前の意図と一致しない、または対象・差分を確認できない場合はBLOCKEDです。`relatedTo`／`blocks` の変更だけではBLOCKEDにしません。

## In Plan Review: Review

Plan Reviewは常に成果物作成主体とは**独立**したread-only Reviewerが実行します。executorの種類をworkflow metadataへ保存せず、entry pointにかかわらずReview packet、decision vocabulary、Status transition、durable stopを同じ契約で使います。

Review開始時は過去chatの結論を前提にせず、Issue / Status / Description / canonical Plan /全Comments / Labels / relations、最新Harnessのcanonical reference、repository evidenceとreview対象差分をfreshに再取得します。Plan作成主体と同一contextでpositive decisionを確定しません。

canonical/localで利用可能な既定Reviewerは次です。

- Lightweight Reviewer: `agents/plan-reviewer-lightweight.toml`（Terra/high、read-only）
- Strict: [strict-profile.md](strict-profile.md) を追加適用
- 判定： `APPROVE`/`CHANGES_REQUIRED`/`BLOCKED`

Reviewerは要求適合、Repository整合、受入条件、テスト戦略、failure boundary、検証可能性、未確認事項、レビュー対象のPlan・成果物・差分、mode/profile、Test判定、`blockedBy` snapshotと、PlanがIssue達成に必要な最小scopeであることを確認します。Effective Runtime/Entry-point、Actual Contract Impact、Diagnostic Evidence Fidelity、Canonical Synchronizationの4条件を独立に判定し、成立した条件に対応する範囲だけを確認します。存在確認やstatic evidenceだけでruntime成功を認定しません。Bugでは調査子IssueのResult、Root Cause Gate、原因とscopeの対応、回帰Testを確認します。`relatedTo`／`blocks` はscope・受入条件への実質影響がある場合だけ確認対象にします。

execution binding / adapter / context一般化を含む変更では、旧binding固有の暗黙前提がcanonical全体に残っていないか、新contextから旧context固有capabilityを除いた反例でも成立するか、既存context側の安全条件を弱めていないか、変更ファイルだけでなくtransitiveなcanonical referencesが整合するかも確認します。

One-off処理の恒久script/flag/専用entry pointは、Planに承認済み例外として記録されていない場合 `scope-removal` とします。

明示的な別要件がない限り、対象はsingle-userの個人Mac上で実行するlocal scriptまたは小規模automationのtrusted local environmentです。Planの抽象化、設定機構、framework、compatibility layer、依存追加、defensive infrastructure、将来対応は、現在のIssue要件、既存構成、安全性、データ保全、既存互換性の具体的な必要性と照合します。根拠のないscope外の複雑化は `scope-removal` とします。明示的なIssue要件や安全性・データ保全・互換性に必要な複雑さは受け入れ、将来の拡張性、一般論、industry best practice、style preferenceだけを理由にAcceptance-blockingにしません。

Spikeでは [spike.md](spike.md) のPlanning Review差分も適用します。Bugでは [bug.md](bug.md) の調査記録、原因とscopeの対応、回帰Testを確認します。

Canonical Review Resultのdecisionは `APPROVE`/`CHANGES_REQUIRED`/`BLOCKED` を使います。`APPROVE` では親Agentから渡された `test_decision`、`relations_snapshot` をそのまま返し、レビュー対象と結果をCommentへ保存します。

- `CHANGES_REQUIRED` → Comment保存後 `Todo` へ戻して停止
- `APPROVE` → `Test required` なら `Test Implementation`、`Test not required` なら `Implementation` へ更新して停止し、人間確認を待つ
- 判断不能 → 共通 `BLOCKED`
