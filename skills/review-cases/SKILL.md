---
name: review-cases
description: 個人NotionのUnreviewed Caseを人間の選択したOutcomeに従ってPolicyへ関連付け、作成、更新、またはNo Actionとしてレビュー完了する。
notion_sync: false
role: Main
tags: [notion, case, policy, decision-log]
---

# Review Cases

個人NotionのCases DBから`Review Status=Unreviewed`のCaseと関連し得るPolicies DBの候補を取得し、人間が選択したReview Outcomeだけを実行する。対象DBは固定された個人NotionのCases（page `https://app.notion.com/p/3e90eca1408047bdab8945cf19e02d2d`、data source `collection://6549ebbe-1dac-4a5e-9d36-17ddb46a5215`）とPolicies（page `https://app.notion.com/p/eed9843aea2c44d6886738e111aeb08e`、data source `collection://e226c613-a17a-4136-8b97-f880765abb84`）をfetchして確認し、Linear Issue IDから解決しない。Notion操作は標準の個人Notion接続（`mcp__codex_apps__notion`）だけを使用する。

## Input

次のlogical review payloadを受け取る。

- 対象Case Page ID（または一意に照合できるCase識別情報）
- 人間が選択した`Review Outcome`（`Existing Policy`／`New Policy`／`Policy Updated`／`No Action`）
- `Existing Policy`／`Policy Updated`では人間が選択した対象Policy Page ID
- `Policy Updated`では人間が確定した更新後のPolicy本文と必要に応じたContext
- `New Policy`では人間が確定したName、Policy、任意Context
- 任意のReview Note
- `human_feedback_confirmed`（boolean。未指定を許容）

Case、Outcome、対象Policy、更新内容が確定していない場合は確認を求め、mutationを行わない。Outcomeを自動選択しない。`Policy Updated`の更新後本文が未指定の場合はPolicyを変更せず確認要求で停止する。

## Procedure

1. **Cases／Policies DBとschemaをreadbackする。**
   - 上記の固定DB pageをfetchし、対象DB、data source、必須Propertyの型を確認する。Linear Issue IDからDBを解決しない。
   - Casesの`Name`、`Occurred At`、`Source`、`Subject`、`Summary`、`Context`、`Review Status`、`Feedback Counted`、Policiesの`Name`、`Policy`、`Context`、`Status`、`Feedback Count`を確認する。
   - Casesの`Review Outcome`がselect型でoptionsが`Existing Policy`、`New Policy`、`Policy Updated`、`No Action`の4つ、`Review Note`がtext型、`Reviewed At`がdate型であることを確認する。
   - Casesの`Related Policies`がrelation型でPolicies data sourceをtargetとし、Policiesの`Source Cases`がrelation型でCases data sourceをtargetとすることを確認する。DB、data source、schema、property型、options、relation targetの取得結果が不成立・不一致・不明、または権限エラーの場合はmutationなしで未完了／BLOCKEDとして停止する。
2. **Unreviewed CaseとPolicy候補を提示する。**
   - `Review Status=Unreviewed`のCaseを取得し、関連し得る既存Policy候補を提示する。
   - 候補が意味的に近いだけ、複数候補、対象Page不明の場合は自動選択せず、人間の選択を待つ。
3. **人間のReview Outcomeを実行する。**
   - 実行前に対象Case、候補、Outcome、人間が確定した入力、予定するmutationを提示する。Outcome、対象Page、作成内容、更新本文のいずれかが未確定なら確認を求め、mutationを行わない。
   - **Existing Policy**：人間が選択したPolicyだけを対象にCaseとのRelationを追加する。Caseの元事象と既存Relation、Policy本文は保持する。Relation mutation直後にCaseとPolicyの双方向Relationをreadbackする。
   - **New Policy**：人間が確定したName、Policy、任意ContextだけでPolicyを別Pageとして作成する。作成直後にPage IDと各Propertyをreadbackして一意に確認し、その後にCaseとのRelationを追加して両Pageをreadbackする。入力にない内容を補完しない。
   - **Policy Updated**：人間が選択した既存Policyの本文を必須として更新し、Contextは指定された場合だけ更新する。本文がない場合はPolicy、Relation、Review Statusを変更せず確認要求で停止する。Policy更新直後、Relation追加直後の各時点でreadbackする。
   - **No Action**：Policy、Relation、Policy Feedback Count、Caseの`Feedback Counted`を変更せず、`$sync-policies`も呼び出さない。CaseのReview metadataとReviewed化だけを行う。
4. **Feedback Countを条件付きで更新する。**
   - No Actionではこの手順を実行しない。既存Policyを対象とするOutcomeで、Sourceが`Human`で、`human_feedback_confirmed=true`、かつCaseの`Feedback Counted=false`の場合だけ、対象PolicyのFeedback Countを一度加算し、直後にPolicyとCaseをreadbackして両方の現在値を確認する。New Policyの初期Countは次項の作成mutationで設定する。
   - **New Policy**では、Policy作成mutationに初期`Feedback Count`（条件を満たす場合は1、それ以外は0）を含め、作成直後のreadbackで確認する。条件を満たす場合だけ、その後にCaseの`Feedback Counted=true`をmutationし、直後にCaseをreadbackする。Policy作成とCase flag更新を重ねて再実行しない。
   - **Existing Policy／Policy Updated**では、条件を満たす場合だけPolicyの現在Countに1を加算するmutationを行い、成功readback後にCaseの`Feedback Counted=true`をmutationし、直後にCaseをreadbackする。未指定・false、Sourceが`Workflow`／`Hook`、またはCaseの`Feedback Counted=true`の場合はPolicy CountとCase flagを変更しない。
   - Count増分後にCase flag更新が失敗またはreadback不明となった場合は、Policyのbaselineと現在値から今回の加算を一意に確認できる場合だけCase flag更新を一度だけ再開する。一意に確認できない場合は追加加算を行わず未完了／BLOCKEDで停止する。
5. **Review metadataとCase状態を保存する。**
   - 全OutcomeでReview Outcome、必要なReview Note、Reviewed Atを保存し、Caseを`Reviewed`にする。
   - Case本文と事象内容を保持する。Case Relation、対象Policy、Review metadata、Feedback Countedの現在値を保存する。
   - Policyの実変更（New Policyの新規作成、Policy Updatedの本文／Context更新、既存PolicyのFeedback Count加算）があるOutcomeでは、該当するPolicy mutationとRelation、Feedback Count更新の成功readbackがすべて完了した後、入力なし`$sync-policies`を1回だけ呼び出してsuccessを確認する。その後にReview metadataとCaseの`Reviewed`を保存し、直後にCaseをreadbackする。sync errorまたは結果不明ではReview Statusを`Reviewed`にせず、Notion状態をreadbackして未完了／BLOCKEDで停止する。Policyの実変更がないExisting PolicyまたはNo Actionではsyncを呼ばず、schema確認後にRelation／metadata／`Reviewed`だけを保存する。
6. **各mutationをreadbackし、Policy変更後だけ同期する。**
   - New Policy作成、Case Relation、Feedback Counted更新、Policy更新、Review metadata更新、Review Status更新の各mutation直後にreadbackし、識別情報と現在値を確認する。確認できない場合は次のmutationへ進まない。
   - Policyの実変更（新規作成、本文／Context更新、Feedback Count加算）を伴うsyncは手順5の1箇所でのみ実行し、手順5のsuccess確認後にReview metadata／`Reviewed`へ進む。ここではsyncを再実行しない。
   - 途中失敗またはreadback不明の場合は、既存Caseの元事象、Relation、Review Status、Feedback Countedと作成済みPolicyの有無・Propertyをreadbackする。同一状態を一意に確認できる場合だけ、その状態から未完了の次段階を一度だけ再開する。作成・Relation・Count更新の重複を避け、状態を一意に確認できない場合は追加mutationなしで未完了／BLOCKEDとして停止する。

## Output

- 実行前に対象Cases／Policies DB、Unreviewed Case、候補Policy、人間のOutcome、予定するmutationを示す。
- 成功時にCase Page、Policy Page、Outcome、Relation、Review metadata、Case本文保持、Feedback Countの変更前後、Feedback Counted、sync結果、readback結果を示す。
- 入力未確定、候補選択待ち、schema未解決、権限・通信エラー、部分失敗、readback不明、sync失敗は停止理由を示し、成功と報告しない。

## Hard constraints

- 固定された個人NotionのCases／Policies DBをfetchして確認し、指定されたdata sourceだけへ書き込む。Linear Issue IDからDBを解決しない。
- Review Outcomeを自動選択しない。人間が選択した4分岐だけを処理する。
- Case本文と事象内容を保持する。Policy Updatedの本文未指定時はPolicyを変更しない。
- 既存CaseのRelationを保持し、指定されたRelationだけを追加する。ContextまたはReview Noteが省略された場合、既存値を無用に変更しない。
- `human_feedback_confirmed=true`のHumanだけFeedback Countを一度加算する。未指定・false、Workflow／Hook、Feedback Counted=trueでは加算しない。
- No ActionではPolicy、Relation、Count、Feedback Counted、syncを変更しない。Policyの実変更（新規作成、本文／Context更新、Feedback Count加算）がある場合は成功readback後に入力なしの`$sync-policies`を1回だけ呼び出し、success確認後にだけCaseをReviewedにする。既存PolicyとのRelation追加だけでPolicyを変更しない場合はsyncを呼ばない。sync errorまたは結果不明では成功扱いしない。
- mutation後のreadbackを確認できない操作を成功と報告しない。部分失敗時に追加作成・追加加算を行わず、状態を一意に確認できない場合は未完了／BLOCKEDで停止する。
- 新しいadapter、fake adapter、テスト基盤、runtime cache、Workflow／Hookの実装を追加しない。
