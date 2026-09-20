# Planning / Plan Review

## Planning

Descriptionは課題の要点だけを保持します。詳細Planは `artifact_key: plan` の単一可変コメントへ保存します。既存Planがあれば同じコメントIDを更新します。

Planには課題に必要な範囲で次を含めます。

- 対象範囲と変更対象
- 実施項目
- `Test required` / `Test not required` と理由
- Test requiredの場合の主テスト層、失敗発生境界、隣接回帰、未検証境界
- 実利用経路、仕様影響、診断根拠、基準文書同期のうち成立するもの
- 検証方法
- 未確認事項

リポジトリを確認せず対象ファイルや実装手順を推測しません。一回限りの移行は手動またはワークフロー内の遅延移行を優先し、恒久スクリプトを安易に追加しません。

Plan保存後に正規化SHA-256を計算し、approvalへ `current_plan_hash` とPlanコメントIDを保存します。内容が変われば `workflow.toml` の失効規則を適用します。

Bugでは [bug.md](bug.md)、Spikeでは [spike.md](spike.md) の追加条件を適用します。

## 既存Planへの差戻し

承認済みPlanの前提・受入条件に実質的な変更が必要だと証跡から判明したとき、未完了Issueの作業フェーズからPlanningへ戻す処理は受理済み `workflow.toml[phase_return]` に従います。現在のPlan版・旧承認・テストmanifest・candidate SHAをイベントに固定し、旧Plan Reviewおよび下流承認を失効させます。変更前のPlan承認を新Planへ流用せず、同じ `artifact_key: plan` を改訂した後、通常の独立Plan Reviewを実行します。原因が不明なときや既存のReview判定で扱える場合は、独自の差戻しを開始しません。

## Plan Review

Plan Reviewは成果物作成主体とは独立した読み取り専用Reviewerが行います。開始時に最新のIssue、Description、Plan、approval、delivery、全イベント、Label、依存関係、基準Harness、対象リポジトリを再取得します。

確認項目:

- 要求と受入条件を満たす最小範囲か
- リポジトリ事実と整合するか
- Test decisionとテスト戦略が妥当か
- 失敗発生境界・未検証範囲が明確か
- local / remote能力差を意味論の分岐にしていないか
- Plan変更時の承認失効、legacy migration、bindingが安全か
- 実利用経路／仕様影響／診断／基準文書同期の成立条件を独立に扱っているか

判定は `APPROVE` / `CHANGES_REQUIRED` / `BLOCKED`。

- APPROVE: approvalへ `approved_plan_hash=current_plan_hash` と判定を保存
- CHANGES_REQUIRED: findingを不変イベントへ保存し、approvalを更新
- BLOCKED: 判断不能理由を不変イベントへ保存

次Statusは判定とtest decisionを `workflow.toml` へ適用して決めます。ここで遷移表を再定義しません。
