# Test Implementation + Test Review

通常Issue（Bug modeを含む）かつ `Test required` の `Test Implementation`/`In Test Review` で読む。共通契約とReview作法は `../SKILL.md` に従う。

## Test方針

Test Implementation前に、IssueのAcceptance Criteriaと失敗発生境界から、必要なtest layerをPlanとTest stateへ明示します。`Test required` は専用Test成果物を作ることを意味しますが、すべてのIssueで同じlayerやE2Eを要求する意味ではありません。

| Test layer | 主な責務 |
| --- | --- |
| Unit | pure logic、変換、state transition、境界条件を検証する |
| Integration | filesystem、subprocess、DB、API、GUI automation、OS applicationなど外部境界との相互作用を検証する |
| End-to-end / Acceptance | entry pointから最終状態までの利用者に見えるワークフローを検証する |
| Static assertion | 実行時の動作の代替ではなく、禁止API・architecture invariant・implementation constraintを補助的に検証する |
| Manual check / Human Acceptance | 自動化が合理的でない、または安全でない実利用条件を確認する |

次の順序で選びます。

1. Issueの失敗が発生するもっとも低い「実境界」を特定する
2. その境界を直接通る主test layerを選ぶ
3. 低いlayerで保証できる範囲と、上位layerまたはmanual checkへ残す範囲を分ける
4. 各layerの期待値をAcceptance Criteria、公開契約、ユーザー可視の振る舞いから定義する

## 失敗発生境界の原則

TestはIssueの不具合が実際に発生する失敗発生境界を可能な限り通します。失敗発生境界を直接通るTestは、合理的かつ安全に自動化できる場合に必須です。GUI、OS integration、destructive state、外部service等で自動化が合理的でない・安全でない場合は、直接Testを無条件に強制せず、代替確認と未検証範囲を明記します。外部境界が失敗発生境界そのものの場合、外部境界をmock/検証用データで置き換えたTestだけではAcceptanceを保証したことにしません。

Mock、検証用データ、stubを使う場合は、Test state/Review Resultに次を明記します。

- 何を置き換えたか
- 置き換えによって未検証になる挙動
- その未検証範囲を確認するintegration、E2E、manual checkまたはHuman Acceptance
- 対象ロジックそのものをmockしていないこと

直接境界を自動化しない場合は、さらに次をTest state/Review Resultへ明記します。

- 直接通せない理由（安全性、破壊性、外部service、再現性、権限等）
- 自動Testで保証できる範囲
- 未検証範囲
- 代替するintegration、E2E、manual checkまたはHuman Acceptance

例として、Finderとの相互作用が失敗発生境界なら、Finder非接続の検証用データやpure handlerだけでは十分ではありません。Raycast起動経路でのみ発生する不具合なら、そのentry pointを含む確認を残します。

HIR-169のように「既存Finder windowがあるときのwindow数・path・Desktop window」が受入条件となるIssueでは、Finderとのintegrationまたは実際のentry pointを含むAcceptanceを主境界にします。Finder非接続の検証用データ、pure handler test、production sourceのstatic assertionは補助に留め、それだけでTest Reviewを承認しません。

## 実装詳細よりも振る舞いを重視

期待値はIssueのAcceptance Criteria、公開契約、ユーザー可視の結果から導出します。現在の実装や予定実装の内部構造から期待値を作りません。

ソースレベルのstatic assertionは、実行可能な実行時の動作の代替にしません。次の目的に限って補助的に使います。

- Implementation constraint自体がRequirementである
- 危険なAPI・禁止構文の不在を守る
- Architecture invariantを守る
- Runtime testを補助する
- Runtime testが合理的に不可能で、未検証範囲と代替確認を明示できる

Testを全部PASSさせても実不具合が残り得る場合は、Test不足として扱います。Static assertion PASSをintegration、E2E、Human Acceptance PASSと同義にしません。

## Bug修正の回帰テスト規則

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

Bugのroot cause `investigation`、hypothesis、discriminating testは修正Testの代替ではありません。Root Cause Gateを通過した後、同じ失敗発生境界を保つregression Testを設計します。

## Mock / 検証用データと状態待ち

Mock/検証用データはpure logicや異常系を高速に守るために使えます。ただし、原因候補がexternal APIの意味、GUI、OS automation、timing、process、filesystem、DBの動作にある場合、mockだけでroot cause fixの回帰保証を完了しません。

非同期処理は固定sleep/delayより観測可能な状態変化を待ちます。たとえばprocess exists、expected IDの出現、status change、file existence/content change、API state、UI elementの観測可能化を使います。Fixed delayが必要な場合は、理由、timeout、失敗時の観測をPlanまたはTest stateへ記録します。

## 検証実行の境界

Test layerと実行境界は別軸です。Testが何を検証するかと、どの環境でAcceptanceの根拠を取得するかを混同しません。

- **CI Verification**: clean/reproducibleなremote CIで実行できる検証。Acceptanceの根拠に使う場合はcandidate SHAとCI対象SHAの一致を確認する。CI PASSだけでLocal AcceptanceまたはHuman AcceptanceをPASS扱いしない
- **Local Acceptance**: CIでは合理的に再現できず、local runtime、OS/app、credential、symlink、実entry pointなどが必要な検証。現在環境で実行不能ならcandidate SHA、command/entry point、必要environment/application、expected result、未確認理由を引き継ぐ
- **Human Acceptance**: UX、操作感、視覚品質、その他人間の判断を要する最終確認。Local Acceptanceと同一視しない

Repositoryにcanonical test suite / validation commandがある場合、新規testは原則そのsuiteへ追加し、Issueごとの専用CI workflowを増やしません。

## Test Implementation

`state_key: test-implementation` の可変フェーズ状態をTest成果物の現在の永続状態として使います。stateが存在しない初回だけ新規Commentを作成し、そのComment IDを保持します。既存の同じstateがある場合は同じCommentを更新し、別のTest Implementation state Commentは追加しない・作成しない。

このstateは少なくとも現在のTest成果物path / 成果物、SHA-256またはGit blob hash、実行command/result、主test layer、失敗発生境界を含む検証境界、`unverified`、必要なmanual checkを保持します。改訂では過去のスナップショットを追記せず、`state_key: test-implementation` の同じComment IDへ現在の成果物/hashと検証結果を更新します。変更理由が重要なReviewの指摘事項なら、そのfindingは共通immutable eventとして別Commentへ残し、stateから参照できます。

1. Implementer（原則Luna/medium）へ承認済みPlan、主test layer、失敗発生境界、bug case、隣接regression、mock/static limitationを渡し、Planで許可されたTest成果物を変更させる
2. Acceptance Criteriaを振る舞い単位で検証するTestを作る。Static assertionだけで実行時の動作を表現しない
3. 失敗発生境界を直接通るTestを、合理的かつ安全に自動化可能なら含める。自動化しない場合は理由、自動Testの保証範囲、未検証範囲、代替するintegration/E2E/manual check/Human Acceptanceを記録する。置き換えた外部境界も明記する
4. Bug fixでは、修正前のbug case FAILと既存正常ケースPASSを確認する。確認不能なら具体的な理由を記録する
5. `test-implementation` stateを現在の成果物・検証結果へ更新して再取得確認し、`In Test Review` へ更新する

Test成果物の作成自体がroot-cause `investigation` やproduction implementationを代替してはいけません。

## Test Review

`state_key: test-review` の可変フェーズ状態をTest Reviewの引き継ぎ / 結果に使います。存在しない初回だけレビュー資料を新規Commentとして作成しComment IDを保持します。既存の同じstateがある場合はレビュー資料を同じCommentへ更新し、別のReview state Commentは作成しない・追加しない。独立Reviewerはその同じstateへReview Resultと現在の `approved_tests` / 未検証境界を更新します。承認の `TESTS_APPROVED` ではimmutable eventを増やしません。`TESTS_CHANGES_REQUIRED` / `PLAN_INCOMPLETE` / 具体的な `BLOCKED` は共通immutable eventの取り決めに従いイベントを追記し、現在状態も更新します。

Test Reviewはentry pointにかかわらず、成果物作成主体とは**独立**したread-only Reviewerが実行します。executorの種類をワークフローmetadataへ保存せず、approved-tests、判定の語彙、Status transitionを同じ取り決めで使います。

Review開始時は過去chatの結論を前提にせず、最新のLinear Issue / Status / canonical Plan /全Comments / Labels / relations、最新Harnessのcanonical reference、リポジトリの根拠、Test成果物のpath/hash、再実行commandと結果を最新状態として再取得する。Test成果物作成主体と同一contextで承認判定を確定しない。独立Reviewerを現在の実行から利用できない場合は `In Test Review` のまま永続的に停止し、`test-review` stateのレビュー資料から別Chat等へ引き継ぐ。

canonical/localで利用可能な既定Reviewerは次です。

- Lightweight Reviewer: `agents/reviewer-lightweight.toml`（Terra/high、read-only）
- Strict: [strict-profile.md](strict-profile.md) を追加適用
- 判定： `TESTS_APPROVED`/`TESTS_CHANGES_REQUIRED`/`PLAN_INCOMPLETE`/`BLOCKED`

Reviewerは少なくとも次を確認します。

- Acceptance Criteriaを振る舞いとして検証しているか
- 選択したtest layerがIssueの失敗発生境界を適切に通しているか。合理的・安全に自動化可能な場合は直接Testがあり、自動化困難な場合は例外理由、保証範囲、未検証範囲、代替確認があるか
- Bug fixなら元の失敗を検出できるか、修正前FAILを確認できない理由が具体的か
- 既存正常ケースの隣接regressionが含まれているか
- Mock、検証用データ、static assertionで置き換えた範囲と未検証範囲が明示されているか
- Implementation detailへ過度に結合していないか
- Fixed delayではなく状態変化を待っているか、delayの理由が明示されているか
- 「このTest群をすべてPASSさせても、Issueで報告された実際の不具合が残り得るか」を否定できるか

最後の問いに肯定で答えられる場合は `TESTS_CHANGES_REQUIRED`、Planに失敗発生境界や必要なlayerがない場合は `PLAN_INCOMPLETE` とします。

execution binding / adapter / context一般化を含む変更では、旧binding固有の暗黙前提がcanonical全体に残っていないか、新contextから旧context固有capabilityを除いた反例でも成立するか、既存context側の安全条件を弱めていないか、変更ファイルだけでなく間接的なcanonical referencesが整合するかも確認します。

Canonical Review Resultのdecisionは `TESTS_APPROVED`/`TESTS_CHANGES_REQUIRED`/`PLAN_INCOMPLETE`/`BLOCKED` を使います。Test Implementationのpath/SHA-256/再実行command/必要な手動確認を `approved_tests` 候補としてReviewerへ渡します。

- `TESTS_APPROVED` → approved-testsを `test-review` stateの現在のReview Resultとして固定し `Implementation` へ進む
- `TESTS_CHANGES_REQUIRED` → immutableな指摘事項イベントを保存し現在状態を更新して `Test Implementation` へ戻す
- `PLAN_INCOMPLETE` → immutableな判定イベントと現在状態を保存して `Todo` へ戻し停止する
- `BLOCKED` → 具体的なblockerをimmutable eventとして保存し現在状態を更新、Statusを維持して停止する
