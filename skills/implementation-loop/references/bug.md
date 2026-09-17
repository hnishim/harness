# Bug mode

`Bug` Labelの通常Issueへ追加適用します。Bugは常に `Test required` です。

## 原因確定

親IssueをPlanningへ進める前に、必要なら原因調査用のSpike子Issueを1件だけ作成・再利用します。子Issueは独立したimplementation-loop入力として実行します。

原因確定には症状と直接対応する証拠が必要です。修正成功だけを原因証明にしません。仮説、反証、Rejected hypotheses、結論を残し、`ROOT_CAUSE_CONFIRMED` と言える場合だけ親Planへ進みます。

原因未確定、再現不能、証拠不足では親Issueを進めません。

## 回帰テスト

PlanとTest Reviewでは少なくとも次を扱います。

- 修正前の不具合ケースFAILを可能な範囲で確認
- 隣接する正常ケースPASS
- 修正後に不具合ケースと隣接ケースPASS
- 修正前FAILを取得できない場合は具体的理由と未検証境界

原因調査用実験は修正回帰テストの代替ではありません。
