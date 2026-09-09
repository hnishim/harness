# Bug mode: 原因調査

`Bug` labelのIssueで読む。共通契約とReview作法は `../SKILL.md` に従う。

`Bug` は新しいLinear Statusではなくmode modifierです。`Backlog`/`Todo` にあるBugは、同じStatusのまま原因調査を先に行い、原因が確定した場合だけ対応Planを作成します。調査中に実装、Test成果物、canonical Plan、Status、Labelsを変更しません。調査結果を保存するLinear Commentだけは、調査完了後に親Agentが作成できます。

Bug modeはIssueに完全一致する `Bug` labelがある場合だけ選択します。Issueのtitle、本文、症状からBug modeを推測したり、`Bug` labelを自動追加したりしません。

## Mode boundary

- `Bug` と `Spike` が同時に付いている場合はmode不明としてBLOCKEDです
- `Bug` は `Test required` 固定です。専用Testが不要という理由で `Test not required` にはしません
- Bug modeのTest/Implementationは通常Issueのphase手順を使います。追加のmode差分は、Planに原因調査の根拠と回帰検証を含めることです

## Backlog / Todo: 原因調査

Plan作成前に、親Agentが次を読み取り中心で実施します。

1. Issue、Status、Description、全Comments、Labels、relations、Repository root/worktree、適用されるlocal instructionsを再取得する
2. 症状、発生条件、期待動作、実際の動作を確定し、既存の再現手順または安全な最小再現を確認する
3. 関係する実装、設定、生成物、実行経路、ログ、既存Testを追跡し、症状と原因候補の因果関係を観測可能な証拠で切り分ける
4. 少なくとも、確認した原因、除外した主な仮説、未確認事項、原因から導く最小対応scopeを分けて記録する
5. 調査結果を次の形式でLinear Commentへ保存する。既存の調査記録がある場合も、現在のIssue・Repository・再現条件と整合することを確認し、意味のある差分があれば更新記録を追加する

```text
Bug Investigation
対象Issue: <Issue ID>
判定: ROOT_CAUSE_CONFIRMED | ROOT_CAUSE_UNCONFIRMED | BLOCKED
症状: <観測した事実>
再現条件: <条件、入力、実行経路、または再現不能の事実>
原因: <確認できた原因。未確定なら候補と明記>
根拠: <path、ログ、再現結果、設定、既存Test等>
除外した仮説: <確認できた範囲>
最小対応scope: <原因に直接対応する対象>
未確認事項: <なし | 内容>
```

`ROOT_CAUSE_CONFIRMED` は、症状を説明する具体的な因果関係を対象Repositoryまたは実行時観測で確認でき、Planの最小対応scopeを根拠付きで決められる場合だけ使います。候補が有力でも因果関係を確認できない、再現条件が不明、対象Repository/worktreeが一意でない、または外部・実機結果が不明な場合は `ROOT_CAUSE_UNCONFIRMED` または `BLOCKED` とし、Planを作成せずStatusを維持して停止します。

原因調査は、Repositoryのtracked file、外部サービス、認証情報、ユーザーデータを変更しない安全な観測に限定します。不可逆変更、実運用データへの書込み、秘密値を含む再現、または調査のための恒久的なfixture/config変更が必要な場合はBLOCKEDです。必要なら一時的な無害入力・既存fixture・`/tmp` 等の隔離領域を使い、調査後に残存物がないことを確認します。

## Plan handoff

`ROOT_CAUSE_CONFIRMED` の調査記録を保存・再取得確認した後だけ、同じ実行内で `planning.md` のcanonical Plan作成へ進みます。Planには次を含めます。

- 最新のBug原因調査記録への参照
- 確認済みの原因と、対応対象をそのscopeに限定する理由
- 原因を再発させないTestの対象、期待結果、再実行方法
- `### テスト判定` の `Test required`
- 調査で未確認の事項と、それをImplementationの成功条件に含めない境界

Bugの原因調査は独立Reviewや新しいStatusを追加するphaseではありません。Plan Reviewは調査記録の証拠、原因と対応scopeの対応、回帰Testの十分性を確認します。調査記録がない、Planが調査結果を参照しない、または原因がPlan作成時点の対象と整合しない場合は、Plan Reviewを通さずBLOCKEDとします。
