# Test Implementation / Test Review

通常課題の `Test required` で使用します。

## Test Implementation

承認済みPlanから、受入条件を振る舞いとして検証するテストだけを先に作ります。実装本体を混ぜません。

テスト層は、不具合が発生し得る処理の境目に応じて選びます。単体、結合、E2E／受入、静的検査、手動確認を同一視しません。外部システムとの接続部分を模擬する場合は、模擬した範囲と実際のシステムでは未検証の範囲を明示します。

テストを候補ブランチのrefにコミットした後、同じ入力から常に同じ内容となるよう次のmanifestを作成し、approvalに現在の値として保存します。

- `paths`: リポジトリ相対パスの辞書順集合
- `content_sha256`: 各パスの内容SHA-256
- `manifest_hash`
- `rerun_command`
- `manual_checks`
- `unverified`
- `test_lifetimes`: 各新規・変更テストについて `test_id`、`classification`、`end_condition`、`retention_reason` を持つ、維持・削除条件の記録

`classification` は `transitional`（移行用）または `permanent_regression`（恒久回帰用）とします。移行用では役目が終わる条件を `end_condition` に記録します。移行完了後も恒久CIへ残す場合は、その理由を `retention_reason` に記録します。恒久回帰用では期待値が製品要件・契約に由来することを説明できる状態にし、現行コードの動作をそのまま期待値にしただけのテストを恒久的に残しません。

Characterization test、完全なfixture、完全一致検証は移行時の安全確認として必要なら使用できますが、その必要性だけで恒久回帰用とは扱いません。

この段階のmanifestはレビュー対象であり、まだ承認されていません。

## 承認済みテストの欠陥からの差戻し

Implementationなどの進行中に、具体的な確認結果から承認済みテスト自体の欠陥が確定した場合は、Statusを維持する専用副状態を新設せず `workflow.toml[phase_return]` の汎用差戻しでTest Implementationへ戻します。原因を本体実装とテストのどちらに帰属するか判断できない場合は先に停止します。変更しない承認済みPlan、baseline、候補ref・履歴、影響しない本体実装を保持し、旧テストmanifestに対するTest Review承認を無効化し、旧CI・受入の結果を新しい候補には利用しません。テスト候補を修正するコミットでは強制更新を使わず、変更前後の各テストhashを再計算して新manifestを作成します。旧承認や旧CIを新manifestへ流用せず、通常の独立Test Reviewを受けます。独立したレビュー担当がいなければ、テストを未承認のまま停止します。

## Test Review

成果物を作成した実行とは独立した読み取り専用のレビュー担当が、最新Plan、テスト候補、manifest、基準Harnessを再取得してレビューします。

最低限確認します。

- 受入条件を実装詳細ではなく振る舞いとして検証するか
- 不具合が発生し得る処理の境目を、適切な最下層のテストで直接検証しているか
- 能力不足、承認失効、migration、close、Git安全条件等の組合せは、単なるキー存在ではなく代表入力を使うシナリオで検証されるか
- 模擬環境や静的検査だけの結果を、実際の環境で正常に動作した証拠として扱っていないか
- Approved testsを実装から固定・再実行できるmanifestか
- 新規・変更テストを、移行用か恒久的な回帰テスト用か適切に分類しているか
- 移行用テストの終了条件が明確か。恒久CIへ残す場合は合理的な保持理由があるか
- 恒久回帰用テストの期待値が製品要件・契約に由来し、現行コードの動作をそのまま期待値にしただけのテストになっていないか
- ローカル／リモートでの実装、GitHubからの読取り、CI結果の確認を組み合わせても、既存のGit操作の安全条件を弱めないか

判定は `TESTS_APPROVED`/`TESTS_CHANGES_REQUIRED`/`PLAN_INCOMPLETE`/`BLOCKED`。

TESTS_APPROVEDでは、レビュー対象manifestを `approved_tests_manifest` としてapprovalへ固定し、そのmanifest hashと判定を保存します。変更要求・Plan不足・BLOCKEDの具体的な理由は、追記専用の履歴に保存します。

次Statusは判定を `workflow.toml` へ適用して決めます。

## Implementation開始条件

Implementation開始時は、Git上のapproved testパス集合と各内容SHA-256を再計算し、approved manifestと完全一致することを確認します。一致しなければTest Review承認を失効させます。

実装中はapproved test成果物を変更対象から除外します。
