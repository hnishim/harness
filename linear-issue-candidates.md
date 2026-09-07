# Agent Development Workflow — Linear Issue Candidates

Version: 1.0 — 2026-09-05（JST）

本書は `agent-development-workflow.md` のTargetへ移行するための変更候補です。実装Planや実装開始の承認ではありません。Currentで既に解決している過去の問題、根拠のないモデル昇格、新しいReviewer/状態機械/自動Policy強制は候補に含めません。

必要な変更を5つの責務単位にまとめました。C1は照合契約を独立Issue HIR-152として登録し、単一入口統合の既存Issue HIR-55と関連付けました。C2–C4は既存Project全件一覧と関連Issueの検索で同じ未完了scopeのIssueを特定できなかったため、Agent HarnessのBacklogにHIR-149/150/151として登録しました。C5もHIR-153として独立起票しました。未承認の設計提案であることを明記しています。

## C1 / P0 — phase再開時にPlan承認対象と必要な前提を照合する

**Problem**

現行はPlan・mode/profile・Test判定を再取得・検証しますが、保存済みAPPROVEが現在のPlanを承認したことを判別する根拠が不足しています。成果物hashは要求やprofileの同一性を証明しません。また、依存先が必要な作業の開始条件と、Pending/Canceled/Duplicateの扱いが未明示です。これは現行契約から導く失敗シナリオで、今回の実行で誤遷移を再現したという意味ではありません。

**Expected change**

既存Review Commentに最小のPlan識別情報を追加し、phase開始・保存直前・Closeで既存metadataと対応を確認します。必要な依存成果物をPlanで定義し、当該phaseでの充足を確認します。無関係な表示変更を実質的な要件変更と分けます。新しいStatus、承認DB、controllerは追加しません。

既存HIR-55は単一入口と途中再開を対象にしていましたが、元の統合内容は対応済みとしてDoneへ更新しました。C1の照合契約はHIR-152で独立追跡し、現行契約・旧phase語彙・案内の整理はHIR-153（C5）へ分離します。古いLuna Plan/Sol Review要件と現行の差は、C5の人間判断事項として残します。

**Acceptance criteria**

- 同じ承認対象での正当な再開、表示のみの変更、実質的Plan変更、profile変更を区別できます。実質変更を古いAPPROVEで通過させません。
- 旧CommentにPlan識別がない場合の安全な再Review手順があり、既存Doneを一括再審査しません。
- 対象phaseに必要な前提が未充足なら作業開始せず、不要な依存のDone待ちを全phaseへ強制しません。
- 未対応StatusではIssue・worktreeを変更せず、適用外であることを報告します。
- Plan APPROVE後の人間停止、連続変更要求の停止、Test baseline保護、明示Closeを維持します。
- schemaを変える場合はSkillと全該当Agentを同時に揃えます。旧`review_phase`を削除し、第二schemaや互換layerを追加しません。
- initial-plan / implementation-loopの専用Linear経路を揃え、既存dirty変更を無断で上書き・公開しません。

**Related section**

`agent-development-workflow.md §5.2、§7 F2/F3/F6、§10.3、§12 D-003、§13 C1/C5`

登録Issue: [HIR-152](https://linear.app/hnishim/issue/HIR-152/c1-issue成果物外部状態の照合契約を実装する)。関連既存Issue: [HIR-55](https://linear.app/hnishim/issue/HIR-55/codex-planningをimplementation-loopへ統合してstatus駆動の単一エントリーポイントにする)。HIR-152はHIR-137をblockし、HIR-55とはrelated toで結びます。現行実装根拠: `skills/implementation-loop/SKILL.md:164–173`、`references/test.md:15`、`references/implementation.md:17`。

## C2 / P1 — 外部サービス成果物を実readbackでReview・Closeする

**Problem**

HIR-137の成果物はNotionの2 DBです。現行の共通fingerprintはRepository相対pathとSHA-256を前提とし、外部実体を表現できません。implementerは外部書込み禁止であり、Notion-only作業の担当境界も明記が必要です。不要なfake adapter/Testファイルを作ってこの不足を埋めるとscopeが拡大します。

**Expected change**

外部作業の実行担当を親とし、元の依頼・Planで承認されたservice/workspace/entityと操作に限定します。親の検証記録に受入条件のreadback結果を保存し、独立Review対象と対応付けます。Close前に外部状態を再照合します。Repository変更がなければGit公開は非該当とし、外部成果物の受入は省略しません。汎用adapter、artifact registry、新しいReview phaseは作りません。

**Acceptance criteria**

- Notion-onlyの例で、Repositoryコード・fake adapterを追加せず、実対象のProperty型・Relation等を受入証拠として扱えます。
- 実行担当と対象・操作承認が明確です。Linear更新承認を他serviceの包括的な書込み権限と解釈しません。
- 必須の実readbackや実機確認が未確認ならPASS/Doneになりません。任意の追加確認を必須化しません。
- 外部成果物がReview後に変わった場合はClose前に検出します。同一対象・内容なら重複実装しません。
- 親の検証記録とReviewerの正規Resultを区別し、保存時の後付けfieldで現行schemaを破りません。
- Git非該当でも明示Closeと必要な受入確認を維持します。ファイル成果物の既存hash保護も維持します。

**Related section**

`agent-development-workflow.md §7 F4、§10.2/10.4、§12 D-004、§13 C2`

Project: Agent Harness。HIR-137の完了後に着手します。関連: HIR-137、HIR-16、HIR-152。実Notion DB作成・schema設定そのものはHIR-137のscopeとして残します。

## C3 / P1 — Linear部分保存を照合して未完了の遷移だけ再開する

**Problem**

既存の書込み前後readbackは有効ですが、Review Comment成功・Status更新失敗などの途中状態を再利用する手順がありません。結果不明を未実行扱いすると重複Commentや不要な再Reviewへ進みます。HIR-141/142の502後重複は、曖昧な書込み結果を即retryする危険を示しています。

**Expected change**

結果不明時に同一対象・内容の保存を再取得して照合し、一意に確認できれば未完了の更新だけを実施します。保存済みReviewを再投稿・再判定しません。保存不明や他編集の混在では停止します。initial-planとimplementation-loopの既存保存境界へ規則を追加し、汎用transaction・retry serviceは作りません。

**Acceptance criteria**

- Comment成功/Status失敗、Status成功/応答喪失、Description成功/次更新失敗を区別し、同じ内容を重複保存しません。
- 現在対象と保存済み判定が一致しない場合は、古い判定でStatusを進めません。C1の対象照合契約と整合します。
- 別編集、複数候補、読取り不能では停止し、結果不明のままblind retryしません。
- Plan APPROVEの遷移を復旧した後も、人間確認待ちを飛ばしてTest/Implementationへ進みません。
- 保存済み結果を認識した場合、Review回数を架空に増やさず、過去の変更要求を消しません。

**Related section**

`agent-development-workflow.md §5.3、§7 F5、§10.5、§12 D-006、§13 C3`

Project: Agent Harness。HIR-152とHIR-142の完了後に着手します。関連: HIR-55、HIR-142、HIR-152。新規Issue作成機能をimplementation-loopへ追加する提案ではありません。

## C4 / P1 — 同一Closeで作成したcommitを検証して公開処理を再開する

**Problem**

現行Git Skillは既存未送信commitがあると停止します。commit成功後にpushが失敗した同じCloseも、次回実行ではその停止条件に該当します。停止報告にはcommit済みの真偽がありますが、来歴を検証するcommit hash等は必須ではありません。現行の安全性を保った限定再開が必要です。

**Expected change**

失敗時もcommit hash・Repository・送信先・Issue/Reviewとの対応を既存結果記録へ残します。再開時にremoteを再取得し、同一Close由来のcommitとReview済み内容の一致、対象外commit不在、remote先行不在を確認した場合だけ未完了pushを行います。既に送信済みなら再commitせず、必要な完了確認へ進めます。複数Repositoryでは成功済みを照合して残りだけを扱います。

**Acceptance criteria**

- commit成功/push失敗から、同一内容を再commitせず再開できます。
- push成功/応答喪失、全push成功/Linear Done更新失敗を再取得で判別し、二重操作しません。
- 同一Close由来を証明できないcommit、Review対象と内容が違うcommit、対象外commitの混在では停止します。
- remote先行・分岐、自動rebase/merge禁止、force push禁止、承認・権限不足時停止を維持します。
- 複数Repositoryの一部成功ではDoneへ進めず、再開時に成功済み対象を変更しません。
- 新しいreceipt DB/serviceや広い「既存commitをpush可能」例外を追加しません。

**Related section**

`agent-development-workflow.md §5.2/5.3、§7 F5、§10.5、§12 D-006、§13 C4`

Project: Agent Harness。HIR-152の完了後に着手します。関連: HIR-87、HIR-109、HIR-152。完了済みのClose承認導入を再実装するIssueではありません。

## 既存Issueで扱う事項

| 既存Issue | 今回追加で確認した事項・次のaction | 新規Issueにしない理由 |
| --- | --- | --- |
| HIR-88 | real clientでtextlint Hookの登録・信頼・起動・payload・readbackを確認します。空白pathの生成commandも起動境界として確認します。 | Hook不発の実再現と最小修正が既存scopeです。unitは77件中75成功・2skipであり、実clientの完了証拠にしません。 |
| HIR-35 | gh guardについて、実clientでの発火・context payload・対象2操作の境界を確認します。 | textlintの受入条件にgh全体の検証を混在させず、Hook展開の既存Issueへ記録します。 |
| HIR-82 | READMEのsetup入口とmanual acceptanceのAgent数を現物に合わせます。既存dirty文書変更との所有権を確認します。 | 統合後の文書追随であり、新しいarchitectureではありません。Doneの状態変更や再openは今回行いません。 |
| HIR-55 | 元の単一入口統合は対応済みとしてDoneへ更新しました。C1はHIR-152、C5はHIR-153へ分離しています。 | 完了済みIssueへ残作業を混在させません。 |
| HIR-142 | Case保存失敗時に、どこで停止し、成功済みcore処理を再実行せずどこから再開するか明確化します。 | producer接続と失敗処理は既存scopeです。勝手にbest-effort化しません。 |
| HIR-137 / 136 / 140 / 138 / 139 | 各既存Planと依存に沿って実装・実readbackを進めます。Notion実体は今回未確認です。 | 今回新しく発生したworkではなく、既に担当と未完了事項が記録されています。 |

## Issue化しない判断

- HIR-99の旧削除処理、HIR-115の再認可、旧Review schema不一致は、現行の是正を確認したため同じバグを再登録しません。
- 定量的な複雑性予算、追加Reviewer、Astra常用、Policy自動強制、汎用adapterは必要性を確認できませんでした。
- モデルの費用対効果は未実測です。既存モデルを変更する受入条件がないため、測定基盤の実装Issueを作りません。
- 新しいcanonical documentは本タスクの成果物です。文書を作るためだけの追加実装Issueは不要です。

## 登録記録

独立レビュー後、ユーザーのAGENTS.mdにある未解決事項のLinear記録ルールに従って以下へ記録し、保存後の再取得で確認しました。登録は提案の追跡であり、実装開始・canonical Plan変更・既存IssueのCloseを意味しません。

| 対応 | 記録先 | 保存確認 |
| --- | --- | --- |
| C1 | [HIR-152](https://linear.app/hnishim/issue/HIR-152/c1-issue成果物外部状態の照合契約を実装する) | Agent Harness / Todo; HIR-137をblock、HIR-55とrelated to; 依存方向確定 Comment `12fdc0d3-d00f-40db-b4ce-b302709f6cc1` |
| C1の統合関連 | [HIR-55](https://linear.app/hnishim/issue/HIR-55/codex-planningをimplementation-loopへ統合してstatus駆動の単一エントリーポイントにする) | Done; HIR-152とrelated to; Closeout Comment `31cda5f3-ab27-4f73-80c0-8a6ff0b13a51` |
| C2 | [HIR-149](https://linear.app/hnishim/issue/HIR-149/外部サービス成果物を実readbackでreviewcloseする) | Agent Harness / Backlog |
| C3 | [HIR-150](https://linear.app/hnishim/issue/HIR-150/linear部分保存を照合して未完了の遷移だけ再開する) | Agent Harness / Backlog |
| C4 | [HIR-151](https://linear.app/hnishim/issue/HIR-151/同一closeで作成したcommitを検証して公開処理を再開する) | Agent Harness / Backlog |
| C5 | [HIR-153](https://linear.app/hnishim/issue/HIR-153/c5-現行契約の不整合とworkflow案内を整理する) | Agent Harness / Backlog; HIR-152をblock、HIR-55/HIR-150とrelated to |
| textlint実効性 | HIR-88 | Comment `56ee89c0-3587-42b0-95bd-94d7cf01f29e` |
| gh guard実効性 | HIR-35 | Comment `806f2054-b754-46ea-8714-074596238299` |
| setup/Agent案内の追随 | HIR-82 | Comment `a3726bf7-ab64-4eba-9b21-85ab5a824722` |
| Case保存失敗後の境界 | HIR-142 | Comment `8b775483-e73e-4c47-a643-2bd1bc0691e9` |

### 依存関係・判断境界の追記

2026-09-05に、C1–C5とCase/Policy各Issueへ人間判断事項と停止条件を保存しました。既存のcanonical Descriptionとmarkerは直接変更していません。

* HIR-152 (C1) → HIR-137。HIR-137がCase/Policyの物理schema、HIR-136/140/138/139/142、HIR-149を順にblockします。
* HIR-150 (C3) はHIR-152とHIR-142に依存します。
* HIR-151 (C4) はHIR-152に依存します。
* HIR-149 (C2) はHIR-137に依存します。
* HIR-153 (C5) はHIR-152に依存し、HIR-55とHIR-150に関連します。
* HIR-16、HIR-137、HIR-136、HIR-140、HIR-138、HIR-139、HIR-142には、Plan作業が対象・権限・Policy／Caseの意味・review outcome・cache対象・失敗境界を推測しないためのコメントを追加しました。
