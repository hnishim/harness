#!/usr/bin/env python3
from __future__ import annotations

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


def evaluate_phase_return(
    phase_return: dict[str, Any],
    *,
    changed_binding: str,
    source_status: str,
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
    return {
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
    }


def evaluate_migration(
    migration: dict[str, Any],
    *,
    migration_ids: list[str],
    source_snapshot_matches: bool,
    origin_known: bool,
    duplicate_state: bool = False,
    binding_conflict: bool = False,
) -> str:
    blocked = set(require_list(migration.get("block_on"), "migration.block_on"))
    conditions = {
        "multiple_migration_ids": len(set(migration_ids)) > 1,
        "unknown_origin": not origin_known,
        "source_snapshot_mismatch": not source_snapshot_matches,
        "duplicate_state": duplicate_state,
        "binding_conflict": binding_conflict,
    }
    if any(conditions.get(name, False) for name in blocked):
        return "BLOCKED"
    if migration_ids and migration.get("resume_known_partial") is True:
        return "resume_partial"
    return "start_migration"


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


def evaluate_local_post_close_sync(
    safety: dict[str, Any],
    *,
    close_core_complete: bool,
    fetch_succeeded: bool,
    relation: str,
    target_checked_out_here: bool,
    current_worktree_clean: bool,
    target_checked_out_elsewhere: bool,
    prewrite_ref_unchanged: bool,
    post_readback_matches: bool,
) -> dict[str, str]:
    if safety.get("requires_close_core_complete") and not close_core_complete:
        return {"outcome": "not_run", "reason": "close_core_incomplete"}
    if safety.get("fetch_required") and not fetch_succeeded:
        return {"outcome": "skipped", "reason": "fetch_failed"}
    if relation == "same":
        return {"outcome": "already_synced", "reason": "same_sha"}
    if relation != "behind":
        return {"outcome": "skipped", "reason": {
            "ahead": "local_ahead",
            "diverged": "diverged",
        }.get(relation, "comparison_failed")}
    if target_checked_out_elsewhere and safety.get("skip_if_checked_out_in_other_worktree"):
        return {"outcome": "skipped", "reason": "checked_out_in_other_worktree"}
    if (
        target_checked_out_here
        and safety.get("clean_worktree_required_when_checked_out")
        and not current_worktree_clean
    ):
        return {"outcome": "skipped", "reason": "dirty_target_worktree"}
    if safety.get("pre_write_compare_and_swap_required") and not prewrite_ref_unchanged:
        return {"outcome": "skipped", "reason": "concurrent_ref_update"}
    if safety.get("post_write_readback_required") and not post_readback_matches:
        return {"outcome": "skipped", "reason": "post_readback_mismatch"}
    return {
        "outcome": "synced",
        "mode": "ff_only_worktree" if target_checked_out_here else "cas_ref_update",
    }


def evaluate_close_completion(
    policy: dict[str, Any],
    *,
    candidate_sha: str,
    published_sha: str | None,
    published_readback: bool,
    non_force: bool,
    local_sync_outcome: str,
    local_sha: str | None,
    local_readback: bool,
    remote_identity: str,
    published_target_ref: str,
    expected_remote_identity: str,
    expected_target_ref: str,
    ci_state: str,
    close_instruction_valid: bool,
    candidate_is_ancestor_or_same: bool,
    historical_blocked_record: bool,
) -> str:
    if published_sha is None or candidate_sha != published_sha:
        return "BLOCKED"
    if policy.get("published_remote_field") and remote_identity != expected_remote_identity:
        return "BLOCKED"
    if policy.get("published_target_ref_field") and published_target_ref != expected_target_ref:
        return "BLOCKED"
    if policy.get("published_readback_field") and not published_readback:
        return "BLOCKED"
    if policy.get("non_force_required") and not non_force:
        return "BLOCKED"
    if policy.get("ci_success_required") and ci_state != policy.get("ci_success_value"):
        return "BLOCKED"
    if policy.get("close_instruction_required") and not close_instruction_valid:
        return "BLOCKED"
    if policy.get("candidate_ancestry_required") and not candidate_is_ancestor_or_same:
        return "BLOCKED"
    if historical_blocked_record and not policy.get("historical_blocked_non_authoritative"):
        return "BLOCKED"
    if local_sync_outcome in {"synced", "already_synced"}:
        if policy.get("local_readback_required_when_synced") and (
            local_sha != published_sha or not local_readback
        ):
            return "BLOCKED"
    if local_sync_outcome == "skipped" and not policy.get("local_sync_does_not_block_when_skipped"):
        return "BLOCKED"
    return "CLOSE_COMPLETE"


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
migration = table(data, "migration")
git_backends = table(data, "git_backends")

required_statuses = {
    "Backlog", "Todo", "In Plan Review", "Test Implementation",
    "In Test Review", "Implementation", "In Implementation Review",
    "Awaiting Acceptance",
}
assert required_statuses <= {item.get("status") for item in routes if isinstance(item, dict)}

# HIR-289: the canonical loop has one Git backend. Close does not select a
# backend from historical delivery metadata; it always requires local Git.
assert set(git_backends) == {"local"}
local_backend = require_mapping(git_backends["local"], "git_backends.local")
assert local_backend.get("workflow") == "implementation-loop"
assert local_backend.get("executor") == "local_git"
for action_name in ("test_implementation", "implementation", "close"):
    action = require_mapping(actions.get(action_name), f"actions.{action_name}")
    assert "local_git" in set(require_list(
        action.get("required_capabilities"),
        f"actions.{action_name}.required_capabilities",
    ))
    assert action.get("on_missing_capability") == "stay"

local_post_close_sync = require_mapping(
    local_backend.get("post_close_sync"),
    "git_backends.local.post_close_sync",
)
for key, expected in {
    "requires_close_core_complete": True,
    "blocks_close_complete": False,
    "fetch_required": True,
    "source_ref": "published_target_ref",
    "destination_ref": "corresponding_local_branch",
    "fast_forward_only": True,
    "force_update_allowed": False,
    "reset_hard_allowed": False,
    "auto_stash_allowed": False,
    "rebase_allowed": False,
    "branch_switch_allowed": False,
    "clean_worktree_required_when_checked_out": True,
    "skip_if_checked_out_in_other_worktree": True,
    "cas_ref_update_when_not_checked_out": True,
    "pre_write_compare_and_swap_required": True,
    "post_write_readback_required": True,
    "delivery_field": "local_post_close_sync",
}.items():
    assert local_post_close_sync.get(key) == expected, key
assert set(require_list(local_post_close_sync.get("outcomes"), "sync outcomes")) == {
    "synced", "already_synced", "skipped", "not_applicable",
}
assert {"outcome", "reason", "target_ref", "local_sha", "remote_sha"} <= set(
    require_list(local_post_close_sync.get("record_fields"), "sync record fields")
)

close_completion = require_mapping(
    local_backend.get("close_completion"),
    "git_backends.local.close_completion",
)
for key, expected in {
    "candidate_sha_field": "candidate_sha",
    "published_sha_field": "published_sha",
    "published_remote_field": "published_remote",
    "published_target_ref_field": "published_target_ref",
    "published_readback_field": "published_readback",
    "non_force_required": True,
    "ci_success_required": True,
    "ci_success_value": "success",
    "close_instruction_required": True,
    "candidate_ancestry_required": True,
    "historical_blocked_non_authoritative": True,
    "local_readback_required_when_synced": True,
    "local_sync_does_not_block_when_skipped": True,
}.items():
    assert close_completion.get(key) == expected, key

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
    },
}
for binding, expected in phase_return_cases.items():
    assert evaluate_phase_return(
        phase_return,
        changed_binding=binding,
        source_status=expected["source_status"],
    ) == {"outcome": "return", **{key: expected[key] for key in (
        "target_status", "retains", "invalidates", "required_reviews",
    )}}
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

# Capability and migration boundaries fail closed; GitHub access is not a
# substitute for local Git, and partial legacy migrations resume only when the
# source is unambiguous.
for capability_name in (
    "local_git", "github_read", "github_write", "independent_reviewer",
    "strict_reviewer", "local_acceptance", "ci_observation",
):
    assert capability_name in capabilities
assert evaluate_action_capabilities(
    actions, "test_review", {"github_read", "github_write"}
) == {"result": "stay", "missing": ["independent_reviewer"]}
for action_name in ("test_implementation", "implementation", "close"):
    assert evaluate_action_capabilities(
        actions, action_name,
        {"linear_read", "linear_write", "repository_read", "repository_write", "github_write"},
    ) == {"result": "stay", "missing": ["local_git"]}
assert evaluate_migration(
    migration, migration_ids=["migration-a"],
    source_snapshot_matches=True, origin_known=True,
) == "resume_partial"
assert evaluate_migration(
    migration, migration_ids=["migration-a", "migration-b"],
    source_snapshot_matches=True, origin_known=True,
) == "BLOCKED"
assert evaluate_migration(
    migration, migration_ids=["migration-a"],
    source_snapshot_matches=True, origin_known=False,
) == "BLOCKED"

# Spike close remains version-bound.
assert evaluate_spike_close(
    spike_binding, current_result_hash="result-v2",
    reviewed_result_hash="result-v1", review_decision="DECISION_READY",
) == "BLOCKED"
assert evaluate_spike_close(
    spike_binding, current_result_hash="result-v2",
    reviewed_result_hash="result-v2", review_decision="DECISION_READY",
) == "close_allowed"

# Post-close synchronization is best-effort and non-destructive.
assert evaluate_local_post_close_sync(
    local_post_close_sync, close_core_complete=False, fetch_succeeded=True,
    relation="behind", target_checked_out_here=True,
    current_worktree_clean=True, target_checked_out_elsewhere=False,
    prewrite_ref_unchanged=True, post_readback_matches=True,
) == {"outcome": "not_run", "reason": "close_core_incomplete"}
assert evaluate_local_post_close_sync(
    local_post_close_sync, close_core_complete=True, fetch_succeeded=True,
    relation="same", target_checked_out_here=True,
    current_worktree_clean=True, target_checked_out_elsewhere=False,
    prewrite_ref_unchanged=True, post_readback_matches=True,
) == {"outcome": "already_synced", "reason": "same_sha"}
assert evaluate_local_post_close_sync(
    local_post_close_sync, close_core_complete=True, fetch_succeeded=True,
    relation="behind", target_checked_out_here=True,
    current_worktree_clean=False, target_checked_out_elsewhere=False,
    prewrite_ref_unchanged=True, post_readback_matches=True,
) == {"outcome": "skipped", "reason": "dirty_target_worktree"}
assert evaluate_local_post_close_sync(
    local_post_close_sync, close_core_complete=True, fetch_succeeded=True,
    relation="behind", target_checked_out_here=False,
    current_worktree_clean=True, target_checked_out_elsewhere=True,
    prewrite_ref_unchanged=True, post_readback_matches=True,
) == {"outcome": "skipped", "reason": "checked_out_in_other_worktree"}
assert evaluate_close_completion(
    close_completion, candidate_sha="candidate",
    published_sha=None, published_readback=False, non_force=True,
    local_sync_outcome="skipped", local_sha=None, local_readback=False,
    remote_identity="origin", published_target_ref="refs/heads/main",
    expected_remote_identity="origin", expected_target_ref="refs/heads/main",
    ci_state="success", close_instruction_valid=True,
    candidate_is_ancestor_or_same=True, historical_blocked_record=False,
) == "BLOCKED"  # candidate ref alone is not publication evidence
assert evaluate_close_completion(
    close_completion, candidate_sha="candidate",
    published_sha="candidate", published_readback=True, non_force=True,
    local_sync_outcome="skipped", local_sha="old", local_readback=False,
    remote_identity="origin", published_target_ref="refs/heads/main",
    expected_remote_identity="origin", expected_target_ref="refs/heads/main",
    ci_state="success", close_instruction_valid=True,
    candidate_is_ancestor_or_same=True, historical_blocked_record=True,
) == "CLOSE_COMPLETE"
assert evaluate_close_completion(
    close_completion, candidate_sha="candidate",
    published_sha="candidate", published_readback=False, non_force=True,
    local_sync_outcome="skipped", local_sha="old", local_readback=False,
    remote_identity="origin", published_target_ref="refs/heads/main",
    expected_remote_identity="origin", expected_target_ref="refs/heads/main",
    ci_state="success", close_instruction_valid=True,
    candidate_is_ancestor_or_same=True, historical_blocked_record=False,
) == "BLOCKED"
assert evaluate_close_completion(
    close_completion, candidate_sha="candidate",
    published_sha="candidate", published_readback=True, non_force=False,
    local_sync_outcome="skipped", local_sha="old", local_readback=False,
    remote_identity="origin", published_target_ref="refs/heads/main",
    expected_remote_identity="origin", expected_target_ref="refs/heads/main",
    ci_state="success", close_instruction_valid=True,
    candidate_is_ancestor_or_same=True, historical_blocked_record=False,
) == "BLOCKED"
assert evaluate_close_completion(
    close_completion, candidate_sha="candidate",
    published_sha="candidate", published_readback=True, non_force=True,
    local_sync_outcome="synced", local_sha="different", local_readback=True,
    remote_identity="origin", published_target_ref="refs/heads/main",
    expected_remote_identity="origin", expected_target_ref="refs/heads/main",
    ci_state="success", close_instruction_valid=True,
    candidate_is_ancestor_or_same=True, historical_blocked_record=False,
) == "BLOCKED"
for close_case in (
    {"remote_identity": "other", "published_target_ref": "refs/heads/main", "ci_state": "success", "close_instruction_valid": True, "candidate_is_ancestor_or_same": True},
    {"remote_identity": "origin", "published_target_ref": "refs/heads/release", "ci_state": "success", "close_instruction_valid": True, "candidate_is_ancestor_or_same": True},
    {"remote_identity": "origin", "published_target_ref": "refs/heads/main", "ci_state": "pending", "close_instruction_valid": True, "candidate_is_ancestor_or_same": True},
    {"remote_identity": "origin", "published_target_ref": "refs/heads/main", "ci_state": "success", "close_instruction_valid": False, "candidate_is_ancestor_or_same": True},
    {"remote_identity": "origin", "published_target_ref": "refs/heads/main", "ci_state": "success", "close_instruction_valid": True, "candidate_is_ancestor_or_same": False},
):
    assert evaluate_close_completion(
        close_completion, candidate_sha="candidate", published_sha="candidate",
        published_readback=True, non_force=True, local_sync_outcome="skipped",
        local_sha=None, local_readback=False,
        expected_remote_identity="origin", expected_target_ref="refs/heads/main",
        historical_blocked_record=False, **close_case,
    ) == "BLOCKED"

architecture = (ROOT / "agent-development-workflow.md").read_text(encoding="utf-8")
assert "implementation-loop" in architecture
assert "remote Git backend" not in architecture
instructions = (ROOT / "custom-instructions" / "openai-instructions.md").read_text(encoding="utf-8")
assert "implementation-loop" in instructions
assert "remote-implementation-loop" not in instructions
ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
assert "test_workflow_toml_contract.py" in ci
assert "test_issue_creation_contract.py" in ci

print("[PASS] HIR-289 workflow simplification, local Git safety, binding invalidation, and close boundaries")
