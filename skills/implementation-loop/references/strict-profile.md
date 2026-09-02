# Strict Profile

`Strict profile` labelのIssueでのみ適用します。Labelの新規付与はPlanning側でユーザー承認済みであることを前提とします。Status routing、Linear更新、mode、Test判定、Close、review上限は `SKILL.md` をSource of Truthとし、ここではstrict固有の追加確認だけを定義します。

## 通常Issue

- Testは入力組合せではなく、独立して失敗し得る公開動作またはIssueに関係するrisk単位で設計する
- 同じ挙動を確認する組合せ差は、代表ケースまたはparameterized testへまとめる
- GUI、permission、network、external system等で自動化できないものは具体的な手動確認にする
- Issueに関係しない観点を網羅性のためだけに追加しない

Test Reviewではacceptance/riskとのtraceability、関係するfailure/cleanup/security/privacy/data-loss経路、手動確認の完了条件を追加確認する。

Implementation Reviewではapproved-testsまたはverification baselineの維持、重要riskの検証根拠、docs/config/runtime behaviorの整合を追加確認する。

## Spike

Experiment / Result Reviewでは、Issueに関係するhigh-risk観点、実験条件の偏り、再現性、false positive / false negativeにつながる未検証条件を追加確認する。ただし本番品質や網羅的TestをSpikeへ要求しない。

原則としてstrict Reviewerは `agents/reviewer.toml`（Sol / high、read-only）を使う。利用不能・timeout・実行状態不明の場合は、同等のstrict設定と独立性を確認できるReviewerにだけ再委譲できる。lightweight Reviewerへ降格しない。同等Reviewerを確保できなければ `BLOCKED` とする。
