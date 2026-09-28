---
name: create-issue
description: Linear Issueを短い課題定義として作成し、必要な場合だけ同一Planコメントへ未承認の初稿を保存する。
metadata:
  notion_sync: "false"
---

# Create Issue

## 目的

Issue作成時点でPlanningを先取りしてDescriptionを肥大化させません。Descriptionは原則として数行にし、次だけを記録します。

- 何を解決したいか
- 期待する結果
- 重要な制約

## リポジトリ未確認時の境界

リポジトリを確認する前に、対象ファイル、ファイルパス、実装手順、詳細なテスト方法・検証方法を推測してDescriptionへ書きません。未確認の実装詳細をIssue本文の事実として扱いません。

## Plan初稿

単純・簡単な依頼では**短いDescriptionのみ**を作り、PlanはPlanningで初めて作成します。

一方、Issue作成前の会話ですでに詳細な仕様・設計・制約が十分に確定している場合は、その情報を捨てず、Descriptionとは別に `artifact_key: plan` の**Plan初稿**コメントを1件だけ作成します。

- Plan初稿は未承認
- 後続Planningがリポジトリ事実を確認して**同じコメント**を更新する
- Planningで別のPlanコメントを作って重複させない
- 詳細設計が確定していない事項は未確認として残す

## Subscription保証

Agentが起票するIssueでは、`implementation-loop/workflow.toml` のSubscription契約を参照し、HiroのSubscriptionを **assignee bootstrap** で一度だけ保証します。

1. 本来のnext actorを先に確定する
2. 永続状態で `subscription_bootstrapped: true` が確認できなければ、一度HiroをAssigneeにしてreadbackする
3. 直後に本来のAssignee（AgentまたはHuman）へ戻し、再度readbackする
4. 両方の更新が確認できた後、canonicalな `state_key: delivery` コメントへ `subscription_bootstrapped: true` を保存する。Deliveryがまだなければ最小のdelivery状態を1件だけ作り、後続のimplementation-loopが同じコメントを再利用する
5. Bootstrap済みIssueではこの往復を繰り返さない

Assigneeを一時的にHiroへ変更するbootstrapは、本来のnext actorへ戻す前の中間操作です。一時的なHuman assignmentは停止判定対象ではない中間操作であり、本来のAssigneeへ戻してreadbackした後に停止判定を行います。

この処理は購読付与のためだけに別credentialや環境別APIを要求しません。Linear connectorからsubscriber一覧を直接readbackできない場合は、その範囲を未検証として扱い、Assignee更新の成功だけをSubscription表示の確認済みとはみなしません。

Issue作成Skill自身はPlan Reviewや実装可否を判定しません。
