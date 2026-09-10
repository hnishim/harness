---
name: implementation-loop
description: Linear IssueのStatusから必要なphaseを判定し、Bugでは調査用子Spikeの証拠ベースRoot Cause Gateを先行して、Planning、Test、Implementation、Spike、独立Review、明示的Closeまでを単一入口で進める。
notion_sync: false
---

# Implementation Loop

## 役割

入力はLinear Issue IDです。Statusから基準referenceを選びます。

| Status | 読むreference |
| --- | --- |
| `Backlog` / `Todo` / `In Plan Review` | [references/planning.md](references/planning.md) |
| `Test Implementation` / `In Test Review` | [references/test.md](references/test.md) |
| `Implementation` / 通常Issueの `In Implementation Review` | [references/implementation.md](references/implementation.md) |
| `In Implementation Review`（SpikeのResult Review） | [references/spike.md](references/spike.md) |
| `Done` | なし |
| その他のStatus（`Pending` / `Canceled` / `Duplicate` 等） | 対象外Statusを報告して終了。Issue・Description・Comment・Label・Status・Repositoryを変更せず、独自fallbackやStatus変換を行わない |

`Spike` labelと `Bug` labelはmode modifierです。両方が付いている場合はmodeを一意に判定できないためBLOCKEDです。Planningでは `Spike` labelなら [references/spike.md](references/spike.md)、`Bug` labelなら [references/bug.md](references/bug.md) を `planning.md` に追加します。Bugの `Backlog`/`Todo` では、症状確認後に既存のSpike flowを使う調査用子Issueを冪等に作成・再利用し、`ROOT_CAUSE_CONFIRMED` の結果とRoot Cause Gateを確認してから親BugのPlanを作成します。Bugは `Test required` 固定です。Spikeの `Implementation`/`In Implementation Review` では `spike.md` を `implementation.md` の代わりに使います。通常Issueの `In Implementation Review` は人間レビュー待ちであり、AIの独立Reviewは実行しません。SpikeがTest Statusにある場合はBLOCKEDです。

通常Issueが `Implementation` 完了時に `In Implementation Review` へ到達した場合は、`implementation.md` の人間レビュー待ちとして扱います。

`Strict profile` labelはReview profile modifierです。独立Review時だけ [references/strict-profile.md](references/strict-profile.md) を追加します。

Close待ちで明示的Close指示を受けた場合だけ [references/close.md](references/close.md) を読みます。

## 共通契約

- PhaseのSource of TruthはStatus
- ModeのSource of Truthは `Spike` または `Bug` label。両方なし=normal、いずれか1つ=該当mode、両方あり=BLOCKED
- ProfileのSource of Truthは `Strict profile` label。あり=strict、なし=lightweight
- Phase開始前にIssue、Status、Description、全Comments、Labels、relations（依存関係）、Repository root/worktree/適用されるlocal instructionsを再取得する
- Repositoryは明示パス、現在workspace、そこから一意に決まるGit rootの順で確定する
- Linearへの書き込みは親Agentが行う。このSkillの起動は、本文と各referenceで定義した対象IssueのDescription/Comment/TestグループLabel/Status更新への承認を含む。Bug modeの `Backlog`/`Todo` では、必要な場合に限り、調査子Issueの新規作成、`parentId` 設定、既存 `Spike` label付与、初期Status `Backlog` 設定、作成・再利用した子Issue IDの親Commentへの保存とreadbackもこのwrite scopeに含む。`Bug` と `Spike` labelを同じIssueへ付けず、`Strict profile` labelの新規付与は明示的なユーザー承認を必要とする
- Linearの参照・更新は専用Linear API/connectorを使用する。LinearをComputer Use/GUIで参照・操作せず、専用経路が利用不能な場合もGUIへ自動fallbackせずBLOCKEDとする。ユーザーがLinear UI自体の確認・操作を明示した場合だけComputer Useを使用できる
- 書き込み直前に対象フィールドを再取得してbaseline一致を確認し、書き込み後も意図した差分だけを再取得確認する
- Marker外のDescription、Testグループ以外のLabels、title、assignee、relations等を保持する
- Workflow Status、Review回数、Review結果はCommentへ残す
- 作業scopeは承認済みPlanの範囲・制約・受入条件に限定する
- Bug調査は親Bugの症状確認と、`Spike` labelの調査子Issueに分離する。親Bugの1回の実行では子Issueの検索・必要時の冪等な作成・親へのID保存・readbackまでを行い、子Issueが未完了なら親のStatusを維持して停止する。子Issueは独立したIssue IDで別のimplementation-loop入力として既存Spike flowを進み、親の再実行で `BUG_INVESTIGATION_RESULT` とResult Reviewを再取得する。証拠がRoot Cause Gateを満たす場合だけ親BugのFix Planへ進む。調査子Issueを重複作成せず、`Bug` と `Spike` labelを同じIssueに付けない
- Test判定が `Test required` のPlanは、主test layer、failure boundary、bug case、隣接regression、mock/fixture/static assertionの未検証範囲、状態待ちを必要な範囲で明示する。外部境界を置き換えたTestやstatic assertionだけをruntime behaviorの証拠にしない
- Phase作業・Review開始前、およびReviewer findingを採用する前に、現在の依頼内でユーザーが明示した要件・制約とcanonical Planの整合を確認する
- 明示指示がcanonical Planのscope・behavior・受入条件を実質的に変更しないclarificationなら、その指示を作業・Reviewer packetへ反映して現phaseを継続する。Reviewer findingがそのclarificationと衝突する場合は実装せず、clarificationを含むpacketでReviewをやり直す
- 明示指示がcanonical Planを実質的に変更する場合は、古いPlanのまま実装・Review・finding採用・正判定保存を行わない。Statusを `Todo` へ戻して停止し、次回Planningでcanonical Planへ反映する。ユーザーの意思がすでに明確なら再確認を要求しない
- 無関係なworktree変更を保持する

Repositoryやbaselineを一意に確認できない場合はBLOCKEDです。

開始時、Issue取得とStatus検証に成功したら、各chatで1回だけ `Issue概要: <Issue ID> — <title>` を表示します。

停止時は次の形式で報告します。

```text
結果: BLOCKED
停止箇所: <取得|canonical Plan|Repository|Agent|検証|保存|Git/外部>
確認事項: <確認できた事実。原因未確定ならその旨>
推奨対応: <推奨する次の行動>
再開条件: <再開に必要な条件>
```

## Canonical Description / Plan

Description管理領域は次のASCII marker 1組です。

```text
CODEX_LINEAR_ISSUE_DESCRIPTION_START
...
CODEX_LINEAR_ISSUE_DESCRIPTION_END
```

実装へ渡すPlanはmarker内の `## 承認済みPlan` から終端 `## 参考情報` の直前までです。両見出しは1つずつ、Plan内部の見出しは `###` 以下とします。

- `Backlog`/`Todo` でmarkerがない場合の作成・既存Planの正規化は `planning.md` に従う
- `In Plan Review` 以降は正しいmarkerとcanonical Planを必須とする
- 通常IssueはPlan内のTest判定とTestグループLabelが `Test required`/`Test not required` のどちらか1つで一致していることを必須とする
- Bugは、調査子Issueの最新 `BUG_INVESTIGATION_RESULT`、その `ROOT_CAUSE_CONFIRMED` の根拠とResult Review、親のRoot Cause GateをPlanが参照し、Plan内のTest判定が `Test required` であることを必須とする。子Issueが未完了または結果不明なら親のPlanへ進まない
- Spikeは `Test not required`

Markerの複数、片側欠落、逆順、境界不明はBLOCKEDです。

### Plan / phase gate

- Plan Reviewでは、canonical Planの境界、レビュー対象のPlan・成果物・差分、Issue／mode／profile／Test判定／`blockedBy` をCommentへ明記し、以後のphase開始前に現在値と意味のある変更を再確認します。`blocks` と `relatedTo` はこのmetadataに含めません
- Plan Review Commentには、Canonical Review Resultとは別の親Agent所有のReview Context envelopeを保存します。最小形式は `approved_scope`、`review_targets`、`meaningful_diff_at_review`、`comparison_basis`、`unverified` とし、Plan全文snapshotやFingerprintの代わりにはしません。親Agentが作成・保存・後続phaseで照合し、Reviewerは既存のCanonical Review Resultだけを返します
- `Implementation`、通常Issueの `In Implementation Review`、`Test Implementation`、`In Test Review`、Spikeの `In Implementation Review`、Close開始前は、現在のcanonical Plan、mode/profile、Test判定Label、Planが依存する `blockedBy`、最新Comments、Repository/worktreeを再取得します。`blocks`/`relatedTo` はscope・受入条件への実質影響がある場合だけ個別に確認します
- Bugの `Test Implementation` 以降は、調査子Issueの最新 `BUG_INVESTIGATION_RESULT` とResult Review、親のRoot Cause Gate、Planがその記録・原因・bug case・隣接regressionを参照していることも再確認します。調査子Issueが未完了、結果不明、または調査対象や原因の根拠が変わっている場合は古いPlanを使わず `Todo` へ戻して停止します
- 最新のPlan Review Comment自体が `APPROVE` で、Issue／mode／profile／Test判定／`blockedBy` snapshotと、レビュー対象・意味のある差分の確認が現在値と整合する場合だけ次phaseへ進みます。要求・scope・受入条件に影響する変更、対象・差分が不明、より新しい `CHANGES_REQUIRED`/`BLOCKED`、または判断不能なら古いAPPROVEを使わず停止します
- Canonical Planが有効な未Done Issueで、最新Plan Review Commentに `test_decision` または `relations_snapshot` がない場合は、Plan本文を変更せず `In Plan Review` へ戻してfresh Plan Reviewを実施します。Freshな正判定の新Commentだけを証拠とし、既存Done Issueを一括再Reviewしません
- Comment欠落、Issue／scope／acceptance／mode／profile／Test判定／`blockedBy` の不一致、第三者編集、結果不明、権限不足はBLOCKEDです。`relatedTo`／`blocks` の変更だけではBLOCKEDやfresh Reviewの理由にしません

レビュー後の意味のある変更は、対象path、Git差分、実験結果、または外部readbackなど利用可能な証拠で確認します。表記・空白のみの変更は、それだけで再Review理由にしません。対象・差分を確認できない場合は古い承認を流用せず停止します

## Review共通契約

Planning、Test、Resultの各独立Reviewに共通して次を適用します。

- Reviewerは成果物がIssue達成に必要な最小scopeかを確認する
- `scope-removal` は、残置cost/riskが除去・再検証costを上回る実質的なscope外複雑性に限る
- 明示的な別要件がない限り、対象はsingle-userの個人Mac上で実行するlocal scriptまたは小規模automationのtrusted local environmentです。Plan、Test、Implementation、Result Reviewでは、抽象化、設定機構、framework、compatibility layer、依存追加、defensive infrastructure、将来対応を、現在のIssue要件、既存構成、安全性、データ保全、既存互換性の具体的な必要性と照合します。根拠のないscope外の複雑化は `scope-removal` とし、明示的な要件や安全性・データ保全・互換性に必要な複雑さはAcceptance-blockingにしません。将来の拡張性、一般論、industry best practice、style preferenceだけでは複雑さを正当化しません
- Reviewerはphaseを進める前に修正必須の指摘だけを出し、各findingに `acceptance`/`safety`/`bug`/`scope-removal` の分類、具体的根拠、影響、必要最小の修正を含める
- 親AgentはReviewerの技術判断を再Reviewせず、canonical Review Resultのschema、workflow metadata、decision/findings整合だけを検証する
- Reviewerはread-only
- Reviewerは親Agentの現在の実行内で、ユーザーから見えるtop-level task/threadをReviewer専用に新規作成せず、同期的な独立read-only subagentとして起動します
- 同phaseの再Reviewでは、親Agentが最新の同phase Review Resultと、前回Reviewを受けた今回の修正roundで実際に変更した内容をReviewer packetへ含める。前回必須findingの修正と今回の修正roundを主対象とする
- 新しい必須findingは、今回の修正roundで新たに発生した、前回時点では観測不能だった、または前回判定を覆す新しい具体的根拠が得られた場合だけ追加できる。前回non-blocker・既存dirty・scope外と扱った事項を必須へ再分類する場合も、新しい具体的根拠を明示する
- 同じphaseで変更要求判定が2回連続した場合は、finding内容が異なっていても2回連続とみなす。通常のbackward transitionを行った後、その実行を停止する
- Reviewer利用不能または判断不能はBLOCKEDとする

### Canonical Review Result

Reviewerは親Agentから `phase`、`issue`、`profile`、`mode` とphase固有metadataを受け取り、次のJSON objectだけを返します。これをReview結果の唯一のschemaとします。

```json
{
  "phase": "Plan Review|Test Review|Result Review",
  "issue": "HIR-123",
  "profile": "lightweight|strict",
  "mode": "normal|spike|bug",
  "test_decision": null,
  "relations_snapshot": null,
  "decision": "phase-specific decision",
  "findings": [
    {
      "id": "F1",
      "category": "acceptance|safety|bug|scope-removal",
      "evidence": "具体的根拠",
      "impact": "具体的影響",
      "required_change": "必要最小の修正"
    }
  ],
  "blocker": null,
  "approved_tests": null
}
```

Workflow metadataの扱い：

- `phase`/`issue`/`profile`/`mode` は親Agentが渡した値をReviewerがそのまま返す
- Plan Reviewでは、親Agentが渡した `test_decision` と `relations_snapshot`（`blockedBy` のみ）を変更せず返す。Plan Review以外は両方とも `null`
- Test Reviewでは、親AgentがTest Implementationのpath/SHA-256/再実行command/必要な手動確認を `approved_tests` 候補として渡す。`TESTS_APPROVED` の場合だけReviewerがその値を返し、それ以外は `null`
- その他のphase固有metadataは `null`

親AgentはJSON parse、必須key、workflow metadata一致、phaseで許可されたdecision、decision/findings/blockerの整合、finding必須項目を検証します。不正なら形式訂正を1回だけ求め、再度不正ならBLOCKEDです。親Agentは有効なReview Resultの意味を書き換えません。

Decision整合：

- 正判定： `findings=[]`、`blocker=null`
- 変更要求・`PLAN_INCOMPLETE`・`MATERIAL_DEVIATION`: `findings` を1件以上、`blocker=null`
- `BLOCKED`: `findings=[]`、`blocker` に判断不能の具体的理由

`BLOCKED` は共通BLOCKEDとして停止し、Statusを維持します。それ以外のcanonical Review Resultは、値を変えずに次のMarkdownへ整形してLinear Commentへ保存します。

```text
フェーズ: <phase>
対象Issue: <issue>
プロファイル: <profile>
モード: <mode>
test_decision: <Plan Reviewで非nullの場合だけ>
relations_snapshot: <Plan Reviewで非nullの場合だけJSON>
判定: <decision>
必須指摘: <findings。なければ なし>
approved-tests: <approved_testsが非nullの場合だけ>
```

JSONからMarkdownへの整形はrepresentationの変更だけとし、decision、finding、workflow metadataを追加・削除・再分類しません。`test_decision` と `relations_snapshot` も同じ値を保存します。

## Routing / 停止境界

保存・再取得確認後のforward transitionは同じ実行内で継続できます。

次は停止境界です。

- Plan Review `APPROVE` 後： 次Statusへ更新して停止し、人間確認を待つ。以後の明示的な `implementation-loop` 実行を人間確認後の再開指示として扱う
- `CHANGES_REQUIRED`/`PLAN_INCOMPLETE`/`MATERIAL_DEVIATION` で `Todo` へ戻った場合
- 同一Review phaseで2回連続の変更要求になった場合
- 通常IssueのImplementation完了後は、検証・Human Acceptance確認点をCommentに保存し、Statusを `In Implementation Review` に更新して人間レビュー待ちとする。通常IssueではAIの独立Reviewを実行しない。Human Acceptanceで問題があれば、明示再開後にImplementationで修正・再検証する
- Spikeの `DECISION_READY` のClose待ち
- BLOCKED
- `Done`

Plan Review後の次回実行は、`Test required` なら `test.md`、`Test not required` なら `implementation.md` から開始します。`TESTS_APPROVED` 後は同一実行で `implementation.md` へ進めます。

Bug modeは常に `Test required` のため、Plan Review `APPROVE` 後は `Test Implementation` へ進みます。症状確認と調査子IssueのRoot Cause GateはPlan作成前に完了している必要があり、Test/Implementationの途中で原因を推測して補完しません。親Bugの実行中に子Issueのlifecycleを再帰的に完了させません。

## Test以降の開始ゲート

`Test Implementation` 以降はcanonical Plan、mode/profile、Test判定、Repository/worktreeを再検証します。変更予定pathと既存dirty pathが重なる場合、その変更が同一Issueの直前phase成果物として確認できなければBLOCKEDです。Hunk単位の自動分離は行いません。

## `In Implementation Review` substate

通常Issueでは、Implementation完了時に保存された検証結果とHuman Acceptance確認点を人間が確認します。AIの独立Reviewは実行しません。問題があれば明示的な再開指示を受けて `Implementation` へ戻し、修正・再検証します。問題がなければ、明示的なClose指示を受けて [references/close.md](references/close.md) に進みます。

SpikeではResult Reviewとして扱います。

Result Reviewでは、今回scopeの実験結果、対象成果物、検証観測、Planの判断基準をCommentへ明記します。前回Review後に要件・仮説・判断基準・実験結果へ意味のある変更がある、または対象・差分を確認できない場合は、前回の正判定を流用せずResult Reviewを再実行します。表記・空白のみの変更は、それだけで再Review理由にしません。

- Spikeで最新のResult Reviewが `DECISION_READY` で、対象・証拠・判断基準に意味のある変更がない → Close待ち
- 対象・証拠・判断基準が変わっている、または有効な正判定Commentがない → Result Reviewを実行
- 明示的Close指示がある場合も、最新の正判定と対象・証拠の整合を確認してCloseへ進む

## 終了報告

必要な項目だけを日本語名で簡潔に報告します。

```text
実行フェーズ: <phase>
プロファイル: <lightweight | strict>
モード: <normal | spike | bug>
テスト判定: <Test required | Test not required | 該当なし>
レビュー判定: <decision | 該当なし>
ステータス遷移: <before → after>
検証結果: <要約>
未確認事項: <なし | 内容>
クローズ待ち: <はい | いいえ>
```
