# Test Implementation + Test Review

通常Issue（Bug modeを含む）かつ `Test required` の `Test Implementation`/`In Test Review` で読む。共通契約とReview作法は `../SKILL.md` に従う。

## Test Strategy

Test Implementation前に、IssueのAcceptance Criteriaとfailure boundaryから、必要なtest layerをPlanとTest Commentへ明示します。`Test required` は専用Test成果物を作ることを意味しますが、すべてのIssueで同じlayerやE2Eを要求する意味ではありません。

| Test layer | 主な責務 |
| --- | --- |
| Unit | pure logic、変換、state transition、境界条件を検証する |
| Integration | filesystem、subprocess、DB、API、GUI automation、OS applicationなど外部境界との相互作用を検証する |
| End-to-end / Acceptance | entry pointから最終状態までのuser-visible workflowを検証する |
| Static assertion | runtime behaviorの代替ではなく、禁止API・architecture invariant・implementation constraintを補助的に検証する |
| Manual check / Human Acceptance | 自動化が合理的でない、または安全でない実利用条件を確認する |

次の順序で選びます。

1. Issueの失敗が発生するもっとも低い「実境界」を特定する
2. その境界を直接通る主test layerを選ぶ
3. 低いlayerで保証できる範囲と、上位layerまたはmanual checkへ残す範囲を分ける
4. 各layerの期待値をAcceptance Criteria、公開契約、ユーザー可視の振る舞いから定義する

## Failure Boundary Principle

TestはIssueの不具合が実際に発生するfailure boundaryを可能な限り通します。外部境界がfailure boundaryそのものの場合、外部境界をmock/fixtureで置き換えたTestだけではAcceptanceを保証したことにしません。

Mock、fixture、stubを使う場合は、Test Comment/Review Resultに次を明記します。

- 何を置き換えたか
- 置き換えによって未検証になる挙動
- その未検証範囲を確認するintegration、E2E、manual checkまたはHuman Acceptance
- 対象ロジックそのものをmockしていないこと

例として、Finderとのinteractionがfailure boundaryなら、Finder非接続fixtureやpure handlerだけでは十分ではありません。Raycast起動経路でのみ発生する不具合なら、そのentry pointを含む確認を残します。

HIR-169のように「既存Finder windowがあるときのwindow数・path・Desktop window」が受入条件となるIssueでは、Finderとのintegrationまたは実際のentry pointを含むAcceptanceを主境界にします。Finder非接続fixture、pure handler test、production sourceのstatic assertionは補助に留め、それだけでTest Reviewを承認しません。

## Behavior over implementation detail

期待値はIssueのAcceptance Criteria、公開契約、ユーザー可視の結果から導出します。現在の実装や予定実装の内部構造から期待値を作りません。

Source-level static assertionは、実行可能なruntime behaviorの代替にしません。次の目的に限って補助的に使います。

- Implementation constraint自体がRequirementである
- 危険なAPI・禁止構文の不在を守る
- Architecture invariantを守る
- Runtime testを補助する
- Runtime testが合理的に不可能で、未検証範囲と代替確認を明示できる

Testを全部PASSさせても実不具合が残り得る場合は、Test不足として扱います。Static assertion PASSをintegration、E2E、Human Acceptance PASSと同義にしません。

## Bugfix regression contract

Bug modeでは、可能な範囲でproduction fix前に次を同じ条件で確認します。

```text
Before fix:
bug case        -> FAIL
adjacent case A -> PASS
adjacent case B -> PASS

After fix:
bug case        -> PASS
adjacent case A -> PASS
adjacent case B -> PASS
```

Bug caseだけを追加して既存正常ケースを回帰対象から外しません。隣接ケースはIssue固有にPlanで決め、必要な代表性を確保します。修正前に失敗を確認できない場合は、破壊的・状態再現困難・外部service依存・historical codeの欠落など具体的な理由を記録し、修正済みTestのPASSだけをregression成立と扱いません。

Bugのroot cause investIgAtion、hypothesis、discriminating testは修正Testの代替ではありません。Root Cause Gateを通過した後、同じfailure boundaryを保つregression Testを設計します。

## Mock / fixture と状態待ち

Mock/fixtureはpure logicや異常系を高速に守るために使えます。ただし、原因候補がexternal API semantics、GUI、OS automation、timing、process、filesystem、DB behaviorにある場合、mockだけでroot cause fixの回帰保証を完了しません。

非同期処理は固定sleep/delayより観測可能な状態変化を待ちます。たとえばprocess exists、expected IDの出現、status change、file existence/content change、API state、UI elementの観測可能化を使います。Fixed delayが必要な場合は、理由、timeout、失敗時の観測をPlanまたはTest Commentへ記録します。

## Test Implementation

1. Implementer（原則Luna/medium）へ承認済みPlan、主test layer、failure boundary、bug case、隣接regression、mock/static limitationを渡し、Planで許可されたTest成果物を変更させる
2. Acceptance Criteriaをbehavior単位で検証するTestを作る。Static assertionだけでruntime behaviorを表現しない
3. Failure boundaryを直接通るTestを含め、置き換えた外部境界と未検証範囲を記録する
4. Bug fixでは、修正前のbug case FAILと既存正常ケースPASSを確認する。確認不能なら具体的な理由を記録する
5. 変更ファイル、検証command/result、成果物path/hash、主test layer、failure boundary、未検証事項、必要なmanual checkをCommentへ保存し `In Test Review` へ更新する

Test成果物の作成自体がroot-cause investIgAtionやproduction implementationを代替してはいけません。

## Test Review

- Lightweight Reviewer: `agents/reviewer-lightweight.toml`（Terra/high、read-only）
- Strict: [strict-profile.md](strict-profile.md) を追加適用
- 判定： `TESTS_APPROVED`/`TESTS_CHANGES_REQUIRED`/`PLAN_INCOMPLETE`

`PLAN_INCOMPLETE` はPlan不足がImplementation開始を妨げる場合に使います。

Reviewerは少なくとも次を確認します。

- Acceptance Criteriaをbehaviorとして検証しているか
- 選択したtest layerがIssueのfailure boundaryを適切に通しているか
- Bug fixなら元のfailureを検出できるか、修正前FAILを確認できない理由が具体的か
- 既存正常ケースの隣接regressionが含まれているか
- Mock、fixture、static assertionで置き換えた範囲と未検証範囲が明示されているか
- Implementation detailへ過度に結合していないか
- Fixed delayではなく状態変化を待っているか、delayの理由が明示されているか
- 「このTest群をすべてPASSさせても、Issueで報告された実際の不具合が残り得るか」を否定できるか

最後の問いに肯定で答えられる場合は `TESTS_CHANGES_REQUIRED`、Planにfailure boundaryや必要なlayerがない場合は `PLAN_INCOMPLETE` とします。

Canonical Review Resultのdecisionは `TESTS_APPROVED`/`TESTS_CHANGES_REQUIRED`/`PLAN_INCOMPLETE`/`BLOCKED` を使います。Test Implementationのpath/SHA-256/再実行command/必要な手動確認を `approved_tests` 候補としてReviewerへ渡します。

- `TESTS_APPROVED` → approved-testsをbaselineとして固定し `Implementation` へ進む
- `TESTS_CHANGES_REQUIRED` → `Test Implementation` へ戻す
- `PLAN_INCOMPLETE` → 理由をCommentへ保存して `Todo` へ戻し停止する
