# Agent Development Workflow Architecture

Version: 2.0  
Updated: 2026-09-18

## 目的

この文書はHarness全体のアーキテクチャ、責務境界、主要な設計理由だけを説明します。実行手順や状態遷移の第二の正規仕様にはしません。

## 正規情報源

| 対象 | 正規情報源 |
| --- | --- |
| Issue、現在Status、Plan、承認、受入状態、履歴イベント | Linear |
| source、tests、candidate | 対象Gitリポジトリ |
| 機械的な状態遷移、能力、binding、失効、Git backend安全条件 | `skills/implementation-loop/workflow.toml` |
| フェーズごとの意味判断 | `skills/implementation-loop/references/` |
| 実行入口 | `skills/implementation-loop/SKILL.md` |
| 再現可能な自動検証 | CI |
| OS／アプリ／credential固有の検証 | local環境 |
| 最終受入 | Human |

## 単一のlocal / remoteワークフロー

Canonical implementation-loopはlocal/remoteで同じStatus、判断基準、承認境界を使います。差は利用可能能力とGit backendだけです。

通常のGit checkpointでは、Issue専用作業ブランチをローカル／リモートで継続します。local worktreeを利用できる場合はlocal Git、remote-only環境ではGitHub read/writeを利用します。Closeの公開方法は起点ではなく利用可能能力と対象リポジトリの規則で決めます。

能力不足、由来不明、readback不能、分岐や結果不明はPASSへ変換せず、現在Statusを再開地点として停止します。

## Statusを再開地点として使う理由

Statusは表示上の進捗だけでなく、別実行・別環境から「次にどの責務を行うか」を再構築する粗粒度の永続状態です。

詳細な成果物bindingはLinearの少数の可変コメントへ持たせ、Statusへ詰め込みません。Status数を減らすこと自体は目的にしません。

## Linear永続化

課題の要点はDescription、詳細Planは単一Planコメント、承認版はapproval、候補と受入はdeliveryへ分離します。Spikeだけresultを追加します。

重要な変更要求や失敗理由は不変イベントとして残します。現在状態をイベント列から再構築するevent sourcingにはしません。

承認はコメントIDやStatusだけでなくPlan hash、approved tests manifest、candidate SHA、result hash等の対象版へ結び付けます。対象が変われば対応する承認を失効させます。

## 独立Reviewer

Plan Review、Test Review、Test not requiredのImplementation Review、Spike Result Reviewは成果物作成主体と独立した読み取り専用Reviewerが行います。

独立Reviewerを利用できないことはレビュー省略の理由ではありません。該当Statusに資料を残して停止します。

## Test-first

Test requiredでは、実装前にテスト成果物を作成・レビューし、承認済みテスト集合をmanifestとして固定します。Implementationはそのテストを変更対象から除外します。

この境界は、実装を見てから期待値を作る自己追認を避けるためにあります。

## Bug

Bugは原因確定後にだけPlanningへ進み、Test requiredです。必要な原因調査はSpike子Issueとして独立実行します。修正成功だけを原因証明にしません。

## CandidateとAcceptance

通常Issueは実装・検証後にcandidate SHAを固定し、そのcandidateへlocal/human acceptanceを結び付けます。Human Acceptance前に既定ブランチへ公開しません。

Test requiredは実装後レビューを重ねずAcceptanceへ進みます。Test not requiredはcandidateへ独立Implementation Reviewを結び付けてからAcceptanceへ進みます。

## Git安全条件

Local/remoteのいずれもnon-force、履歴書換えなし、対象範囲／由来確認、書込み前後readbackを守ります。

Remote Git backendはIssue専用candidate refの作成・更新に使用し、Human Acceptanceと明示Close指示前にdefault branchを更新しません。候補作成ではnon-forceと前後readbackを必須とし、Divergedまたはreadback不能では停止します。Closeでは承認済み差分と統合後の公開結果を照合し、PR mergeによる別SHAを候補内容変更とは区別します。

## Close

Human Acceptance PASSはDoneではありません。明示close指示後にentry gateを再確認し、ローカルGitまたはPull Requestによる通常の統合を実施します。公開前の必要CIと公開先の実状態・承認済み差分の対応を確認します。公開後SHAへの一律追加CIは要求しません。

当該Issueでローカル利用が必要なら、安全な同期・設定等の適用・実際の利用を確認するまでDoneにしません。リモート公開後に必要なローカル反映が未完了ならAwaiting Acceptanceへ引き継ぎます。不要ならローカル起点か否かでDoneを分岐しません。具体的な安全条件は `workflow.toml` と `references/close.md` が所有します。

Spikeは現在result版に結び付くDECISION_READYをclose条件にします。

## 機械契約と意味判断の分離

`workflow.toml` は、事実が決まった後のルーティング、能力、遷移、binding、失効を所有します。

Markdownは、Test requiredか、原因確定か、findingがblockingか、受入条件を満たすか等の意味判断を所有します。

同じ遷移表をMarkdownへ再記述せず、TOMLを独自条件式言語へ肥大化させません。

## 自己変更時の制御面

ワークフロー自身を変更するIssueは、未受理candidateの新契約を自分自身の実行制御へ適用しません。現在受理済みHarnessを制御面、candidateをレビュー対象成果物として扱います。

これはワークフロー変更中に検証対象が自分の合否条件を変える循環を防ぐためです。

ローカルのSessionStartは、受理済みHarness control planeの鮮度を確認し、安全に可能な場合だけHarness自身をfast-forwardします。同期不能なら古い制御面へフォールバックせず開始を止めます。一般の作業対象リポジトリはこの責務では更新しません。

## 旧形式移行

既存未完了Issueは一括変換せず、最初の再開時に冪等な遅延移行を行います。同一由来の部分移行は再開し、複数移行候補・由来不明・矛盾では安全側で停止します。

旧形式読取は移行専用で、新しい更新を旧形式へ二重書きしません。

## 保守原則

- 新しい機械的条件はまずTOMLへ置けるか判断する
- 意味判断は参照文書へ置く
- アーキテクチャ文書へフィールド一覧や具体的遷移表を複製しない
- 実行主体名を状態へしない
- 利用できない検証をPASS扱いしない
- 改善が必要ならcanonical Skill側を変更し、環境別例外を積み上げない
