## スキルの作成・更新と検証

- スキルを新規作成・更新した後は、`~/Library/Mobile Documents/com~apple~CloudDocs/Dev/scripts/validate-skill <スキルディレクトリ>` を実行して検証する
- `quick_validate.py` を素の `python3` で直接実行せず、必ず上記ラッパーを使う。ラッパーは `Dev` 配下の専用 `venv` に固定されている

## 未解決事項・追加作業・TODOの記録

作業中に今回の依頼では解決しない残懸念、追加作業、TODOが発生した場合は、放置せず、適切なLinearのProjectおよびIssueとして記録する。

- 既存のIssueで扱うのが適切な場合は、そのIssueを再利用して記録する
- 適切な既存Issueがない場合は、新しいIssueを作成する
- Issueには、発見した背景・残っている事項・次に必要なアクションを記録する
- Linearへ記録できない場合は、記録できなかった事実と理由を最終報告に明記する

## Git / GitHub操作

- ローカルRepositoryのstatus、diff、branch、add、commit、fetch、pull、pushなどのGit操作にはGit CLIを使用する
- Add、commit、pushを一連で実行する場合は `git-add-commit-push` Skillを使用する
- GitHub上のIssue、Pull Request、review、CI/status、repository情報などの操作には、利用可能であればGitHub pluginを使用する
- `gh` CLIは、GitHub pluginでは実行できない操作に必要な場合だけ使用する
- Sandbox/restricted context内の `gh` 認証エラーだけを根拠にGitHub認証が無効と判断しない
- GitHub pluginまたは通常のGit/`gh` 経路で扱える操作について、tool errorや認証確認失敗だけを理由にBrowser Useへ切り替えない

## 責務境界

| 操作 | 原則経路 |
| -- | -- |
| status / diff / branch / add / commit / fetch / pull / push | ローカルGit CLI |
| add → commit → pushの一連処理 | `git-add-commit-push` Skill |
| GitHub Issue / PR / review / CI/status / repository情報 | GitHub plugin |
| pluginで扱えず、GitHub API操作等に必要な場合 | `gh` CLI |
| Browser Use | 上記経路の単なる失敗時fallbackとしては使わない |

`git fetch`/`git pull`/`git push` はGitHub resource API操作ではなくGit transportとして扱うため、GitHub pluginへ置換しない。
