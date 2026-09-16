# 実装

通常課題の `Implementation` / `In Implementation Review` / `Awaiting Acceptance` で読む。共通の取り決めと検証記録は `../SKILL.md` に従う。Spikeの `Implementation` / `In Implementation Review` は [spike.md](spike.md) の実験／結果レビューとして扱う。

## 実装

1. `Test required` は最新 `TESTS_APPROVED` と `approved-tests`、`Test not required` は計画記載の検証方法を基準とする
2. `Test required` は開始前に `approved-tests` のパス／ハッシュ一致を確認し、実装では `approved-tests` を変更対象から除外する。不一致はBLOCKEDとする
3. 作業エージェント（原則Luna/medium）へ計画と基準を渡し、計画範囲を実装させる
4. 実装後に計画との対応関係、変更ファイル、自動テスト／検証の結果、未検証事項を確認する。次の4条件を独立に判定する
   - 実利用経路 / 実行入口: ソースと実利用経路が分離する場合だけ、必要な範囲を確認する
   - 実際の仕様影響: 外部の取り決めを変更する場合だけ、実際の呼び出し元／利用側への影響を確認する
   - 診断根拠の保持: 失敗調査または実行時検証で必要な場合だけ、診断の根拠の保持を確認する
   - 基準文書との同期: 既存の基準文書が管轄する取り決めを変更する場合だけ、必要な同期を確認する
   ソースを直接実行した成功だけで実行時の成功と扱わない。「診断根拠の保持」の条件が成立する場合は、ラッパーや例外捕捉が必要な診断の根拠を失っていないか確認する
5. 検証が完了したら、ステータスを変更する前に論理的な `checkpoint` を**有効なGit実行主体**へ委譲し、対象課題の変更だけを候補コミットへ固定する。基準となる `implementation-loop` の既定の実行方法はローカル環境のGit実行主体で、従来どおり `git-add-commit-push checkpoint` を使用する。別の実行入口がGit実行主体を差し替える場合も候補SHA、対象範囲／由来、強制更新なし／履歴書き換えなし、変更後の再取得確認に関する共通の取り決めを満たす。`checkpoint` が失敗・結果不明・対象範囲混在の場合は後続ステータスへ進めず、`Implementation` で停止する
6. `checkpoint` 後は後述の `state_key: implementation-completion` を現在の候補へ更新して再取得確認する。`Test required` は実装レビューを実行しないままステータスを `Awaiting Acceptance` へ更新する。`Test not required` はステータスを `In Implementation Review` へ更新し、現在の候補に対する独立実装レビューを実行する

## 実装完了／受入確認状態

`state_key: implementation-completion` の可変フェーズ状態を実装完了から受入確認までの現在の永続状態として使います。状態が存在しない初回だけ新規コメントを作成し、そのコメントIDを保持します。既存状態がある再実装、候補の改訂、受入確認待ちでは同じコメントIDを更新し、別の実装完了／受入確認状態コメントは追加しない・作成しない。

この状態は少なくとも実装完了、`test_decision`、現在の `candidate_commit`／候補SHA、候補ブランチまたはリモート／`ref` 到達状態、自動テスト／検証、CI検証、検証境界、`unverified`、残るローカル環境での受入確認、残る人間による受入確認、受入確認状態（`pending` / `pass`）を現在値として保持します。人間による受入確認の対象は現在の候補SHAへ結び付けます。必要な過去の状態／重要なイベントの参照はコメントIDで保持します。

CIの根拠を受入確認に使う場合は候補SHAとCI対象SHAの一致を確認し、CI PASSだけでローカル環境／人間による受入確認をPASS扱いしません。ローカル環境での受入確認を別環境へ引き継ぐ場合は候補SHA、コマンド／実行入口、必要な環境／アプリケーション、期待結果、未確認理由を現在状態へ残します。送信先を区別しない全体的な `push済み` / `未push` だけを後続クローズの判断根拠にしません。実行時経路、診断、仕様に関する記録はそれぞれ該当する場合だけ含め、非該当課題に `N/A` 項目を埋めるスキーマを要求しません。`Current / Verified`、`Proposed / Target`、`Unverified` を混同せず、未実行をPASSと表現しません。

人間による受入確認PASSは `implementation-completion` 状態の受入確認状態を同じコメントへ更新します。ローカル環境での受入確認FAIL／人間による受入確認FAILは理由追跡が必要なため共通の不変イベントとして新規コメントへ追記し、現在のフェーズ状態はそのイベントコメントIDと再開条件を参照します。FAIL時は候補を保持して明示的な再開指示後に `Implementation` へ戻します。

`candidate_commit` は課題の完了を意味せず、人間による受入確認で確認する候補を識別します。基準となるローカル実行で既存の未コミット変更が今回課題の対象パスと混在して分離不能な場合は、差分断片単位で推測せず `checkpoint` を実行しません。リモート実行ではローカル環境の作業ツリーや未コミット差分の存在を要求せず、候補 `ref`／`tree` の再取得確認で対象範囲を確認します。

候補の安全条件は有効なGit実行方法ごとに維持します。ローカル実行では `candidate_commit == current HEAD` をクローズまで維持し、対象パスに受入確認後の未コミット差分がないことを確認します。リモート実行では `candidate_commit == candidate ref` を維持し、受入確認時に記録した候補 `ref`／`tree` から変化していないことを再取得確認します。同一リポジトリ・同一ブランチ／`ref` では人間による受入確認待ち候補の後に別課題で候補を進めません。人間による受入確認FAILで同じ課題を再実装する場合は旧候補を保持して新しい候補 `checkpoint` を積めます。最終クローズではクローズ先リモート／`ref` を先に確定し、Linear記録済みの同一課題のcheckpoint列のうち、その対象 `ref` から現在到達不能なcheckpointだけを古い順に `allowed_checkpoint_shas` として渡します。別のリモート／`ref` へ先行プッシュ済みでもクローズ先から未到達なら含め、クローズ先から既に到達可能なら除外し、送信対象コミット列全体との完全一致を確認してから公開します。

## `In Implementation Review`: 実装レビュー

通常課題で `In Implementation Review` にある場合は、`implementation-completion` 状態から `test_decision` と現在の候補 (`candidate_commit`) を再取得し、候補 `ref`／`tree` と一致することを確認します。通常課題のこのステータスは `Test not required` の独立実装レビュー中だけを表します。`Test required` がこのステータスにある場合は旧契約または不整合として推測せずBLOCKEDし、永続状態を確認します。

実装レビューのレビューコメントには、`issue`、`phase`=`Implementation Review`、`test_decision`=`Test not required`、`candidate_commit`、`review_targets`、`verification_evidence`、`decision`、`findings`、`blocker` を保存します。

`state_key: implementation-review` の可変フェーズ状態を実装レビューのレビューコメントとして使います。状態が存在しない初回だけ新規コメントを作成し、そのコメントIDを保持します。既存の同じ状態ではレビュー資料、候補、検証の根拠、レビュー結果を同じコメントへ更新し、別の実装レビュー状態コメントは追加しない・作成しない。

`Test not required` では現在の候補に対する最新の承認済み実装レビューが存在するかでレビュー状態を判定します。

- 現在の候補に結び付いた `APPROVE` がない場合は独立実装レビュー待ち
- レビュー対象候補SHA (`candidate_commit`) が現在の候補と一致する `implementation-review` 状態の最新 `APPROVE` がある場合はステータスを `Awaiting Acceptance` へ更新する
- 候補変更時は旧候補へ結び付いた `APPROVE` は失効し、新しい候補のレビュー資料／結果へ状態を更新して最新のレビューを行う

実装レビューは成果物作成主体とは**独立**した読み取り専用レビュー担当が行います。成果物作成主体は同一実行環境で承認判定または `APPROVE` を確定しない。実装レビュー開始時は**最新状態として**現在の候補 (`candidate_commit`) を確認し、その後Linearの課題／ステータス／基準となる計画／全コメント／ラベル／依存関係とリポジトリの根拠、現在の候補に対する差分／成果物、検証の根拠、未確認事項を再取得します。過去のチャットの説明や結論をレビュー根拠にしません。

レビュー責務は受入条件、現在の候補の差分／成果物、検証の根拠、未確認事項の独立確認に限定し、旧来の広範なコード品質レビューを全面復活させません。レビューは成果物修正へ越境しません。

`implementation-review` 状態には最新の実行やクローズでレビュー資料を再構築できる最小限の永続メタデータとして、`issue`、`phase`=`Implementation Review`、`test_decision`=`Test not required`、`candidate_commit`、`review_targets`（現在の候補の差分／成果物）、`verification_evidence`、`unverified`、`decision`、`findings`、`blocker` を現在値として保持します。`review_targets` と `verification_evidence` は基準となるレビュー結果の `review_context` に保持し、本文中の説明だけで代替しません。レビュー資料とレビュー結果は同じコメントへ更新します。

基準となる判定は次を使います。

- `APPROVE` → 指摘事項のない承認レビューとして `implementation-review` 状態を更新し、ステータスを `Awaiting Acceptance` へ更新して現在の候補に紐付く受入待ちへ進む
- `CHANGES_REQUIRED` → 指摘事項を共通の不変イベントへ追記し、現在状態を更新してステータスを `Implementation` へ戻して停止する
- `BLOCKED` → 具体的な停止理由を不変イベントへ追記し、現在状態を更新してステータスを維持して停止する

独立レビュー担当を現在の実行から利用できない場合は、レビューに必要な現在の候補／差分／検証の根拠／未確認事項を `implementation-review` 状態から再構築できる状態にして `In Implementation Review` で永続的に停止し、別Chat等の独立実行へ引き継ぎます。

## `Awaiting Acceptance`: ローカル環境／人間による受入確認待ち

通常課題の `Awaiting Acceptance` はAIによる実装レビューの完了有無ではなく、現在の候補に対するローカル環境／人間による受入確認の未確認事項を保持する受入待ちステータスです。

- `Test required`: 実装レビューは実行しない。候補 `checkpoint` 後に直接 `Awaiting Acceptance` へ進む
- `Test not required`: 現在の候補に結び付いた最新 `implementation-review` 状態の `APPROVE` が存在し、レビュー対象候補SHAと現在の候補が一致する場合だけ `Awaiting Acceptance` に到達できる。候補変更時は旧 `APPROVE` を失効させる

`implementation-completion` 状態の実装完了、自動テスト／検証、CI検証、残るローカル環境での受入確認、残る人間による受入確認、現在の候補SHAを確認します。ローカル環境での受入確認を現在の環境で実行できない場合は候補SHA、コマンド／実行入口、必要な環境／アプリケーション、期待結果、未確認理由を同じ状態へ残し、`Awaiting Acceptance` のまま引き継ぎます。

問題が見つかった場合は、ローカル環境での受入確認FAIL／人間による受入確認FAILを不変イベントへ残し、候補を保持して明示的な再開指示後に `Implementation` へ戻します。問題がなければ人間による受入確認PASSを同じ状態へ更新し、明示的なクローズ指示を受けて [close.md](close.md) に進みます。人間による受入確認または実装レビューの正判定だけで `Done` へ進めません。
