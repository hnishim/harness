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

この段階のmanifestはレビュー候補であり、承認済みmanifestではありません。

## Test Review

成果物作成主体とは独立した読み取り専用Reviewerが、最新Plan、テスト候補、manifest、基準Harnessを再取得してレビューします。

最低限確認します。

- 受入条件を実装詳細ではなく振る舞いとして検証するか
- 失敗発生境界を合理的な最下層で直接通すか
- 能力不足、承認失効、migration、close、Git安全条件等の組合せは、単なるキー存在ではなく代表入力を使うシナリオで検証されるか
- モック／静的検査だけで実動作PASSを主張していないか
- approved testsを実装から固定・再実行できるmanifestか
- local / remote統合で既存Git安全条件を弱めないか

判定は `TESTS_APPROVED` / `TESTS_CHANGES_REQUIRED` / `PLAN_INCOMPLETE` / `BLOCKED`。

TESTS_APPROVEDでは、レビュー対象manifestを `approved_tests_manifest` としてapprovalへ固定し、そのmanifest hashと判定を保存します。変更要求・Plan不足・BLOCKEDは不変イベントへ保存します。

次Statusは判定を `workflow.toml` へ適用して決めます。

## Implementation開始条件

Implementation開始時は、Git上のapproved testパス集合と各内容SHA-256を再計算し、approved manifestと完全一致することを確認します。一致しなければTest Review承認を失効させます。

実装中はapproved test成果物を変更対象から除外します。
