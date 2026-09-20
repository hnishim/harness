## スキルを作成・更新した場合の検証

- スキルを新規作成・更新した後は、`~/Library/Mobile Documents/com~apple~CloudDocs/Dev/scripts/validate-skill <スキルディレクトリ>` を実行して検証する
- `quick_validate.py` を素の `python3` で直接実行せず、必ず上記ラッパーを使う

## 未解決事項・追加作業・TODOの記録

今回の依頼で解決しない残懸念や追加作業はLinearへ記録する。同じ対象・目的の既存Issueがあれば再利用し、なければ新規Issueを作る。記録できない場合は理由を報告する。

## 実装ワークフローの振り分け

- Linear Issueを起点とする実装・修正・調査は、`implementation-loop` を唯一の実行入口として使う
- 実行開始時に最新Linear Issue、Harness、対象リポジトリを取得し、`workflow.toml` のStatus→action、必要能力、mode/profile制約を適用する
- Git変更を伴う処理はlocal Gitを使う。Local worktreeまたはローカルGitが利用できない場合は停止し、GitHubの読み書き権限へ切り替えない
- Bug/Spikeはmodeとして扱い、別ワークフローへ分岐しない
- Strict profileは必要なstrict Reviewer能力を要求し、利用不能ならレビューステータスで停止する
- 独立レビュー担当が必要だが現在実行で利用できない場合は、該当レビューステータスと永続資料を残して別実行へ引き継ぐ
- Local-only検証ができない場合は未検証のまま引き継ぎ、PASSへ昇格しない
- Status遷移、binding、承認失効、Git安全条件の正規仕様をこの指示へ複製せずHarnessを参照する

## Git / GitHub操作

- Localリポジトリの状態、差分、branch、stage、commit、fetch、pull、pushはGit CLIを使用する
- Localでstage/commit/pushを一連実行する場合は `git-add-commit-push` を使用する
- GitHub上のIssue、Pull Request、CI、リポジトリ情報には利用可能ならGitHubプラグインを使用する
- GitHub API／コネクタはIssue・コードの読取とCI結果の観測に限り、candidate refの作成・更新・公開には使わない
- `gh` CLIはGitHubプラグインで実行できない操作に必要な場合だけ使う
- Sandbox内の `gh` 認証エラーだけを根拠にGitHub認証無効と判断しない
- GitHubプラグインまたは通常のGit／`gh` 経路で扱える操作を、ツールエラーだけでBrowser Useへ切り替えない
- Local worktreeのfetch/pull/pushはGit通信として扱いGitHubリソースAPIへ置換しない

## Linear操作

- LinearのIssue、Project、Comment、Status操作は利用可能ならLinearプラグインを使用する
- Linearプラグインが利用できない場合はComputer Useへ切り替えず、操作不能として停止する
