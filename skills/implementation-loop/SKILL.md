---
name: implementation-loop
description: Linear Issueを起点に、利用可能能力に応じてlocal / remoteの同一状態機械を実行するcanonical implementation workflow。
metadata:
  notion_sync: "false"
---

# Implementation Loop

## 正規情報源

このSkillがlocal/remote共通の唯一の入口です。実行時は次を正規情報源として扱います。

- Linear: Issue、Status、Label、Plan、approval、delivery、result、不変イベント
- 対象Gitリポジトリ： source、tests、candidate
- このHarness: `workflow.toml` と各参照文書
- CI: 再現可能な自動検証
- Local環境： OS／アプリ／credential等のlocal-only検証
- Human: 明示的な最終受入確認

実行主体名はワークフロー状態へ保存しません。

## 実行時制御契約

各実行の開始時にLinear Issue、全コメント、Status、Label、依存関係、対象リポジトリを再取得した後、**現在受理済みの基準Harness**にある `skills/implementation-loop/workflow.toml` を読みます。

ローカル実行では、SessionStartが受理済みHarness control planeを `ready` または `updated` と確認できることを開始条件とします。`harness_gate=blocked` の場合は古いHarnessへフォールバックせず、その実装ワークフローを開始しません。リモート実行ではGitHub上の受理済みHarnessを直接取得する現行契約を維持します。

1. `routes` でStatusからactionを決める
2. `actions` と `profiles` で必要能力を決める
3. Mode制約を確認する
4. 各参照文書で意味判断を行う
5. 判断確定後、`transitions`、`bindings`、`invalidation` に従って次Statusと承認失効を決める
6. 書込み直前に基準Harnessを再取得し、開始時と同じ契約であることを確認する

当該Issue自身が `workflow.toml` を変更していても、候補上の未受理TOMLをそのIssue自身の制御へ使いません。現在受理済みの基準Harnessを制御面、候補を成果物として分離します。新しい契約は公開後の次回実行から有効です。

Markdownへ同じ状態遷移表・失効表を複製しません。Markdownは「何を判断するか」を所有し、TOMLは判断後の機械的処理を所有します。

## Mode / profile

- `Bug` Label: bug mode。原因確定前は親Issueを実装へ進めません。常に `Test required`
- `Spike` Label: spike mode。主成果物はresult
- 両方ある場合： BLOCKED
- どちらもない場合： normal
- `Strict profile`: strict。必要なstrict Reviewer能力がなければレビューStatusを維持して停止
- それ以外： lightweight

## 能力とGit backend

フェーズ開始時に、現在環境で利用できる能力を事実として判定します。

- 通常のGit checkpointではlocal worktree/Gitが利用可能なら `git_backends.local`、利用できずGitHub read/writeが利用可能なら `git_backends.remote` を使う
- **Closeでは** `workflow.toml[git_backends.close_selection]` に従い、deliveryへ記録したClose起点と明示的な切替許可を現在の能力と併せて判定する。`local-origin` の暗黙remote切替は許可しない
- `remote-only` 起点ではremote backendを使い、ローカル後処理を要求しない。Local-originから明示的にremoteへ切り替えたCloseでは、local同期が未完了の間は `Awaiting Acceptance` を維持する
- 旧deliveryの `close_origin`、`remote_close_authorized`、`local_origin_close_sync` は履歴証跡として保持・読取するが、根拠のない切替許可として解釈しない
- Local-only検証が必要だが利用不能： 未検証のままdeliveryへ引き継ぐ
- Strict Reviewerが必要だが利用不能： profileを緩和せず停止

能力不足をPASSへ変換しません。`remote Git` の操作契約は [references/remote-git.md](references/remote-git.md) を使います。

## Linearの永続構造

新形式では通常Issueの可変情報を次の3件へ集約します。

- `artifact_key: plan`: 詳細Plan本文
- `state_key: approval`: Plan Review、approved tests manifest、Implementation Review、Spike Result Review等の版binding
- `state_key: delivery`: baseline/candidate、検証、CI、local/human acceptance、close進行

Spikeだけ `artifact_key: result` を追加します。

各論理キーは1件だけです。改訂時は同じコメントIDを更新し、同じ現在状態のスナップショットを追加しません。重要な変更要求、具体的BLOCKED、受入FAIL、Bug原因根拠、Spike最終判断は不変イベントとして追記します。

### Hash

PlanとresultはUTF-8、改行LF、各行末の空白除去、末尾改行1個へ正規化してSHA-256を計算します。

Approved tests manifestは、リポジトリ相対パスを辞書順に並べ、各ファイルSHA-256、再実行コマンド、手動確認、未検証範囲、各新規・変更テストの寿命情報を含む決定的な表現からmanifest hashを計算します。寿命情報にはテスト識別子、分類、終了条件、恒久保持理由を含め、分類・終了条件・恒久保持理由の変更もmanifest hashを変化させます。Test Review承認はmanifestの特定版へ結び付けます。

## 旧形式からの遅延移行

新契約公開前から存在する未完了Issueは、最初の再開時に1件ずつ冪等に移行します。一括移行用の恒久スクリプトは作りません。

1. 新形式の `migration_complete: true` が同一schemaで揃っていれば新形式を使用
2. 旧形式のみなら、書込み前に移行元snapshotを固定する
   - `workflow_schema`
   - 旧Description Planのhash
   - 対象となる旧可変コメントID集合
3. Issue IDとsnapshotから一意な `migration_id` を決め、作成するplan/approval/delivery/resultへ同じ値と移行元ID集合を記録
4. 旧Planを意味変更せずplanへ移し、旧承認は対象Plan／tests／candidate／resultの同一性を証明できる場合だけ再binding
5. 同一migration_id・同一snapshotの部分状態は既存コメントを再利用して不足分だけ継続
6. 全必要コメントを書いて再取得一致後にだけ `migration_complete: true` とし、新形式へ切替
7. 切替後にDescriptionを短い課題定義へ整理し、旧Planを第二の正規情報源として残さない

複数migration_id、由来不明、snapshot不一致、重複state、binding矛盾、変換対象を一意に決められない場合は推測せずBLOCKEDです。単に途中移行であることだけではBLOCKEDにしません。

旧 `plan-review`/`test-implementation`/`test-review`/`implementation-completion`/`implementation-review`/`close`/`spike-result` 等は移行入力としてのみ読み、新規更新には使いません。

## フェーズ

### 必要な前フェーズへの差戻し

未完了Issueの進行中に前の作業フェーズへ戻る必要が確定した場合は、既存のReview判定と通常進行を優先し、それだけでは扱えない差戻しに限り、受理済み `workflow.toml[phase_return]` を適用します。差戻し先は原因と影響した成果物から決め、単にStatusを自由に変更する操作とは扱いません。診断・承認失効・候補保持・途中書込みからの再開は [references/implementation.md](references/implementation.md)、[references/planning.md](references/planning.md)、[references/test.md](references/test.md) を使います。Close開始済み、原因未確定、binding不整合、候補の由来不明は停止します。新しい契約は当該HarnessのHuman Acceptanceと公開後の次回実行から適用します。


Statusに対応するactionを `workflow.toml` から選び、次の意味判断文書を適用します。

- Planning/Plan Review: [references/planning.md](references/planning.md)
- Test Implementation/Test Review: [references/test.md](references/test.md)
- Implementation/Acceptance: [references/implementation.md](references/implementation.md)
- Bug: [references/bug.md](references/bug.md)
- Spike: [references/spike.md](references/spike.md)
- Close: [references/close.md](references/close.md)
- Strict profile: [references/strict-profile.md](references/strict-profile.md)

## 独立レビュー

Plan Review、Test Review、normal + Test not requiredのImplementation Review、Spike Result Reviewは、成果物を作成した実行から独立した読み取り専用Reviewerが行います。同一実行内での自己レビューは禁止します。対象成果物とその作成主体を特定できない場合は独立性を推定せず、当該レビューStatusを維持して停止します。レビュアーの環境別選定順序と停止条件は `workflow.toml[independent_reviewer]` に従います。既存のStrict profile追加能力要件は維持します。

レビュー判定は各参照文書の語彙だけを使います。正判定は指摘なし、変更要求は具体的findingあり、BLOCKEDは判断不能の具体的理由ありとします。

## 失効

意味判断後、変更されたbindingに対して `workflow.toml[invalidation]` を適用します。

- Plan版変更： Plan Reviewと下流承認を失効
- Approved tests manifest変更： Test Reviewを失効
- Candidate SHA変更： candidate依存のImplementation Review／受入確認を失効
- Spike result版変更： Result Reviewを失効

失効した承認をStatus名だけから復活させません。

## Git checkpoint

実装・テスト成果物は、現在選択されたGit backendで候補へ固定します。

- Local: local Git executor
- Remote: GitHub candidate ref executor

共通条件は、候補SHA、基準SHA、対象範囲／由来、non-force、履歴書換えなし、変更後readbackです。人間受入前に既定ブランチへ公開しません。

## 停止境界

次では安全側で停止します。

- 必要能力不足
- 独立レビュー待ち
- 変更要求
- Binding不一致
- Migration矛盾
- Checkpoint／外部書込みの結果不明
- Local-only検証未実施
- Human Acceptance待ち
- 明示close待ち
- Done

停止時は再開に必要なStatus、候補SHA、binding、未検証事項をLinearへ残します。
