## スキルの作成・更新と検証

- スキルを新規作成・更新した後は、`~/Library/Mobile Documents/com~apple~CloudDocs/Dev/scripts/validate-skill <スキルディレクトリ>` を実行して検証する
- `quick_validate.py` を素の `python3` で直接実行せず、必ず上記ラッパーを使う。ラッパーは `Dev` 配下の専用 `venv` に固定されている

## 未解決事項・追加作業・TODOの記録

作業中に今回の依頼では解決しない残懸念、追加作業、TODOが発生した場合は、放置せず、適切なLinearのProjectおよびIssueとして記録する。

- 既存のIssueで扱うのが適切な場合は、そのIssueを再利用して記録する
- 適切な既存Issueがない場合は、新しいIssueを作成する
- Issueには、発見した背景・残っている事項・次に必要なアクションを記録する
- Linearへ記録できない場合は、記録できなかった事実と理由を最終報告に明記する

## Implementation workflow routing

- Linear Issueを起点とする実装・修正・調査でlocal worktreeとcanonical independent Reviewerを利用できる環境は、`implementation-loop` をentry pointとして使う
- local worktreeを利用できないremote / Chat環境で、対象Issueが **normal + lightweight**、独立Reviewerを利用できず、Linear/GitHub connectorで作業可能な場合は `remote-implementation-loop` をentry pointとして使う
- `Bug / Spike / Strict profile` はremote adapterで部分実行・self-review fallback・remote resumeを行わず、canonical/local `implementation-loop` へhandoffする
- workflow本文、Status transition、Review decision、checkpoint/Acceptance semanticsはこのinstructionsへ複製せず、Harness上の各SkillをSource of Truthとする

## Git / GitHub操作

- ローカルRepositoryのstatus、diff、branch、add、commit、fetch、pull、pushなどのGit操作にはGit CLIを使用する
- Add、commit、pushを一連で実行する場合は `git-add-commit-push` Skillを使用する
- GitHub上のIssue、Pull Request、review、CI/status、repository情報などの操作には、利用可能であればGitHub pluginを使用する
- `remote-implementation-loop` のeligibleなremote executionでlocal worktreeを利用できない場合だけ、同Skillのremote Git executor contractに従ってGitHub API / connectorでcandidate branch/refを操作できる
- `gh` CLIは、GitHub pluginでは実行できない操作に必要な場合だけ使用する
- Sandbox/restricted context内の `gh` 認証エラーだけを根拠にGitHub認証が無効と判断しない
- GitHub pluginまたは通常のGit/`gh` 経路で扱える操作について、tool errorや認証確認失敗だけを理由にBrowser Useへ切り替えない
- local worktreeの `git fetch`/`git pull`/`git push` はGitHub resource API操作ではなくGit transportとして扱うため、GitHub pluginへ置換しない

## Linear操作

- LinearのIssue、Project、コメント、ステータスなどを操作するときは、Computer Useやブラウザ操作を使用せず、利用可能な場合はLinearプラグイン（`[@Linear](plugin://linear@openai-curated-remote)`）を必ず使用する
- Linearプラグインが利用できない場合は、Computer Useへフォールバックせず、操作できない旨を報告する
