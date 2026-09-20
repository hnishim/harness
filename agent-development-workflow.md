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
| 機械的な状態遷移、能力、binding、失効、local Git安全条件 | `skills/implementation-loop/workflow.toml` |
| フェーズごとの意味判断 | `skills/implementation-loop/references/` |
| 実行入口 | `skills/implementation-loop/SKILL.md` |
| 再現可能な自動検証 | CI |
| OS／アプリ／credential固有の検証 | local環境 |
| 最終受入 | Human |

## 単一のlocal Gitワークフロー

Canonical implementation-loopのGit変更はlocal Gitだけで行います。GitHubはIssue・コードの読取とCI結果の観測に使えますが、候補作成・公開の代替経路にはしません。

Git checkpointとCloseはlocal Gitを必須とし、local worktreeまたはlocal Gitが利用できなければGitHubの読み書き権限へ切り替えず、現在Statusを再開地点として停止します。旧deliveryのremote-only起点や切替許可は履歴として読めますが、新しい公開権限にはしません。

GitHubのIssue読取、コード読取、CI観測と、Git変更に必要なlocal Git能力を混同しません。

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

Local Gitでnon-force、履歴書換えなし、対象範囲／由来確認、書込み後readbackを守ります。

Candidate SHAと公開対象の一致、受入前の既定ブランチ非公開、失敗時の非破壊停止を維持します。

## Close

Human Acceptance PASSはDoneではありません。明示close指示後にentry gateを再確認し、受理済みcandidateを公開し、必要CIを公開済みSHAへ結び付けて確認してからDoneへ進みます。

Local Gitでのclose本体の成功後、公開済み対象refへローカル対象ブランチを安全に追従できる場合だけ非阻害の後処理として同期します。同期不能でもローカル状態を変更して成立させず、close本体やDoneを失効させません。具体的な安全条件は `workflow.toml` と `references/close.md` が所有します。

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
