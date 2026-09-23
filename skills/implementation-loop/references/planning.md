# Planning / Plan Review

## Planning

Descriptionは課題の要点だけを保持します。詳細Planは `artifact_key: plan` を持つ、更新可能な1件のコメントに保存します。既存Planがあれば同じコメントIDを更新します。

Planには課題に必要な範囲で次を含めます。

- 対象範囲と変更対象
- 実施項目
- `Test required` / `Test not required` と理由
- Test requiredの場合の主なテスト層、不具合が発生する処理の境目、関連機能の回帰テスト、未検証の範囲
- 実際に利用する手順・呼び出し経路、仕様への影響、原因を判断した根拠、関連する基準文書の更新のうち、該当するもの
- 検証方法
- 未確認事項

リポジトリを確認せず対象ファイルや実装手順を推測しません。一回限りの移行では手動の操作またはワークフロー内での再開時の移行を優先し、恒久スクリプトを安易に追加しません。

Plan保存後に正規化SHA-256を計算し、approvalへ `current_plan_hash` とPlanコメントIDを保存します。内容が変われば `workflow.toml` の失効規則を適用します。

Bugでは [bug.md](bug.md)、Spikeでは [spike.md](spike.md) の追加条件を適用します。

## 既存Planへの差戻し

承認済みPlanの前提・受入条件に実質的な変更が必要だと確認結果から判明したとき、未完了Issueの作業フェーズからPlanningへ戻す処理は受理済み `workflow.toml[phase_return]` に従います。現在のPlanの版・旧承認・テストmanifest・候補コミットのSHAを追記専用の履歴に記録し、旧Plan Reviewおよび後続工程の承認を無効化します。変更前のPlan承認を新Planへ流用せず、同じ `artifact_key: plan` を改訂した後、通常の独立Plan Reviewを実行します。原因が不明な場合は差戻しを開始しません。既存のReview判定で扱える場合は、その判定に従います。

## Plan Review

Plan Reviewは成果物を作成した実行とは独立した読み取り専用のレビュー担当が行います。開始時に最新のIssue、Description、Plan、approval、delivery、全イベント、Label、依存関係、基準Harness、対象リポジトリを再取得します。

確認項目:

- 要求と受入条件を満たす最小範囲か
- リポジトリ事実と整合するか
- Test decisionとテスト戦略が妥当か
- 不具合が発生する処理の境目と未検証の範囲が明確か
- ローカル環境とリモート環境で実行できる操作の違いを理由に、判断基準を変えていないか
- Plan変更時の承認の無効化、旧形式からの移行、承認と対象の版の対応に問題がないか
- 実際に利用する手順・呼び出し経路／仕様への影響／原因の調査／関連する基準文書の更新について、それぞれ必要となる条件を確認しているか

判定は `APPROVE` / `CHANGES_REQUIRED` / `BLOCKED`。

- APPROVE: approvalへ `approved_plan_hash=current_plan_hash` と判定を保存
- CHANGES_REQUIRED: 具体的な指摘事項を追記専用の履歴に保存し、approvalを更新
- BLOCKED: 判断できない具体的な理由を追記専用の履歴に保存

次Statusは判定とtest decisionを `workflow.toml` へ適用して決めます。ここで遷移表を再定義しません。
