# implementation-loop Case reflection scenario verification

このシナリオは、明示的なClose処理から`add-case`へlogical Case payloadを接続する契約を確認するTest Implementation成果物です。イベント発生時のHookや常時監視は対象にせず、Close中の一度の振り返りだけを対象にします。実NotionのmutationはImplementation後のadd-case側シナリオで行い、ここでは呼出し境界、payload、停止条件を確認します。

## 共通確認

- 対象Issueのcanonical Plan、最新Plan Review、Status、Test判定、relations、Repository/worktreeを再取得し、現在のPlanと一致することを確認します。
- Close開始条件、Review／Repositoryゲート、明示的Close指示が揃う前は、Case振り返りも`add-case`呼出しも行いません。
- Closeの振り返り対象は今回のIssue／workflow／taskで証拠により確認できる事象だけです。未定義の意味、推測したCase名、推測した時刻は入力しません。
- payloadは`producer=implementation-loop`、`case_name`、`subject`、`summary`、`occurred_at`、任意の`context`、`case_intent=new`、`human_reindication=false`を使い、Notion DB ID、Property名、Relation名、Page IDを含めません。
- `case_name`はPlanで人間が確定した候補シグナルの値を使用します。Sourceはadd-case境界で`Workflow`へ正規化します。

## I1 明示的Closeだけで起動

明示的Close指示と既存Review／Repositoryゲートが揃った実行、揃っていない実行、イベント発生時のHook相当入力、常時監視相当入力を分けて確認します。

期待結果:

- ゲートと明示的Closeが揃った実行だけ、振り返りを一度行います。
- Hook、常時監視、Close以外のイベント入力では振り返りと`add-case`呼出しを行いません。
- Review正判定だけでClose処理を開始したり、Caseを保存したりしません。

## I2 候補なし

今回の実行にPlanで確定したCase候補シグナルがないCloseを確認します。

期待結果:

- `add-case`呼出しは0回です。
- Case、Policy、Feedback Countを変更せず、通常のClose処理を継続します。

## I3 候補あり・logical payload

Planで人間が確定した候補シグナルに一致し、Subject、Summary、Occurred At、Contextの根拠を取得できる事象を1件および複数件用意します。

期待結果:

- 事象ごとに1つのlogical payloadを作成し、`add-case`を1回ずつ呼び出します。
- payloadに`producer=implementation-loop`、`case_name`、`case_intent=new`、`human_reindication=false`を含めます。
- `Source=Workflow`への変換はadd-case境界で行い、producer側はNotionの物理schemaを参照しません。
- CaseはUnreviewedで記録され、Policy作成、Policy Relation、Feedback Count加算、Review完了は行いません。

## I4 Reviewer指摘の採用境界

Canonical Reviewerが必須指摘を返した場合について、(a)親Agentがユーザー要件・canonical Planと不整合または過剰と判断して採用しない場合、(b)整合を確認して採用し、実際のPlanまたは実装変更に至った場合を確認します。Reviewerの任意提案は別に確認します。

期待結果:

- (a)および任意提案では、Reviewerの指摘だけを理由にCaseを作成しません。
- (b)は、当該Reviewerシグナルを人間が候補リストへ含めている場合だけCase候補になります。
- 親AgentはReviewerの技術判定を再Reviewせず、要件整合の確認と採用結果だけをworkflow事実として扱います。

## I5 外部副作用の失敗・結果不明・誤対象

外部書込みの失敗、応答消失による結果不明、誤対象または意図しない破壊的副作用が発生したCloseを確認します。通常の人間ゲート停止や予定されたテスト失敗は別に確認します。

期待結果:

- Planで当該シグナルを確定している場合だけ、証拠に基づくpayloadを作成します。
- 必須事実が不足する場合はpayloadと`add-case`呼出しを行わず、Case境界でBLOCKEDとします。
- payloadまたは`add-case`が失敗した場合、成功と報告せず、完了済みcore作業とGit公開処理を再実行しません。

## I6 同一発生のClose再実行

同じ発生事象について、同じ`occurred_at`、対象、事実、Contextを持つpayloadでCloseを再実行します。

期待結果:

- 初回と再実行で同一logical payloadを使用します。
- `add-case`側の既存Case照合・再利用へ委ね、同じCaseを重複作成しません。
- PolicyのRelationやFeedback Countを変更しません。

## I7 同様だが別発生

同じ候補シグナルと対象に近い事象を、異なる発生時刻または異なる証拠で2回用意します。

期待結果:

- 発生ごとに別payload、別Caseとして扱います。
- 表現の類似だけで既存Caseへ統合したり、新規Case作成を抑止したりしません。
- 再発パターンの集約とCountはPolicy側の人間Reviewに残します。

## I8 必須事実不足

候補シグナルは一致するが、Subject、Summary、Occurred At、Contextのいずれかを証拠で確定できないケースを確認します。

期待結果:

- payloadを作成せず、`add-case`呼出しを0回にします。
- 推測保存せず、Case境界でBLOCKEDとして不足事実と停止理由を報告します。

## 判定記録

| 項目 | 記録内容 |
| --- | --- |
| Scenario | I1〜I8 |
| Close gate | 明示的Close、Review／Repositoryゲートの確認結果 |
| Candidate | 候補シグナル、採用根拠、または候補なし |
| payload | producer、case_name、Source変換、Subject、Summary、Occurred At、Context、case_intent、human_reindication |
| add-case calls | 呼出し回数、同一payload再実行時の照合結果 |
| mutation | Case／Policy／Feedback Countの差分 |
| 結果 | PASS／FAIL／MANUAL-UNVERIFIED／BLOCKED |
| 証跡 | Review Comment、Issue URL、外部結果、停止理由 |
