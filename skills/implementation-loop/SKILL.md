---
name: implementation-loop
description: Linear IssueのStatusから必要なphaseを判定し、Planning、Test、Implementation、Spike、独立Review、明示的Closeまでを単一入口で進める。
notion_sync: false
---

# Implementation Loop

## 役割

入力はLinear Issue IDです。Statusから基準referenceを選びます。

| Status | 読むreference |
| --- | --- |
| `Backlog` / `Todo` / `In Plan Review` | [references/planning.md](references/planning.md) |
| `Test Implementation` / `In Test Review` | [references/test.md](references/test.md) |
| `Implementation` / `In Implementation Review` | [references/implementation.md](references/implementation.md) |
| `Done` | なし |

`Spike` labelはmode modifierです。Planningでは `planning.md` に [references/spike.md](references/spike.md) を追加し、`Implementation` / `In Implementation Review` では `spike.md` を `implementation.md` の代わりに使います。SpikeがTest Statusにある場合はBLOCKEDです。

`Strict profile` labelはReview profile modifierです。独立Review時だけ [references/strict-profile.md](references/strict-profile.md) を追加します。

Close待ちで明示的Close指示を受けた場合だけ [references/close.md](references/close.md) を読みます。

## 共通契約

- phaseのSource of TruthはStatus
- modeのSource of Truthは `Spike` label
- profileのSource of Truthは `Strict profile` label。あり=strict、なし=lightweight
- phase開始前にIssue、Status、Description、全Comments、Labels、relations（依存関係）、Repository root / worktree / 適用されるlocal instructionsを再取得する
- Repositoryは明示パス、現在workspace、そこから一意に決まるGit rootの順で確定する
- Linearへの書き込みは親Agentが行う。このSkillの起動は、本文と各referenceで定義した対象IssueのDescription / Comment / TestグループLabel / Status更新への承認を含む。`Strict profile` labelの新規付与は明示的なユーザー承認を必要とする
- Linearの参照・更新は専用Linear API / connectorを使用する。LinearをComputer Use / GUIで参照・操作せず、専用経路が利用不能な場合もGUIへ自動fallbackせずBLOCKEDとする。ユーザーがLinear UI自体の確認・操作を明示した場合だけComputer Useを使用できる
- 書き込み直前に対象フィールドを再取得してbaseline一致を確認し、書き込み後も意図した差分だけを再取得確認する
- marker外のDescription、Testグループ以外のLabels、title、assignee、relations等を保持する
- Workflow Status、Review回数、Review結果はCommentへ残す
- 作業scopeは承認済みPlanの範囲・制約・受入条件に限定する
- phase作業・Review開始前、およびReviewer findingを採用する前に、現在の依頼内でユーザーが明示した要件・制約とcanonical Planの整合を確認する
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

- `Backlog` / `Todo` でmarkerがない場合の作成・既存Planの正規化は `planning.md` に従う
- `In Plan Review` 以降は正しいmarkerとcanonical Planを必須とする
- 通常IssueはPlan内のTest判定とTestグループLabelが `Test required` / `Test not required` のどちらか1つで一致していることを必須とする
- Spikeは `Test not required`

markerの複数、片側欠落、逆順、境界不明はBLOCKEDです。

### Plan identity / phase gate

- `plan_fingerprint` は `plan-fingerprint-v1` とし、canonical Plan本文を改行のCRLF／CRからLFへの正規化後にUTF-8化してSHA-256化した値です。本文は行頭の完全一致 `## 承認済みPlan\n` から行頭の完全一致 `## 参考情報\n` の直前までを含み、trim、末尾空白削除、追加改行をしません
- Issue ID、mode、profile、Test判定、relationsはfingerprintに埋め込まず、再取得した現在値とReview Commentのmetadataを個別に完全一致照合します。Plan Reviewの `test_decision` は判定文字列、`relations_snapshot` は `blocks` / `blockedBy` / `relatedTo` に現在のIssue IDを昇順で格納したJSON objectです
- `Implementation`、`Test Implementation`、`In Test Review`、`In Implementation Review`、Close開始前は、現在のcanonical Plan、mode/profile、Test判定Label、relations、最新Comments、Repository/worktreeを再取得します
- 最新のPlan Review Comment自体が `APPROVE` で、Issue／mode／profile／Test判定／relations snapshot／plan fingerprintが現在値と一致する場合だけ次phaseへ進みます。より新しい `CHANGES_REQUIRED`、`BLOCKED`、判断不能、またはmetadata／fingerprint不一致があれば古いAPPROVEを使わず停止します
- canonical Planが有効な未Done Issueで、最新Plan Review Commentに `plan_fingerprint`、`test_decision`、または `relations_snapshot` がない場合は、Plan本文を変更せず `In Plan Review` へ戻してfresh Plan Reviewを実施します。freshな正判定の新Commentだけを証拠とし、既存Done Issueを一括再Reviewしません
- Comment欠落、Issue／scope／acceptance／mode／profile／Test判定／relationsの不一致、第三者編集、結果不明、権限不足はBLOCKEDです

成果物fingerprintは `artifact-fingerprint-v1` とし、今回scopeの各成果物を `Git root basename | Repository内相対path | SHA-256` の1行へ変換します。削除はSHA-256の代わりに `deleted` とし、行をUTF-8の辞書順でsortし、LFで連結した末尾改行なしの文字列をSHA-256化します。Git root basenameはRepository識別子として使い、絶対パスやremote URLは入力へ含めません

## Review共通契約

Planning、Test、Implementation、Resultの各独立Reviewに共通して次を適用します。

- Reviewerは成果物がIssue達成に必要な最小scopeかを確認する
- `scope-removal` は、残置cost / riskが除去・再検証costを上回る実質的なscope外複雑性に限る
- 明示的な別要件がない限り、対象はsingle-userの個人Mac上で実行するlocal scriptまたは小規模automationのtrusted local environmentです。Plan、Test、Implementation、Implementation Reviewでは、抽象化、設定機構、framework、compatibility layer、依存追加、defensive infrastructure、将来対応を、現在のIssue要件、既存構成、安全性、データ保全、既存互換性の具体的な必要性と照合します。根拠のないscope外の複雑化は `scope-removal` とし、明示的な要件や安全性・データ保全・互換性に必要な複雑さはAcceptance-blockingにしません。将来の拡張性、一般論、industry best practice、style preferenceだけでは複雑さを正当化しません
- Reviewerはphaseを進める前に修正必須の指摘だけを出し、各findingに `acceptance` / `safety` / `bug` / `scope-removal` の分類、具体的根拠、影響、必要最小の修正を含める
- 親AgentはReviewerの技術判断を再Reviewせず、canonical Review Resultのschema、workflow metadata、decision / findings整合だけを検証する
- Reviewerはread-only
- 同phaseの再Reviewでは、親Agentが最新の同phase Review Resultと、前回Reviewを受けた今回の修正roundで実際に変更した内容をReviewer packetへ含める。前回必須findingの修正と今回の修正roundを主対象とする
- 新しい必須findingは、今回の修正roundで新たに発生した、前回時点では観測不能だった、または前回判定を覆す新しい具体的根拠が得られた場合だけ追加できる。前回non-blocker・既存dirty・scope外と扱った事項を必須へ再分類する場合も、新しい具体的根拠を明示する
- 同じphaseで変更要求判定が2回連続した場合は、finding内容が異なっていても2回連続とみなす。通常のbackward transitionを行った後、その実行を停止する
- Reviewer利用不能または判断不能はBLOCKEDとする

### Canonical Review Result

Reviewerは親Agentから `phase`、`issue`、`profile`、`mode` とphase固有metadataを受け取り、次のJSON objectだけを返します。これをReview結果の唯一のschemaとします。

```json
{
  "phase": "Plan Review|Test Review|Implementation Review|Result Review",
  "issue": "HIR-123",
  "profile": "lightweight|strict",
  "mode": "normal|spike",
  "plan_fingerprint": null,
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
  "approved_tests": null,
  "artifact_fingerprint": null
}
```

workflow metadataの扱い:

- `phase` / `issue` / `profile` / `mode` は親Agentが渡した値をReviewerがそのまま返す
- Plan Reviewでは、親Agentが渡した `plan_fingerprint` 候補をReviewerが変更せず返す。Plan Review以外は `null`
- Plan Reviewでは、親Agentが渡した `test_decision` と `relations_snapshot` を変更せず返す。Plan Review以外は両方とも `null`
- Test Reviewでは、親AgentがTest Implementationのpath / SHA-256 / 再実行command / 必要な手動確認を `approved_tests` 候補として渡す。`TESTS_APPROVED` の場合だけReviewerがその値を返し、それ以外は `null`
- Implementation / Result Reviewでは、親Agentが算出した `artifact_fingerprint` をReviewerがそのまま返す
- その他のphase固有metadataは `null`

親AgentはJSON parse、必須key、workflow metadata一致、phaseで許可されたdecision、decision / findings / blockerの整合、finding必須項目を検証します。不正なら形式訂正を1回だけ求め、再度不正ならBLOCKEDです。親Agentは有効なReview Resultの意味を書き換えません。

decision整合:

- 正判定: `findings=[]`、`blocker=null`
- 変更要求・`PLAN_INCOMPLETE`・`MATERIAL_DEVIATION`: `findings` を1件以上、`blocker=null`
- `BLOCKED`: `findings=[]`、`blocker` に判断不能の具体的理由

`BLOCKED` は共通BLOCKEDとして停止し、Statusを維持します。それ以外のcanonical Review Resultは、値を変えずに次のMarkdownへ整形してLinear Commentへ保存します。

```text
フェーズ: <phase>
対象Issue: <issue>
プロファイル: <profile>
モード: <mode>
plan_fingerprint: <Plan Reviewで非nullの場合だけ>
test_decision: <Plan Reviewで非nullの場合だけ>
relations_snapshot: <Plan Reviewで非nullの場合だけJSON>
判定: <decision>
必須指摘: <findings。なければ なし>
approved-tests: <approved_testsが非nullの場合だけ>
成果物fingerprint: <artifact_fingerprintが非nullの場合だけ>
```

JSONからMarkdownへの整形はrepresentationの変更だけとし、decision、finding、workflow metadataを追加・削除・再分類しません。`plan_fingerprint`、`test_decision`、`relations_snapshot` も同じ値を保存します。

## Routing / 停止境界

保存・再取得確認後のforward transitionは同じ実行内で継続できます。

次は停止境界です。

- Plan Review `APPROVE` 後: 次Statusへ更新して停止し、人間確認を待つ。以後の明示的な `implementation-loop` 実行を人間確認後の再開指示として扱う
- `CHANGES_REQUIRED` / `PLAN_INCOMPLETE` / `MATERIAL_DEVIATION` で `Todo` へ戻った場合
- 同一Review phaseで2回連続の変更要求になった場合
- `PASS` / `DECISION_READY` のClose待ち
- BLOCKED
- `Done`

Plan Review後の次回実行は、`Test required` なら `test.md`、`Test not required` なら `implementation.md` から開始します。`TESTS_APPROVED` 後は同一実行で `implementation.md` へ進めます。

## Test以降の開始ゲート

`Test Implementation` 以降はcanonical Plan、mode/profile、Test判定、Repository/worktreeを再検証します。変更予定pathと既存dirty pathが重なる場合、その変更が同一Issueの直前phase成果物として確認できなければBLOCKEDです。hunk単位の自動分離は行いません。

## `In Implementation Review` の共通substate

Review直前に、今回scopeの各成果物について `Repository識別子 | Repository内相対path | SHA-256`（削除は `deleted`）をsortしてhash化した `成果物fingerprint` を作ります。

- 通常Issueで最新のImplementation Reviewが `PASS` かつfingerprint一致 → Close待ち
- Spikeで最新のResult Reviewが `DECISION_READY` かつfingerprint一致 → Close待ち
- fingerprintが変わっている、または有効な正判定Commentがない → 対応referenceのReviewを実行
- 明示的Close指示がある場合も、最新の正判定とfingerprint一致を確認してCloseへ進む

## 終了報告

必要な項目だけを日本語名で簡潔に報告します。

```text
実行フェーズ: <phase>
プロファイル: <lightweight | strict>
モード: <normal | spike>
テスト判定: <Test required | Test not required | 該当なし>
レビュー判定: <decision | 該当なし>
ステータス遷移: <before → after>
検証結果: <要約>
未確認事項: <なし | 内容>
クローズ待ち: <はい | いいえ>
```
