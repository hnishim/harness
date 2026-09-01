# Spike Execution

`Spike` labelのIssueでのみ適用します。Status routingとLinear更新は `SKILL.md` をSource of Truthとします。

- `Implementation` はExperiment / PoC、`In Implementation Review` はResult Reviewとして扱う
- 判断に必要な最小の実験だけを行い、本番品質、網羅的テスト、一般化、無関係なrefactorを追加しない
- 結果は仮説ごとに条件、観測、再現手順、成功/失敗/未検証を残す
- Result Reviewはコード品質より、証拠の十分性、偏り、再現性、Planの判断基準との対応を優先する
- 完了時は採用方式、制約、未対応範囲、追加検証/Spikeの要否をLinear Commentに残す
