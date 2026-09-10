# Bug mode: Root-cause `investigation`

`Bug` labelのIssueで読む。共通契約とReview作法は `../SKILL.md` に従う。

`Bug` は新しいLinear Statusではなくmode modifierです。`Backlog`/`Todo` の親Bugは、症状の確認とroot-cause `investigation` を先に行い、証拠で原因を確認できた場合だけ対応Planを作成します。親BugのStatusは調査中も変更せず、既存のSpike flowを使う調査用子Issueを1件だけ作成・再利用します。親Bugの1回の実行で子Issueのlifecycleを再帰的に完了させず、子Issueを独立したimplementation-loopの入力として扱います。

Bug modeはIssueに完全一致する `Bug` labelがある場合だけ選択します。Issueのtitle、本文、症状からBug modeを推測したり、`Bug` labelを自動追加したりしません。

## Mode boundary

- `Bug` と `Spike` が同時に付いている場合はmode不明としてBLOCKEDです
- `Bug` は `Test required` 固定です。専用Testが不要という理由で `Test not required` にはしません
- Bug親Issueは修正の要求・症状・調査子Issueへの参照・確定原因・修正方針・回帰Testを所有します
- 調査子Issueは既存の `Spike` labelを付けた子Issueとして、再現・仮説・識別検証・証拠・除外仮説・結論を所有します
- 調査子Issueの作成は冪等です。親の直接の子で、`Spike` labelがあり、root-cause `investigation` を目的とする既存Issueが1件あれば再利用します。0件なら1件だけ作成し、複数件で一意に決められない場合は追加作成せずBLOCKEDです
- 調査子Issueは親のBug modeを継承しません。`Bug` と `Spike` の同時付与を避け、既存Spike flowだけで扱います

## Backlog / Todo: 症状確認と調査子Issue

親Bugについて、Plan作成前に親Agentが次を実施します。

1. 親Issue、Status、Description、全Comments、Labels、relations、Repository root/worktree、適用されるlocal instructionsを再取得する
2. `Symptom reproduced / confirmed` として、期待動作、実際の動作、再現条件、実行経路、再現率または再現不能の事実を分けて確認する。症状を確認できない場合はroot causeをconfirmedにしない
3. 親の直接の子から調査子Issueを一意に検索する。0件なら、Linear write contractの範囲で、`parentId` を親Issueに設定し、既存 `Spike` labelを付け、初期Statusを `Backlog` にした子Issueを1件だけ作成する。`Bug` labelは付けない。作成・再利用した子Issue IDを親Commentへ保存し、親Issueと子Issueをreadbackする
4. 子Issueが新規作成された、または子IssueのResult Reviewが未完了である場合、親BugのStatusを維持して停止する。親の1回の実行内で子Issueへexecution targetを切り替えたり、子IssueのPlanning・Experiment・Result Reviewを再帰的に実行したりしない
5. 子Issueは独立したIssue IDを入力として、別のimplementation-loop実行で既存Spike flowのPlanning → Experiment/PoC → Result Reviewを進む。通常Spikeの契約を維持し、`BUG_INVESTIGATION_RESULT` がある場合だけroot-cause固有のResult Review評価を適用する
6. 親Bugを再実行したとき、保存済みの子Issueを再取得し、Result Reviewが完了していること、最新結果が `BUG_INVESTIGATION_RESULT` 契約に従うことを確認する。`DECISION_READY` がなく、`ROOT_CAUSE_CONFIRMED` の結果が保存されていない場合は親のStatusを維持して停止する
7. `ROOT_CAUSE_CONFIRMED` の場合だけ、親Issueの調査記録として次の要素を保存・再取得確認し、`planning.md` のcanonical Planへ進む

## Parent Bug と `investigation` child の責務

親Bugには次を保存します。

- 症状、期待動作、実際の動作、再現条件
- 調査子Issueへの参照
- 子Issueの確定結論と根拠への参照
- 確認済み原因、最小修正scope、回帰Testの対象
- 修正成功だけでは原因確定にならないこと、および未確認事項

調査子Issueには次を保存します。

- 安全な再現手順と観測結果
- 1件以上のroot-cause hypothesisと、合理的に存在するplausible alternatives
- 各仮説が正しい場合・誤りの場合の予測
- Plausible alternativesが存在する場合に、それらを識別するdiscriminating test
- 実行した検証、入力、観測、再現率
- 反証された仮説と、その根拠
- `ROOT_CAUSE_CONFIRMED`、`ROOT_CAUSE_UNCONFIRMED`、または `BLOCKED` の結論

調査子Issueの結果Commentは、次の契約を使います。`Hypothesis` は候補であり、`Confirmed root cause` と同じ意味ではありません。

```text
BUG_INVESTIGATION_RESULT
Parent Issue: <親Bug Issue ID>
Investigation Issue: <調査子Issue ID>
Symptom: <期待動作と実際の動作>
Reproduction: <条件、入力、実行経路、再現率、または再現不能の理由>
Hypotheses:
- H1: <仮説>
  Prediction if true: <正しい場合の観測>
  Prediction if false: <誤りの場合の観測>
  Discriminating test: <識別検証>
Execution: <実行した検証>
Evidence: <直接的な観測、ログ、最小再現、設定差分等>
Rejected hypotheses:
- <仮説>: <反証した根拠>
Conclusion: ROOT_CAUSE_CONFIRMED | ROOT_CAUSE_UNCONFIRMED | BLOCKED
Confirmed root cause: <確定原因。未確定なら空欄または候補と明記>
Remaining unknowns: <未確認事項>
```

## Root Cause Gate

親BugをFix designへ進めるのは、次をすべて満たす場合だけです。

- 症状が十分に再現・観測されている
- 1件以上の明示的なroot-cause hypothesisがある
- Plausible alternative hypothesesが合理的に存在する場合、それらを識別する検証を実行している
- 結論を支える直接的なevidenceが調査子Issueに保存されている
- Plausible alternativesがある場合、それらを反証、または優先度を下げる根拠がある
- Evidenceとconfirmed root causeの因果関係を説明できる
- 修正scopeと回帰Testを原因へ直接対応付けられる

コード読解だけ、症状の再現だけ、「もっともらしい」説明だけ、または修正後に直ったことだけでは `ROOT_CAUSE_CONFIRMED` にしません。合理的なplausible alternativeがない明白な原因では、架空の第二仮説を作らず、直接Evidenceで因果関係を確認できればPASSできます。条件を満たさない場合は `ROOT_CAUSE_UNCONFIRMED` または `BLOCKED` とし、親のPlan・Test成果物・修正・Statusを進めません。

最低限、次の判定になります。

| 状態 | Root Cause Gate |
| --- | --- |
| 仮説だけ、またはsource-code inspectionだけ | FAIL。親のFixへ進まない |
| 症状のreproductionだけ | FAIL。原因を識別できていない |
| plausible alternativesがあり、Evidence付きdiscriminating testで仮説間を識別できる | PASS候補。因果関係と代替仮説の扱いも記録する |
| `ROOT_CAUSE_UNCONFIRMED` / `UNRESOLVED` | FAIL。親のFixへ進まない |
| 明白なtypo等で合理的なalternativeがなく、直接Evidenceがある | 架空の第二仮説なしで、同じ子Issue契約を満たす場合だけPASS |
| 修正後に症状が消えただけ | 原因確定の根拠にしない |

調査結果を保存した後の再実行は、同じ親子関係と調査結果を再取得して再利用します。既存の調査子Issueを重複作成しません。

原因確定後の順序は次のとおりです。

```text
Investigation child
  -> ROOT_CAUSE_CONFIRMED
  -> parent Fix design
  -> regression test: FAIL before fix
  -> fix
  -> regression test: PASS after fix
  -> Human Acceptance
```

調査で使用する入力は、tracked file、既存fixture、無害な固定入力、隔離領域など安全な観測に限定します。不可逆変更、実運用データへの書込み、秘密値を含む再現、または調査のための恒久fixture/config変更が必要な場合はBLOCKEDです。調査後は一時生成物が残っていないことを確認します。

## Plan handoff

親Bugの再実行で `ROOT_CAUSE_CONFIRMED` の結果と調査子IssueのResult Reviewを保存・再取得確認できた場合だけ、`planning.md` のcanonical Plan作成へ進みます。Planには次を含めます。

- 調査子Issueへの参照と最新の `BUG_INVESTIGATION_RESULT`
- 確認済みの原因と、対応対象をそのscopeに限定する理由
- 原因を再発させないbug case回帰Test、隣接する既存正常case、期待結果、再実行方法
- `### テスト判定` の `Test required`
- 主test layer、failure boundary、mock/fixture/static assertionの未検証範囲
- 調査で未確認の事項と、それをImplementationの成功条件に含めない境界

Bugの原因調査は新しいLinear StatusやBug専用Agentを追加するphaseではありません。調査子Issueを独立したimplementation-loop入力として既存Spike flowで完了させ、親Bugの再実行でRoot Cause Gateを満たした結果を読んでから通常のPlan Review、Test Implementation、Test Review、Implementation、Human Acceptanceへ接続します。
