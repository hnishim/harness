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
    "ci",
    "test",
    "tests",
    "check",
    "checks",
    "validate",
    "validation",
    "verify",
    "verification",
    "lint",
}
NEGATIVE_CI_TOKENS = {
    "release",
    "deploy",
    "deployment",
    "publish",
    "publishing",
    "docs",
    "documentation",
    "maintenance",
    "cleanup",
    "sync",
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
require(canonical, "独立", "read-only Reviewer")
require(planning, "独立", "APPROVE", "CHANGES_REQUIRED", "BLOCKED")
require(test_ref, "独立", "TESTS_APPROVED", "TESTS_CHANGES_REQUIRED", "PLAN_INCOMPLETE", "BLOCKED")

require(remote, "normal + lightweight", "Bug", "Spike", "Strict profile", "対象外",
        "Review Status", "handoff", "local worktree", "GitHub repository read/write")
forbid(remote, "## Review executor binding", "Self-review開始時", "2回連続",
       "独立read-only reviewerを現在環境から利用できない場合だけ `review_mode: self` を使う")

for reviewer in (plan_reviewer_light, plan_reviewer_strict, reviewer_light, reviewer_strict):
    require(reviewer, "旧binding", "反例", "既存context", "transitive")

# Adding Implementation Review must not replace the existing Test Review or
# Spike Result Review phases. Both reviewer profiles remain read-only and keep
# the phase-specific decision vocabularies for all three supported phases.
for reviewer in (reviewer_light, reviewer_strict):
    require(reviewer,
            "Test・Result・Implementation共通の独立read-only Reviewer",
            "review phaseは `Test Review`、`Implementation Review`、`Result Review` のいずれか",
            "- Test Review: `TESTS_APPROVED` / `TESTS_CHANGES_REQUIRED` / `PLAN_INCOMPLETE` / `BLOCKED`",
            "- Implementation Review: `APPROVE` / `CHANGES_REQUIRED` / `BLOCKED`",
            "- Result Review: `DECISION_READY` / `CHANGES_REQUIRED` / `MATERIAL_DEVIATION` / `BLOCKED`",
            "ファイル編集")

# Fresh readback is a common canonical Review contract, not an
# Implementation-Review-only rule. Every Review starts from current Linear,
# harness, repository and phase-specific artifact evidence.
require(canonical,
        "## Review共通契約",
        "ReviewerはReview開始時に最新Linear Issue / Status / canonical Plan /全Comments / Labels / relations",
        "最新Harness reference",
        "review対象のrepository evidence",
        "phase固有のartifact、diff、test evidence、current candidate")
require_regex(
    planning,
    r"In Plan Review: Review.{0,1800}Review開始時.{0,1200}Issue / Status / Description / canonical Plan /全Comments / Labels / relations.{0,700}最新Harness.{0,700}repository evidence.{0,700}review対象差分.{0,300}fresh",
    "Plan Review fresh-reads current Linear, Harness, repository and review target evidence",
)
require_regex(
    test_ref,
    r"Test Review.{0,1800}Review開始時.{0,1200}最新のLinear Issue / Status / canonical Plan /全Comments / Labels / relations.{0,700}最新Harness.{0,700}repository evidence.{0,700}test artifact.{0,700}(再実行command|再実行).{0,300}fresh",
    "Test Review fresh-reads current Linear, Harness, repository and test artifact evidence",
)
require_regex(
    canonical,
    r"Review共通契約.{0,3200}(現在Status|current Status).{0,700}(Review phase|phase).{0,500}(だけ|のみ).{0,1000}(成果物修正|Implementation).{0,500}(越境しない|行わない)",
    "Review execution is limited to the current Status Review phase and does not cross into artifact modification or Implementation",
)

require(implementation, "`Test required`", "Implementation Reviewを実行しない",
        "`Test not required`", "Implementation Reviewを実行する", "current candidate",
        "candidate変更時", "`candidate_commit`", "`APPROVE`", "`CHANGES_REQUIRED`",
        "`BLOCKED`", "Human Acceptance待ち")
forbid(implementation, "通常IssueではAIの独立Reviewを実行しない")

require_regex(close_ref, r"`Test required`.{0,500}Implementation Review.{0,120}(Close条件にしない|前提にしない|要求しない|不要)",
              "Test required Close does not require Implementation Review")
require_regex(close_ref, r"`Test not required`.{0,900}(Implementation Review|Review Comment).{0,500}(対象candidate SHA|review対象candidate SHA|candidate_commit).{0,300}(current|現在).{0,300}(一致|同一).{0,300}`APPROVE`",
              "Test not required Close requires APPROVE bound to current candidate")
require_regex(close_ref, r"(candidate変更|candidate_commit.{0,120}変更).{0,500}(旧|過去).{0,250}`APPROVE`.{0,250}(失効|無効)",
              "old Implementation Review approval is invalid after candidate change")

require_regex(implementation, r"`Test not required`.{0,1600}Implementation Review.{0,500}独立",
              "Test not required Implementation Review is independent")
require_regex(implementation, r"(成果物作成主体|実装主体|Implementer).{0,500}(同一実行コンテキスト|同一context).{0,500}(positive|正判定|`APPROVE`).{0,250}(確定しない|禁止)",
              "artifact-producing context cannot finalize a positive Implementation Review")
require_regex(implementation, r"Implementation Review.{0,1800}(fresh|再取得).{0,700}(Linear|Issue).{0,700}(repository evidence|repository).{0,700}(current candidate|candidate_commit)",
              "Implementation Review fresh-reads Linear, repository evidence, and current candidate")
for reviewer in (reviewer_light, reviewer_strict):
    require(reviewer, "Implementation Review", "Acceptance Criteria", "Verification evidence",
            "APPROVE", "CHANGES_REQUIRED", "BLOCKED", "ファイル編集")
    require_regex(reviewer, r"Implementation Review.{0,1200}独立",
                  "reviewer agent treats Implementation Review as independent")
    require_regex(reviewer, r"Implementation Review.{0,2200}(fresh|再取得).{0,900}(current candidate|candidate_commit).{0,900}(Linear|Issue).{0,900}(repository evidence|repository)",
                  "reviewer agent fresh-reads candidate, Linear, and repository evidence")

require(remote_git, "blob", "tree", "commit", "ref", "non-force", "readback", "1回だけretry",
        "PR merge", "squash", "rebase", "candidate SHA")
require(canonical, "Repository evidenceはactive Git binding",
        "canonical/local bindingではGit root、worktree、適用されるlocal instructions",
        "remote bindingではrepository identity、default/candidate ref、baseline")
require(implementation, "local bindingでは `candidate_commit == current HEAD`",
        "remote bindingでは `candidate_commit == candidate ref`", "candidate ref/tree")
require(close_ref, "active Git binding", "local bindingではcandidate SHAがcurrent HEAD",
        "remote bindingではcandidate SHAがcandidate ref", "candidate ref/tree")
require(test_ref, "Test layer", "execution boundary")
require(implementation, "candidate SHA", "CI対象SHA")

# HIR-236: requiredness must come from provider configuration first and then
# conservatively from the workflow definition itself. A second workflow
# allowlist file must not be required for the normal path.
assert not legacy_ci_registry.exists(), (
    "legacy .github/implementation-loop-ci.yml must be removed; "
    "workflow identity must not be duplicated in a second registry"
)
forbid(close_ref, ".github/implementation-loop-ci.yml")
require_regex(
    close_ref,
    r"provider.{0,500}(required checks|required CI|ruleset).{0,800}(Source of Truth|最優先).{0,1400}(workflow|\.github/workflows/)",
    "provider-native required configuration takes precedence over workflow discovery",
)
require_regex(
    close_ref,
    r"provider.{0,800}(取得不能|readback不能|取得できない|unavailable|inaccessible).{0,1000}(requiredなし|designationなし|absent|none).{0,500}(推測しない|みなさない|inferしない|assumeしない).{0,1000}(`ci_applicability=unknown`|safe-stop|BLOCKED)",
    "unavailable provider requiredness is not guessed as absent and safe-stops",
)
require(close_ref,
        ".github/workflows/",
        "positive token",
        "negative token",
        "# implementation-loop-ci: validation",
        "# implementation-loop-ci: ignore",
        "`paths`",
        "`paths-ignore`",
        "`ci_applicability=unknown`",
        "required set")
for token in sorted(POSITIVE_CI_TOKENS):
    require(close_ref, f"`{token}`")
for token in sorted(NEGATIVE_CI_TOKENS):
    require(close_ref, f"`{token}`")

# The canonical contract must bind classification to either workflow name or
# filename stem, not merely mention both concepts independently.
require_regex(
    close_ref,
    r"(workflow\s*`?name`?|workflow名).{0,350}(または|or).{0,350}(filename stem|file name stem|ファイル名stem|filename).{0,900}(positive token|validation)",
    "workflow identity classification uses workflow name OR filename stem",
)

# Every unambiguous validation candidate is part of the required set. It is
# not sufficient to choose one representative workflow when several apply.
require_regex(
    close_ref,
    r"(validation candidate|automatic validation candidate).{0,700}(1件以上|一つ以上|one or more|>=\s*1).{0,900}(ambiguous.{0,300}(ない|なし|0|none)|曖昧.{0,300}(ない|なし)).{0,1100}(全体|すべて|全件|all).{0,350}(required set|required)",
    "all unambiguous validation candidates become the required set",
)

# Repositories with no target-applicable workflow, or only clearly
# non-validation workflows, resolve to none rather than unknown/required.
require_regex(
    close_ref,
    r"((applicable|target.{0,80}適用).{0,220}workflow.{0,300}(存在しない|ない)|workflow.{0,300}(存在しない|ない)).{0,900}(non-validation.{0,300}(のみ|だけ)|明確.{0,200}non-validation.{0,300}(のみ|だけ)).{0,900}`ci_applicability=none`",
    "no applicable workflow or non-validation-only repository resolves to none",
)

# Ambiguous trigger applicability and path filters must safe-stop instead of
# being promoted to required or demoted to none.
require_regex(
    close_ref,
    r"(複雑.{0,100}trigger|complex trigger|target ref.{0,300}(一意に判定できない|判定不能|ambiguous)).{0,1000}`ci_applicability=unknown`",
    "complex or unresolvable target trigger applicability resolves to unknown",
)
require_regex(
    close_ref,
    r"`paths`.{0,500}`paths-ignore`.{0,1000}(判定不能|一意に判定できない|ambiguous|automatic判定.{0,100}しない).{0,800}`ci_applicability=unknown`",
    "paths and paths-ignore applicability uncertainty resolves to unknown",
)
require_regex(
    close_ref,
    r"(positive|validation).{0,1000}(negative|release|deploy).{0,1000}(混在|ambiguous|unknown)",
    "mixed validation/non-validation identity remains ambiguous instead of being promoted",
)
require_regex(
    close_ref,
    r"(override|implementation-loop-ci: validation).{0,1000}(push|target ref).{0,700}(満た|成立|適用)",
    "co-located override cannot bypass push-to-target applicability",
)

# Co-located override metadata is a narrow exception. Malformed metadata never
# becomes a fallback permission to continue Close.
require_regex(
    close_ref,
    r"(override|implementation-loop-ci).{0,700}(重複|duplicate).{0,900}`ci_applicability=unknown`",
    "duplicate co-located override metadata resolves to unknown",
)
require_regex(
    close_ref,
    r"(override|implementation-loop-ci).{0,700}(競合|conflict).{0,900}`ci_applicability=unknown`",
    "conflicting co-located override metadata resolves to unknown",
)
require_regex(
    close_ref,
    r"(override|implementation-loop-ci).{0,700}(未知|unknown).{0,300}(値|value|metadata).{0,900}`ci_applicability=unknown`",
    "unknown co-located override value resolves to unknown",
)
require_regex(
    close_ref,
    r"(CI-like automation|workflow).{0,1000}(存在しない|ないこと).{0,700}`ci_applicability=none`",
    "none requires configuration evidence that no applicable CI-like automation exists",
)

# Representative identities from HIR-225 / HIR-226 / HIR-227 must be
# classifiable without a separate registry. Release/deploy/docs-style names
# stay out of the required validation set, while mixed/unknown identities
# remain ambiguous and therefore safe-stop.
for identity in ("CI", "Tests", "Repository validation", "lint checks"):
    assert classify_identity(identity) == "validation", identity
for identity in ("Release", "Deploy", "Docs maintenance", "Publishing sync"):
    assert classify_identity(identity) == "non-validation", identity
for identity in ("CI deploy", "Validation release", "Build", "Automation"):
    assert classify_identity(identity) == "ambiguous", identity

# Harness's own workflow is a representative target-push validation workflow.
require(ci_workflow, "name: CI", "push:", "main")

# HIR-234 post-publish execution semantics are unchanged.
require(close_ref, "ci_applicability", "execution observation", "published_sha",
        "matching publish-trigger", "local Git executor", "remote Git executor")
require(close_ref, "`ci_applicability=required` のまま", "`not_observed`",
        "matching publish-trigger run", "`ci_applicability=none`", "CI-like automation")
require(close_ref, "`event=push`", "`head_branch == target branch/ref`", "`head_sha == published_sha`",
        "`pull_request` eventのsuccessはpost-publish `push` CIの代替にしない")
require(close_ref, "`status=completed && conclusion=success` のみ", "`neutral`", "`skipped`", "unknown conclusion")
require(remote, "close.md", "post-publish CI")
forbid(remote, "event=push", "conclusion=success")

require(architecture, "remote-implementation-loop", "normal + lightweight", "独立",
        "CI Verification", "Local Acceptance", "Human Acceptance", "post-publish CI",
        "workflow")
forbid(architecture, ".github/implementation-loop-ci.yml")
require_regex(
    architecture,
    r"post-publish CI.{0,2200}(provider|required).{0,1000}(workflow|\.github/workflows/)",
    "architecture documents provider/workflow-owned CI requiredness",
)
forbid(architecture, "review_mode: self", "review_mode: independent", "self-reviewへ差し替え")
require(openai, "remote-implementation-loop", "implementation-loop", "独立",
        "Git transportとして扱うため、GitHub pluginへ置換しない")
forbid(openai, "review_mode: self", "self-review")
require(agent_yaml, "$remote-implementation-loop")
forbid(agent_yaml, "self-review")

print("[PASS] independent review + workflow-derived post-publish CI contract")
