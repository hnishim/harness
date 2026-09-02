# Spike

`Spike` labelのIssueで読む。共通契約とReview作法は `../SKILL.md` に従う。

Spikeは `Test not required` とし、専用Test phaseを使いません。

## Planning差分

Planは完成品の実装手順ではなく、仮説、検証論点、観測方法、採用/不採用の判断基準を中心に作ります。

- Experiment / PoCはDecisionに必要な最小コード・計測・fixtureに限定する
- 受入条件は各検証点を成功・失敗・未検証に分類でき、次のDecisionを導けること
- 本番データ、認証情報、課金、権限、security/privacy、不可逆変更など安全に暫定判断できない事項は共通 `BLOCKED`

Planning Reviewではコード品質より、仮説・観測・判断基準がDecisionに十分かを確認します。

## `Implementation`: Experiment / PoC

1. implementer（原則 Luna / medium）へ承認済みExperiment Planを渡す
2. Decisionに必要な最小のPoC、計測、fixture、実験を行う
3. 各検証論点について条件、観測結果、再現手順、成功/失敗/未検証を記録する
4. 実験結果をCommentへ保存し `In Implementation Review` へ更新する

## `In Implementation Review`: Result Review

- lightweight Reviewer: `agents/reviewer-lightweight.toml`（Terra / high、read-only）
- strict: [strict-profile.md](strict-profile.md) を追加適用
- 判定: `DECISION_READY` / `CHANGES_REQUIRED` / `MATERIAL_DEVIATION`

証拠の十分性、偏り、再現性、Planの判断基準との対応を確認します。

Review Comment差分:

```text
判定: DECISION_READY | CHANGES_REQUIRED | MATERIAL_DEVIATION
成果物fingerprint: <sha256>
```

- `DECISION_READY` → 採用方式、制約、未対応範囲、追加Spikeの要否をCommentへ保存してClose待ち
- `CHANGES_REQUIRED` → `Implementation` へ戻す
- `MATERIAL_DEVIATION` → Planや仮説の再設計が必要な理由をCommentへ保存して `Todo` へ戻し停止する
