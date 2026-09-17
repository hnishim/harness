#!/usr/bin/env python3
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(rel: str) -> str:
    path = ROOT / rel
    assert path.is_file(), f"missing required artifact: {rel}"
    return path.read_text(encoding="utf-8")


def require(text: str, *needles: str) -> None:
    for needle in needles:
        assert needle in text, f"missing contract text: {needle!r}"


def forbid(text: str, *needles: str) -> None:
    for needle in needles:
        assert needle not in text, f"forbidden contract text present: {needle!r}"


def require_regex(text: str, pattern: str, description: str) -> None:
    assert re.search(pattern, text, flags=re.DOTALL), f"missing semantic contract: {description}"


def identity_tokens(value: str) -> set[str]:
    return {token for token in re.split(r"[^a-z0-9]+", value.lower()) if token}


POSITIVE_CI_TOKENS = {
    "ci", "test", "tests", "check", "checks", "validate", "validation",
    "verify", "verification", "lint",
}
NEGATIVE_CI_TOKENS = {
    "release", "deploy", "deployment", "publish", "publishing", "docs",
    "documentation", "maintenance", "cleanup", "sync",
}


def classify_identity(value: str) -> str:
    tokens = identity_tokens(value)
    positive = bool(tokens & POSITIVE_CI_TOKENS)
    negative = bool(tokens & NEGATIVE_CI_TOKENS)
    if positive and not negative:
        return "validation"
    if negative and not positive:
        return "non-validation"
    return "ambiguous"


remote = read("skills/remote-implementation-loop/SKILL.md")
canonical = read("skills/implementation-loop/SKILL.md")
planning = read("skills/implementation-loop/references/planning.md")
test_ref = read("skills/implementation-loop/references/test.md")
implementation = read("skills/implementation-loop/references/implementation.md")
close_ref = read("skills/implementation-loop/references/close.md")
remote_git = read("skills/remote-implementation-loop/references/remote-git.md")
architecture = read("agent-development-workflow.md")
openai = read("custom-instructions/openai-instructions.md")
agent_yaml = read("skills/remote-implementation-loop/agents/openai.yaml")
plan_reviewer_light = read("agents/plan-reviewer-lightweight.toml")
plan_reviewer_strict = read("agents/plan-reviewer.toml")
reviewer_light = read("agents/reviewer-lightweight.toml")
reviewer_strict = read("agents/reviewer.toml")
ci_workflow = read(".github/workflows/ci.yml")
legacy_ci_registry = ROOT / ".github" / "implementation-loop-ci.yml"

for text in (canonical, planning, test_ref, remote, architecture, openai, agent_yaml):
    forbid(text, "review_mode: self", "review_mode: independent")
for text in (canonical, planning, test_ref):
    forbid(text, "active Review executor")
require(canonical, "独立", "読み取り専用レビュー担当")
require(planning, "独立", "APPROVE", "CHANGES_REQUIRED", "BLOCKED")
require(test_ref, "独立", "TESTS_APPROVED", "TESTS_CHANGES_REQUIRED", "PLAN_INCOMPLETE", "BLOCKED")

require(remote, "軽量プロファイル", "Bug", "Spike", "Strict profile",
        "現在のフェーズ", "機能", "レビューステータス", "引き継ぎ",
        "ローカル環境の作業ツリー", "GitHubリポジトリの読み書き")
forbid(remote, "normal + lightweight")
forbid(remote, "## Review executor binding", "Self-review開始時", "2回連続",
       "独立read-only reviewerを現在環境から利用できない場合だけ `review_mode: self` を使う")

for reviewer in (plan_reviewer_light, plan_reviewer_strict, reviewer_light, reviewer_strict):
    require(reviewer, "旧実行方法", "反例", "既存実行環境", "間接的な")

# Adding Implementation Review must not replace the existing Test Review or
# Spike Result Review phases. Both reviewer profiles remain read-only and keep
# the phase-specific decision vocabularies for all three supported phases.
for reviewer in (reviewer_light, reviewer_strict):
    require(reviewer,
            "テスト・結果・実装共通の独立した読み取り専用レビュー担当",
            "レビュー対象フェーズは `Test Review`、`Implementation Review`、`Result Review` のいずれか",
            "- テストレビュー: `TESTS_APPROVED` / `TESTS_CHANGES_REQUIRED` / `PLAN_INCOMPLETE` / `BLOCKED`",
            "- 実装レビュー: `APPROVE` / `CHANGES_REQUIRED` / `BLOCKED`",
            "- 結果レビュー: `DECISION_READY` / `CHANGES_REQUIRED` / `MATERIAL_DEVIATION` / `BLOCKED`",
            "ファイル編集")

# Fresh readback is a common canonical Review contract, not an
# Implementation-Review-only rule. Every Review starts from current Linear,
# harness, repository and phase-specific artifact evidence.
require(canonical,
        "## レビュー共通の取り決め",
        "最新のLinear課題／ステータス／基準となる計画／全コメント／ラベル／依存関係",
        "最新Harness参照文書",
        "レビュー対象のリポジトリの根拠",
        "フェーズ固有の成果物、差分、テストの根拠、現在の候補")
require_regex(
    planning,
    r"In Plan Review.{0,1800}計画レビュー.{0,1800}レビュー開始時.{0,1500}課題／ステータス／説明欄／基準となる計画／全コメント／ラベル／依存関係.{0,900}最新Harness.{0,900}リポジトリの根拠.{0,900}レビュー対象差分.{0,400}(再取得|最新状態)",
    "Plan Review fresh-reads current Linear, Harness, repository and review target evidence",
)
require_regex(
    test_ref,
    r"テストレビュー.{0,2200}レビュー開始時.{0,1500}最新のLinearの課題／ステータス／基準となる計画／全コメント／ラベル／依存関係.{0,900}最新Harness.{0,900}リポジトリの根拠.{0,900}テスト成果物.{0,900}再実行コマンド.{0,400}(再取得|最新状態)",
    "Test Review fresh-reads current Linear, Harness, repository and test artifact evidence",
)
require_regex(
    canonical,
    r"レビュー共通の取り決め.{0,4200}(現在ステータス|現在の.*ステータス).{0,900}(レビューフェーズ|フェーズ).{0,600}(だけ|のみ).{0,1200}(成果物修正|実装).{0,700}(越境しない|行わない)",
    "Review execution is limited to the current Status Review phase and does not cross into artifact modification or Implementation",
)

require(implementation, "`Test required`", "実装レビューを実行しない",
        "`Test not required`", "独立実装レビュー", "現在の候補",
        "候補変更時", "`candidate_commit`", "`APPROVE`", "`CHANGES_REQUIRED`",
        "`BLOCKED`", "人間による受入確認")
forbid(implementation, "通常IssueではAIの独立Reviewを実行しない")

require_regex(close_ref, r"`Test required`.{0,700}実装レビュー.{0,200}(クローズ条件にしない|条件にしない|前提にしない|要求しない|不要)",
              "Test required Close does not require Implementation Review")
require_regex(close_ref, r"`Test not required`.{0,1100}(実装レビュー|レビューコメント).{0,700}(候補SHA|candidate_commit).{0,400}(現在).{0,400}(一致|同一).{0,400}`APPROVE`",
              "Test not required Close requires APPROVE bound to current candidate")
require_regex(close_ref, r"(候補変更|candidate_commit.{0,120}変更).{0,600}(旧|過去).{0,300}`APPROVE`.{0,300}(失効|無効)",
              "old Implementation Review approval is invalid after candidate change")

require_regex(implementation, r"`Test not required`.{0,1800}実装レビュー.{0,700}独立",
              "Test not required Implementation Review is independent")
require_regex(implementation, r"成果物作成主体.{0,700}(同一実行環境|同一実行コンテキスト).{0,700}(`APPROVE`|承認判定).{0,350}(確定しない|禁止)",
              "artifact-producing context cannot finalize a positive Implementation Review")
require_regex(implementation, r"実装レビュー.{0,2200}(再取得|最新状態).{0,900}(Linear|課題).{0,900}リポジトリの根拠.{0,900}(現在の候補|candidate_commit)",
              "Implementation Review fresh-reads Linear, repository evidence, and current candidate")
for reviewer in (reviewer_light, reviewer_strict):
    require(reviewer, "Implementation Review", "受入条件", "検証の根拠",
            "APPROVE", "CHANGES_REQUIRED", "BLOCKED", "ファイル編集")
    require_regex(reviewer, r"実装レビュー.{0,1500}独立",
                  "reviewer agent treats Implementation Review as independent")
    require_regex(reviewer, r"実装レビュー.{0,2600}(再取得|最新).{0,1100}(現在の候補|candidate_commit).{0,1100}(Linear|課題).{0,1100}リポジトリの根拠",
                  "reviewer agent fresh-reads candidate, Linear, and repository evidence")

require(remote_git, "blob", "tree", "commit", "ref", "強制更新しない", "再取得確認", "1回だけ再試行",
        "PR", "squash", "rebase", "候補SHA")
require(canonical, "リポジトリの根拠は有効なGit実行方法",
        "基準となるローカル実行ではGit root、作業ツリー、適用されるローカル指示",
        "リモート実行ではリポジトリ識別情報、既定／候補 `ref`、基準")
require(implementation, "ローカル実行では `candidate_commit == current HEAD`",
        "リモート実行では `candidate_commit == candidate ref`", "候補 `ref`／`tree`")
require(close_ref, "有効なGit実行方法", "ローカル実行では候補SHAが現在のHEAD",
        "リモート実行では候補SHAが候補 `ref`", "候補 `ref`／`tree`")
require(test_ref, "テスト層", "実行境界")
require(implementation, "候補SHA", "CI対象SHA")

assert not legacy_ci_registry.exists(), (
    "legacy .github/implementation-loop-ci.yml must be removed; "
    "workflow identity must not be duplicated in a second registry"
)
forbid(close_ref, ".github/implementation-loop-ci.yml")
require_regex(
    close_ref,
    r"提供元.{0,700}(必須検査|必須CI|ruleset).{0,1000}(最優先|基準).{0,1800}(ワークフロー|\.github/workflows/)",
    "provider-native required configuration takes precedence over workflow discovery",
)
require_regex(
    close_ref,
    r"提供元.{0,1000}(取得不能|再取得確認不能|取得できない).{0,1200}(必須指定なし|必須なし).{0,700}(推測しない|推測せず).{0,1200}`ci_applicability=unknown`",
    "unavailable provider requiredness is not guessed as absent and safe-stops",
)
require(close_ref,
        ".github/workflows/",
        "検証用途の語句",
        "非検証用途の語句",
        "# implementation-loop-ci: validation",
        "# implementation-loop-ci: ignore",
        "`paths`",
        "`paths-ignore`",
        "`ci_applicability=unknown`",
        "必須集合")
for token in sorted(POSITIVE_CI_TOKENS):
    require(close_ref, f"`{token}`")
for token in sorted(NEGATIVE_CI_TOKENS):
    require(close_ref, f"`{token}`")

require_regex(
    close_ref,
    r"ワークフローの `name`.{0,350}(または).{0,350}(ファイル名|stem).{0,1000}検証用途の語句",
    "workflow identity classification uses workflow name OR filename stem",
)
require_regex(
    close_ref,
    r"自動検証の候補.{0,800}(1件以上|一つ以上).{0,1100}(判定不能.{0,300}(ない|なし)|判定不能なものがない).{0,1300}(全体|すべて|全件).{0,450}(必須集合|required)",
    "all unambiguous validation candidates become the required set",
)
require_regex(
    close_ref,
    r"対象 `ref` へ適用可能なワークフローが存在しない.{0,1200}検証対象外のみ.{0,1200}`ci_applicability=none`",
    "no applicable workflow or non-validation-only repository resolves to none",
)
require_regex(
    close_ref,
    r"(複雑な起動条件|対象 `ref` への適用を一意に判定できない).{0,1200}`ci_applicability=unknown`",
    "complex or unresolvable target trigger applicability resolves to unknown",
)
require_regex(
    close_ref,
    r"`paths`.{0,600}`paths-ignore`.{0,1200}判定不能.{0,1000}`ci_applicability=unknown`",
    "paths and paths-ignore applicability uncertainty resolves to unknown",
)
require_regex(
    close_ref,
    r"検証用途の語句.{0,1200}非検証用途の語句.{0,1200}(混在|判定不能)",
    "mixed validation/non-validation identity remains ambiguous instead of being promoted",
)
require_regex(
    close_ref,
    r"(上書き指定|implementation-loop-ci: validation).{0,1200}(push|対象 `ref`).{0,900}(満た|適用)",
    "co-located override cannot bypass push-to-target applicability",
)
require_regex(
    close_ref,
    r"(上書き指定|implementation-loop-ci).{0,900}重複.{0,1100}`ci_applicability=unknown`",
    "duplicate co-located override metadata resolves to unknown",
)
require_regex(
    close_ref,
    r"(上書き指定|implementation-loop-ci).{0,900}競合.{0,1100}`ci_applicability=unknown`",
    "conflicting co-located override metadata resolves to unknown",
)
require_regex(
    close_ref,
    r"(上書き指定|implementation-loop-ci).{0,900}未知の値.{0,1100}`ci_applicability=unknown`",
    "unknown co-located override value resolves to unknown",
)
require_regex(
    close_ref,
    r"CI相当の自動化.{0,1200}(存在しない|ないこと).{0,900}`ci_applicability=none`",
    "none requires configuration evidence that no applicable CI-like automation exists",
)

for identity in ("CI", "Tests", "Repository validation", "lint checks"):
    assert classify_identity(identity) == "validation", identity
for identity in ("Release", "Deploy", "Docs maintenance", "Publishing sync"):
    assert classify_identity(identity) == "non-validation", identity
for identity in ("CI deploy", "Validation release", "Build", "Automation"):
    assert classify_identity(identity) == "ambiguous", identity

require(ci_workflow, "name: CI", "push:", "main")

require(close_ref, "ci_applicability", "実行結果の観測", "published_sha",
        "公開を契機とする一致した", "ローカル環境", "リモート環境")
require(close_ref, "`ci_applicability=required` のまま", "`not_observed`",
        "公開を契機とする一致した実行", "`ci_applicability=none`", "CI相当の自動化")
require(close_ref, "`event=push`", "`head_branch == target branch/ref`", "`head_sha == published_sha`",
        "`pull_request` イベントの成功は公開後の `push` CIの代替にしない")
require(close_ref, "`status=completed && conclusion=success` のみ", "`neutral`", "`skipped`", "未知の `conclusion`")
require(remote, "close.md", "公開後CI判定")
forbid(remote, "event=push", "conclusion=success")

require(architecture, "remote-implementation-loop", "軽量プロファイル", "Bug", "Spike",
        "フェーズ", "機能", "独立", "CI検証", "ローカル環境での受入確認",
        "人間による受入確認", "公開後CI", "ワークフロー")
forbid(architecture, "normal + lightweight", ".github/implementation-loop-ci.yml")
require_regex(
    architecture,
    r"公開後CI.{0,2600}(提供元|必須).{0,1200}(ワークフロー|\.github/workflows/)",
    "architecture documents provider/workflow-owned CI requiredness",
)
forbid(architecture, "review_mode: self", "review_mode: independent", "self-reviewへ差し替え")
require(openai, "remote-implementation-loop", "implementation-loop", "独立",
        "Git通信として扱うため、GitHubプラグインへ置換しない")
forbid(openai, "review_mode: self", "self-review")
require(agent_yaml, "$remote-implementation-loop")
forbid(agent_yaml, "self-review")

bug_ref = read("skills/implementation-loop/references/bug.md")
spike_ref = read("skills/implementation-loop/references/spike.md")
routing_test = read("custom-instructions/tests/test-openai-routing-contract.sh")

require_regex(
    remote,
    r"`Bug` / `Spike` ラベル自体.{0,220}(対象判定の)?除外条件.{0,160}しない",
    "Bug / Spike labels alone do not make the remote adapter ineligible",
)
require_regex(
    remote,
    r"現在のフェーズ.{0,400}(必要|要求).{0,180}機能.{0,900}(満たせ|利用可能).{0,700}(継続|進め)",
    "remote eligibility is decided from current-phase capability",
)
require(remote, "local-only", "unavailable", "未検証", "引き継ぎ")
forbid(remote,
    "`Bug` labelがあるIssueは対象外。部分実行、remote resumeを行わず",
    "`Spike` labelがあるIssueは対象外。Experiment/PoCやResult Reviewをremote化せず")
require_regex(remote, r"`Strict profile`.{0,400}(対象外|対象)",
              "Strict profile remains a remote hard exclusion")

require(bug_ref, "有効なGit実行方法", "基準となるローカル実行", "リモート実行",
        "リポジトリ識別情報", "基準コミット", "ローカル環境だけ", "未確認")
forbid(bug_ref, "Repository root/worktree、適用されるlocal instructionsを再取得する")
require_regex(
    bug_ref,
    r"ローカル環境だけ.{0,900}(再現|識別検証).{0,1100}(未確認|引き継ぎ).{0,1100}`ROOT_CAUSE_CONFIRMED`",
    "Bug investigation does not turn local-only evidence into a remote root-cause pass",
)

require(spike_ref, "論理的な `checkpoint`", "有効なGit実行主体",
        "基準となるローカル実行", "リモート実行", "`baseline_commit`", "有効なGit実行方法")
forbid(spike_ref,
    "未コミットのproduction変更があれば、handoff前に `git-add-commit-push` を `checkpoint` として委譲します")
require_regex(spike_ref, r"後片付け.{0,2200}有効なGit実行方法",
              "Spike diagnostic cleanup is verified through the active Git binding")

require_regex(
    architecture,
    r"`Bug` / `Spike` ラベル自体.{0,700}(除外条件).{0,300}(しない|ではない)",
    "architecture no longer treats Bug / Spike labels as remote hard exclusions",
)
require_regex(
    architecture,
    r"現在のフェーズ.{0,500}機能.{0,1100}(リモート環境|引き継ぎ)",
    "architecture documents phase/capability remote eligibility",
)
forbid(architecture,
    "Bug/Spike/Strictはremote adapterへ分岐せずcanonical/local `implementation-loop` が所有します。")

require_regex(
    openai,
    r"`Bug` / `Spike` ラベル自体.{0,700}(除外条件).{0,300}(しない|ではない)",
    "OpenAI routing no longer treats Bug / Spike labels as remote hard exclusions",
)
require(openai, "軽量プロファイル", "現在のフェーズ", "機能", "Strict profile",
        "独立レビュー担当の利用可否")
forbid(openai,
    "`Bug / Spike / Strict profile` はremote adapterで部分実行・remote resumeを行わず")

forbid(routing_test, "'normal + lightweight'", "'Bug / Spike / Strict profile'")
require(routing_test, "現在のフェーズ", "機能", "Strict profile", "Bug", "Spike")

print("[PASS] independent review + capability-based remote Bug/Spike contract")
