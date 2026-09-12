#!/usr/bin/env python3
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

# Close must reject an unreviewed or stale Test-not-required candidate.
require(close_ref,
        "`Test not required`",
        "Implementation Review",
        "current candidate",
        "`APPROVE`",
        "candidate_commit")

# Reviewer agents support the minimal Test-not-required Implementation Review
# without taking artifact-modification responsibility.
for reviewer in (reviewer_light, reviewer_strict):
    require(reviewer,
            "Implementation Review",
            "Acceptance Criteria",
            "Verification evidence",
            "APPROVE",
            "CHANGES_REQUIRED",
            "BLOCKED",
            "ファイル編集")

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
