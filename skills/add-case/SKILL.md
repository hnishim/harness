---
name: add-case
description: 具体的な事象を個人NotionのCases DBへCaseとして記録し、明示されたHuman再指摘だけPolicy Feedback Countを冪等に加算する。
notion_sync: false
role: Main
tags: [notion, case, decision-log]
---

# Add Case

logical Case payloadを、固定された個人NotionのCases DBへ保存する。対象Cases DBはDatabase URL `https://app.notion.com/p/3e90eca1408047bdab8945cf19e02d2d` をfetchして確認し、data source URL `collection://6549ebbe-1dac-4a5e-9d36-17ddb46a5215` をquery/create対象とする。Linear Issue IDからDBを解決しない。Notion操作は標準の個人Notion接続（`mcp__codex_apps__notion`）だけを使用する。

## Input

次のlogical Case payloadを受け取る。

- `Name`、`Occurred At`、`Source`、`Subject`、`Summary`、任意の`Context`
- `case_intent`（人間が確定した `new` または `retry`／`reuse`）
- 任意の対象Case Page ID
- 任意の関連Policy候補または対象Policy Page ID
- `human_reindication`（boolean。未指定を許容）

入力された事実（Source、Subject、Occurred At、Summary）、`case_intent`、人間の意図、対象Pageが確定していない場合は確認を求め、保存・更新・Feedback Count加算を行わない。Sourceは `Human`、`Workflow`、`Hook` のいずれかへ正規化し、解釈できない値は保存せず停止する。

## Procedure

1. **Cases DBとschemaをreadbackする。**
   - Database URLをfetchし、対象DBであることとschemaを確認する。
   - data source URLをquery/create対象として使用する。
   - `Name`（title）、`Occurred At`（date）、`Source`（select）、`Subject`（rich text）、`Summary`（rich text）、`Context`（rich text）、`Review Status`（select、値 `Unreviewed`／`Reviewed`）、`Feedback Counted`（checkbox）の存在と型を確認する。
   - DB、data source、必須Propertyの取得結果が不成立・不一致・不明、または権限エラーの場合はmutationなしで停止する。
   - Feedback Countを変更する場合だけ、固定されたPolicies DB page URL `https://app.notion.com/p/eed9843aea2c44d6886738e111aeb08e` をfetchしてschemaをreadbackし、data source URL `collection://e226c613-a17a-4136-8b97-f880765abb84` を対象にする。Linear Issue IDを解決キーにしない。

2. **既存Caseを先に特定する。**
   - Page IDが指定されていれば、そのPageをfetchしてCases DB所属とpayloadをreadbackし、同じCase Pageを再利用する。
   - Page IDがない場合、`Source`、`Subject`、`Summary`、`Occurred At`、`Context`が一致する既存Caseをqueryする。
   - 一致が1件だけなら再利用する。`case_intent=retry`／`reuse`で0件または複数件なら新規作成せず、Feedback Countも変更せず、候補Page IDと停止理由を示して未完了／BLOCKEDで停止する。`case_intent=new`で0件の場合だけ新規作成へ進む。
   - 再利用したCaseの`Feedback Counted`をreadbackする。trueならFeedback Countを加算しない。

3. **新規Caseを保存する。**
   - 既存Caseを再利用できず、照合条件が0件であることが確定した場合に限り、Cases data sourceへ1件作成する。
   - `Name`、`Occurred At`、正規化した`Source`、`Subject`、`Summary`、指定された`Context`を保存し、`Review Status=Unreviewed`、`Feedback Counted=false`とする。
   - Case保存後にPageと各Propertyをreadbackし、readbackできない場合は成功と報告せず停止する。

4. **関連Policyを扱う。**
   - Policy候補が十分明確で、対象Pageを一意に特定できる場合だけCaseにRelationを設定する。
   - 候補が意味的に近いだけ、複数候補、対象Page不明の場合は自動選択せず、候補を提示して停止するかRelationなしで保存する。候補Relationだけを再指摘とは扱わない。
   - Policyを自動生成しない。PolicyなしCaseは成功できる。

5. **Human再指摘のFeedback Countを処理する。**
   - `Source=Human`、`human_reindication=true`、かつ既存Policy Pageを一意に明確特定できる場合だけ、対象Policyの`Feedback Count`を1回増加する。
   - Policy更新前にPolicies DBの対象PageとCountをreadbackし、更新後にCountとCaseの`Feedback Counted=true`をreadbackする。両方のreadbackが確認できた場合だけ成功と報告する。
   - `human_reindication=false`または未指定、候補Relationだけ、`Source=Workflow`／`Hook`では加算しない。これらのCaseは`Feedback Counted=false`とする。
   - 同一Human feedbackの再実行では、既存Caseの`Feedback Counted=true`なら加算しない。Policy更新またはCase flag更新の部分失敗・readback不明・二重加算の可能性がある場合は盲目的に再試行せず、Notionの両DBをreadbackして未完了／BLOCKEDで停止する。

## Output

- 実行前に対象Cases DB、入力事実と人間の意図、既存Case／Policy候補、予定するmutationを示す。
- 成功時にCase Page、Policy Page、作成・再利用・Relation、変更Property、Feedback Countの変更前後、`Feedback Counted`、readback結果を示す。
- schema未解決、入力未確定、候補判定不能、Page照合不能、権限・通信エラー、部分失敗は停止理由と候補を示し、成功と報告しない。

## Hard constraints

- 固定されたCases DB page URLをfetchしてschemaを確認し、指定されたCases data sourceだけへ書き込む。Policies DBも固定URL／data sourceをfetch・readbackしてから操作する。
- Linear Issue IDからNotion DBを解決しない。新しいpersistence boundary、adapter、runtime cache、テスト基盤を追加しない。
- 入力事実、`case_intent`、人間の意図、対象Pageを推測・一般化しない。不明ならmutationを0回にする。
- Caseは常に`Review Status=Unreviewed`で扱い、Policyを自動生成しない。
- Feedback Countは明示されたHuman再指摘かつ既存Policy一意特定時だけ1回加算する。Workflow、Hook、候補Relation、通常Caseでは加算しない。
- mutation後のreadbackを確認できない操作を成功と報告しない。部分失敗時に追加作成・追加加算を行わない。
