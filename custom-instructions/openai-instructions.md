## スキルを作成・更新した場合の検証

- スキルを新規作成または更新した後は、`~/Library/Mobile Documents/com~apple~CloudDocs/Dev/scripts/validate-skill <スキルディレクトリ>` を実行して検証する
- `quick_validate.py` を素の `python3` で直接実行せず、必ず上記ラッパーを使う

## 未解決事項・追加作業・TODOの記録

今回の依頼で解決しない懸念事項や追加作業はLinearに記録する。同じ対象・目的の既存Issueがあれば再利用し、なければ新規Issueを作る。記録できない場合は理由を報告する。

## 実装ワークフローの振り分け

- Linear Issueを起点とする実装・修正・調査は、local/remoteを問わず `implementation-loop` を唯一の実行入口として使う
- 実行開始時に最新のLinear Issue、Harness、対象リポジトリを取得する。`workflow.toml` に従い、Statusに対応する操作・必要な操作を実行できるか・mode/profileの制約を確認する
- Local worktreeが利用できる場合はlocal Git backendを使う。これらはローカル環境でのGit操作を指す
- Local worktreeを使えず、remote-only環境でGitHubの読取り・書込みができる場合は、現在有効なSkillに定義されたremote Git backendを使い、同じIssue専用作業ブランチで作業を続ける
- Closeでは受入・明示指示・公開先の実状態を照合し、利用可能なローカルGitまたはGitHub Pull Requestで統合する。ローカル反映が必要なら実利用まで確認できる環境に引き継ぐ。旧 `local-origin` 等の起点別フラグは公開権限として使わない
- Bug/Spikeはmodeとして扱い、別ワークフローへ分岐しない
- Strict profileは必要なstrict Reviewer能力を要求し、利用不能ならレビューステータスで停止する
- 独立レビュー担当を現在の実行で確保できない場合は、該当するレビューステータスを維持し、再開に必要な資料をLinearに保存して別の実行へ引き継ぐ
- Local-only検証ができない場合は未検証のまま引き継ぎ、検証が成功したことにはしない
- Status遷移、承認と対象の版の対応、承認の無効化、Git操作の安全条件をこの文書に重複して定義せず、Harnessを参照する

## macOSのアプリケーション固有リソースの命名

- 自作アプリケーションが新たに作成する `~/Library/Application Support/` 配下のアプリケーション固有フォルダーと、Keychainエントリーのサービス名は、原則 `my.<app>` とし、リソースの区別が必要な場合は `my.<app>.<resource>` とする。`<app>` はアプリケーション・用途、`<resource>` は機能・リソースを識別し、既存の `my.<用途>.<機能>` と整合させる。
- Keychainのアカウント名にはこの規則を適用しない。既存名称に依存するリソースや、外部アプリケーション・プラットフォームが名称を指定するリソースは機械的に改名しない。既存資産の移行は本規則の適用対象外とする。

## Git / GitHub操作

- ローカルリポジトリの状態・差分の確認や、branch、stage、commit、fetch、pull、pushにはGit CLIを使用する
- ローカル環境でstage/commit/pushをまとめて実行する場合は `git-add-commit-push` を使用する
- GitHub上のIssue、Pull Request、CI、リポジトリ情報には利用可能ならGitHubプラグインを使用する
- ローカルのworktreeを利用できない実行では、`implementation-loop` のremote Git backendに従い、GitHub API／コネクタで候補ブランチのrefを操作できる。CloseのPR統合は、Human Acceptanceと明示Close指示、リポジトリの規則・必須チェックを満たした場合だけ行う
- `gh` CLIはGitHubプラグインで実行できない操作に必要な場合だけ使う
- Sandbox内で `gh` の認証エラーが発生したことだけを根拠に、GitHubの認証が無効だと判断しない
- GitHubプラグインまたは通常のGit／`gh` で実行できる操作は、ツールエラーが発生したという理由だけでBrowser Useへ切り替えない
- ローカルのworktreeで行うfetch/pull/pushはGit通信として実行し、GitHubのリソースAPIによる操作へ置き換えない
- 読み取り専用Git操作（status、diff、show等）は既定のsandbox経路で実行する
- メタデータを書き込む可能性があるGit操作（fetch、pull、merge、commit、push等）は、sandboxで試す前に `sandbox_permissions: "require_escalated"` を指定できる通常macOS実行環境を要求する。利用できない場合は広い `.rules` のallowを追加せず停止する
- 実行環境側でGit操作が拒否された場合はGit自体の障害と判断して諦めず、通常のmacOS実行環境で同じ操作を一度だけ再試行し、再試行が成功した場合は処理を続行し、再試行後も失敗した場合に限り停止または `skip` します

## Linear操作

- LinearのIssue、Project、Comment、Statusを操作する際は、利用可能であればLinearプラグインを使用する
- Linearプラグインが利用できない場合はComputer Useへ切り替えず、操作不能として停止する
