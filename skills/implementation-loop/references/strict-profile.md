# Strict Profile

`Strict profile` labelのIssueでのみ適用します。Labelの新規付与はPlanning側でユーザー承認済みであることを前提とします。Status routing、Linear更新、mode、Test判定、Close、review上限は `SKILL.md` をSource of Truthとし、ここではstrict固有の追加確認だけを定義します。

## 通常Issue

Test設計前にchange classを `small | stateful | high-risk` に分類し、Issueに関係する範囲で自動scenario、手動受入、対象外を整理する。

- small: 必要最小限。原則4 scenario以下
- stateful: 必要なstate transitionを扱う。原則7 scenario以下
- high-risk: 記載riskに必要なfailure injection / manual checkを追加し、7 scenarioを超える場合だけ理由を残す
- GUI、permission、network、external system等で自動化できないものは具体的な手動確認にする
- Issueに関係しない観点を網羅性のためだけに追加しない

Test Reviewではacceptance/riskとのtraceability、関係するfailure/cleanup/security/privacy/data-loss経路、手動確認の完了条件を追加確認する。

Implementation Reviewではapproved-testsまたはverification baselineの維持、重要riskの検証根拠、docs/config/runtime behaviorの整合を追加確認する。

## Spike

Experiment / Result Reviewでは、Issueに関係するhigh-risk観点、実験条件の偏り、再現性、false positive / false negativeにつながる未検証条件を追加確認する。ただし本番品質や網羅的TestをSpikeへ要求しない。

原則としてstrict Reviewerは `agents/reviewer.toml`（Sol / high、read-only）を使う。代替Agentでも独立性と検証強度を下げない。
