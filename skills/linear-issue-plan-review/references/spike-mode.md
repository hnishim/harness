# Spike Mode

`Spike` labelのIssueでのみ適用します。titleや本文からSpikeを推測せず、labelだけを判定根拠にします。

- 完成品ではなく、仮説、検証論点、観測方法、採用/不採用の判断基準を中心にPlanを作る
- Experiment / PoCは判断に必要な最小コード・計測・fixtureに限定し、本番品質を要求しない
- 受入条件は各検証点を成功・失敗・未検証に分類でき、次のDecisionを導けることとする
- 専用Test phaseは使わず `Test not required` とする。検証を省略する意味ではない
- 本番データ、認証情報、課金、権限、security/privacy、不可逆変更など安全に暫定判断できない事項は推測せず `PLAN_BLOCKED` とする
