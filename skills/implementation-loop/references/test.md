# Test Implementation / Test Review

通常課題の `Test required` で使用します。

## Test Implementation

承認済みPlanから、受入条件を振る舞いとして検証するテストだけを先に作ります。実装本体を混ぜません。

テスト層は失敗発生境界から選びます。単体、結合、E2E／受入、静的検査、手動確認を同一視しません。外部境界をモックする場合は、置き換えた範囲と未検証範囲を明示します。

テスト成果物をcandidate refへcheckpointした後、次のmanifestを決定的に作りapprovalへ現在値として保存します。

- `paths`: リポジトリ相対パスの辞書順集合
- `content_sha256`: 各パスの内容SHA-256
- `manifest_hash`
- `rerun_command`
- `manual_checks`
- `unverified`
- `test_lifetimes`: 各新規・変更テストについて `test_id`、`classification`、`end_condition`、`retention_reason` を持つ寿命レコード

`classification` は `transitional`（移行用）または `permanent_regression`（恒久回帰用）とします。移行用では役目が終わる条件を `end_condition` に記録します。移行完了後も恒久CIへ残す場合は、その理由を `retention_reason` に記録します。恒久回帰用では期待値が製品要件・契約に由来することを説明できる状態にし、現行実装の単なる写経を恒久化しません。

Characterization test、完全fixture、完全一致検証は移行時の安全確認として必要なら使用できますが、その必要性だけで恒久回帰用とは扱いません。

この段階のmanifestはレビュー候補であり、承認済みmanifestではありません。

## 承認済みテストの欠陥からの差戻し

Implementation等の進行中に、証跡付きで承認済みテスト自体の欠陥が確定した場合は、Statusを維持する専用副状態を新設せず `workflow.toml[phase_return]` の汎用差戻しでTest Implementationへ戻します。原因を本体実装とテストのどちらに帰属するか判断できない場合は先に停止します。変更しない承認済みPlan、baseline、候補ref・履歴、影響しない本体実装を保持し、旧テストmanifestとTest Review承認、旧CI・受入の新版への利用を失効させます。テスト候補を修正するcheckpointはnon-forceとし、変更前後の各テストhashを再計算して新manifestを作成します。旧承認や旧CIを新manifestへ流用せず、通常の独立Test Reviewを受けます。Reviewer不在なら未承認のまま停止します。

## Test Review

成果物作成主体とは独立した読み取り専用Reviewerが、最新Plan、テスト候補、manifest、基準Harnessを再取得してレビューします。

最低限確認します。

- 受入条件を実装詳細ではなく振る舞いとして検証するか
- 失敗発生境界を合理的な最下層で直接通すか
- 能力不足、承認失効、migration、close、Git安全条件等の組合せは、単なるキー存在ではなく代表入力を使うシナリオで検証されるか
- モック／静的検査だけで実動作PASSを主張していないか
- Approved testsを実装から固定・再実行できるmanifestか
- 新規・変更テストの寿命分類が妥当か
- 移行用テストの終了条件が明確か。恒久CIへ残す場合は合理的な保持理由があるか
- 恒久回帰用テストの期待値が製品要件・契約に由来し、現行実装の単なる写経になっていないか
- Local/remote実装とGitHub読取・CI観測の組合せで既存Git安全条件を弱めないか

判定は `TESTS_APPROVED`/`TESTS_CHANGES_REQUIRED`/`PLAN_INCOMPLETE`/`BLOCKED`。

TESTS_APPROVEDでは、レビュー対象manifestを `approved_tests_manifest` としてapprovalへ固定し、そのmanifest hashと判定を保存します。変更要求・Plan不足・BLOCKEDは不変イベントへ保存します。

次Statusは判定を `workflow.toml` へ適用して決めます。

## Implementation開始条件

Implementation開始時は、Git上のapproved testパス集合と各内容SHA-256を再計算し、approved manifestと完全一致することを確認します。一致しなければTest Review承認を失効させます。

実装中はapproved test成果物を変更対象から除外します。
