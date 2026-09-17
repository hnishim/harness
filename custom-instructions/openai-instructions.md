## スキルの作成・更新と検証

- スキルを新規作成・更新した後は、`~/Library/Mobile Documents/com~apple~CloudDocs/Dev/scripts/validate-skill <スキルディレクトリ>` を実行して検証する
- `quick_validate.py` を素の `python3` で直接実行せず、必ず上記ラッパーを使う

## 未解決事項・追加作業・TODOの記録

今回の依頼で解決しない残懸念や追加作業はLinearへ記録する。既存Issueが適切なら再利用し、なければ新規Issueを作る。記録できない場合は理由を報告する。

## 実装ワークフローの振り分け

- Linear Issueを起点とする実装・修正・調査は、local / remoteを問わず `implementation-loop` を唯一の実行入口として使う
- 実行開始時に最新Linear Issue、Harness、対象リポジトリを取得し、`workflow.toml` のStatus→action、必要能力、mode/profile制約を適用する
- local worktreeが利用できる場合はlocal Git backendを使う
- local worktreeが利用できずGitHub read/writeが利用可能な場合はcanonical Skill内のremote Git backendを使う
- Bug / Spikeはmodeとして扱い、別ワークフローへ分岐しない
- Strict profileは必要なstrict Reviewer能力を要求し、利用不能ならレビューステータスで停止する
- 独立レビュー担当が必要だが現在実行で利用できない場合は、該当レビューステータスと永続資料を残して別実行へ引き継ぐ
- local-only検証を実行できない場合は未検証のまま引き継ぎ、PASSへ昇格しない
- Status遷移、binding、承認失効、Git安全条件の正規仕様をこの指示へ複製せずHarnessを参照する

## Git / GitHub操作

- localリポジトリの状態、差分、branch、stage、commit、fetch、pull、pushはGit CLIを使用する
- localでstage/commit/pushを一連実行する場合は `git-add-commit-push` を使用する
- GitHub上のIssue、Pull Request、CI、リポジトリ情報には利用可能ならGitHubプラグインを使用する
- local worktreeを利用できない実行だけ、`implementation-loop` のremote Git backendに従ってGitHub API／コネクタでcandidate refを操作できる
- `gh` CLIはGitHubプラグインで実行できない操作に必要な場合だけ使う
- sandbox内の `gh` 認証エラーだけを根拠にGitHub認証無効と判断しない
- GitHubプラグインまたは通常のGit／`gh` 経路で扱える操作を、ツールエラーだけでBrowser Useへ切り替えない
- local worktreeのfetch/pull/pushはGit通信として扱いGitHubリソースAPIへ置換しない

## Linear操作

- LinearのIssue、Project、Comment、Status操作は利用可能ならLinearプラグインを使用する
- Linearプラグインが利用できない場合はComputer Useへ切り替えず、操作不能として停止する
