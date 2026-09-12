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

# Canonical Review is always independent. Review-mode metadata and executor-mode
# switching are no longer part of workflow state or comments.
for text in (canonical, planning, test_ref, remote, architecture, openai, agent_yaml):
    forbid(text, "review_mode: self", "review_mode: independent")
for text in (canonical, planning, test_ref):
    forbid(text, "active Review executor")
require(canonical, "独立", "read-only Reviewer")
require(planning, "独立", "APPROVE", "CHANGES_REQUIRED", "BLOCKED")
require(test_ref, "独立", "TESTS_APPROVED", "TESTS_CHANGES_REQUIRED", "PLAN_INCOMPLETE", "BLOCKED")

# Remote eligibility is intentionally unchanged: normal + lightweight only,
# Bug/Spike/Strict excluded. Reviewer availability must not broaden or narrow
# eligibility; if an independent Review cannot run here, stop and hand off.
require(remote,
        "normal + lightweight",
        "Bug",
        "Spike",
        "Strict profile",
        "対象外",
        "Review Status",
        "handoff",
        "local worktree",
        "GitHub repository read/write")
forbid(remote,
       "## Review executor binding",
       "Self-review開始時",
       "2回連続",
       "独立read-only reviewerを現在環境から利用できない場合だけ `review_mode: self` を使う")

# HIR-229 regression: independent reviewers for binding/adapter/context changes
# must check old-binding assumptions, a counterexample context, existing-context
# safety, and transitive canonical references.
for reviewer in (plan_reviewer_light, plan_reviewer_strict, reviewer_light, reviewer_strict):
    require(reviewer,
            "旧binding",
            "反例",
            "既存context",
            "transitive")

# Test-required issues keep the simplified flow: no Implementation Review.
# Test-not-required issues use In Implementation Review as a durable two-substate
# phase, keyed by current candidate SHA and a candidate-bound Review decision.
require(implementation,
        "`Test required`",
        "Implementation Reviewを実行しない",
        "`Test not required`",
        "Implementation Reviewを実行する",
        "current candidate",
        "candidate変更時",
        "`candidate_commit`",
        "`APPROVE`",
        "`CHANGES_REQUIRED`",
        "`BLOCKED`",
        "Human Acceptance待ち")
forbid(implementation, "通常IssueではAIの独立Reviewを実行しない")

# Close semantics are relational, not just keyword presence:
# 1. Test required must remain exempt from Implementation Review.
# 2. Test not required requires a latest positive Review bound to the current
#    candidate SHA.
# 3. Changing the candidate invalidates an older approval.
require_regex(
    close_ref,
    r"`Test required`.{0,500}Implementation Review.{0,120}(Close条件にしない|前提にしない|要求しない|不要)",
    "Test required Close does not require Implementation Review",
)
require_regex(
    close_ref,
    r"`Test not required`.{0,900}(Implementation Review|Review Comment).{0,500}(対象candidate SHA|review対象candidate SHA|candidate_commit).{0,300}(current|現在).{0,300}(一致|同一).{0,300}`APPROVE`",
    "Test not required Close requires APPROVE bound to current candidate",
)
require_regex(
    close_ref,
    r"(candidate変更|candidate_commit.{0,120}変更).{0,500}(旧|過去).{0,250}`APPROVE`.{0,250}(失効|無効)",
    "old Implementation Review approval is invalid after candidate change",
)

# Test-not-required Implementation Review must itself be an independent fresh
# review. A positive decision cannot be made by the artifact-producing context,
# and the reviewer must reconstruct evidence from the current candidate plus
# fresh Linear/repository state.
require_regex(
    implementation,
    r"`Test not required`.{0,1600}Implementation Review.{0,500}独立",
    "Test not required Implementation Review is independent",
)
require_regex(
    implementation,
    r"(成果物作成主体|実装主体|Implementer).{0,500}(同一実行コンテキスト|同一context).{0,500}(positive|正判定|`APPROVE`).{0,250}(確定しない|禁止)",
    "artifact-producing context cannot finalize a positive Implementation Review",
)
require_regex(
    implementation,
    r"Implementation Review.{0,1800}(fresh|再取得).{0,700}(Linear|Issue).{0,700}(repository evidence|repository).{0,700}(current candidate|candidate_commit)",
    "Implementation Review fresh-reads Linear, repository evidence, and current candidate",
)
for reviewer in (reviewer_light, reviewer_strict):
    require(reviewer,
            "Implementation Review",
            "Acceptance Criteria",
            "Verification evidence",
            "APPROVE",
            "CHANGES_REQUIRED",
            "BLOCKED",
            "ファイル編集")
    require_regex(
        reviewer,
        r"Implementation Review.{0,1200}独立",
        "reviewer agent treats Implementation Review as independent",
    )
    require_regex(
        reviewer,
        r"Implementation Review.{0,2200}(fresh|再取得).{0,900}(current candidate|candidate_commit).{0,900}(Linear|Issue).{0,900}(repository evidence|repository)",
        "reviewer agent fresh-reads candidate, Linear, and repository evidence",
    )

# Remote Git/candidate and verification boundaries remain unchanged.
require(remote_git,
        "blob", "tree", "commit", "ref",
        "non-force",
        "readback",
        "1回だけretry",
        "PR merge", "squash", "rebase",
        "candidate SHA")
require(canonical,
        "Repository evidenceはactive Git binding",
        "canonical/local bindingではGit root、worktree、適用されるlocal instructions",
        "remote bindingではrepository identity、default/candidate ref、baseline")
require(implementation,
        "local bindingでは `candidate_commit == current HEAD`",
        "remote bindingでは `candidate_commit == candidate ref`",
        "candidate ref/tree")
require(close_ref,
        "active Git binding",
        "local bindingではcandidate SHAがcurrent HEAD",
        "remote bindingではcandidate SHAがcandidate ref",
        "candidate ref/tree")
require(test_ref, "Test layer", "execution boundary")
require(implementation, "candidate SHA", "CI対象SHA")

# Architecture/bootstrap/remote metadata are synchronized to the independent
# Review contract without changing local Git routing.
require(architecture,
        "remote-implementation-loop",
        "normal + lightweight",
        "独立",
        "CI Verification", "Local Acceptance", "Human Acceptance")
forbid(architecture, "review_mode: self", "review_mode: independent", "self-reviewへ差し替え")
require(openai,
        "remote-implementation-loop",
        "implementation-loop",
        "独立",
        "Git transportとして扱うため、GitHub pluginへ置換しない")
forbid(openai, "review_mode: self", "self-review")
require(agent_yaml, "$remote-implementation-loop")
forbid(agent_yaml, "self-review")

print("[PASS] independent review / remote implementation-loop contract")
