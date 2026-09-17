---
name: create-issue
description: Linear Issueを短い課題定義として作成し、必要な場合だけ同一Planコメントへ未承認の初稿を保存する。
notion_sync: false
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

Issue作成Skill自身はPlan Reviewや実装可否を判定しません。
