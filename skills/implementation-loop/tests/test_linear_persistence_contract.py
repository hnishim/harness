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


def require_regex(text: str, pattern: str, description: str) -> None:
    assert re.search(pattern, text, flags=re.DOTALL), f"missing semantic contract: {description}"


canonical = read("skills/implementation-loop/SKILL.md")
planning = read("skills/implementation-loop/references/planning.md")
test_ref = read("skills/implementation-loop/references/test.md")
implementation = read("skills/implementation-loop/references/implementation.md")
spike = read("skills/implementation-loop/references/spike.md")
close_ref = read("skills/implementation-loop/references/close.md")
initial_plan = read("skills/initial-plan/SKILL.md")
architecture = read("agent-development-workflow.md")
remote = read("skills/remote-implementation-loop/SKILL.md")
ci = read(".github/workflows/ci.yml")

# HIR-250: current durable workflow state is compacted into one mutable
# comment per logical state while material decisions/findings remain immutable.
require(canonical,
        "mutable phase state",
        "immutable event",
        "state_key",
        "同じComment ID")
require_regex(
    canonical,
    r"state_key.{0,600}(複数|duplicate|重複).{0,700}BLOCKED",
    "duplicate phase-state keys safe-stop instead of guessing",
)
require_regex(
    canonical,
    r"positive Review.{0,900}(更新|update).{0,500}(phase state|state Comment|同じComment)",
    "positive review updates current phase state rather than appending duplicate evidence",
)
require_regex(
    canonical,
    r"(CHANGES_REQUIRED|TESTS_CHANGES_REQUIRED).{0,1500}(immutable event|event Comment).{0,900}(append|新規Comment)",
    "material review findings remain immutable append-only events",
)
require(canonical, "全Comments", "独立", "fresh")

# Handoff/result and revisions use stable state keys per phase.
require(planning, "state_key: plan-review")
require(test_ref, "state_key: test-implementation", "state_key: test-review")
require(implementation, "state_key: implementation-completion", "state_key: implementation-review")
require(spike, "state_key: spike-result")
require(close_ref, "state_key: close")
require_regex(
    planning,
    r"Review packet.{0,1200}(同じ|same).{0,500}(Comment|phase state).{0,1200}Review Result",
    "plan-review handoff and result share one mutable state comment",
)
require_regex(
    test_ref,
    r"revision.{0,1200}(test-implementation|state_key).{0,800}(更新|update)",
    "test revisions replace current test implementation state",
)
require_regex(
    close_ref,
    r"(Completion|Result|Acceptance).{0,1000}(Comment ID|comment_id|参照).{0,1200}(delta|Close固有)",
    "close state references prior durable state and stores only close-specific delta",
)

# Description ownership is protection-by-explicit-human-marker, not an
# AI-managed region. Legacy CODEX markers remain readable for migration only.
for text in (canonical, planning, initial_plan):
    require(text, "HUMAN_AUTHORED_START", "HUMAN_AUTHORED_END")
require_regex(
    canonical,
    r"CODEX_LINEAR_ISSUE_DESCRIPTION_START.{0,1200}(legacy|旧|互換|正規化)",
    "legacy CODEX marker is compatibility input rather than current ownership source of truth",
)
require_regex(
    initial_plan,
    r"(Agent|AI).{0,900}(自動|automatic).{0,700}HUMAN_AUTHORED.{0,700}(付けない|付与しない|作成しない)",
    "agent-created descriptions do not automatically receive human-authored protection markers",
)
require_regex(
    planning,
    r"canonical Plan.{0,1200}(重複|全文複製|duplicate).{0,700}(避け|抑制|しない)",
    "canonical plan avoids unnecessary duplication of existing description content",
)

# Architecture owns the high-level SoT model; remote remains a thin adapter.
require(architecture, "mutable phase state", "immutable")
require(remote, "canonical", "薄い", "Review semantics")

# The repository CI must execute this contract test.
require(ci, "python3 skills/implementation-loop/tests/test_linear_persistence_contract.py")

print("[PASS] Linear persistence and Description ownership contract")
