---
name: initial-plan
description: BacklogのLinear IssueをRepository参照なしで初期整理し、Todoへ進める任意frontend。
notion_sync: false
---

# Initial Plan

## 役割

入力はLinear Issue IDです。専用Linear connectorだけを使い、Linear上の情報だけを使って、未承認の初期Planを作成します。GUI/Computer Use/別connectorへのfallbackは禁止です。初期Planは整理結果であり、承認済みcanonical Planや実装開始の根拠として扱いません。`Todo` 以降のcanonical化とPlan Reviewは `implementation-loop` が行います。Repositoryは参照しません。

対象Statusは `Backlog` のみです。その他のStatusでは変更せず終了します。

このSkillの起動は、対象IssueのDescriptionとStatus更新への承認を含みます。Labelは変更しません。

## Linear経路

Linearの取得・保存・readbackは専用Linear connectorだけで行います。専用connectorが利用できない、または結果が不明な場合は、GUI/Computer Use/別connectorへfallbackせずBLOCKEDです。

## 取得

Issue、Description、Comments、Labelsの順に取得します。いずれかの取得に失敗した、または結果が不明な場合はBLOCKEDです。

開始時、取得とStatus検証に成功したら `Issue概要: <Issue ID> — <title>` を1行だけ表示します。

## Description

既存Descriptionを保持し、次のmarker 1組で管理領域を追加・更新します。初期Planを保存しても、IssueはPlan Review済みとはみなしません。

```text
CODEX_LINEAR_ISSUE_DESCRIPTION_START
...
CODEX_LINEAR_ISSUE_DESCRIPTION_END
```

Markerの複数、片側欠落、逆順、境界不明はBLOCKEDです。

初期Planは目的・要件・受入条件を基本とし、必要な場合だけ背景、制約、実装/検証方針、仮定、参考情報を加えます。

小さいTaskは短く、複雑なIssueは判断に必要な粒度で書きます。

`Spike` labelがある場合は、仮説、検証論点、観測方法、採用/不採用の判断基準を中心に整理します。

## 保存

1. Descriptionの対象領域だけを更新する
2. 保存直前にIssue/Description/Comments/Labels/Statusを再取得し、baseline一致を確認する。Statusが `Backlog` でない、対象値が変わっている、またはmarkerの境界が変わっている場合は保存せずBLOCKEDとする
3. Description保存後にDescription/Comments/Labels/Statusを再取得し、初期Planの意図した差分、markerの一意性、marker外の保持、保存結果を確認する。いずれかの保存またはreadbackの結果が失敗または不明な場合はBLOCKEDとする
4. Statusを `Todo` へ更新する
5. StatusとDescriptionを再取得し、`Todo` と保存済み初期Planを確認する。ここでPlan Reviewや実装へ自動遷移しない

## BLOCKED

取得、保存、またはreadbackの結果が失敗・不明な場合は、推測やfallbackをせずBLOCKEDで停止します。

```text
結果: BLOCKED
停止箇所: <取得|Description|保存|readback>
確認事項: <確認できた事実。原因未確定ならその旨>
推奨対応: <推奨する次の行動>
再開条件: <再開に必要な条件>
```

## 終了報告

```text
実行フェーズ: Initial Plan
モード: <normal | spike>
ステータス遷移: Backlog → Todo
保存結果: <要約>
未確認事項: <なし | 内容>
```
