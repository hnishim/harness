# add-case scenario verification

このシナリオは、`skills/add-case/SKILL.md` の操作契約を、実際の個人Notion接続とCases DBで確認するためのTest Implementation成果物です。各シナリオは独立した入力を使い、実行前後にCases DBと、Feedback Countを変更する場合は対象Policies DBをreadbackします。DBまたは必須Propertyを解決できない場合はmutationを行わず停止します。

## 共通確認

- 対象はHIR-137で作成・確認したCases DBです。固定URLは`https://app.notion.com/p/3e90eca1408047bdab8945cf19e02d2d`、data source URLは`collection://6549ebbe-1dac-4a5e-9d36-17ddb46a5215`とし、Linear Issue IDから解決しません。
- 必須Property（Name、Occurred At、Source、Subject、Summary、Context、Review Status、Feedback Counted）と型をreadbackし、`Review Status`はselect、値`Unreviewed`／`Reviewed`であることを確認します。対象が不明または不一致なら全シナリオを実行せず停止します。
- Feedback Countを変更するシナリオでは、対象Policies DBの必須Propertyと対象Policy Page IDもreadbackします。
- 各シナリオの開始前に、対象DBのPage ID、payload、対象PolicyのFeedback Count、既存CaseのFeedback Countedを記録します。
- 各シナリオの終了後に同じDBをreadbackし、作成・更新Page、Relation、Feedback Countの差分が期待結果だけであることを確認します。
- Page IDまたは一意な照合結果を確定できない場合は、Case作成やFeedback Count加算を行わず、未完了／BLOCKEDとして記録します。
- 各シナリオは同一payloadを再利用せず、再実行シナリオだけ同一payloadまたは前回Case Page IDを意図的に再利用します。

## S1 PolicyなしCase

Policy候補がないpayloadをSource `Human`、`human_reindication=false`で指定します。

期待結果:

- Case Pageを1件だけ作成する。
- Name、Occurred At、Source、Subject、Summary、Contextがpayloadに対応する。
- Sourceは`Human`、Review Statusは`Unreviewed`、Feedback Countedは`false`になる。
- Policyを作成せず、Feedback Countを変更しない。
- Policyなしでも成功として報告する。

## S2 Human再指摘（true）

既存Policyを1件だけ明確に指定できるpayloadをSource `Human`、`human_reindication=true`で指定します。

期待結果:

- Case Pageを1件作成し、明確に特定したPolicyとのRelationを設定する。
- 対象PolicyのFeedback Countを1回だけ増加する。
- CaseのFeedback Countedを`true`にする。
- 他のPolicy、他のCaseは変更しない。

## S3 Human（false）

既存Policy候補があっても、Source `Human`、`human_reindication=false`で指定します。

期待結果:

- Caseを作成し、候補が十分明確な場合だけRelationを設定する。
- PolicyのFeedback Countは増加しない。
- CaseのFeedback Countedは`false`のままにする。

## S4 Human（未指定）

`human_reindication`を省略したSource `Human` payloadを指定します。

期待結果:

- Caseを作成する。
- PolicyのFeedback Countを増加しない。
- CaseのFeedback Countedは`false`にする。

## S5 Workflow / Hook

同じ内容のpayloadをSource `Workflow`、次に`Hook`として指定します。`human_reindication`は未指定または`true`でも、Human以外の分岐として確認します。

期待結果:

- それぞれCaseを作成し、Sourceを正規化して保存する。
- Review Statusは`Unreviewed`になる。
- Policy候補が明確ならRelationだけを設定する。
- PolicyのFeedback Countを増加せず、CaseのFeedback Countedも`false`にする。

## S6 候補Relationのみ

意味的に近いPolicy候補があるが、Humanの再指摘を明示しないpayloadを指定します。

期待結果:

- 十分明確な候補だけをRelationに設定する。
- 候補Relationだけを根拠にFeedback Countを増加しない。
- Policyを自動生成しない。
- Caseは正常に保存できる。

## S7 Feedback Counted=trueの再実行

S2で作成したCase Page IDを指定し、同じHuman payloadを再実行します。

期待結果:

- 同じCase Pageを再利用する。
- 既存CaseのFeedback Countedが`true`ならPolicyのFeedback Countを増加しない。
- Caseを重複作成せず、成功報告はreadbackで確認した状態だけに基づく。

## S8 同一payloadの再実行

前回のCase Page IDを指定せず、Source、Subject、Summary、Occurred At、Contextが同一のpayloadを再実行します。

期待結果:

- 既存Caseが1件だけならそのPageを再利用する。
- 新規Caseを作成せず、Feedback Countを増加しない。
- 既存Caseが特定できない場合はmutationなしで未完了／BLOCKEDとする。

## S9 Page IDなし・単一照合

Page IDなしで、Source、Subject、Summary、Occurred At、Contextが同一の既存Caseが1件だけ存在するpayloadを指定します。

期待結果:

- 単一の既存Case Pageを再利用する。
- 新規Caseを作成せず、Feedback Countを増加しない。
- readbackで再利用したPage IDを記録する。

## S10 Page IDなし・照合不能／複数候補

Page IDなしで、同一Caseが0件の場合と2件以上の場合をそれぞれ確認します。

期待結果:

- 自動的に新規作成せず、Feedback Countも増加しない。
- 未完了／BLOCKEDとして停止し、候補Page IDまたは停止理由を記録する。
- 照合不能・複数候補を成功として報告しない。

## S11 review-cases経由の再実行

既存Caseを`review-cases`経由で再実行し、前回Case Page IDまたは単一照合結果を引き継ぎます。

期待結果:

- 元のCase Pageを再利用する。
- Feedback Counted=trueならPolicyのFeedback Countを増加しない。
- CaseやPolicyを重複作成せず、readback結果を報告する。

## S12 Policy更新成功・Case flag更新成功

Source `Human`、`human_reindication=true`、明確な既存Policyを指定し、Policy Feedback Count更新とCase Feedback Counted更新がともに成功する条件で実行します。

期待結果:

- PolicyのFeedback Countが1回だけ増加する。
- CaseのFeedback Countedが`true`になる。
- 両方のreadback成功後だけ成功と報告する。

## S13 Policy更新失敗／Case flag更新成功・失敗

S12相当のpayloadで、Policy更新が失敗する場合を、Case flag更新の成功・失敗それぞれで確認します。

期待結果:

- 成功と報告せず、Notion上のPolicyとCaseをreadbackして停止する。
- 二重加算の可能性がある場合は盲目的に再試行しない。
- 追加Case作成や追加Feedback Count加算を行わない。

## S14 Policy更新成功／Case flag更新失敗

S12相当のpayloadで、Policy Feedback Count更新は成功するがCase Feedback Counted更新が失敗する条件で実行します。

期待結果:

- 成功と報告せず、Policy Feedback CountとCase flagをreadbackする。
- Policy側の加算済み状態を確認できないまま再試行しない。
- 部分失敗または二重加算の可能性を未完了／BLOCKEDとして記録する。

## 判定記録

各シナリオについて、次を記録してTest Reviewへ渡します。

| 項目 | 記録内容 |
| --- | --- |
| Scenario | S1〜S14 |
| payload | Source、Occurred At、Subject、Summary、Context、human_reindication、Page ID |
| Case Page | 作成・再利用したPage IDまたは未確定 |
| Policy Page | Relation対象、Feedback Count対象または未対象 |
| mutation前後 | 作成・更新Page、Relation、Review Status、Feedback Count、Feedback Countedの差分 |
| readback | Cases／Policies DBとPropertyの確認結果 |
| 結果 | PASS／FAIL／MANUAL-UNVERIFIED／BLOCKED |
| 証跡 | Notion Page URL、readback結果、または停止理由 |
