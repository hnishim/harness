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
ci_contract = read(".github/implementation-loop-ci.yml")

# Canonical entry point remains independent/local by default.
require(canonical, "review_mode: independent", "local Git executor", "checkpoint", "publish checkpoint")
require(planning, "review_mode: independent", "active Review executor")
require(test_ref, "review_mode: independent", "CI Verification", "Local Acceptance", "Human Acceptance")
require(implementation, "active Git executor", "CI Verification", "Remaining Local Acceptance", "Remaining Human Acceptance")
require(close_ref, "active Git executor", "publish checkpoint")

# Remote adapter is intentionally thin and only supports normal + lightweight.
require(remote,
        "normal + lightweight",
        "review_mode: self",
        "independent reviewer",
        "Bug",
        "Spike",
        "Strict profile",
        "canonical/local `implementation-loop`")
forbid(remote,
       "Bug modeでは親Bugの症状確認",
       "ROOT_CAUSE_CONFIRMED` 後",
       "## Test Implementation",
       "## Implementation\n")

# Self review must be a fresh pass, not a rubber stamp, and convergence is bounded.
require(remote,
        "Issue / Status / canonical Plan / Comments / Labels / relations",
        "repository evidence",
        "2回連続")

# Remote Git executor preserves candidate identity and uses bounded readback/retry.
require(remote_git,
        "blob", "tree", "commit", "ref",
        "non-force",
        "readback",
        "1回だけretry",
        "PR merge", "squash", "rebase",
        "candidate SHA")

# Repository/candidate evidence is conditional on the active Git binding.
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

# Verification axes remain separate and CI evidence is tied to the candidate SHA.
require(test_ref, "Test layer", "execution boundary")
require(implementation, "candidate SHA", "CI対象SHA")

# HIR-234: Close applies one canonical post-publish CI gate for local and remote publish.
require(close_ref,
        "ci_applicability",
        "execution observation",
        "published_sha",
        "matching publish-trigger",
        "local Git executor",
        "remote Git executor")

# Applicability is configuration state; missing execution evidence never turns required CI into none/unknown.
require(close_ref,
        "`ci_applicability=required` のまま",
        "`not_observed`",
        "matching publish-trigger run",
        "`ci_applicability=none`",
        "CI-like automation")

# Same-SHA PR success cannot satisfy the post-publish push gate.
require(close_ref,
        "`event=push`",
        "`head_branch == target branch/ref`",
        "`head_sha == published_sha`",
        "`pull_request` eventのsuccessはpost-publish `push` CIの代替にしない")

# GitHub Actions PASS uses a positive allowlist; ambiguous conclusions cannot pass.
require(close_ref,
        "`status=completed && conclusion=success` のみ",
        "`neutral`",
        "`skipped`",
        "unknown conclusion")

# Repository-owned CI is required only by explicit designation when provider required checks are absent.
require(ci_contract,
        "provider: github-actions",
        "workflow: .github/workflows/ci.yml",
        "event: push",
        "branch: main")
require(close_ref,
        ".github/implementation-loop-ci.yml",
        "explicit declaration",
        "requiredness")

# The remote adapter delegates Close semantics to canonical close.md rather than duplicating provider rules.
require(remote, "close.md", "post-publish CI")
forbid(remote, "event=push", "conclusion=success")

# Architecture/bootstrap are synchronized without breaking local routing.
require(architecture,
        "remote-implementation-loop",
        "normal + lightweight",
        "CI Verification", "Local Acceptance", "Human Acceptance",
        "post-publish CI",
        ".github/implementation-loop-ci.yml")
require(openai,
        "remote-implementation-loop",
        "implementation-loop",
        "Git transportとして扱うため、GitHub pluginへ置換しない")
require(agent_yaml, "$remote-implementation-loop")

print("[PASS] remote implementation-loop contract")
