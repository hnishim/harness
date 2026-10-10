# Planning / Plan Review

## Planning

local Planningでは、Repository-aware Planの初回作成は必ずPlannerへ委任します。local Planningでは、Repository-aware Planの改訂も必ずPlannerへ委任します。親エージェントはRepository-aware Planを直接作成しないものとします。親エージェントはRepository-aware Planを直接改訂しないものとします。PlannerはPlan案の範囲、実施項目、Test decision、テスト／検証戦略、未確認事項を整理します。親エージェントはRepositoryとの整合、受入条件、Plan hashとbindingを検証し、Linearへの保存、Status・Assignee、承認と遷移を管理します。PlannerはファイルやLinearを変更せず、Statusやbindingを決定しません。BLOCKEDまたは未解決の人間判断をPLAN_READY／Plan readyとして扱いません。人間判断が解決した後も、親エージェントは自らRepository-aware Planを改訂せず、改訂をPlannerへ委任します。

Descriptionは課題の要点だけを保持します。詳細Planは `artifact_key: plan` を持つ、更新可能な1件のコメントに保存します。既存Planがあれば同じコメントIDを更新します。

Planには課題に必要な範囲で次を含めます。

- 対象範囲と変更対象
- 実施項目
- `Test required`/`Test not required` と理由
- Test requiredの場合の主なテスト層、不具合が発生する処理の境目、関連機能の回帰テスト、未検証の範囲
- 実際に利用する手順・呼び出し経路、仕様への影響、原因を判断した根拠、関連する基準文書の更新のうち、該当するもの
- 検証方法
- 未確認事項

リポジトリを確認せず対象ファイルや実装手順を推測しません。受入条件を満たす既存機能・設定・共通関数を先に検討し、最小の実現方式を選びます。1回限りの移行では手動の操作またはワークフロー内での再開時の移行を優先します。新規の処理、恒久・一時スクリプト、抽象化、依存、設定の自動操作などは、より単純な方法では満たせない具体的な要件やリスクがある場合だけ採用し、理由をPlanに示します。安全性・データ保全・互換性に必要な処理を省略しません。

Test decisionは検証の要否と、新規・変更テストコードの要否を区別して判断します。既存テスト、静的検査、手動確認、Local Acceptanceで十分なら、検証を実施する場合も `Test not required` を選べます。`Test required` とする場合は、新規・変更テストが検出する具体的なリスクと、既存の検証手段に加えてテストコードを作成・自動化・一時使用・維持する必要性をPlanに示します。一時テストも既定で追加しません。Bug modeの `Test required` は維持し、採用したテストの寿命管理は [test.md](test.md) に従います。

仕様、優先順位、設計方針、副作用受容など、合理的に一意化できない人間判断が残る場合は、Agentが任意の選択肢を採用してPlan readyにしません。未決事項・選択肢・トレードオフをPlanまたは追記専用イベントへ保存し、同じStatusのままHumanをnext actorとして停止します。人間判断を現在のPlan版へ反映した後、Agentだけで継続可能ならAgentへ戻してPlanningを再開します。

Plan保存後に正規化SHA-256を計算し、approvalへ `current_plan_hash` とPlanコメントIDを保存します。内容が変われば `workflow.toml` の失効規則を適用します。

Bugでは [bug.md](bug.md)、Spikeでは [spike.md](spike.md) の追加条件を適用します。

### Plan改訂時の既存価値保持

既存Planを改訂する場合は、改訂前Planに含まれる利用者価値・利用経路・外部挙動を改訂後Planと照合します。新しい方式を追加したことだけを理由に、既存要件を削除・置換しないものとします。既存要件と新方式が両立可能なら、既存要件を保持します。

利用者価値・利用経路・外部挙動の削除・置換が必要な場合は、その削除・置換についてHumanの明示承認を得るまでPlan ready（`PLAN_READY`）にしないものとします。必要性と失われる既存価値をPlanまたは追記専用イベントへ保存し、同じStatusのままHumanをnext actorとして停止します。明示承認後は、その判断をPlanへ反映して通常のPlan Reviewへ進めます。

この確認は利用者価値・利用経路・外部挙動が失われる変更を対象とし、単なる文言整理・実装詳細変更は対象外です。そのため、利用者価値等を失わない文言整理・実装詳細変更では追加の人間確認は不要です。既存要件を網羅的にID管理する仕組みは要求しません。

実現方式を変更する改訂では、旧方式に付随した処理・テスト・検証・依存関係を再評価し、不要になったものを機械的に持ち越しません。利用者価値・受入条件そのものは維持します。

## 既存Planへの差戻し

承認済みPlanの前提・受入条件に実質的な変更が必要だと確認結果から判明したとき、未完了Issueの作業フェーズからPlanningへ戻す処理は受理済み `workflow.toml[phase_return]` に従います。現在のPlanの版・旧承認・テストmanifest・候補コミットのSHAを追記専用の履歴に記録し、旧Plan Reviewおよび後続工程の承認を無効化します。変更前のPlan承認を新Planへ流用せず、同じ `artifact_key: plan` を改訂した後、通常の独立Plan Reviewを実行します。原因が不明な場合は差戻しを開始しません。既存のReview判定で扱える場合は、その判定に従います。

## Plan Review

Plan Reviewは成果物を作成した実行とは独立した読み取り専用のレビュー担当が行います。開始時に最新のIssue、Description、Plan、approval、delivery、全イベント、Label、依存関係、基準Harness、対象リポジトリを再取得します。

確認項目：

- 要求と受入条件を満たす最小範囲か。既存機能・設定・共通関数や一度限りの手動操作など、提案より単純な方法で十分でないか
- リポジトリ事実と整合するか
- Test decisionとテスト戦略が妥当か。検証の必要性と新規・変更テストコードの必要性を混同せず、追加テストが検出する具体的リスクと作成・維持の理由があるか
- 不具合が発生する処理の境目と未検証の範囲が明確か
- ローカル環境とリモート環境で実行できる操作の違いを理由に、判断基準を変えていないか
- Plan変更時の承認の無効化と、承認と対象の版の対応に問題がないか
- 既存Planの改訂では、改訂前の利用者価値・利用経路・外部挙動が、Humanの明示承認なく欠落していないか。変更した方式では不要な処理・テスト・検証・依存関係を温存していないか
- 実際に利用する手順・呼び出し経路／仕様への影響／原因の調査／関連する基準文書の更新について、それぞれ必要となる条件を確認しているか

提案が正しく動作し安全であることだけでは、追加コード・テストの必要性は正当化されません。追加の必要性を具体的に説明できない場合は `CHANGES_REQUIRED` とし、理由を指摘します。一方、複雑な変更、データ損失、継続的な回帰などへの合理的な対策は、単純化だけを理由に却下しません。

判定は `APPROVE`/`CHANGES_REQUIRED`/`BLOCKED`。

- APPROVE: approvalへ `approved_plan_hash=current_plan_hash` と判定を保存
- CHANGES_REQUIRED: 具体的な指摘事項を追記専用の履歴に保存し、approvalを更新
- BLOCKED: 判断できない具体的な理由を追記専用の履歴に保存

Plan Reviewには人間確認gateがあります。Reviewer判定は対象Plan版へbindingしてapprovalへ保存しますが、その判定だけではStatus transitionを適用しません。同じPlan Review StatusのままHumanをnext actorとしてassignし、Status・Assignee・approvalをreadbackしてdurable stopします。Test Review、Implementation Review、Spike Result Reviewにはこの追加Human確認を要求しません。

人間確認が現在のReviewer判定とPlan版に対応していることを確認した後、判定とtest decisionを `workflow.toml` へ適用して次Statusを決めます。ここで遷移表を再定義しません。遷移後は本来のnext actorへAssigneeを更新してreadbackし、最終next actorがHumanならその実行を停止し、Agentなら他の停止条件がない限り次のactionへ継続します。Plan Reviewの確認gateを遷移後に別の停止条件として二重化しません。

Plan ReviewのAPPROVEで同一実行を停止する場合は、停止前にチャットへ「設計判断の要点」を出力します。主情報は、Planning開始時の重要な未確定・不明事項、それぞれを確定した根拠と確定内容です。重要な代替案を採用しなかった理由と残る未解決事項は、該当する場合に併記します。最後にTest decisionと次Status／actionを簡潔に示します。作業項目の要約は補助情報とし、未確定事項がどう確定されたかを中心にします。説明は人間に分かりやすい言葉で行い、内部のStatus名・field名・hashやworkflow識別子の羅列だけで済ませません。
