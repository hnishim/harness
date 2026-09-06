---
name: add-policy
description: 人間が確定したPolicyを個人NotionのPolicies DBへ追加・検索・更新し、Feedback Countを管理する。
notion_sync: false
role: Main
tags: [notion, policy, decision-log]
---

# Add Policy

人間が明示的に確定したPolicyだけを、個人NotionのPolicies DB（page URL: `https://app.notion.com/p/eed9843aea2c44d6886738e111aeb08e`、data source URL: `collection://e226c613-a17a-4136-8b97-f880765abb84`）へ追加または更新する。Notion操作には標準の個人Notion接続（`mcp__codex_apps__notion`）だけを使用し、Molcure接続や別DBへ切り替えない。Linear Issue IDは恒常的なDB解決キーとして使用しない。

## Procedure

1. 入力を確認する。
   - Name、Policy、任意のContextを受け取る。
   - 人間の意図を「新規」「同等内容の再指摘」「内容変更」「管理編集」のいずれかで明示的に確認する。
   - 意図、対象Page、または変更内容が確定していない場合は確認を求め、保存しない。
2. 対象DBとschemaをreadbackする。
   - 上記のPolicies DB page URLをfetchして対象DBを確認し、data source URLをquery/createの対象として使用する。Linear Issue IDからDBを解決しない。
   - `Name`（title）、`Policy`（rich text）、`Context`（rich text）、`Status`（select）、`Feedback Count`（number）の存在と型を確認する。
   - DBまたは必須Propertyを解決できない、不一致、権限エラー、readback結果不明の場合は、mutationを行わず停止する。
3. 既存Policyを検索する。
   - Policy本文は前後空白を除き、連続する空白を1つに正規化して比較する。
   - 正規化後に完全一致する候補は同一Policyとして提示する。
   - 完全一致しない意味的候補は候補として提示し、人間が対象Pageと意図を選択するまで停止する。候補が複数、判定不能、対象Page不明の場合も自動選択しない。
4. 人間の確定した分岐を実行する。
   - **新規**：既存の同一候補がないことを確認し、Name、Policy、Context、Status=`Active`、Feedback Count=`1`でPageを1件作成する。
   - **同等内容の再指摘**：重複Pageを作成せず、人間が選択または完全一致で確定したPageのFeedback Countだけを`+1`する。
   - **内容変更**：人間が明示選択したPageのPolicyとContextだけを更新する。Feedback Countは増やさない。
   - **管理編集**：人間が指定した管理項目だけを更新する。Policyの規範内容を推測して変更せず、Feedback Countは増やさない。
5. mutation後にreadbackする。
   - 作成・更新対象、変更されたProperty、Feedback Count、他Pageへの影響をreadbackで確認する。
   - mutationが失敗した場合は成功と報告せず、実際のNotion状態をreadbackして停止する。追加のPage作成・更新・Count加算は行わない。

6. 成功readback後に`$sync-policies`を入力なしで一度だけ呼び出す。
   - 同期失敗は未完了として報告し、Notion mutationを再実行しない。

## Output

- 実行前に対象DB、入力意図、候補Page、実行するmutationを示す。
- 人間の選択待ち、schema未解決、候補判定不能、権限・通信エラーは、理由とともに停止状態として報告する。
- 成功時は対象Page、変更Property、Feedback Countの変更前後、およびreadback結果を報告する。
- NotionへのPolicy変更後は、成功readbackを確認してから`$sync-policies`を一度だけ呼び出す。

## Hard constraints

- 人間が確定していないPolicyを新規作成・一般化・自動登録しない。CaseからPolicyを自動生成しない。
- 意味的候補、複数候補、判定不能候補を自動選択しない。明示選択前の作成・更新・Feedback Count加算は0回とする。
- 固定されたPolicies DB page URLをfetchして確認したdata source（`collection://e226c613-a17a-4136-8b97-f880765abb84`）以外へ書き込まない。Linear Issue IDを恒常的な解決キーとして使わない。DBまたは必須Propertyのreadbackが不成立なら一切mutationしない。
- Humanの同等内容の再指摘だけFeedback Countを増やす。Workflow、Hook、管理編集では増やさない。
- ContextやStatusなど、指定されていないPropertyを暗黙に変更しない。
- 成功readbackを確認できない操作を成功と報告しない。
