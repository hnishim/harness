# add-policy scenario verification

このシナリオは、`skills/add-policy/SKILL.md` の操作契約を、実際の個人Notion接続とPolicies DBで確認するためのTest Implementation成果物です。各シナリオは同じ入力を再利用せず、実行前後に対象DBをreadbackします。DBまたは必須Propertyを解決できない場合は、全シナリオを実行せず停止します。

## 共通確認

- 対象はHIR-137で作成・確認したPolicies DBです。
- 必須Property（Name、Policy、Context、Status、Feedback Count）と型をreadbackし、対象が不明または不一致ならmutationを行いません。
- 各シナリオの開始前に、対象候補PageのID、Policy、Context、Status、Feedback Countを記録します。
- 各シナリオの終了後に同じDBをreadbackし、作成・更新Pageが意図した対象だけであることを確認します。
- 人間が意図または対象Pageを確定していない状態では、作成・更新・Feedback Count加算を実行しません。

## S1 新規Policy

入力の人間の意図を「新規」とし、既存Policyと正規化後完全一致しないPolicy本文を指定します。Contextは任意の値を指定します。

期待結果:

- 新しいPageを1件だけ作成する。
- Name、Policy、Contextが入力に対応する。
- Statusは`Active`、Feedback Countは`1`になる。
- 既存Pageは変更されない。

## S2 正規化後完全一致の同等再指摘

S1で作成したPolicyを対象に、人間の意図を「同等内容の再指摘」として指定します。Policy本文には前後空白と連続空白だけを加え、意味や文字列を変更しません。

期待結果:

- 新しいPageを作成しない。
- S1のPageだけを対象にFeedback Countを1増加する。
- Policy、Context、Name、Statusは変更しない。
- 他のPageのFeedback Countは変更しない。

## S3 明示的な内容変更

既存候補が表示された状態で、人間の意図を「内容変更」とし、対象Pageを明示選択します。新しいPolicy本文とContextを指定します。

期待結果:

- 明示選択したPageのPolicyとContextだけを更新する。
- Pageを新規作成しない。
- Feedback Countは増加しない。
- 対象PageのName、Status、および他のPageは変更しない。

## S4 管理上の編集

既存Pageを明示選択し、人間の意図を「管理編集」として誤字・表現修正を指定します。

期待結果:

- 指定された管理項目だけを更新する。
- Feedback Countは増加しない。
- Policyの規範内容、Context、Status、および他のPageは、指定がない限り変更しない。

## S5 意味的候補があるが人間未選択

入力Policyと意味的に近い候補を1件以上用意し、候補が表示された時点で処理を停止します。人間は対象Pageと意図を選択しません。

期待結果:

- 確認要求または候補提示を返す。
- Pageを作成・更新しない。
- Feedback Countを加算しない（mutation回数は0）。

## S6 複数候補または判定不能

複数の意味的候補、または対象DB・候補を判定できない入力を用意し、人間の明示選択なしで処理を終了させます。

期待結果:

- 自動選択せず、確認要求またはBLOCKEDとして停止する。
- Pageを作成・更新しない。
- Feedback Countを加算しない（mutation回数は0）。

人間が対象Pageと意図を明示した後は、再指摘なら選択PageのFeedback Countだけを1増加し、内容変更なら選択PageのPolicy／Contextだけを更新します。

## S7 Policy変更失敗

既存Pageの更新またはFeedback Count更新が失敗する条件で実行します。失敗後に対象Pageをreadbackします。

期待結果:

- 成功と報告しない。
- Notion上の実際の状態を確認して停止する。
- 失敗後に別Pageの作成・更新・Feedback Count加算を行わない。

## 判定記録

各シナリオについて、次を記録してTest Reviewへ渡します。

| 項目 | 記録内容 |
| --- | --- |
| Scenario | S1〜S7 |
| 入力意図 | 新規／同等再指摘／内容変更／管理編集 |
| 選択Page | Page IDまたは未選択 |
| mutation前後 | 作成・更新PageとFeedback Countの差分 |
| readback | 対象DBとPropertyの確認結果 |
| 結果 | PASS／FAIL／MANUAL-UNVERIFIED |
| 証跡 | Notion Page URLまたは停止理由 |
