## スキルの作成・更新と検証

- スキルを新規作成・更新した後は、`~/Library/Mobile Documents/com~apple~CloudDocs/Dev/scripts/validate-skill <スキルディレクトリ>` を実行して検証する。
- `quick_validate.py` を素の `python3` で直接実行せず、必ず上記ラッパーを使う。ラッパーは`Dev`配下の専用`venv`に固定されている。

## 未解決事項・追加作業・TODOの記録

作業中に今回の依頼では解決しない残懸念、追加作業、TODOが発生した場合は、放置せず、適切なLinearのProjectおよびIssueとして記録する。

- 既存のIssueで扱うのが適切な場合は、そのIssueを再利用して記録する。
- 適切な既存Issueがない場合は、新しいIssueを作成する。
- Issueには、発見した背景・残っている事項・次に必要なアクションを記録する。
- Linearへ記録できない場合は、記録できなかった事実と理由を最終報告に明記する。
