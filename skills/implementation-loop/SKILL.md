---
name: implementation-loop
description: Linear Statusをphase selectorとしてPlanningを委譲し、通常IssueまたはSpikeのExecution、独立Review、明示的Closeまでを実行する。
---

# Implementation Loop

## 役割

入力はLinear Issue IDです。**Linear Status = 現在実行すべきphase** とします。

`Backlog` / `Todo` / `In Plan Review` は `linear-issue-plan-review` へ委譲し、このSkillはPlanning内部仕様を持ちません。Executionでは `Spike` labelの有無で通常IssueとSpikeを分岐します。

## 共通契約

- phase開始前にIssue、Status、Description、全Comments、Labels、Repository root / worktreeを再取得する
- Linearへの書き込みは親Agentだけが行う。このSkillの起動は、本文で定義した対象IssueのComment / Status更新への承認を含む
- 書き込み直前にbaseline一致を確認し、書き込み後に意図した差分だけを再取得確認する。不一致・取得不能では進めない
- phaseはStatusだけで決める。modeは `Spike` labelだけで決める
- Planning Statusではcanonical markerを事前検証せずPlanning Skillへ委譲する
- Execution Statusではcanonical marker / Planを検証し、曖昧ならworker/reviewerを起動しない
- `Strict profile` ありをstrict、なしをlightweightとし、このSkillではprofile labelを変更しない。Labelの新規付与はPlanning側でユーザー承認後にのみ行う
- 通常IssueではPlanのTest判定とTestグループLabel（`Test required` / `Test not required`）が1つずつ一致することを必須とする。Spikeは `Test not required` だけであることを確認する
- 承認済みPlanの範囲・制約・受入条件を拡張しない。Planを超える変更はPlanningへ戻す
- 要件のない抽象化、設定化、依存追加、refactorを行わず、無関係なworktree変更を保持する
- Review履歴、実行Status、回数、結果はDescriptionではなくCommentへ残す

開始時、Issue取得とStatus検証に成功したら `Issue概要: <Issue ID> — <title>` を1行だけ表示する。同じチャットですでに表示済みなら再掲しない。Planningへ委譲するときは `issue_summary_displayed=true` を渡す。

停止時は次の形式で報告する。

```text
結果: BLOCKED
停止箇所: <取得|canonical Plan|Agent|検証|保存|Git/外部>
確認事項: <確認できた事実。原因未確定ならその旨>
推奨対応: <推奨する次の行動>
再開条件: <再開に必要な条件>
```

## Routing

### 共通

| Status | phase |
| --- | --- |
| `Backlog` / `Todo` / `In Plan Review` | `linear-issue-plan-review`へ委譲 |
| `Implementation` | Implementation または Spike Experiment / PoC |
| `In Implementation Review` | Implementation Review または Spike Result Review / Close |
| `Done` | 完了済み。変更せず終了 |

### 通常Issueのみ

| Status | phase | 成功時 |
| --- | --- | --- |
| `Test Implementation` | Test Implementation | `In Test Review` |
| `In Test Review` | Test Review | `TESTS_APPROVED → Implementation`; `TESTS_CHANGES_REQUIRED → Test Implementation`; `PLAN_INCOMPLETE → Todo` |

Spikeで `Test Implementation` / `In Test Review` にいる場合は状態不整合として停止する。

### 進行規則

- forward transitionは再取得確認後、同じ実行内で次phaseへ進めてよい
- `CHANGES_REQUIRED`、`PLAN_INCOMPLETE`、`MATERIAL_DEVIATION` で `Todo` へ戻ったら、その実行では停止する
- 各Reviewでは、まず直前phaseの成果物自体がIssue達成に必要な最小限かを確認する。scope外の実質的な複雑性の除去は必須指摘になり得るが、残置costより削除・再検証costが大きいだけのcleanupでは再ループさせない
- Reviewerは実装必須の指摘だけを出し、各指摘に `acceptance` / `safety` / `bug` / `scope-removal` の分類と具体的根拠を付ける。任意改善はユーザーが求めた場合を除きReview結果へ残さない
- 親Agentは分類と具体的根拠があることだけを確認し、技術的なReviewをやり直さない。根拠が欠ける指摘は実装要求にせず、必須指摘が残らなければ各Reviewの正判定へ補正する
- 変更要求を保存したとき、直前の同phase Review Commentも同じ変更要求なら2回連続とみなす。通常のbackward transitionは行うが、その実行ではそこで停止し、次の明示的な実行まで自動修正を続けない
- `PASS` / `DECISION_READY`、BLOCKED、2回連続の変更要求、Close待ちでは停止する

Planning委譲後はIssueを再取得し、確定したStatusだけを次のroutingに使う。`Done` はno-opで終了する。

## Execution開始ゲート

Execution Statusでは次を確認する。

1. canonical markerと `## 承認済みPlan` / `## 参考情報` を安全に抽出できる
2. `Spike` labelの有無からmodeを一意に決められる
3. `Strict profile` labelの有無からprofileを一意に決められる
4. 通常IssueはTest判定とTest Labelが一致する。Spikeは `Test not required` である
5. Repository root / worktreeと保持すべき既存変更を確認できる
6. 各worker phase開始時に既存dirty pathを確認する。今回変更予定pathと重なり、かつ同一Issueの直前phase成果物として確認できない変更がある場合は停止する。hunk単位の自動分離は行わない

不一致は自動修復せず停止する。

### `In Implementation Review` のphase内substate

StatusはphaseのSource of Truthのままとし、Commentは `In Implementation Review` 内でReview済みかを判定するためだけに使う。

Review直前に、今回scopeの相対pathと各成果物のSHA-256（削除は `deleted`）をsortしてhash化した `成果物fingerprint` を作る。`In Implementation Review` 開始時に、最新の該当Review Commentと現在のfingerprintを比較する。

- 通常Issueで最新Commentが `フェーズ: Implementation Review`、`判定: PASS`、fingerprint一致 → Reviewを再実行せずClose待ち
- Spikeで最新Commentが `フェーズ: Result Review`、`判定: DECISION_READY`、fingerprint一致 → Reviewを再実行せずClose待ち
- fingerprintが変わっている、または有効なReview Commentがない → Reviewを実行する
- PASS / DECISION_READY以外のReview結果なのにStatusが `In Implementation Review` のままなら状態不整合として停止する

明示的Close指示がある場合も、最新のPASS / DECISION_READYとfingerprint一致を確認できる場合だけCloseへ進む。

## 通常Issue: Test Implementation / Review

### Test Implementation

`Test required` の場合だけ実行する。

1. implementer（原則 Luna / medium）へPlanを渡し、Planで許可されたテスト成果物だけを変更させる
2. Requirements / Acceptance Criteriaから公開動作単位のテストを作り、Issueに関係する重要なfailure / edge / side effectを扱う
3. strictでは [references/strict-profile.md](references/strict-profile.md) を追加適用する
4. 成功時は変更ファイル、検証command / result、成果物path/hash、未検証事項をCommentへ保存し `In Test Review` へ更新する

### Test Review

- lightweight: `agents/reviewer-lightweight.toml`（Terra / high、read-only）
- strict: `agents/reviewer.toml`（Sol / high、read-only）+ strict追加要件
- `review_phase: tests-only`
- 判定: `TESTS_APPROVED` / `TESTS_CHANGES_REQUIRED` / `PLAN_INCOMPLETE`

まずTest成果物そのものが必要最小限かを確認する。Acceptance Criteriaを超えた網羅性、Issueと関係の薄いedge case、不要なfixture / mock / helper / abstraction、Testのためだけのproduction interface複雑化が実質的な負荷を生む場合は削減対象とする。

`TESTS_APPROVED` では承認テストのpath、SHA-256、再実行command、必要な手動確認を `approved-tests` baselineとしてCommentへ固定し、`Implementation` へ進める。以後このbaselineの削除・弱体化・skip・無断変更を禁止する。

`PLAN_INCOMPLETE` はPlan不足が実装開始を妨げる場合だけ使う。その他の指摘の扱いは進行規則のReview共通契約に従う。

Test Review Commentは少なくとも次を含める。

```text
フェーズ: Test Review
対象Issue: <issue-identifier>
プロファイル: lightweight | strict
判定: TESTS_APPROVED | TESTS_CHANGES_REQUIRED | PLAN_INCOMPLETE
必須指摘: <各指摘を acceptance | safety | bug | scope-removal の分類と具体的根拠付きで記載。なければ なし>
approved-tests: <TESTS_APPROVED時のみpath / SHA-256 / 再実行command / 必要な手動確認>
```

`TESTS_CHANGES_REQUIRED` は `Test Implementation` へ戻す。直前のTest Reviewも `TESTS_CHANGES_REQUIRED` なら、遷移後にその実行を停止する。`PLAN_INCOMPLETE` は理由をCommentへ保存して `Todo` へ戻す。

## 通常Issue: Implementation / Review

### Implementation

1. `Test required` は最新 `TESTS_APPROVED` と `approved-tests`、`Test not required` はPlan記載の検証方法をbaselineとする
2. implementerへPlanとbaselineを渡し、Plan範囲だけを実装させる
3. approved-testsは変更させない。無効なら停止する
4. 実装後にPlan traceability、変更ファイル、検証結果、未検証事項を確認する
5. completion Commentを保存し `In Implementation Review` へ更新する

### Implementation Review

- lightweight: `agents/reviewer-lightweight.toml`（Terra / high、read-only）
- strict: `agents/reviewer.toml`（Sol / high、read-only）+ strict追加要件
- `review_phase: implementation`
- 判定: `PASS` / `CHANGES_REQUIRED` / `MATERIAL_DEVIATION`

まず実装結果そのものが必要最小限かを確認する。Plan外のrefactor、不要な汎用化・抽象化・設定化・interface / layer / dependency追加、使われない拡張ポイント、将来対応が実質的な複雑性・保守負荷・riskを生む場合は削減対象とする。

`MATERIAL_DEVIATION` は承認済みPlanへ戻らないと解決できない実質的な乖離だけに使う。その他の指摘の扱いは進行規則のReview共通契約に従う。

Review Commentは少なくとも次を含める。

```text
フェーズ: Implementation Review
対象Issue: <issue-identifier>
プロファイル: lightweight | strict
判定: PASS | CHANGES_REQUIRED | MATERIAL_DEVIATION
成果物fingerprint: <sha256>
必須指摘: <各指摘を acceptance | safety | bug | scope-removal の分類と具体的根拠付きで記載。なければ なし>
```

`PASS` はReview結果、変更・検証結果、残作業、未検証事項を同Commentへ保存しStatusを維持してCloseを待つ。`CHANGES_REQUIRED` は `Implementation` へ戻し、直前のImplementation Reviewも `CHANGES_REQUIRED` なら遷移後にその実行を停止する。`MATERIAL_DEVIATION` は期待値・観測値・影響範囲をCommentへ保存して `Todo` へ戻す。

## Spike: Experiment / Result Review

Spikeでは [references/spike-mode.md](references/spike-mode.md) を適用し、`Test Implementation` / `In Test Review` を使わない。

### `Implementation`: Experiment / PoC

1. implementerへ承認済みExperiment Planを渡す
2. 判断に必要な最小のPoC、計測、fixture、実験だけを行い、本番品質・網羅的テスト・無関係なrefactorを要求しない
3. 各検証論点について条件、観測結果、再現手順、成功/失敗/未検証を記録する
4. 実験結果をCommentへ保存し `In Implementation Review` へ更新する

### `In Implementation Review`: Result Review

独立ReviewerはまずExperiment / PoC自体が判断に必要な最小限だったかを確認し、不要な本番品質化、網羅的テスト、過剰なfixture / 計測 / abstractionがあれば削減対象とする。その上で、コード品質より、結果からPlanの判断基準に沿った結論を導けるか、偏り・不足がないか、追加検証が必要かを確認する。

判定は次の3つ。

- `DECISION_READY`: 採用方式、制約、未対応範囲、追加Spikeの要否を結論としてCommentへ保存し、Statusを維持してCloseを待つ
- `CHANGES_REQUIRED`: 判断に必要な追加検証、Experiment修正、または実質的に過剰なPoC成果物の削減が必要な場合だけ使う
- `MATERIAL_DEVIATION`: Planや仮説の再設計が本当に必要かを確認し、必要な場合だけ理由をCommentへ保存して `Todo` へ戻す

指摘の扱いは進行規則のReview共通契約に従う。

Result Review Commentは少なくとも次を含める。

```text
フェーズ: Result Review
対象Issue: <issue-identifier>
プロファイル: lightweight | strict
判定: DECISION_READY | CHANGES_REQUIRED | MATERIAL_DEVIATION
成果物fingerprint: <sha256>
必須指摘: <各指摘を acceptance | safety | bug | scope-removal の分類と具体的根拠付きで記載。なければ なし>
```

`CHANGES_REQUIRED` は `Implementation` へ戻す。直前のResult Reviewも `CHANGES_REQUIRED` なら遷移後にその実行を停止する。

## Close

通常Issueの `PASS` またはSpikeの `DECISION_READY` 後、ユーザーから対象Issueを閉じる明示的な指示を受けた場合だけ行う。

1. Issue ID / Statusと、現在の成果物fingerprintに一致する最新の `PASS` / `DECISION_READY` Review Commentを再取得確認する
2. `git-add-commit-push` へ対象範囲とクローズ指示を渡して委譲する。Git操作の安全条件・remote選択は同SkillをSource of Truthとする
3. Git Skillが成功、または送信すべき変更なしを確認できた場合だけ `Done` へ更新する
4. Git失敗・結果不明・Issue/Review state不一致では `In Implementation Review` に留める
5. `Done` 更新後に再取得確認する

## Agent / packet failure

worker/reviewer出力が要求schema・phase・decisionに適合しない場合、形式訂正を1回だけ求めてよい。再度不正ならStatusを変えず停止する。

## 終了報告

必要な項目だけを日本語名で簡潔に報告する。通常Issueの `PASS` / Spikeの `DECISION_READY` ではClose待ちであることを明示する。

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
