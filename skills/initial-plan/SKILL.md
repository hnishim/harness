---
name: initial-plan
description: BacklogのLinear Issueに対して、Linear上の情報だけから初期実装プランを作成し、Issue Descriptionを定型フォーマットへ整理してTodoへ進める。
metadata:
  version: "0.3"
---

# Linear 初期プラン作成

## 目的

指定されたLinear Issueに対して、Repositoryを確認する前段階の**初期プラン**を作成し、その内容をIssue Descriptionへ保存する。Linear Issueを永続的なSource of Truthとして扱い、チャット履歴だけを要求仕様の根拠にしない。このSkillが完了したIssueは `Todo` とし、後続のCodex側PlanningがRepositoryを確認してcanonicalな実装プランへ更新する。

## 共通方針

- 記述は目的達成に必要な最小限とし、できるだけシンプルでライトにします。複雑化させません
- 重複や効果の薄い記述は追加せず、同じ内容をより短く書ける場合は短いほうを採用します
- 作業範囲だけでなく共通化すべき部分がないかを常に検討します。ただし、未確認のRepository事実は断定せず、共通化のためにIssueの要件・スコープを広げません

## Descriptionの粒度

Issueの規模・性質を次の順で4分類し、最初に該当した粒度を使う。

1. **Spike**: タイトルが `Spike:` で始まる、または `Spike` ラベルがあるIssue
2. **複雑Issue**: 非Spikeで、複数の実装論点・依存関係・検証論点があるIssue
3. **小規模Task**: 非Spikeかつ複雑Issueではなく、設定変更・文書変更・単純Taskなど、要件・依存関係・検証論点が限定的なIssue
4. **通常Issue**: 上記以外のIssue

全分類で目的・明示要件・存在する制約・受入条件・canonical Description block内の実装プランを保持する。小規模Taskはこれらを中心にし、検証は受入条件または短いテストプランに含め、情報のない任意セクションを省略する。通常Issueは標準形、複雑IssueとSpikeは後続Planningに必要な詳細度を使う。実装プランでは必要に応じて `Linearで確定済み` と `Repository確認事項` を区別し、未確認のRepository情報は事実化しない。

## Description block markerとLinearの正規化

初期Planと後続のRepository-aware Planningが同じDescriptionを段階的に更新できるよう、標準Description全体を1組のcanonical markerで囲む。標準Descriptionは `## 目的` から `## 参考情報` までとし、内部の実装プラン、テストプラン、受け入れ条件、仮定、未解決事項も同じblock内で更新する。

```text
CODEX_LINEAR_ISSUE_DESCRIPTION_START
## 目的

<標準Description>
## 参考情報

<参考情報>
CODEX_LINEAR_ISSUE_DESCRIPTION_END
```

- 完全なDescription marker pairを1組だけ保存する
- Markerは必ず単独行にする
- 初期Planを更新するときもmarker外のIssue情報を保持し、Description block内だけを置き換える
- Markerが複数ある、片側が欠落する、順序が逆、または範囲を一意に決められない場合は、Descriptionを上書きせず `BLOCKED` とする

## 必須入力

ユーザーは、原則として `HIR-123` のようなLinear Issue IDで対象Issueを1件指定する。

対象Issueを一意に特定できない場合は、変更操作を行う前にIssue IDを確認する。

## 使用するLinear操作

Linearの接続アプリ／プラグインを使用する。

利用可能であれば、以下の操作を使う。

- `Linear.get_issue`
- `Linear.list_comments`
- `Linear.list_issue_statuses`
- `Linear.save_issue`

Linear Issueの内容を取得するためにWeb検索で代用しない。

Linearへアクセスできない、または対象Issueを取得できない場合は処理を中止し、その旨をユーザーへ伝える。Issue内容を推測で補わない。

## ワークフロー

1. 指定されたIssueをLinearから取得する
2. Issueのコメントも取得し、要件の補足や重要な意思決定があれば参照する
3. チームのIssue Statusに `Backlog` と `Todo` が存在することを確認する
4. 現在のIssue Statusを確認する

   - `Backlog`: 初期Plan作成対象として続行する
   - `Todo`: 初期Plan作成済みでCodex側Planning待ちの状態とみなす。ユーザーが明示的に「初期Planを再作成」「初期Planを更新」などを依頼していない限り上書きしない
   - `In Plan Review` 以降の実装ワークフロー上のStatus: ユーザーが明示的に再作成・置換を依頼していても、後続workflowのcanonical stateを壊す可能性があるため原則として更新しない
5. Issue title、既存Description、関連コメントを読む
6. 内容を以下に分類する

   - 明示された事実・要件
   - 制約
   - プラン作成のために必要な仮定
   - 未解決事項
7. 上記の分類に応じた粒度で、下記の定型フォーマットを基にDescription案を作る
8. 既存Issueに含まれる重要情報を保持する。再構成はしてよいが、要件・制約・リンク・重要な注記を黙って削除しない
9. Linear上で確認できないコードベース上の事実を捏造しない。特に、未確認のファイルパス、モジュール名、API、クラス、関数、依存関係、DBスキーマ等を事実として書かない
10. コードベース確認が必要な場合は、Codex実行時に「何を確認するか」「その確認結果で何を決めるか」が分かる形で実装プランへ明記する
11. 作成した内容にDescription marker pairが1組だけ含まれ、HTMLコメント形式のmarkerやLinearで変換される終端記号の並びが含まれていないことを確認する
12. Issue Descriptionを更新する。保存前にIssueを再取得し、対象IssueとDescriptionの変更がないことを確認できない場合は上書きせず `BLOCKED` とする
13. `Backlog` から開始した場合は、Description保存確認後の同じワークフローでIssue Statusを `Todo` に変更する。`Todo` の明示的な初期Plan更新ではStatusを維持する
14. Description保存後にIssueを再取得し、Description marker pairが1組であること、marker外の内容が保持されていること、期待したStatusであることを確認する。確認できない場合は成功扱いにしない
15. ユーザーには、対象Issue IDと「初期Planを記載し、Codex側Planningを開始できるTodoにした」ことだけ簡潔に報告する。依頼されない限り、Description全文はチャットへ再掲しない

## Descriptionの定型フォーマット

以下は通常Issue、複雑Issue、Spikeの標準形である。含める見出しの順序を守り、小規模Taskでは情報のない任意セクションを省略する。

```markdown
CODEX_LINEAR_ISSUE_DESCRIPTION_START

## 目的

<このIssueで達成すること。簡潔に、成果ベースで記載する。>

## 背景・コンテキスト

<既存挙動、背景、依存関係、理由など、Issueやコメントから確認できる情報を記載する。実質的な情報がなければセクションごと省略する。>

## 要件

- <明示された機能要件・非機能要件>
- ...

## 制約・対象外

- <既知の制約、互換性要件、明示的な非対象、スコープ境界>
- ...

実質的な情報がなければセクションごと省略する。

## 実装プラン

1. <具体的な実装ステップ>
2. <具体的な実装ステップ>
3. ...

Coding Agentが実行できる程度に具体化する。ただし、未確認のコードベース詳細を事実として書かない。
Repository確認が必要な場合は、確認対象と、その結果によって決まる事項を明記する。

## テストプラン

- <確認すべき主要挙動・Acceptance Condition>
- <重要なEdge Case / Failure Case>
- ...

テストは「要件」と「受け入れ条件」に追跡可能な形にする。

## 受け入れ条件

- [ ] <完了を客観的に判定できる条件>
- [ ] ...

## 仮定

- <初期プラン作成のために置いた仮定>
- ...

仮定がなければセクションごと省略する。

## 未解決事項

- <実装や検証に影響する未確定事項>
- ...

重要な未解決事項がなければセクションごと省略する。

## 参考情報

- <Issue内に既に存在する関連Issue、URL、文書、参照先など>
- ...

参考情報がなければセクションごと省略する。
CODEX_LINEAR_ISSUE_DESCRIPTION_END
```

## プラン品質ルール

### 要件

- Issue titleの言い換えだけで済ませず、ユーザーの意図を保持する
- 要件と実装案を分離する
- 仮定を要件として扱わない
- 推測で新しい要件を追加しない

### 実装プラン

- 独立して理解できる手順へ分解する
- 推測したコード構文ではなく、期待する挙動と責務の境界を中心に書く
- Issue情報だけでは不足する場合、コードベース調査自体を明示的なステップとして含める
- 過剰設計を避け、明示された要件を満たす最小限の変更を優先する
- Migration、互換性、Error Handling、Cleanupなどは、そのIssueに関係する場合だけ含める
- 完成度を高く見せるためだけに新しいArchitectureを選ばない

### テストプラン

- 主要な正常系を含める
- 要件から導ける重要なEdge Case・Failure Caseを含める
- 小規模Task（HIR-62相当）、通常Issue、複雑Issue（HIR-83相当）、Spike（HIR-52相当）の出力を比較する
- Issueが要求していない限り、実装詳細へ過度に依存するテストを避ける
- Issueから確認できないTest Frameworkを勝手に指定しない

### 受け入れ条件

- 各項目を客観的なPass/Failで判定できるようにする
- 「まさしく動く」「きれいなコード」「良いUX」など、測定不能な表現を単独で使わない
- すべての明示要件が、少なくとも1つの受け入れ条件またはテスト項目へ対応していることを確認する

## 情報不足時の扱い

このSkillはChatGPT側でも実行されるため、ローカルRepositoryへアクセスできない場合がある。Linear Issueだけではコードベース情報が不足する場合でも、初期プラン自体は可能な範囲で作成する。その際は以下を守る。

- Repositoryで確認すべき内容を明示する
- 実装上の未確定事項は「未解決事項」へ記載するか、Repository確認後に決める判断として「実装プラン」に書く
- Repository構造や現行挙動を確認したように装わない

後続のCodex側Planning Workflowで、実際のコードベースに照らして初期プランを検証・具体化し、その後 `In Plan Review` へ進める。

## Statusの意味

実装ワークフローでは以下の状態を使用する。

`Backlog` → `Todo` → `In Plan Review` → `Test Implementation` → `In Test Review` → `Implementation` → `In Implementation Review` → `Done`

このSkillでは以下の意味とする。

- `Backlog`: 初期Planがまだ作成されていない
- `Todo`: 初期PlanがDescriptionに存在し、Codex側のRepository-aware Planningを開始できる
- `In Plan Review`: Repositoryを確認したPlanが存在し、レビュー可能またはレビュー中

このSkillは原則として `Todo` で終了する。

## Linearへ保存する前の最終確認

更新前に以下を確認する。

- 指定されたIssueだけを編集している
- 既存Issueに明示されていた要件・制約・重要情報を落としていない
- 事実、仮定、未解決事項を区別している
- 未確認のコードベース詳細を事実として書いていない
- 実装プランがCodex側Planningへ引き継げる程度に具体的である
- テストプランを含める場合は、主要要件と重要なFailure Caseをカバーしている
- 受け入れ条件が客観的に判定可能である
- Descriptionの見出し順がテンプレートどおりである
- 粒度分類、必須情報、空セクションの省略、Linear確定事項とRepository確認事項の区別を守っている
- `Backlog` から開始した場合、最終Statusが `Todo` になっている
