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


def require_anchor_metadata_contract(
    text: str,
    anchor_pattern: str,
    required_patterns: list[tuple[str, str]],
    description: str,
) -> None:
    matches = list(re.finditer(anchor_pattern, text, flags=re.DOTALL))
    assert matches, f"missing metadata contract anchor: {description}"
    for match in matches:
        window = text[max(0, match.start() - 1200): match.end() + 4200]
        if all(re.search(pattern, window, flags=re.DOTALL) for pattern, _ in required_patterns):
            return
    missing = ", ".join(label for _, label in required_patterns)
    raise AssertionError(
        f"missing durable metadata near {description}: expected {missing}"
    )


def require_immutable_event_contract(text: str, event_pattern: str, description: str) -> None:
    matches = list(re.finditer(event_pattern, text, flags=re.DOTALL))
    assert matches, f"missing immutable event class: {description}"
    for match in matches:
        window = text[max(0, match.start() - 600): match.end() + 1000]
        if (
            re.search(r"(immutable event|event Comment)", window, flags=re.DOTALL)
            and re.search(r"(append|新規Comment|新規.{0,120}Comment)", window, flags=re.DOTALL)
        ):
            return
    raise AssertionError(
        f"missing immutable append contract tied to event class: {description}"
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
planning_contract = canonical + "\n" + planning

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

# Every immutable event class in the approved Plan is asserted independently.
# The helper accepts any occurrence of the class that is actually tied to the
# immutable-event + new-comment append contract; unrelated earlier mentions do
# not decide the result.
require_immutable_event_contract(
    canonical,
    r"CHANGES_REQUIRED",
    "CHANGES_REQUIRED review finding",
)
require_immutable_event_contract(
    canonical,
    r"TESTS_CHANGES_REQUIRED",
    "TESTS_CHANGES_REQUIRED review finding",
)
require_immutable_event_contract(
    canonical,
    r"PLAN_INCOMPLETE",
    "PLAN_INCOMPLETE decision",
)
require_immutable_event_contract(
    canonical,
    r"MATERIAL_DEVIATION",
    "MATERIAL_DEVIATION finding",
)
require_immutable_event_contract(
    canonical,
    r"\bBLOCKED\b",
    "concrete blocked reason",
)
require_immutable_event_contract(
    canonical,
    r"Local.{0,120}Acceptance.{0,120}FAIL",
    "Local Acceptance failure",
)
require_immutable_event_contract(
    canonical,
    r"Human.{0,120}Acceptance.{0,120}FAIL",
    "Human Acceptance failure",
)
require_immutable_event_contract(
    canonical,
    r"(?:Bug|root[- ]cause).{0,1200}(?:root[- ]cause|evidence|証拠)",
    "Bug root-cause evidence",
)
require_immutable_event_contract(
    canonical,
    r"Spike.{0,1400}(?:finding|主要.{0,120}(?:観測|結果))",
    "Spike material finding",
)
require_immutable_event_contract(
    canonical,
    r"Spike.{0,1400}Decision",
    "Spike final decision",
)
require(canonical, "全Comments", "独立", "fresh")

# Durable reconstruction requires more than the state key itself. The common
# persistence schema must retain the current values needed by a fresh executor
# to resume, review, accept, or close without replaying superseded snapshots.
require_anchor_metadata_contract(
    canonical,
    r"mutable phase state",
    [
        (r"state_key", "state key"),
        (r"Comment ID", "stable comment id"),
        (
            r"((artifact|candidate).{0,220}(SHA|hash|commit))|"
            r"((SHA|hash|commit).{0,220}(artifact|candidate))",
            "current artifact or candidate SHA/hash",
        ),
        (r"Review packet", "review packet"),
        (r"Review Result", "review result"),
        (r"(verification boundary|検証境界)", "verification boundary"),
        (r"(unverified|未検証)", "unverified boundary"),
        (r"(参照Comment ID|reference Comment ID|Comment ID.{0,220}参照)", "referenced comment id"),
    ],
    "mutable phase state schema",
)
require_anchor_metadata_contract(
    canonical,
    r"immutable event",
    [
        (r"(phase|フェーズ)", "phase"),
        (r"state_key", "state key"),
        (
            r"((artifact|candidate).{0,220}(SHA|hash|commit))|"
            r"((SHA|hash|commit).{0,220}(artifact|candidate))",
            "artifact or candidate SHA/hash",
        ),
        (r"decision", "decision"),
        (r"(finding|blocker|evidence|証拠)", "finding/blocker/evidence"),
    ],
    "immutable event schema",
)

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

# Representative lifecycle states must retain the metadata that makes the
# HIR-248/HIR-242/HIR-21 style resume paths reconstructable. Common schema
# fields may be defined in the canonical skill, but each phase still has to bind
# its state to the phase-specific durable values below.
require_anchor_metadata_contract(
    planning,
    r"state_key: plan-review",
    [
        (r"Review packet", "plan review packet"),
        (r"Review Result", "plan review result"),
        (r"(unverified|未検証)", "plan review unverified boundary"),
    ],
    "plan-review state",
)
require_anchor_metadata_contract(
    test_ref,
    r"state_key: test-implementation",
    [
        (r"(artifact|成果物|変更ファイル|path)", "test artifact"),
        (r"(SHA|hash)", "test artifact hash"),
        (r"(verification boundary|未検証|manual check)", "test verification boundary"),
    ],
    "test-implementation state",
)
require_anchor_metadata_contract(
    implementation,
    r"state_key: implementation-completion",
    [
        (r"(candidate_commit|candidate SHA|candidate)", "candidate binding"),
        (r"Acceptance", "acceptance state"),
        (r"(unverified|未検証)", "acceptance unverified boundary"),
    ],
    "implementation-completion state",
)
require_anchor_metadata_contract(
    spike,
    r"state_key: spike-result",
    [
        (r"(result|結果|evidence|観測)", "spike result evidence"),
        (r"Decision", "spike decision"),
    ],
    "spike-result state",
)
require_anchor_metadata_contract(
    close_ref,
    r"state_key: close",
    [
        (r"(accepted candidate|accepted_candidate|candidate SHA)", "accepted candidate binding"),
        (r"(Completion|Result|Acceptance).{0,1200}(Comment ID|comment_id|参照)", "prior state reference"),
        (r"(post-publish CI|final Status|最終Status)", "close-specific publication metadata"),
    ],
    "close state",
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

# Legacy CODEX markers must not remain an active ownership/edit boundary under
# different wording. These semantic negatives intentionally target normative
# old behavior while allowing migration/read-compatibility discussion.
for text, description in (
    (planning_contract, "canonical planning retains AI-managed CODEX ownership semantics"),
    (initial_plan, "initial-plan retains AI-managed CODEX ownership semantics"),
):
    forbid_regex(
        text,
        r"(?:CODEX_LINEAR_ISSUE_DESCRIPTION_(?:START|END)|CODEX.{0,120}marker)"
        r".{0,1400}(?:Agent|AI).{0,240}(?:管理領域|ownership)"
        r".{0,600}(?:として扱う|として管理する|にする|を更新する|を編集する|を変更する|を維持する)",
        description,
    )
    forbid_regex(
        text,
        r"(?:CODEX_LINEAR_ISSUE_DESCRIPTION_(?:START|END)|CODEX.{0,120}marker)"
        r".{0,1400}(?:marker内|内側|inside).{0,500}"
        r"(?:だけ|のみ)?.{0,100}(?:更新する|編集する|変更する|管理する)",
        description,
    )
    forbid_regex(
        text,
        r"(?:CODEX_LINEAR_ISSUE_DESCRIPTION_(?:START|END)|CODEX.{0,120}marker)"
        r".{0,1400}(?:marker外|外側|outside).{0,500}"
        r"(?:人間|human).{0,500}(?:領域として扱う|保護対象とみなす|ownership boundary)",
        description,
    )
    forbid_regex(
        text,
        r"(?:CODEX_LINEAR_ISSUE_DESCRIPTION_(?:START|END)|CODEX.{0,120}marker)"
        r".{0,1400}(?:新規|current|現行).{0,300}(?:ownership|管理|保護).{0,300}(?:作成する|追加する|維持する)",
        description,
    )

require_regex(
    planning_contract,
    r"HUMAN_AUTHORED.{0,1800}(変更しない|削除しない|保持|保護)|"
    r"(変更しない|削除しない|保持|保護).{0,1800}HUMAN_AUTHORED",
    "canonical planning preserves human-authored protected content",
)
require_regex(
    initial_plan,
    r"HUMAN_AUTHORED.{0,1800}(変更しない|削除しない|保持|保護)|"
    r"(変更しない|削除しない|保持|保護).{0,1800}HUMAN_AUTHORED",
    "initial-plan preserves human-authored protected content",
)
require_regex(
    planning_contract,
    r"CODEX_LINEAR_ISSUE_DESCRIPTION_START.{0,2600}"
    r"((semantic content|内容|既存テキスト).{0,900}(保持|失わ|preserv)|"
    r"(保持|失わ|preserv).{0,900}(semantic content|内容|既存テキスト))",
    "canonical planning preserves legacy semantic content while normalizing layout",
)
require_regex(
    initial_plan,
    r"CODEX_LINEAR_ISSUE_DESCRIPTION_START.{0,2600}"
    r"((semantic content|内容|既存テキスト).{0,900}(保持|失わ|preserv)|"
    r"(保持|失わ|preserv).{0,900}(semantic content|内容|既存テキスト))",
    "initial-plan preserves legacy semantic content while normalizing layout",
)
for text, description in (
    (planning_contract, "canonical planning safe-stops on malformed ownership markers"),
    (initial_plan, "initial-plan safe-stops on malformed ownership markers"),
):
    require_regex(
        text,
        r"(malformed|不正|不整合|壊れ|片側|境界.{0,160}決められない).{0,1800}BLOCKED|"
        r"BLOCKED.{0,1800}(malformed|不正|不整合|壊れ|片側|境界.{0,160}決められない)",
        description,
    )
require_regex(
    initial_plan,
    r"(Agent|AI).{0,900}(自動|automatic).{0,700}HUMAN_AUTHORED.{0,700}(付けない|付与しない|作成しない)",
    "agent-created descriptions do not automatically receive human-authored protection markers",
)
require_regex(
    planning_contract,
    r"(Agent|AI).{0,900}(自動|automatic).{0,700}HUMAN_AUTHORED.{0,700}(付けない|付与しない|作成しない)",
    "canonical planning does not automatically add human-authored protection markers",
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
