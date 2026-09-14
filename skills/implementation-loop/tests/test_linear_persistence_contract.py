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
        assert needle not in text, f"obsolete contract text remains: {needle!r}"


def require_regex(text: str, pattern: str, description: str) -> None:
    assert re.search(pattern, text, flags=re.DOTALL), f"missing semantic contract: {description}"


def forbid_regex(text: str, pattern: str, description: str) -> None:
    assert not re.search(pattern, text, flags=re.DOTALL), f"obsolete semantic contract remains: {description}"


def require_state_contract(text: str, state_key: str) -> None:
    needle = f"state_key: {state_key}"
    start = text.find(needle)
    assert start >= 0, f"missing contract text: {needle!r}"
    window = text[max(0, start - 600): start + 2400]
    require_regex(
        window,
        r"(初回|存在しない|ない場合|create|作成)",
        f"{state_key} defines first creation of the state comment",
    )
    require_regex(
        window,
        r"((既存|存在する|ある場合|same|同じ).{0,900}(update|更新))|((update|更新).{0,900}(既存|存在する|ある場合|same|同じ))",
        f"{state_key} updates the existing state comment after creation",
    )
    require_regex(
        window,
        r"(別|separate).{0,250}Comment.{0,500}(追加しない|作成しない|保存しない|増やさない|appendしない)",
        f"{state_key} explicitly rejects a second append-only state comment",
    )


def require_immutable_event_contract(text: str, event_pattern: str, description: str) -> None:
    match = re.search(event_pattern, text, flags=re.DOTALL)
    assert match, f"missing immutable event class: {description}"
    window = text[max(0, match.start() - 1200): match.end() + 1800]
    require_regex(
        window,
        r"(immutable event|event Comment)",
        f"{description} is classified as an immutable event",
    )
    require_regex(
        window,
        r"(append|新規Comment|新規.*Comment)",
        f"{description} is appended instead of overwritten in mutable phase state",
    )


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
require_immutable_event_contract(
    canonical,
    r"PLAN_INCOMPLETE|MATERIAL_DEVIATION",
    "plan-incomplete or material-deviation decision",
)
require_immutable_event_contract(
    canonical,
    r"BLOCKED",
    "concrete blocked reason",
)
require_immutable_event_contract(
    canonical,
    r"(?:Local|Human).{0,120}Acceptance.{0,120}FAIL",
    "Local/Human Acceptance failure",
)
require_immutable_event_contract(
    canonical,
    r"(?:Bug|root[- ]cause).{0,1200}(?:root[- ]cause|evidence|証拠)",
    "Bug root-cause evidence",
)
require_immutable_event_contract(
    canonical,
    r"Spike.{0,1400}(?:finding|Decision|主要)",
    "Spike material finding or final decision",
)
require(canonical, "全Comments", "独立", "fresh")

# Handoff/result and revisions use stable state keys per phase. Each logical
# state explicitly distinguishes first creation from subsequent in-place update,
# and rejects creating a second state comment for the same logical state.
require_state_contract(planning, "plan-review")
require_state_contract(test_ref, "test-implementation")
require_state_contract(test_ref, "test-review")
require_state_contract(implementation, "implementation-completion")
require_state_contract(implementation, "implementation-review")
require_state_contract(spike, "spike-result")
require_state_contract(close_ref, "close")
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

# Reject the old phase-persistence shapes, not only the absence of new words.
# These assertions prevent an implementation from satisfying the new state-key
# vocabulary while silently retaining the previous separate handoff/result
# write instructions in the same canonical references.
forbid_regex(
    planning,
    r"保存後のPlan Review Commentには.{0,1200}Review Context",
    "legacy standalone Plan Review handoff comment contract",
)
forbid_regex(
    planning,
    r"レビュー対象と結果をCommentへ保存",
    "legacy standalone Plan Review result comment contract",
)
forbid_regex(
    test_ref,
    r"変更ファイル.{0,1400}Commentへ保存し\s*`In Test Review`",
    "legacy append-style Test Implementation handoff contract",
)
forbid_regex(
    implementation,
    r"Checkpoint後のCompletion Commentに.{0,2200}保存する",
    "legacy standalone Completion comment contract",
)
forbid_regex(
    implementation,
    r"Implementation ReviewのReview Commentには.{0,1800}保存する",
    "legacy standalone Implementation Review comment contract",
)
forbid_regex(
    spike,
    r"実験結果をCommentへ保存し\s*`In Implementation Review`",
    "legacy append-style Spike result handoff contract",
)
forbid_regex(
    spike,
    r"`DECISION_READY`\s*→.{0,900}Commentへ保存してClose待ち",
    "legacy standalone Spike decision comment contract",
)
forbid_regex(
    close_ref,
    r"Close Commentには最低限.{0,2200}保存します",
    "legacy standalone Close snapshot contract",
)
forbid_regex(
    close_ref,
    r"CI evidenceと再開条件をCommentへ保存してStatusを維持",
    "legacy separate pre-publish CI stop comment contract",
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
    r"CODEX_LINEAR_ISSUE_DESCRIPTION_START.{0,1400}(legacy|旧|互換|正規化).{0,1200}(新規作成しない|作成しない|追加しない|ownership|保護の根拠.*ない)",
    "initial-plan treats CODEX markers only as legacy compatibility input",
)
require_regex(
    initial_plan,
    r"HUMAN_AUTHORED_START.{0,1200}(変更しない|削除しない|保持|保護).{0,1200}HUMAN_AUTHORED_END",
    "human-authored protected content is preserved",
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
require(planning, "## 承認済みPlan", "## 参考情報")
require_regex(
    planning,
    r"canonical Plan.{0,1600}(一意|1つ|単一).{0,900}(top-level|境界|範囲)",
    "canonical plan has an explicit unique top-level range boundary",
)

# These exact instructions are the obsolete AI-managed ownership contract. If
# they survive beside the new human-protection model, ownership remains
# contradictory even when the positive vocabulary above is present.
forbid(
    initial_plan,
    "既存Descriptionを保持し、次のmarker 1組で管理領域を追加・更新します。",
    "Descriptionの対象領域だけを更新する",
)
forbid(
    planning,
    "Markerがなければ既存Descriptionを保持して末尾に1組作成します。",
)

# Architecture owns the high-level SoT model; remote remains a thin adapter.
require(architecture, "mutable phase state", "immutable")
require(remote, "canonical", "薄い", "Review semantics")

# The repository CI must execute this contract test.
require(ci, "python3 skills/implementation-loop/tests/test_linear_persistence_contract.py")

print("[PASS] Linear persistence and Description ownership contract")
