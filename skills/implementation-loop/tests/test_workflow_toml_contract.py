#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
import re
import subprocess
import tempfile
import tomllib
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
WORKFLOW_PATH = ROOT / "skills" / "implementation-loop" / "workflow.toml"


def fail(message: str) -> None:
    raise AssertionError(message)


def require_mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail(f"{name} must be a TOML table")
    return value


def require_list(value: Any, name: str) -> list[Any]:
    if not isinstance(value, list):
        fail(f"{name} must be a TOML array")
    return value


def table(data: dict[str, Any], name: str) -> dict[str, Any]:
    if name not in data:
        fail(f"missing [{name}] table")
    return require_mapping(data[name], name)


def find_transition(
    transitions: list[dict[str, Any]],
    *,
    source: str,
    decision: str,
    test_decision: str | None = None,
    mode: str | None = None,
) -> dict[str, Any]:
    matches = [
        item
        for item in transitions
        if item.get("from") == source
        and item.get("decision") == decision
        and item.get("test_decision") == test_decision
        and item.get("mode") == mode
    ]
    if len(matches) != 1:
        fail(
            "expected exactly one transition for "
            f"from={source!r} decision={decision!r} "
            f"test_decision={test_decision!r} mode={mode!r}; got {len(matches)}"
        )
    return matches[0]


def evaluate_action_capabilities(
    actions: dict[str, Any],
    action_name: str,
    available: set[str],
) -> dict[str, Any]:
    action = require_mapping(actions.get(action_name), f"actions.{action_name}")
    required = set(require_list(
        action.get("required_capabilities"),
        f"actions.{action_name}.required_capabilities",
    ))
    missing = sorted(required - available)
    if missing:
        return {"result": action.get("on_missing_capability"), "missing": missing}
    return {"result": "run", "missing": []}


def evaluate_invalidations(
    invalidation: dict[str, Any],
    changed_sources: set[str],
) -> set[str]:
    result: set[str] = set()
    for source in changed_sources:
        rule = require_mapping(invalidation.get(source), f"invalidation.{source}")
        result.update(require_list(rule.get("invalidates"), f"invalidation.{source}.invalidates"))
    return result


PHASE_RETURN_INVALIDATION_PATHS = {
    "plan_review": ("approval", "plan_review_decision"),
    "test_review": ("approval", "test_review_decision"),
    "implementation_review": ("approval", "implementation_review_decision"),
    "ci": ("delivery", "ci"),
    "local_acceptance": ("delivery", "local_acceptance"),
    "human_acceptance": ("delivery", "human_acceptance"),
}


def set_nested(state: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    current = state
    for part in parts[:-1]:
        current = require_mapping(current.get(part), f"state.{part}")
    current[parts[-1]] = value


def get_nested(state: dict[str, Any], path: str) -> Any:
    current: Any = state
    for part in path.split("."):
        current = require_mapping(current, f"state.{part}").get(part)
    return current


def git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=cwd, text=True, capture_output=True, check=True
    )


def evaluate_phase_return(
    phase_return: dict[str, Any],
    *,
    changed_binding: str,
    source_status: str,
    snapshot: dict[str, Any] | None = None,
    replacements: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    rules = require_list(
        phase_return.get("binding_returns"),
        "phase_return.binding_returns",
    )
    matches = [
        require_mapping(rule, "phase_return.binding_returns[]")
        for rule in rules
        if isinstance(rule, dict) and rule.get("binding") == changed_binding
    ]
    if len(matches) != 1:
        fail(f"expected one phase-return rule for {changed_binding!r}; got {len(matches)}")
    rule = matches[0]
    source_statuses = set(require_list(
        rule.get("source_statuses"),
        f"phase_return.binding_returns.{changed_binding}.source_statuses",
    ))
    if source_status not in source_statuses:
        return {"outcome": "BLOCKED", "reason": "invalid_source_status"}
    result = {
        "outcome": "return",
        "target_status": rule.get("target_status"),
        "retains": set(require_list(
            rule.get("retains"),
            f"phase_return.binding_returns.{changed_binding}.retains",
        )),
        "invalidates": set(require_list(
            rule.get("invalidates"),
            f"phase_return.binding_returns.{changed_binding}.invalidates",
        )),
        "required_reviews": set(require_list(
            rule.get("required_reviews"),
            f"phase_return.binding_returns.{changed_binding}.required_reviews",
        )),
        "clear_fields": set(require_list(
            rule.get("clear_fields"),
            f"phase_return.binding_returns.{changed_binding}.clear_fields",
        )),
    }
    if snapshot is not None:
        state = deepcopy(snapshot)
        state["status"] = result["target_status"]
        for path in result["clear_fields"]:
            set_nested(state, path, None)
        for invalidated in result["invalidates"]:
            set_nested(state, ".".join(PHASE_RETURN_INVALIDATION_PATHS[invalidated]), None)
        for section, values in (replacements or {}).items():
            require_mapping(state.get(section), f"state.{section}").update(values)
        result["state"] = state
    return result



def evaluate_spike_close(
    spike_binding: dict[str, Any],
    *,
    current_result_hash: str,
    reviewed_result_hash: str | None,
    review_decision: str | None,
) -> str:
    if spike_binding.get("close_requires_current_reviewed_match") is not True:
        fail("Spike close must bind the current result to the reviewed result")
    if current_result_hash != reviewed_result_hash or review_decision != "DECISION_READY":
        return "BLOCKED"
    return "close_allowed"


assert WORKFLOW_PATH.is_file(), "workflow.toml must be the canonical mechanical workflow contract"
data = tomllib.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))
assert isinstance(data.get("schema_version"), int) and data["schema_version"] >= 1

routes = require_list(data.get("routes"), "routes")
transitions = require_list(data.get("transitions"), "transitions")
actions = table(data, "actions")
capabilities = table(data, "capabilities")
modes = table(data, "modes")
profiles = table(data, "profiles")
bindings = table(data, "bindings")
invalidation = table(data, "invalidation")
state_artifacts = table(data, "state_artifacts")
git_backends = table(data, "git_backends")

required_statuses = {
    "Backlog", "Todo", "In Plan Review", "Test Implementation",
    "In Test Review", "Implementation", "In Implementation Review",
    "Awaiting Acceptance",
}
assert required_statuses <= {item.get("status") for item in routes if isinstance(item, dict)}

# HIR-295: local Git remains the preferred backend, while remote-only execution
# is restored as a safe alternative rather than a second workflow entry point.
assert {"local", "remote"} <= set(git_backends)
assert "close_selection" not in git_backends
local_backend = require_mapping(git_backends["local"], "git_backends.local")
assert local_backend.get("workflow") == "implementation-loop"
assert local_backend.get("executor") == "local_git"
remote_backend = require_mapping(git_backends["remote"], "git_backends.remote")
assert remote_backend.get("workflow") == "implementation-loop"
assert remote_backend.get("executor") == "github_api"
assert remote_backend.get("reference") == "references/remote-git.md"
remote_safety = require_mapping(
    remote_backend.get("safety"), "git_backends.remote.safety"
)
for key, expected in {
    "candidate_ref_required": True,
    "force_update_allowed": False,
    "pre_write_readback_required": True,
    "post_write_readback_required": True,
    "default_branch_update_before_acceptance": False,
    "on_diverged": "BLOCKED",
}.items():
    assert remote_safety.get(key) == expected, key
assert "close_completion" not in remote_backend
assert "local_origin_close" not in remote_backend
assert not any(key.startswith("publish_") for key in remote_safety)
for action_name in ("test_implementation", "implementation"):
    action = require_mapping(actions.get(action_name), f"actions.{action_name}")
    required = set(require_list(action.get("required_capabilities"), f"{action_name}.required_capabilities"))
    assert "repository_write" in required and "local_git" not in required
# HIR-302: review routing is contract-driven, independent, read-only, and
# never creates a new conversation. Exercise the selection order as scenarios.
reviewer = table(data, "independent_reviewer")
assert reviewer.get("read_only") is True
assert reviewer.get("allow_new_thread") is False
assert reviewer.get("on_unknown_provenance") == "stay"
reviewer_selection = table(reviewer, "selection")
assert reviewer_selection.get("local") == [
    "independent_subagent", "current_if_not_creator", "stay",
]
assert reviewer_selection.get("remote") == [
    "current_if_not_creator", "stay",
]


def select_reviewer(
    environment: str,
    *,
    subagent_available: bool,
    artifact_known: bool,
    creator_known: bool,
    created_in_current_run: bool,
) -> str:
    if not artifact_known or not creator_known:
        return reviewer["on_unknown_provenance"]
    for choice in reviewer_selection[environment]:
        if choice == "independent_subagent" and subagent_available:
            return choice
        if choice == "current_if_not_creator" and not created_in_current_run:
            return choice
        if choice == "stay":
            return choice
    fail("review selection has no stopping rule")


for created_here in (True, False):
    assert select_reviewer(
        "local", subagent_available=True, artifact_known=True,
        creator_known=True, created_in_current_run=created_here,
    ) == "independent_subagent"
assert select_reviewer(
    "local", subagent_available=False, artifact_known=True,
    creator_known=True, created_in_current_run=False,
) == "current_if_not_creator"
assert select_reviewer(
    "local", subagent_available=False, artifact_known=True,
    creator_known=True, created_in_current_run=True,
) == "stay"
assert select_reviewer(
    "remote", subagent_available=False, artifact_known=True,
    creator_known=True, created_in_current_run=False,
) == "current_if_not_creator"
assert select_reviewer(
    "remote", subagent_available=False, artifact_known=True,
    creator_known=True, created_in_current_run=True,
) == "stay"
# Even an accidentally exposed subagent capability does not trigger remote spawn.
assert select_reviewer(
    "remote", subagent_available=True, artifact_known=True,
    creator_known=True, created_in_current_run=True,
) == "stay"
for environment in ("local", "remote"):
    for artifact_known, creator_known in ((False, True), (True, False)):
        assert select_reviewer(
            environment, subagent_available=True, artifact_known=artifact_known,
            creator_known=creator_known, created_in_current_run=False,
        ) == "stay"
assert "strict_reviewer" in set(require_list(
    table(profiles, "strict").get("required_capabilities"), "strict capabilities",
))

# Independent review remains a real gate where the normal workflow requires it.
for action_name in ("plan_review", "test_review", "implementation_review", "spike_result_review"):
    action = require_mapping(actions.get(action_name), f"actions.{action_name}")
    assert "independent_reviewer" in set(require_list(
        action.get("required_capabilities"),
        f"actions.{action_name}.required_capabilities",
    ))
    assert action.get("on_missing_capability") == "stay"
strict = table(profiles, "strict")
assert "strict_reviewer" in set(require_list(strict.get("required_capabilities"), "strict capabilities"))
assert table(modes, "bug").get("required_test_decision") == "Test required"

# Normal and review transitions remain explicit, without a second return graph.
assert find_transition(
    transitions, source="In Plan Review", decision="APPROVE",
    test_decision="Test required",
)["to"] == "Test Implementation"
assert find_transition(
    transitions, source="In Plan Review", decision="APPROVE",
    test_decision="Test not required",
)["to"] == "Implementation"

# HIR-331: transition-local continuation flags are removed. The durable
# final next actor decides ordinary stop/continue behavior instead.
assert all(
    "continue_in_same_run" not in transition
    for transition in transitions
    if isinstance(transition, dict)
)


def transition_target(
    *,
    source: str,
    decision: str,
    test_decision: str | None = None,
    mode: str | None = None,
) -> str:
    return find_transition(
        transitions,
        source=source,
        decision=decision,
        test_decision=test_decision,
        mode=mode,
    )["to"]


plan_review_cases = {
    "Test required": "Test Implementation",
    "Test not required": "Implementation",
}
routes_by_status = {
    item["status"]: item["action"]
    for item in routes
    if isinstance(item, dict) and "status" in item and "action" in item
}
for test_decision, next_status in plan_review_cases.items():
    assert transition_target(
        source="In Plan Review",
        decision="APPROVE",
        test_decision=test_decision,
    ) == next_status
    assert routes_by_status[next_status] == {
        "Test Implementation": "test_implementation",
        "Implementation": "implementation",
    }[next_status]

assert transition_target(
    source="In Test Review",
    decision="TESTS_APPROVED",
) == "Implementation"

# The execution contract must apply the transition policy after durable Linear
# persistence/readback, and Planning must delegate both target Status and
# continuation policy to workflow.toml rather than duplicating the table.
skill_contract = (
    ROOT / "skills" / "implementation-loop" / "SKILL.md"
).read_text(encoding="utf-8")
planning_contract = (
    ROOT / "skills" / "implementation-loop" / "references" / "planning.md"
).read_text(encoding="utf-8")
architecture_contract = (
    ROOT / "agent-development-workflow.md"
).read_text(encoding="utf-8")

# HIR-276: the retired legacy-Issue migration contract must not return.
# This deliberately does not ban a future, differently designed [migration]
# table; it detects only the retired source-snapshot/resume signature and
# the old delayed-migration instructions.
legacy_migration = data.get("migration")
if isinstance(legacy_migration, dict):
    legacy_snapshot_fields = set(legacy_migration.get("source_snapshot_fields", []))
    retired_legacy_signature = (
        {"legacy_plan_hash", "legacy_state_comment_ids"} <= legacy_snapshot_fields
        and legacy_migration.get("resume_known_partial") is True
    )
    assert not retired_legacy_signature
assert "## 旧形式のIssueを再開時に移行する" not in skill_contract
stop_contract = skill_contract.split("## 停止条件", 1)[1]
assert "- Migration矛盾" not in stop_contract
assert "continue_in_same_run" not in skill_contract
assert "readback" in skill_contract.lower()
assert "continue_in_same_run" not in planning_contract
assert "workflow.toml" in planning_contract
assert re.search(r"next actor|Assignee", skill_contract, re.IGNORECASE)
assert re.search(r"next actor|Assignee", planning_contract, re.IGNORECASE)

# The durable stop is a human design-confirmation boundary, so the contract
# must surface the decisions made during Planning before the run ends.
assert "設計判断の要点" in skill_contract
assert "Plan Review" in skill_contract
assert "Planning開始時" in skill_contract
assert re.search(
    r"readback.*設計判断の要点.*(?:停止|終了|次回)",
    skill_contract,
    re.DOTALL | re.IGNORECASE,
)
assert "設計判断の要点" in planning_contract
for required_summary_element in (
    "Planning開始時",
    "根拠",
    "代替案",
    "Test decision",
    "次Status",
):
    assert required_summary_element in planning_contract
assert re.search(
    r"(?:作業項目|作業.*要約).*補助",
    planning_contract,
    re.DOTALL,
)
# The user-facing stop summary must be understandable without decoding
# workflow-internal identifiers or field names.
for contract in (skill_contract, planning_contract):
    assert "人間に分かりやすい言葉" in contract
    assert re.search(
        r"(?:内部|workflow).*(?:Status|field|hash|識別子).*(?:羅列|だけ|済ませ)",
        contract,
        re.DOTALL | re.IGNORECASE,
    )
assert "Plan Review" in architecture_contract
assert re.search(r"人間.*(?:確認|指示).*待", architecture_contract)
assert "continue_in_same_run" not in architecture_contract


# HIR-331: Assignee remains the durable next-actor signal, but ordinary
# execution stopping is derived from the final durable next actor. Only
# Plan Review keeps a separate human confirmation boundary.
next_actor = table(data, "next_actor")
assert next_actor.get("semantics") == "next_action_capable_actor"
assert next_actor.get("agent") == "nishimiyahirotaka.agent@gmail.com"
assert next_actor.get("human") == "Hiro Nishimiya"
assert next_actor.get("human_wait_actor") == "human"
assert next_actor.get("agent_continue_actor") == "agent"
assert next_actor.get("awaiting_acceptance_actor") == "human"
assert next_actor.get("local_trigger_actor") == "human"
assert next_actor.get("local_agent_continue_actor") == "agent"
assert next_actor.get("durable_stop_actor") == "human"
assert next_actor.get("on_assignee_mismatch") == "BLOCKED"
assert set(require_list(
    next_actor.get("terminal_unassigned"), "next_actor.terminal_unassigned"
)) == {"Done", "Canceled"}

review_confirmation = table(next_actor, "review_confirmation")
assert set(require_list(
    review_confirmation.get("actions"), "next_actor.review_confirmation.actions"
)) == {"plan_review"}
assert review_confirmation.get("transition_requires_human_confirmation") is True
assert review_confirmation.get("reviewer_decision_actor") == "human"
assert review_confirmation.get("confirmed_transition_actor") == "agent"

subscription = table(next_actor, "subscription")
assert subscription.get("method") == "assignee_bootstrap"
assert require_list(
    subscription.get("bootstrap_sequence"), "next_actor.subscription.bootstrap_sequence"
) == ["human", "next_actor"]
assert subscription.get("state_field") == "subscription_bootstrapped"
assert set(require_list(
    subscription.get("entry_points"), "next_actor.subscription.entry_points"
)) == {"create_issue", "implementation_loop"}


def hir331_expected_actor(
    *,
    status: str,
    human_wait: bool = False,
    local_trigger_required: bool = False,
) -> str | None:
    if status in set(require_list(
        next_actor.get("terminal_unassigned"), "next_actor.terminal_unassigned"
    )):
        return None
    if status == "Awaiting Acceptance":
        return next_actor["awaiting_acceptance_actor"]
    if human_wait or local_trigger_required:
        return next_actor["human_wait_actor"]
    return next_actor["agent_continue_actor"]


def hir331_execution_disposition(
    *,
    final_actor: str | None,
    other_stop_condition: bool = False,
) -> str:
    if final_actor is None or other_stop_condition:
        return "stop"
    if final_actor == next_actor["durable_stop_actor"]:
        return "stop"
    if final_actor == next_actor["agent_continue_actor"]:
        return "continue"
    fail(f"unknown final actor: {final_actor!r}")


assert hir331_execution_disposition(
    final_actor=hir331_expected_actor(status="Todo"),
) == "continue"
assert hir331_execution_disposition(
    final_actor=hir331_expected_actor(status="Todo", human_wait=True),
) == "stop"
assert hir331_execution_disposition(
    final_actor=hir331_expected_actor(
        status="Implementation", local_trigger_required=True,
    ),
) == "stop"
assert hir331_execution_disposition(
    final_actor=hir331_expected_actor(status="Awaiting Acceptance"),
) == "stop"
assert hir331_execution_disposition(
    final_actor=hir331_expected_actor(status="Done"),
) == "stop"
assert hir331_execution_disposition(
    final_actor=hir331_expected_actor(status="Implementation"),
    other_stop_condition=True,
) == "stop"


def hir331_review_transition(
    *,
    action: str,
    source: str,
    decision: str,
    test_decision: str | None = None,
    mode: str | None = None,
    reviewer_decision_saved: bool,
    human_review_confirmed: bool = False,
) -> dict[str, Any]:
    if not reviewer_decision_saved:
        return {
            "status": source,
            "transition_applied": False,
            "final_actor": next_actor["agent_continue_actor"],
            "disposition": "stop",
        }
    gated = action in set(require_list(
        review_confirmation.get("actions"),
        "next_actor.review_confirmation.actions",
    ))
    if gated and not human_review_confirmed:
        final_actor = review_confirmation["reviewer_decision_actor"]
        return {
            "status": source,
            "transition_applied": False,
            "final_actor": final_actor,
            "disposition": hir331_execution_disposition(final_actor=final_actor),
        }

    target = transition_target(
        source=source,
        decision=decision,
        test_decision=test_decision,
        mode=mode,
    )
    final_actor = hir331_expected_actor(status=target)
    return {
        "status": target,
        "transition_applied": True,
        "final_actor": final_actor,
        "disposition": hir331_execution_disposition(final_actor=final_actor),
    }


# Plan Review alone waits for human confirmation.
assert hir331_review_transition(
    action="plan_review",
    source="In Plan Review",
    decision="APPROVE",
    test_decision="Test required",
    reviewer_decision_saved=True,
) == {
    "status": "In Plan Review",
    "transition_applied": False,
    "final_actor": "human",
    "disposition": "stop",
}
for test_decision, target in (
    ("Test required", "Test Implementation"),
    ("Test not required", "Implementation"),
):
    assert hir331_review_transition(
        action="plan_review",
        source="In Plan Review",
        decision="APPROVE",
        test_decision=test_decision,
        reviewer_decision_saved=True,
        human_review_confirmed=True,
    ) == {
        "status": target,
        "transition_applied": True,
        "final_actor": "agent",
        "disposition": "continue",
    }

# Test Review proceeds without an extra human confirmation.
assert hir331_review_transition(
    action="test_review",
    source="In Test Review",
    decision="TESTS_APPROVED",
    reviewer_decision_saved=True,
) == {
    "status": "Implementation",
    "transition_applied": True,
    "final_actor": "agent",
    "disposition": "continue",
}

# Implementation/Spike review decisions reach Awaiting Acceptance, whose
# final next actor is Human, so the run stops there without an extra gate.
for action, decision, mode in (
    ("implementation_review", "APPROVE", "normal"),
    ("spike_result_review", "DECISION_READY", "spike"),
):
    assert hir331_review_transition(
        action=action,
        source="In Implementation Review",
        decision=decision,
        mode=mode,
        reviewer_decision_saved=True,
    ) == {
        "status": "Awaiting Acceptance",
        "transition_applied": True,
        "final_actor": "human",
        "disposition": "stop",
    }

# Test-required implementation completion stops at human Acceptance.
implementation_target = transition_target(
    source="Implementation",
    decision="IMPLEMENTATION_COMPLETE",
    test_decision="Test required",
)
implementation_actor = hir331_expected_actor(status=implementation_target)
assert {
    "status": implementation_target,
    "final_actor": implementation_actor,
    "disposition": hir331_execution_disposition(final_actor=implementation_actor),
} == {
    "status": "Awaiting Acceptance",
    "final_actor": "human",
    "disposition": "stop",
}

# Acceptance failure returns to Agent-owned Implementation and can continue.
failed_acceptance_target = transition_target(
    source="Awaiting Acceptance",
    decision="ACCEPTANCE_FAILED",
)
failed_acceptance_actor = hir331_expected_actor(status=failed_acceptance_target)
assert {
    "status": failed_acceptance_target,
    "final_actor": failed_acceptance_actor,
    "disposition": hir331_execution_disposition(final_actor=failed_acceptance_actor),
} == {
    "status": "Implementation",
    "final_actor": "agent",
    "disposition": "continue",
}


def hir331_assignee_consistency(
    *, persisted_assignee: str | None, expected_actor: str | None,
) -> str:
    expected_identity = {
        "agent": next_actor["agent"],
        "human": next_actor["human"],
        None: None,
    }[expected_actor]
    if persisted_assignee == expected_identity:
        return "consistent"
    return next_actor["on_assignee_mismatch"]


assert hir331_assignee_consistency(
    persisted_assignee=next_actor["agent"], expected_actor="human",
) == "BLOCKED"
assert hir331_assignee_consistency(
    persisted_assignee=next_actor["human"], expected_actor="agent",
) == "BLOCKED"
assert hir331_assignee_consistency(
    persisted_assignee=next_actor["human"], expected_actor="human",
) == "consistent"
assert hir331_assignee_consistency(
    persisted_assignee=None, expected_actor=None,
) == "consistent"


# Subscription bootstrap may transiently assign Human, but disposition is
# evaluated only after returning to the actual final next actor.
def hir331_bootstrap_sequence(
    *, already_bootstrapped: bool, next_actor_name: str,
) -> list[str]:
    if already_bootstrapped:
        return [next_actor_name]
    sequence = require_list(
        subscription.get("bootstrap_sequence"),
        "next_actor.subscription.bootstrap_sequence",
    )
    assert sequence == ["human", "next_actor"]
    return ["human", next_actor_name]


bootstrap = hir331_bootstrap_sequence(
    already_bootstrapped=False, next_actor_name="agent",
)
assert bootstrap == ["human", "agent"]
assert hir331_execution_disposition(final_actor=bootstrap[-1]) == "continue"
assert hir331_bootstrap_sequence(
    already_bootstrapped=True, next_actor_name="agent",
) == ["agent"]

test_contract = (
    ROOT / "skills" / "implementation-loop" / "references" / "test.md"
).read_text(encoding="utf-8")
implementation_contract = (
    ROOT / "skills" / "implementation-loop" / "references" / "implementation.md"
).read_text(encoding="utf-8")
assert "同じTest Review StatusのままHuman" not in test_contract
assert "同じImplementation Review StatusのままHuman" not in implementation_contract
assert "次工程へ進んだ後も、その実行で後続作業を開始しない" not in architecture_contract

assert find_transition(
    transitions, source="In Plan Review", decision="CHANGES_REQUIRED",
)["to"] == "Todo"
assert find_transition(
    transitions, source="In Test Review", decision="TESTS_APPROVED",
)["to"] == "Implementation"
assert find_transition(
    transitions, source="In Test Review", decision="TESTS_CHANGES_REQUIRED",
)["to"] == "Test Implementation"
assert find_transition(
    transitions, source="In Test Review", decision="PLAN_INCOMPLETE",
)["to"] == "Todo"
assert find_transition(
    transitions, source="Test Implementation",
    decision="TEST_IMPLEMENTATION_COMPLETE",
)["to"] == "In Test Review"
assert find_transition(
    transitions, source="In Implementation Review", decision="CHANGES_REQUIRED",
    mode="normal",
)["to"] == "Implementation"
assert find_transition(
    transitions, source="Awaiting Acceptance", decision="ACCEPTANCE_FAILED",
)["to"] == "Implementation"
assert find_transition(
    transitions, source="Implementation", decision="IMPLEMENTATION_COMPLETE",
    test_decision="Test required",
)["to"] == "Awaiting Acceptance"
assert find_transition(
    transitions, source="Implementation", decision="IMPLEMENTATION_COMPLETE",
    test_decision="Test not required",
)["to"] == "In Implementation Review"
assert find_transition(
    transitions, source="In Implementation Review", decision="APPROVE",
    mode="normal",
)["to"] == "Awaiting Acceptance"
assert find_transition(
    transitions, source="In Implementation Review", decision="DECISION_READY",
    mode="spike",
)["to"] == "Awaiting Acceptance"
assert find_transition(
    transitions, source="Awaiting Acceptance", decision="CLOSE_COMPLETE",
)["to"] == "Done"

# The generic return rule keeps only decision, evidence, binding, and resume
# safety. Enumerated paths, impact-specific copies, and a second persistence
# protocol duplicate the normal transitions and mutable state, so they are gone.
phase_return = table(data, "phase_return")
assert phase_return.get("decision") == "PHASE_RETURN"
assert set(require_list(phase_return.get("allowed_modes"), "phase_return.allowed_modes")) == {
    "normal", "bug",
}
assert phase_return.get("review_statuses_use_existing_transitions") is True
assert phase_return.get("evidence_required") is True
assert phase_return.get("binding_consistency_required") is True
assert phase_return.get("candidate_provenance_required") is True
assert phase_return.get("revalidate_before_status") is True
assert phase_return.get("resume_preserves_candidate_history") is True
for removed in ("backward_paths", "impacts", "persistence", "on_close_started"):
    assert removed not in phase_return, f"redundant phase_return field remains: {removed}"

phase_return_cases = {
    "plan_hash": {
        "source_status": "Implementation",
        "target_status": "Todo",
        "retains": {"baseline_sha", "candidate_history"},
        "invalidates": {
            "plan_review", "test_review", "implementation_review", "ci",
            "local_acceptance", "human_acceptance",
        },
        "required_reviews": {"plan_review", "test_review_if_required"},
        "clear_fields": {
            "approval.approved_plan_hash", "approval.approved_tests_manifest_hash",
            "delivery.candidate_sha", "delivery.candidate_ref",
        },
    },
    "approved_tests_manifest": {
        "source_status": "Implementation",
        "target_status": "Test Implementation",
        "retains": {
            "baseline_sha", "candidate_history", "unaffected_implementation",
            "approved_plan",
        },
        "invalidates": {
            "test_review", "implementation_review", "ci",
            "local_acceptance", "human_acceptance",
        },
        "required_reviews": {"test_review"},
        "clear_fields": {
            "approval.approved_tests_manifest_hash", "delivery.candidate_sha",
            "delivery.candidate_ref",
        },
    },
    "candidate_sha": {
        "source_status": "Awaiting Acceptance",
        "target_status": "Implementation",
        "retains": {
            "baseline_sha", "candidate_history", "approved_plan",
            "approved_tests_manifest", "unaffected_implementation",
        },
        "invalidates": {
            "implementation_review", "ci", "local_acceptance", "human_acceptance",
        },
        "required_reviews": {"implementation_review_if_test_not_required"},
        "clear_fields": set(),
    },
}
phase_return_snapshot = {
    "status": "Implementation",
    "approval": {
        "current_plan_hash": "plan-v1",
        "current_tests_manifest_hash": "tests-v1",
        "approved_plan_hash": "plan-v1",
        "approved_tests_manifest_hash": "tests-v1",
        "plan_review_decision": "APPROVE",
        "test_review_decision": "TESTS_APPROVED",
        "implementation_review_decision": "APPROVE",
    },
    "delivery": {
        "baseline_sha": "baseline",
        "candidate_sha": "candidate-v1",
        "candidate_ref": "refs/heads/candidate-v1",
        "ci": "success",
        "local_acceptance": "PASS",
        "human_acceptance": "PASS",
    },
    "candidate": {
        "history": ["candidate-v0", "candidate-v1"],
        "unaffected_implementation": "implementation-v1",
    },
}
for binding, expected in phase_return_cases.items():
    replacements = {
        "plan_hash": {
            "approval": {"current_plan_hash": "plan-v2"},
            "delivery": {},
        },
        "approved_tests_manifest": {
            "approval": {"current_tests_manifest_hash": "tests-v2"},
            "delivery": {},
        },
        "candidate_sha": {
            "approval": {},
            "delivery": {
                "candidate_sha": "candidate-v2",
                "candidate_ref": "refs/heads/candidate-v2",
            },
        },
    }[binding]
    scenario = evaluate_phase_return(
        phase_return,
        changed_binding=binding,
        source_status=expected["source_status"],
        snapshot=phase_return_snapshot,
        replacements=replacements,
    )
    assert scenario["outcome"] == "return"
    assert scenario["target_status"] == expected["target_status"]
    assert scenario["retains"] == expected["retains"]
    assert scenario["invalidates"] == expected["invalidates"]
    assert scenario["required_reviews"] == expected["required_reviews"]
    assert scenario["clear_fields"] == expected["clear_fields"]
    assert scenario["state"]["status"] == expected["target_status"]
    assert get_nested(scenario["state"], "delivery.baseline_sha") == "baseline"
    assert get_nested(scenario["state"], "candidate.history") == [
        "candidate-v0", "candidate-v1",
    ]
    for path in expected["clear_fields"]:
        assert get_nested(scenario["state"], path) is None
    for invalidated in expected["invalidates"]:
        assert get_nested(
            scenario["state"], ".".join(PHASE_RETURN_INVALIDATION_PATHS[invalidated])
        ) is None
    if binding == "plan_hash":
        assert scenario["state"]["approval"]["current_plan_hash"] == "plan-v2"
        assert scenario["state"]["candidate"]["unaffected_implementation"] == "implementation-v1"
    elif binding == "approved_tests_manifest":
        assert scenario["state"]["approval"]["current_tests_manifest_hash"] == "tests-v2"
        assert scenario["state"]["approval"]["approved_plan_hash"] == "plan-v1"
        assert scenario["state"]["candidate"]["unaffected_implementation"] == "implementation-v1"
    else:
        assert scenario["state"]["delivery"]["candidate_sha"] == "candidate-v2"
        assert scenario["state"]["delivery"]["candidate_ref"] == "refs/heads/candidate-v2"
        assert scenario["state"]["approval"]["approved_plan_hash"] == "plan-v1"
        assert scenario["state"]["approval"]["approved_tests_manifest_hash"] == "tests-v1"
    assert evaluate_phase_return(
        phase_return,
        changed_binding=binding,
        source_status="Done",
    ) == {"outcome": "BLOCKED", "reason": "invalid_source_status"}

# Only the regular binding invalidation contract decides what must be redone.
for source, expected in {
    "plan_hash": {
        "plan_review", "test_review", "implementation_review", "ci",
        "local_acceptance", "human_acceptance",
    },
    "approved_tests_manifest": {
        "test_review", "implementation_review", "ci",
        "local_acceptance", "human_acceptance",
    },
    "candidate_sha": {"implementation_review", "local_acceptance", "human_acceptance"},
    "spike_result_hash": {"result_review"},
}.items():
    assert evaluate_invalidations(invalidation, {source}) == expected

# Test manifests and state artifacts stay singleton and fully identify the
# approved test set, including test lifetime rationale.
for name in ("plan", "approval", "delivery", "result"):
    assert table(state_artifacts, name).get("multiplicity") == "one"
assert state_artifacts["result"].get("modes") == ["spike"]
plan_binding = table(bindings, "plan")
assert {"comment_id", "current_hash", "approved_hash", "decision"} <= set(
    require_list(plan_binding.get("fields"), "plan binding fields")
)
tests_binding = table(bindings, "tests")
assert {
    "paths", "content_sha256", "manifest_hash", "rerun_command",
    "manual_checks", "unverified", "test_lifetimes",
} <= set(require_list(tests_binding.get("manifest_fields"), "test manifest fields"))
lifetime_record = table(tests_binding, "lifetime_record")
assert set(require_list(lifetime_record.get("classifications"), "test classifications")) == {
    "transitional", "permanent_regression",
}
assert {"test_id", "classification", "end_condition", "retention_reason"} <= set(
    require_list(lifetime_record.get("fields"), "test lifetime fields")
)
assert {"baseline_sha", "candidate_sha", "candidate_ref"} <= set(
    require_list(table(bindings, "candidate").get("fields"), "candidate binding fields")
)
assert {"candidate_sha", "local_acceptance", "human_acceptance"} <= set(
    require_list(table(bindings, "acceptance").get("fields"), "acceptance binding fields")
)
spike_binding = table(bindings, "spike_result")
assert {"current_result_hash", "reviewed_result_hash", "decision"} <= set(
    require_list(spike_binding.get("fields"), "spike binding fields")
)
assert spike_binding.get("close_requires_current_reviewed_match") is True

# Spike close remains version-bound.
assert evaluate_spike_close(
    spike_binding, current_result_hash="result-v2",
    reviewed_result_hash="result-v1", review_decision="DECISION_READY",
) == "BLOCKED"
assert evaluate_spike_close(
    spike_binding, current_result_hash="result-v2",
    reviewed_result_hash="result-v2", review_decision=None,
) == "BLOCKED"
assert evaluate_spike_close(
    spike_binding, current_result_hash="result-v2",
    reviewed_result_hash="result-v2", review_decision="DECISION_READY",
) == "close_allowed"

remote_git = ROOT / "skills" / "implementation-loop" / "references" / "remote-git.md"
assert remote_git.is_file()
remote_git_text = remote_git.read_text(encoding="utf-8")
for required in ("Candidate checkpoint", "candidate ref", "non-force", "readback", "default branch", "BLOCKED"):
    assert required in remote_git_text, required
assert "## Publish checkpoint" not in remote_git_text
assert "local_origin_close_sync" not in remote_git_text
safety_blocks = [block for block in re.findall(r"```toml\n([\s\S]*?)```", remote_git_text) if re.search(r"(?m)^\s*\[git_backends\.remote\.safety\]\s*$", block)]
assert len(safety_blocks) == 1
assert tomllib.loads(safety_blocks[0])["git_backends"]["remote"]["safety"] == remote_safety

ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
assert "test_workflow_toml_contract.py" in ci
assert "test_issue_creation_contract.py" in ci


# HIR-299-GIT-01: non-conflicting changes on main and the issue branch can be merged without
# changing the approved candidate or discarding the parallel main commit.
with tempfile.TemporaryDirectory() as temp:
    repo = Path(temp) / "integration"
    repo.mkdir()
    git("init", "-b", "main", cwd=repo)
    git("config", "user.name", "HIR-299 Test", cwd=repo)
    git("config", "user.email", "hir-299@example.invalid", cwd=repo)
    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    git("add", "base.txt", cwd=repo)
    git("commit", "-m", "base", cwd=repo)
    baseline = git("rev-parse", "HEAD", cwd=repo).stdout.strip()
    git("switch", "-c", "issue-299", cwd=repo)
    (repo / "issue.txt").write_text("approved issue change\n", encoding="utf-8")
    git("add", "issue.txt", cwd=repo)
    git("commit", "-m", "issue change", cwd=repo)
    candidate = git("rev-parse", "HEAD", cwd=repo).stdout.strip()
    git("switch", "main", cwd=repo)
    (repo / "parallel.txt").write_text("parallel main change\n", encoding="utf-8")
    git("add", "parallel.txt", cwd=repo)
    git("commit", "-m", "parallel issue", cwd=repo)
    concurrent_main = git("rev-parse", "HEAD", cwd=repo).stdout.strip()
    git("merge", "--no-ff", "--no-edit", "issue-299", cwd=repo)
    published = git("rev-parse", "HEAD", cwd=repo).stdout.strip()
    assert published != candidate
    assert git("merge-base", "--is-ancestor", candidate, published, cwd=repo).returncode == 0
    assert git("merge-base", "--is-ancestor", concurrent_main, published, cwd=repo).returncode == 0
    assert git("show", "HEAD:issue.txt", cwd=repo).stdout == git(
        "show", f"{candidate}:issue.txt", cwd=repo
    ).stdout
    assert git("show", "HEAD:parallel.txt", cwd=repo).stdout == "parallel main change\n"
    assert git("diff", "--name-only", baseline, candidate, cwd=repo).stdout.strip() == "issue.txt"

# HIR-299-GIT-02: a conflicting integration is not the accepted result.
# A failed non-fast-forward update must also preserve existing local state.
with tempfile.TemporaryDirectory() as temp:
    repo = Path(temp) / "conflict"
    repo.mkdir()
    git("init", "-b", "main", cwd=repo)
    git("config", "user.name", "HIR-299 Test", cwd=repo)
    git("config", "user.email", "hir-299@example.invalid", cwd=repo)
    target = repo / "shared.txt"
    target.write_text("base\n", encoding="utf-8")
    git("add", "shared.txt", cwd=repo)
    git("commit", "-m", "base", cwd=repo)
    git("switch", "-c", "issue-299", cwd=repo)
    target.write_text("candidate\n", encoding="utf-8")
    git("commit", "-am", "candidate change", cwd=repo)
    git("switch", "main", cwd=repo)
    target.write_text("other issue\n", encoding="utf-8")
    git("commit", "-am", "parallel change", cwd=repo)
    original_main = git("rev-parse", "HEAD", cwd=repo).stdout.strip()
    ff_only = subprocess.run(
        ["git", "merge", "--ff-only", "issue-299"], cwd=repo,
        capture_output=True, text=True,
    )
    assert ff_only.returncode != 0
    assert git("rev-parse", "HEAD", cwd=repo).stdout.strip() == original_main
    conflict = subprocess.run(
        ["git", "merge", "--no-ff", "--no-commit", "issue-299"], cwd=repo,
        capture_output=True, text=True,
    )
    assert conflict.returncode != 0
    assert git("rev-parse", "HEAD", cwd=repo).stdout.strip() == original_main
    git("merge", "--abort", cwd=repo)
    assert git("status", "--porcelain=v1", cwd=repo).stdout == ""
    assert target.read_text(encoding="utf-8") == "other issue\n"

# HIR-299-GIT-03: a merged issue branch cannot be deleted while another worktree uses it.
with tempfile.TemporaryDirectory() as temp:
    repo = Path(temp) / "worktree"
    repo.mkdir()
    git("init", "-b", "main", cwd=repo)
    git("config", "user.name", "HIR-299 Test", cwd=repo)
    git("config", "user.email", "hir-299@example.invalid", cwd=repo)
    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    git("add", "base.txt", cwd=repo)
    git("commit", "-m", "base", cwd=repo)
    other = Path(temp) / "other"
    git("worktree", "add", "-b", "issue-299", str(other), cwd=repo)
    (other / "issue.txt").write_text("worktree change\n", encoding="utf-8")
    git("add", "issue.txt", cwd=other)
    git("commit", "-m", "issue change", cwd=other)
    git("merge", "--ff-only", "issue-299", cwd=repo)
    original_issue = git("rev-parse", "issue-299", cwd=repo).stdout.strip()
    delete = subprocess.run(
        ["git", "branch", "-d", "issue-299"], cwd=repo,
        capture_output=True, text=True,
    )
    assert delete.returncode != 0
    assert git("rev-parse", "issue-299", cwd=repo).stdout.strip() == original_issue
    assert git("status", "--porcelain=v1", cwd=other).stdout == ""


remote_caps = {"linear_read", "linear_write", "repository_read", "repository_write", "github_read", "github_write"}

# HIR-299-CLOSE-01..05: representative close/acceptance decisions over observed
# facts. This is a test-only decision oracle, NOT a Git executor or a production
# implementation of the human/agent workflow; real PR and macOS acceptance
# remain separate manual verification boundaries.
def close_observation(
    *,
    available: set[str],
    accepted: bool = True,
    explicit_instruction: bool = True,
    candidate_matches: bool = True,
    target_known: bool = True,
    published_known: bool = True,
    published: bool = False,
    integrated_change_matches: bool = True,
    prepublish_checks_passed: bool = True,
    local_required: bool = False,
    local_sync_complete: bool = False,
    local_applied: bool = False,
    local_verified: bool = False,
    historical_blocked: bool = False,
) -> dict[str, bool | str]:
    # historical_blocked is intentionally non-authoritative: only fresh
    # observations and current bindings decide whether to resume.
    _ = historical_blocked
    capability = evaluate_action_capabilities(actions, "close", available)
    if capability["result"] != "run":
        return {"publish": False, "done": False, "local_handoff": False,
                "reason": "missing_capability"}
    if not (candidate_matches and target_known and published_known):
        return {"publish": False, "done": False, "local_handoff": False,
                "reason": "identity_or_publication_unknown"}
    if not (accepted and explicit_instruction):
        return {"publish": False, "done": False, "local_handoff": False,
                "reason": "acceptance_or_instruction_missing"}
    if not integrated_change_matches:
        return {"publish": False, "done": False, "local_handoff": False,
                "reason": "integrated_change_unverified"}
    if not published:
        return {"publish": prepublish_checks_passed, "done": False,
                "local_handoff": False,
                "reason": "ready_to_publish" if prepublish_checks_passed
                else "prepublish_verification_missing"}
    # A confirmed prior publication never triggers a second publication.
    if not local_required:
        return {"publish": False, "done": True, "local_handoff": False,
                "reason": "published_and_complete"}
    applied = local_sync_complete and local_applied and local_verified
    return {"publish": False, "done": applied, "local_handoff": not applied,
            "reason": "published_and_complete" if applied
            else "local_reflection_pending"}


def close_case(**overrides: Any) -> dict[str, bool | str]:
    # Satisfy the legacy gate solely to exercise downstream scenarios first;
    # CONTRACT-02 below separately requires removal of that local-only gate.
    return close_observation(available=remote_caps | {"local_git"}, **overrides)


# HIR-299-CLOSE-01: an unaccepted change and a candidate-only ref cannot
# publish or count as completed, even when remote Git write is available.
assert close_case(accepted=False)["reason"] == "acceptance_or_instruction_missing"
assert close_case(explicit_instruction=False)["publish"] is False
assert close_case() == {
    "publish": True, "done": False, "local_handoff": False,
    "reason": "ready_to_publish",
}
assert close_case(prepublish_checks_passed=False)["publish"] is False

# HIR-299-CLOSE-02: known publication with another integration commit is
# complete remotely only if its accepted change is accounted for and no local
# application is required. The prior stop flag does not override new readback.
published_remote = close_case(published=True, local_required=False)
assert published_remote == {
    "publish": False, "done": True, "local_handoff": False,
    "reason": "published_and_complete",
}
assert close_case(published=True, historical_blocked=True) == published_remote
assert close_observation(
    available=remote_caps - {"repository_write"}, published=True
)["reason"] == "missing_capability"

# HIR-299-CLOSE-03: if actual local reflection is required, neither an API
# publication nor an updated ref alone satisfies the usability condition.
for local_state in (
    {},
    {"local_sync_complete": True},
    {"local_sync_complete": True, "local_applied": True},
    {"local_sync_complete": False, "local_applied": True, "local_verified": True},
):
    observed = close_case(published=True, local_required=True, **local_state)
    assert observed["publish"] is False  # no duplicate publication
    assert observed["done"] is False
    assert observed["local_handoff"] is True
assert close_case(
    published=True, local_required=True, local_sync_complete=True,
    local_applied=True, local_verified=True,
) == {
    "publish": False, "done": True, "local_handoff": False,
    "reason": "published_and_complete",
}

# HIR-299-CLOSE-04: when public state or approved change correspondence
# cannot be re-established, neither publication nor Done may be inferred.
for uncertainty in (
    {"target_known": False},
    {"published_known": False},
    {"candidate_matches": False},
    {"integrated_change_matches": False},
):
    for already_published in (False, True):
        observed = close_case(published=already_published, **uncertainty)
        assert not observed["publish"] and not observed["done"]
assert close_case(published_known=False, historical_blocked=True) == close_case(
    published_known=False
)

# HIR-299-CLOSE-05: merge-created SHA alone is not a change of approved
# candidate/test manifest; materially changing those bindings invalidates
# only the existing affected approval categories.
assert evaluate_invalidations(invalidation, set()) == set()
assert evaluate_invalidations(invalidation, {"candidate_sha"}) == {
    "implementation_review", "local_acceptance", "human_acceptance",
}
assert "plan_review" not in evaluate_invalidations(
    invalidation, {"approved_tests_manifest"}
)
assert "test_review" in evaluate_invalidations(
    invalidation, {"approved_tests_manifest"}
)

# HIR-299-GIT-04: real local fetch/ff-only on a clean clone; on dirty target
# state the modeled Close decision stays pending without attempting a
# destructive reset, stash, branch switch, or update of the user's worktree.
with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    origin = root / "origin.git"
    origin.mkdir()
    git("init", "--bare", str(origin), cwd=root)
    working = root / "working"
    git("clone", str(origin), str(working), cwd=root)
    git("config", "user.name", "HIR-299 Test", cwd=working)
    git("config", "user.email", "hir-299@example.invalid", cwd=working)
    git("switch", "-c", "main", cwd=working)
    (working / "app.txt").write_text("version-1\n", encoding="utf-8")
    git("add", "app.txt", cwd=working)
    git("commit", "-m", "base", cwd=working)
    git("push", "-u", "origin", "main", cwd=working)
    local = root / "local"
    git("clone", "-b", "main", str(origin), str(local), cwd=root)
    (working / "app.txt").write_text("version-2\n", encoding="utf-8")
    git("commit", "-am", "publish", cwd=working)
    git("push", "origin", "main", cwd=working)
    remote_sha = git("rev-parse", "HEAD", cwd=working).stdout.strip()
    local_before = git("rev-parse", "HEAD", cwd=local).stdout.strip()
    assert local_before != remote_sha
    git("fetch", "origin", cwd=local)
    assert git("status", "--porcelain=v1", cwd=local).stdout == ""
    git("merge", "--ff-only", "origin/main", cwd=local)
    assert git("rev-parse", "HEAD", cwd=local).stdout.strip() == remote_sha
    assert (local / "app.txt").read_text(encoding="utf-8") == "version-2\n"
    (working / "app.txt").write_text("version-3\n", encoding="utf-8")
    git("commit", "-am", "publish newer", cwd=working)
    git("push", "origin", "main", cwd=working)
    (local / "app.txt").write_text("user modification\n", encoding="utf-8")
    (local / "untracked.txt").write_text("keep me\n", encoding="utf-8")
    local_at_start = git("rev-parse", "HEAD", cwd=local).stdout.strip()
    dirty = git("status", "--porcelain=v1", cwd=local).stdout
    assert "app.txt" in dirty and "untracked.txt" in dirty
    git("fetch", "origin", cwd=local)
    assert close_case(published=True, local_required=True,
                      local_sync_complete=False)["done"] is False
    assert git("rev-parse", "HEAD", cwd=local).stdout.strip() == local_at_start
    assert (local / "app.txt").read_text(encoding="utf-8") == "user modification\n"
    assert (local / "untracked.txt").read_text(encoding="utf-8") == "keep me\n"


# HIR-299-CONTRACT-01: common Close eligibility and no duplicate local-only state.
close_action = require_mapping(actions.get("close"), "actions.close")
assert "local_git" not in set(
    require_list(close_action.get("required_capabilities"), "close capabilities")
)
assert "git_backend" not in close_action
assert close_action.get("on_missing_capability") == "stay"
assert "close_completion" not in local_backend
assert "post_close_sync" not in local_backend


# HIR-299-CONTRACT-02: the same normal Close gate is available in either
# execution environment, while missing repository write still prevents it.
remote_caps = {"linear_read", "linear_write", "repository_read", "repository_write", "github_read", "github_write"}
for action_name in ("test_implementation", "implementation", "close"):
    assert evaluate_action_capabilities(actions, action_name, remote_caps) == {
        "result": "run", "missing": [],
    }
assert evaluate_action_capabilities(actions, "close", remote_caps | {"local_git"}) == {
    "result": "run", "missing": [],
}
assert evaluate_action_capabilities(
    actions, "close", remote_caps - {"repository_write"}
) == {"result": "stay", "missing": ["repository_write"]}
assert evaluate_action_capabilities(
    actions, "test_review", {"github_read", "github_write"}
) == {"result": "stay", "missing": ["independent_reviewer"]}
for capability_name in ("local_git", "github_read", "github_write", "independent_reviewer", "strict_reviewer", "local_acceptance", "ci_observation"):
    assert capability_name in capabilities


# HIR-299-ROUTING-01: obsolete blanket local-only and exact-SHA rules are gone.
architecture = (ROOT / "agent-development-workflow.md").read_text(encoding="utf-8")
assert "CloseはローカルGit専用" not in architecture
instructions = (ROOT / "custom-instructions" / "openai-instructions.md").read_text(encoding="utf-8")
assert "implementation-loop" in instructions and "remote-implementation-loop" not in instructions
assert "CloseではローカルGitを必須" not in instructions
assert "GitHub APIでCloseの公開は行わない" not in instructions
skill = (ROOT / "skills" / "implementation-loop" / "SKILL.md").read_text(encoding="utf-8")
assert "git_backends.remote" in skill and "remote-only" in skill
assert "Closeは常に `git_backends.local`" not in skill
close = (ROOT / "skills" / "implementation-loop" / "references" / "close.md").read_text(encoding="utf-8")
assert "Closeは常に `git_backends.local`" not in close
assert "別SHAを作るmerge/squash/rebaseは使いません" not in close


print("[PASS] Git operation scenarios and HIR-299 contract baseline checks")


# HIR-306-CLEANUP-01: normal removal of a clean, published issue worktree
# leaves the default worktree, another issue worktree, and both branches intact.
# This exercises real Git behavior, not an invented cleanup executor.
with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    repo = root / "repo"
    repo.mkdir()
    git("init", "-b", "main", cwd=repo)
    git("config", "user.name", "HIR-306 Test", cwd=repo)
    git("config", "user.email", "hir-306@example.invalid", cwd=repo)
    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    git("add", "base.txt", cwd=repo)
    git("commit", "-m", "base", cwd=repo)
    issue_tree, other_tree = root / "issue", root / "other"
    git("worktree", "add", "-b", "issue-306", str(issue_tree), cwd=repo)
    git("worktree", "add", "-b", "other-issue", str(other_tree), cwd=repo)
    (issue_tree / "change.txt").write_text("accepted\n", encoding="utf-8")
    git("add", "change.txt", cwd=issue_tree)
    git("commit", "-m", "accepted issue change", cwd=issue_tree)
    issue_sha = git("rev-parse", "HEAD", cwd=issue_tree).stdout.strip()
    git("merge", "--ff-only", "issue-306", cwd=repo)
    assert git("rev-parse", "HEAD", cwd=repo).stdout.strip() == issue_sha
    assert git("status", "--porcelain=v1", "--ignored",
               "--untracked-files=all", cwd=issue_tree).stdout == ""
    other_sha = git("rev-parse", "HEAD", cwd=other_tree).stdout.strip()
    git("worktree", "remove", str(issue_tree), cwd=repo)
    listing = git("worktree", "list", "--porcelain", cwd=repo).stdout
    assert not issue_tree.exists()
    assert str(issue_tree) not in listing
    assert str(repo) in listing and str(other_tree) in listing
    assert (repo / "change.txt").read_text(encoding="utf-8") == "accepted\n"
    assert git("rev-parse", "HEAD", cwd=other_tree).stdout.strip() == other_sha
    assert git("rev-parse", "issue-306", cwd=repo).stdout.strip() == issue_sha
    assert git("rev-parse", "other-issue", cwd=repo).stdout.strip() == other_sha

# HIR-306-CLEANUP-02: ignored files require an explicit preflight.
# In particular, ordinary "git worktree remove" is not a substitute for
# testing --ignored: Git may remove ignored files without --force.
with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    repo = root / "repo"
    repo.mkdir()
    git("init", "-b", "main", cwd=repo)
    git("config", "user.name", "HIR-306 Test", cwd=repo)
    git("config", "user.email", "hir-306@example.invalid", cwd=repo)
    (repo / ".gitignore").write_text("*.cache\n", encoding="utf-8")
    git("add", ".gitignore", cwd=repo)
    git("commit", "-m", "ignore cache", cwd=repo)
    target = root / "issue"
    git("worktree", "add", "-b", "issue-306", str(target), cwd=repo)
    ignored = target / "keep.cache"
    ignored.write_text("user data\n", encoding="utf-8")
    assert git("status", "--porcelain=v1",
               "--untracked-files=all", cwd=target).stdout == ""
    preflight = git("status", "--porcelain=v1", "--ignored",
                    "--untracked-files=all", cwd=target).stdout
    assert "!! keep.cache" in preflight
    # The documented cleanup must stop here; do not invoke Git removal.
    assert target.is_dir() and ignored.read_text(encoding="utf-8") == "user data\n"

# HIR-306-CLEANUP-03: tracked/untracked changes and locked worktrees are
# retained. Failed ordinary removals must not lead to a forceful retry.
for dirty_kind in ("tracked", "untracked", "locked"):
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        repo = root / "repo"
        repo.mkdir()
        git("init", "-b", "main", cwd=repo)
        git("config", "user.name", "HIR-306 Test", cwd=repo)
        git("config", "user.email", "hir-306@example.invalid", cwd=repo)
        (repo / "base.txt").write_text("base\n", encoding="utf-8")
        git("add", "base.txt", cwd=repo)
        git("commit", "-m", "base", cwd=repo)
        target = root / "issue"
        git("worktree", "add", "-b", "issue-306", str(target), cwd=repo)
        if dirty_kind == "tracked":
            (target / "base.txt").write_text("user edit\n", encoding="utf-8")
        elif dirty_kind == "untracked":
            (target / "user.txt").write_text("user data\n", encoding="utf-8")
        else:
            git("worktree", "lock", str(target), cwd=repo)
        before = git("worktree", "list", "--porcelain", cwd=repo).stdout
        denied = subprocess.run(["git", "worktree", "remove", str(target)],
                                cwd=repo, text=True, capture_output=True)
        assert denied.returncode != 0, dirty_kind
        assert git("worktree", "list", "--porcelain", cwd=repo).stdout == before
        assert target.is_dir() and (target / "base.txt").exists()
        assert git("rev-parse", "issue-306", cwd=repo).stdout.strip()

# HIR-306-CLEANUP-04: a clean worktree can still contain unpublished work;
# its empty status is not evidence that the issue change was integrated.
with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    repo = root / "repo"
    repo.mkdir()
    git("init", "-b", "main", cwd=repo)
    git("config", "user.name", "HIR-306 Test", cwd=repo)
    git("config", "user.email", "hir-306@example.invalid", cwd=repo)
    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    git("add", "base.txt", cwd=repo)
    git("commit", "-m", "base", cwd=repo)
    target = root / "issue"
    git("worktree", "add", "-b", "issue-306", str(target), cwd=repo)
    (target / "unpublished.txt").write_text("not in main\n", encoding="utf-8")
    git("add", "unpublished.txt", cwd=target)
    git("commit", "-m", "unpublished issue change", cwd=target)
    assert git("status", "--porcelain=v1", "--ignored",
               "--untracked-files=all", cwd=target).stdout == ""
    ancestry = subprocess.run(
        ["git", "merge-base", "--is-ancestor", "issue-306", "main"],
        cwd=repo, capture_output=True, text=True,
    )
    assert ancestry.returncode == 1
    assert target.is_dir() and not (repo / "unpublished.txt").exists()

# HIR-306-CLEANUP-05: squash publication may preserve the approved
# change without making the candidate SHA an ancestor of main. A cleanup
# gate must compare the approved delta with the publication, not SHA
# ancestry alone. This tests a real Git history, not approval provenance.
with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    repo = root / "repo"
    repo.mkdir()
    git("init", "-b", "main", cwd=repo)
    git("config", "user.name", "HIR-306 Test", cwd=repo)
    git("config", "user.email", "hir-306@example.invalid", cwd=repo)
    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    git("add", "base.txt", cwd=repo)
    git("commit", "-m", "base", cwd=repo)
    target = root / "issue"
    git("worktree", "add", "-b", "issue-306", str(target), cwd=repo)
    (target / "approved.txt").write_text("approved change\n", encoding="utf-8")
    git("add", "approved.txt", cwd=target)
    git("commit", "-m", "candidate", cwd=target)
    candidate_sha = git("rev-parse", "HEAD", cwd=target).stdout.strip()
    git("merge", "--squash", "issue-306", cwd=repo)
    git("commit", "-m", "published approved change", cwd=repo)
    published_sha = git("rev-parse", "HEAD", cwd=repo).stdout.strip()
    assert candidate_sha != published_sha
    assert subprocess.run(
        ["git", "merge-base", "--is-ancestor", "issue-306", "main"],
        cwd=repo, capture_output=True,
    ).returncode == 1
    assert git("diff", "--quiet", "issue-306", "main", cwd=repo).returncode == 0
    assert target.is_dir()  # no deletion on inferred ancestry alone


# HIR-306-DECISION-01: representative observations for the documented
# post-Close safety decision. This is a test-only decision matrix, NOT a
# production deletion executor, process-use detector, or proof of document
# compliance. CONTRACT-01 below independently checks the written workflow.
def cleanup_decision(
    *, close_complete: bool = True, local_access: bool = True,
    target_identified: bool = True, branch_matches: bool = True,
    default_tree: bool = False, other_issue: bool = False,
    published_delta_accounted: bool = True, unpublished_work: bool = False,
    worktree_clean_including_ignored: bool = True,
    locked: bool = False, in_use: bool = False, process_use_known: bool = True,
    removal_state: str = "present",
) -> str:
    if not close_complete:
        return "not_started"
    if not local_access:
        return "local_handoff"
    if not target_identified or not branch_matches or default_tree or other_issue:
        return "local_handoff"
    if removal_state == "absent":
        return "already_removed"
    if removal_state != "present":
        return "local_handoff"
    if (not published_delta_accounted or unpublished_work
            or not worktree_clean_including_ignored or locked or in_use
            or not process_use_known):
        return "local_handoff"
    return "normal_remove"


assert cleanup_decision() == "normal_remove"
assert cleanup_decision(close_complete=False) == "not_started"
assert cleanup_decision(local_access=False) == "local_handoff"
assert cleanup_decision(removal_state="absent") == "already_removed"
assert cleanup_decision(removal_state="unknown") == "local_handoff"
for cannot_remove in (
    {"target_identified": False},
    {"branch_matches": False},
    {"default_tree": True},
    {"other_issue": True},
    {"published_delta_accounted": False},
    {"unpublished_work": True},
    {"worktree_clean_including_ignored": False},
    {"locked": True},
    {"in_use": True},
    {"process_use_known": False},
):
    assert cleanup_decision(**cannot_remove) == "local_handoff", cannot_remove
# Cleanup failure/pending/remote-only cannot undo a previously verified Done,
# or re-trigger publication. Earlier Close eligibility remains authoritative.
completed_close = close_case(published=True, local_required=False)
assert completed_close["done"] is True and completed_close["publish"] is False
for pending in ({"local_access": False}, {"removal_state": "unknown"},
                {"in_use": True}):
    assert cleanup_decision(**pending) == "local_handoff"
    assert completed_close["done"] is True and completed_close["publish"] is False
assert close_case(
    published=True, local_required=True, local_sync_complete=False,
)["done"] is False  # cleanup must wait for required local reflection


# HIR-306-CONTRACT-01: inspect ONLY the post-Close cleanup subsection, not
# keyword occurrences elsewhere in close.md. Require an ordered preflight ->
# ordinary removal -> postflight, clear refusals, explicit handoff and
# independence from previously completed publication and Done.
close_contract = (ROOT / "skills" / "implementation-loop"
                  / "references" / "close.md").read_text(encoding="utf-8")
assert "## Done・作業ブランチ整理" in close_contract
done_section = close_contract.split("## Done・作業ブランチ整理", 1)[1]
assert "### Issue専用worktreeの後処理" in done_section
cleanup_section = done_section.split("### Issue専用worktreeの後処理", 1)[1]
cleanup_section = cleanup_section.split("\n## ", 1)[0]
step_tokens = ("1. 削除前", "2. 通常削除", "3. 事後確認")
step_positions = [cleanup_section.index(token) for token in step_tokens]
assert step_positions == sorted(step_positions)
preflight = cleanup_section[step_positions[0]:step_positions[1]]
removal = cleanup_section[step_positions[1]:step_positions[2]]
postflight = cleanup_section[step_positions[2]:]
for required in (
    "公開", "ローカル反映", "完了",
    "対象Issue", "専用ブランチ", "worktree", "一意",
    "git worktree list --porcelain",
    "git status --porcelain=v1 --ignored --untracked-files=all",
    "未公開", "追跡済み", "未追跡", "無視対象", "ロック",
    "承認済み差分", "祖先関係", "他プロセス",
):
    assert required in preflight, f"missing cleanup preflight: {required}"
assert re.search(r"既定worktree.*他Issue.*削除しない", preflight)
assert re.search(r"他プロセス.*確認できない.*削除しない", preflight)
assert re.search(r"未公開.*削除しない", preflight)
for required in (
    "別の作業領域", "git worktree remove", "--force", "rm -rf",
    "stash", "reset", "worktree prune", "使用しない",
    "ブランチは自動削除しない",
):
    assert required in removal, f"missing cleanup removal contract: {required}"
for required in (
    "git worktree list --porcelain", "ファイルシステム",
    "既に削除済み", "削除結果不明", "delivery",
    "最新のGit状態", "Doneを取り消さない", "再公開しない",
):
    assert required in postflight, f"missing cleanup postflight: {required}"


# HIR-332: revising a Plan must not silently remove existing user value.
# Adding a new approach and removing an existing route are separate decisions;
# loss of user-visible value requires explicit human approval.
planning_contract = (
    ROOT / "skills" / "implementation-loop" / "references" / "planning.md"
).read_text(encoding="utf-8")
for required_preservation_term in (
    "既存",
    "利用者価値",
    "利用経路",
    "外部挙動",
    "明示承認",
):
    assert required_preservation_term in planning_contract
assert re.search(
    r"(?:新しい方式|新方式).*理由.*(?:削除|置換).*しない",
    planning_contract,
    re.DOTALL,
)
assert re.search(
    r"(?:削除|置換).*明示承認.*(?:Plan ready|PLAN_READY).*しない",
    planning_contract,
    re.DOTALL | re.IGNORECASE,
)
assert re.search(
    r"(?:文言整理|実装詳細).*(?:対象外|確認.*不要|含めない)",
    planning_contract,
    re.DOTALL,
)

# Plan Review itself must detect silent loss from a revised Plan; a rule that
# exists only in the Planning section would not protect the review boundary.
assert "## Plan Review" in planning_contract
plan_review_contract = planning_contract.split("## Plan Review", 1)[1]
assert re.search(
    r"(?:改訂前|既存).*(?:利用者価値|利用経路|外部挙動).*明示承認.*(?:欠落|失われ)",
    plan_review_contract,
    re.DOTALL,
)

# HIR-341: local Planning delegates repository-aware judgment to a dedicated
# read-only Sol planner, while abnormal Implementation/Spike behavior escalates
# to a separate read-only Sol diagnostic agent without changing the status graph.
planner_path = ROOT / "agents" / "planner.toml"
diagnostic_path = ROOT / "agents" / "diagnostic.toml"
implementer_path = ROOT / "agents" / "implementer.toml"

assert planner_path.is_file(), "HIR-341 planner agent must exist"
assert diagnostic_path.is_file(), "HIR-341 diagnostic agent must exist"
assert implementer_path.is_file()

planner_agent = tomllib.loads(planner_path.read_text(encoding="utf-8"))
diagnostic_agent = tomllib.loads(diagnostic_path.read_text(encoding="utf-8"))
implementer_agent = tomllib.loads(implementer_path.read_text(encoding="utf-8"))

assert planner_agent.get("model") == "gpt-6.1-sol"
assert planner_agent.get("model_reasoning_effort") == "medium"
assert planner_agent.get("sandbox_mode") == "read-only"
assert diagnostic_agent.get("model") == "gpt-6.1-sol"
assert diagnostic_agent.get("model_reasoning_effort") == "high"
assert diagnostic_agent.get("sandbox_mode") == "read-only"
assert implementer_agent.get("model") == "gpt-6-luna"
assert implementer_agent.get("model_reasoning_effort") == "medium"

planner_instructions = planner_agent.get("developer_instructions", "")
diagnostic_instructions = diagnostic_agent.get("developer_instructions", "")
implementer_instructions = implementer_agent.get("developer_instructions", "")

# Planner owns repository-aware Plan judgment only; durable workflow state remains
# with the parent dispatcher.
for required in ("Plan", "Repository", "Test required", "Test not required"):
    assert required in planner_instructions, required
assert re.search(r"(?:read-only|編集.*しない|変更.*しない)", planner_instructions, re.IGNORECASE | re.DOTALL)
assert re.search(r"Linear.*(?:書き込|更新).*(?:しない|行わない)", planner_instructions, re.DOTALL)
assert re.search(r"(?:BLOCKED|人間判断).*(?:PLAN_READY|Plan ready).*(?:しない|返さない)", planner_instructions, re.DOTALL | re.IGNORECASE)

# Diagnostic is analysis-only and must return the evidence needed to choose the
# smallest next experiment or an existing workflow return/stop path.
for required in ("観測", "矛盾", "原因", "1〜3", "実験", "Plan"):
    assert required in diagnostic_instructions, required
assert re.search(r"(?:編集|実装|変更).*(?:しない|行わない)", diagnostic_instructions, re.DOTALL)
assert re.search(r"Linear.*(?:書き込|更新).*(?:しない|行わない)", diagnostic_instructions, re.DOTALL)

# The Luna implementer remains the normal worker. Normal issues escalate on
# repeated failed hypotheses, observation contradictions, plan-external
# workarounds, brute-force expansion, unidentified causes, or layer ambiguity.
for required in (
    "同じ原因仮説",
    "2回",
    "人間",
    "観測",
    "矛盾",
    "fallback",
    "workaround",
    "総当たり",
    "全走査",
    "原因未特定",
    "code",
    "environment",
    "observation",
):
    assert required in implementer_instructions, required
assert re.search(r"(?:Diagnostic|診断).*(?:要求|エスカレーション)", implementer_instructions, re.DOTALL | re.IGNORECASE)
for required_pattern in (
    r"テスト結果.*実機挙動.*矛盾",
    r"探索範囲.*(?:大きく|大幅).*拡張",
    r"(?:Plan|計画).*(?:外|ない).*architecture.*変更",
):
    assert re.search(required_pattern, implementer_instructions, re.DOTALL | re.IGNORECASE), required_pattern

# Spike has a deliberately narrower escalation boundary: ordinary hypothesis
# misses and single experiment failures are normal, while investigation-process
# breakdown is escalated.
spike_contract = (
    ROOT / "skills" / "implementation-loop" / "references" / "spike.md"
).read_text(encoding="utf-8")
for required in ("Diagnostic", "ループ", "観測", "矛盾", "調査範囲", "識別実験", "目的"):
    assert required in spike_contract, required
assert re.search(
    r"(?:仮説.*外れ|仮説.*失敗|実験.*失敗).*(?:だけでは|単独では).*(?:Diagnostic|診断)",
    spike_contract,
    re.DOTALL | re.IGNORECASE,
)

# Parent routing uses the same diagnostic boundary and maps its result back into
# the existing workflow rather than inventing a diagnostic state.
implementation_contract = (
    ROOT / "skills" / "implementation-loop" / "references" / "implementation.md"
).read_text(encoding="utf-8")
for required in ("Diagnostic", "phase_return", "next actor"):
    assert required in implementation_contract, required
assert re.search(
    r"(?:人間.*観測.*矛盾|fallback|workaround|総当たり|全走査)",
    implementation_contract,
    re.DOTALL | re.IGNORECASE,
)
assert re.search(
    r"(?:Plan.*維持|Planning.*戻|外部|判断不能)",
    implementation_contract,
    re.DOTALL | re.IGNORECASE,
)
for required_pattern in (
    r"テスト結果.*実機挙動.*矛盾",
    r"探索範囲.*(?:大きく|大幅).*拡張",
    r"(?:Plan|計画).*(?:外|ない).*architecture.*変更",
):
    assert re.search(required_pattern, implementation_contract, re.DOTALL | re.IGNORECASE), required_pattern

# Local Planning delegates semantic Plan construction/refinement to Planner,
# while the parent retains validation and durable Linear/state responsibilities.
planning_contract = (
    ROOT / "skills" / "implementation-loop" / "references" / "planning.md"
).read_text(encoding="utf-8")
for required in ("Planner", "local", "Linear", "Status", "Assignee", "BLOCKED"):
    assert required in planning_contract, required
assert re.search(r"Planner.*(?:作成|生成|refine|改訂)", planning_contract, re.DOTALL | re.IGNORECASE)
assert re.search(
    r"(?:local Planning|Local Planning).{0,100}(?:Plan|計画).{0,40}(?:作成|生成).{0,40}(?:必ず|常に).{0,60}Planner.{0,30}(?:委譲|委任|任せ)",
    planning_contract,
    re.DOTALL | re.IGNORECASE,
), "local Planning must always delegate Plan creation to Planner"
assert re.search(
    r"(?:local Planning|Local Planning).{0,100}(?:Plan|計画).{0,40}(?:改訂|更新|refine).{0,40}(?:必ず|常に).{0,60}Planner.{0,30}(?:委譲|委任|任せ)",
    planning_contract,
    re.DOTALL | re.IGNORECASE,
), "local Planning must always delegate Plan refinement to Planner"
assert re.search(
    r"(?:親Agent|親エージェント).{0,100}(?:Repository-aware Plan|Repository.*Plan|Plan.*Repository).{0,40}直接.{0,30}(?:作成|生成).{0,30}(?:しない|行わない|禁止)",
    planning_contract,
    re.DOTALL | re.IGNORECASE,
), "the parent must not directly create the Repository-aware Plan"
assert re.search(
    r"(?:親Agent|親エージェント).{0,100}(?:Repository-aware Plan|Repository.*Plan|Plan.*Repository).{0,40}直接.{0,30}(?:改訂|更新|refine).{0,30}(?:しない|行わない|禁止)",
    planning_contract,
    re.DOTALL | re.IGNORECASE,
), "the parent must not directly refine the Repository-aware Plan"
assert re.search(
    r"(?:親Agent|親エージェント).*(?:検証|hash|binding|Linear|Status|Assignee)",
    planning_contract,
    re.DOTALL | re.IGNORECASE,
)
assert re.search(
    r"(?:BLOCKED|人間判断).*(?:Plan ready|PLAN_READY).*(?:しない|扱わない)",
    planning_contract,
    re.DOTALL | re.IGNORECASE,
)

expected_status_graph = {
    "Backlog",
    "Todo",
    "In Plan Review",
    "Test Implementation",
    "In Test Review",
    "Implementation",
    "In Implementation Review",
    "Awaiting Acceptance",
    "Done",
}
assert {
    item["status"]
    for item in routes
    if isinstance(item, dict) and "status" in item
} == expected_status_graph
assert not any(
    "diagnostic" in item["status"].lower()
    for item in routes
    if isinstance(item, dict) and "status" in item
)
