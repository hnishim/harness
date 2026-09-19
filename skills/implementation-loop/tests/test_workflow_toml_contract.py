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
    matches = []
    for item in transitions:
        if item.get("from") != source or item.get("decision") != decision:
            continue
        if item.get("test_decision") != test_decision:
            continue
        if item.get("mode") != mode:
            continue
        matches.append(item)
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
    required = set(
        require_list(
            action.get("required_capabilities"),
            f"actions.{action_name}.required_capabilities",
        )
    )
    missing = sorted(required - available)
    if missing:
        return {
            "result": action.get("on_missing_capability"),
            "missing": missing,
        }
    return {"result": "run", "missing": []}


def evaluate_invalidations(
    invalidation: dict[str, Any],
    changed_sources: set[str],
) -> set[str]:
    invalidated: set[str] = set()
    for source in changed_sources:
        rule = require_mapping(
            invalidation.get(source),
            f"invalidation.{source}",
        )
        invalidated.update(
            require_list(
                rule.get("invalidates"),
                f"invalidation.{source}.invalidates",
            )
        )
    return invalidated


def evaluate_migration(
    migration: dict[str, Any],
    *,
    migration_ids: list[str],
    source_snapshot_matches: bool,
    origin_known: bool,
    duplicate_state: bool = False,
    binding_conflict: bool = False,
    complete: bool = False,
) -> str:
    block_on = set(require_list(migration.get("block_on"), "migration.block_on"))

    conditions = {
        "multiple_migration_ids": len(set(migration_ids)) > 1,
        "unknown_origin": not origin_known,
        "source_snapshot_mismatch": not source_snapshot_matches,
        "duplicate_state": duplicate_state,
        "binding_conflict": binding_conflict,
    }
    if any(conditions.get(name, False) for name in block_on):
        return "BLOCKED"
    if complete:
        return "new_source_of_truth"
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
        fail("spike_result binding must require the current result to match the reviewed result")
    if current_result_hash != reviewed_result_hash:
        return "BLOCKED"
    if review_decision != "DECISION_READY":
        return "BLOCKED"
    return "close_allowed"


def evaluate_remote_checkpoint(
    safety: dict[str, Any],
    *,
    candidate_ref_present: bool,
    force: bool,
    pre_write_readback: bool,
    post_write_readback: bool,
    target_is_default: bool,
    acceptance_complete: bool,
) -> str:
    if safety.get("candidate_ref_required") and not candidate_ref_present:
        return "BLOCKED"
    if safety.get("force_update_allowed") is False and force:
        return "BLOCKED"
    if safety.get("pre_write_readback_required") and not pre_write_readback:
        return "BLOCKED"
    if safety.get("post_write_readback_required") and not post_write_readback:
        return "BLOCKED"
    if (
        safety.get("default_branch_update_before_acceptance") is False
        and target_is_default
        and not acceptance_complete
    ):
        return "BLOCKED"
    return "checkpoint_allowed"


def evaluate_remote_publish(
    safety: dict[str, Any],
    *,
    candidate_sha: str,
    publish_sha: str,
    target_is_ancestor: bool,
    allowed_commit_sequence_matches: bool,
    initial_write_failed: bool,
    readback_target_sha: str,
    target_sha_before_write: str,
    origin_unchanged: bool,
    diverged: bool,
    retry_count: int,
) -> str:
    if safety.get("publish_preserves_candidate_sha") and publish_sha != candidate_sha:
        return "BLOCKED"
    if safety.get("publish_requires_target_ancestor") and not target_is_ancestor:
        return "BLOCKED"
    if safety.get("publish_requires_allowed_commit_sequence") and not allowed_commit_sequence_matches:
        return "BLOCKED"
    if diverged and safety.get("on_diverged") == "BLOCKED":
        return "BLOCKED"
    if not initial_write_failed:
        return "published"
    if safety.get("publish_readback_before_retry") is not True:
        return "BLOCKED"
    if readback_target_sha == candidate_sha:
        return "published"
    if readback_target_sha != target_sha_before_write:
        return "BLOCKED"
    if not origin_unchanged:
        return "BLOCKED"
    retry_limit = safety.get("publish_retry_limit")
    if not isinstance(retry_limit, int):
        fail("remote publish_retry_limit must be an integer")
    if retry_count < retry_limit:
        return "retry_same_non_force_operation"
    return "handoff"


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
        reason = {
            "ahead": "local_ahead",
            "diverged": "diverged",
        }.get(relation, "comparison_failed")
        return {"outcome": "skipped", "reason": reason}
    if (
        target_checked_out_elsewhere
        and safety.get("skip_if_checked_out_in_other_worktree") is True
    ):
        return {"outcome": "skipped", "reason": "checked_out_in_other_worktree"}
    if (
        target_checked_out_here
        and safety.get("clean_worktree_required_when_checked_out") is True
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


assert WORKFLOW_PATH.is_file(), "workflow.toml must be the canonical mechanical workflow contract"
data = tomllib.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))

schema_version = data.get("schema_version")
assert isinstance(schema_version, int) and schema_version >= 1, "schema_version must be a positive integer"

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
    "Backlog",
    "Todo",
    "In Plan Review",
    "Test Implementation",
    "In Test Review",
    "Implementation",
    "In Implementation Review",
    "Awaiting Acceptance",
}
routed_statuses = {r.get("status") for r in routes if isinstance(r, dict)}
missing_statuses = required_statuses - routed_statuses
assert not missing_statuses, f"missing status routes: {sorted(missing_statuses)}"

assert {"local", "remote"} <= set(git_backends), "local and remote Git backends must be modeled under one workflow"
for backend in ("local", "remote"):
    backend_cfg = require_mapping(git_backends[backend], f"git_backends.{backend}")
    assert backend_cfg.get("workflow") == "implementation-loop", (
        f"{backend} backend must point to the canonical implementation-loop"
    )

remote_backend = require_mapping(git_backends["remote"], "git_backends.remote")
remote_safety = require_mapping(remote_backend.get("safety"), "git_backends.remote.safety")
expected_remote_safety = {
    "candidate_ref_required": True,
    "force_update_allowed": False,
    "pre_write_readback_required": True,
    "post_write_readback_required": True,
    "default_branch_update_before_acceptance": False,
    "publish_preserves_candidate_sha": True,
    "publish_requires_target_ancestor": True,
    "publish_requires_allowed_commit_sequence": True,
    "publish_readback_before_retry": True,
    "publish_retry_limit": 1,
    "on_diverged": "BLOCKED",
}
for key, expected in expected_remote_safety.items():
    assert remote_safety.get(key) == expected, (
        f"remote Git safety contract {key!r} must be {expected!r}"
    )

local_backend = require_mapping(git_backends["local"], "git_backends.local")
local_post_close_sync = require_mapping(
    local_backend.get("post_close_sync"),
    "git_backends.local.post_close_sync",
)
expected_local_post_close_sync = {
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
}
for key, expected in expected_local_post_close_sync.items():
    assert local_post_close_sync.get(key) == expected, (
        f"local post-close sync contract {key!r} must be {expected!r}"
    )
assert set(
    require_list(
        local_post_close_sync.get("outcomes"),
        "git_backends.local.post_close_sync.outcomes",
    )
) == {"synced", "already_synced", "skipped", "not_applicable"}
assert {
    "outcome",
    "reason",
    "target_ref",
    "local_sha",
    "remote_sha",
} <= set(
    require_list(
        local_post_close_sync.get("record_fields"),
        "git_backends.local.post_close_sync.record_fields",
    )
)
assert "post_close_sync" not in remote_backend, (
    "remote Git backend must not require local post-close synchronization"
)

for action_name in ("plan_review", "test_review", "implementation_review", "spike_result_review"):
    cfg = require_mapping(actions.get(action_name), f"actions.{action_name}")
    required = set(require_list(cfg.get("required_capabilities"), f"actions.{action_name}.required_capabilities"))
    assert "independent_reviewer" in required, f"{action_name} must require an independent reviewer"
    assert cfg.get("on_missing_capability") == "stay", (
        f"{action_name} must preserve the current Linear status when reviewer capability is unavailable"
    )

strict = require_mapping(profiles.get("strict"), "profiles.strict")
assert "strict_reviewer" in set(require_list(strict.get("required_capabilities"), "profiles.strict.required_capabilities"))

bug = require_mapping(modes.get("bug"), "modes.bug")
assert bug.get("required_test_decision") == "Test required", "Bug mode must remain Test required"

assert find_transition(
    transitions,
    source="In Plan Review",
    decision="APPROVE",
    test_decision="Test required",
)["to"] == "Test Implementation"
assert find_transition(
    transitions,
    source="In Plan Review",
    decision="APPROVE",
    test_decision="Test not required",
)["to"] == "Implementation"
assert find_transition(
    transitions,
    source="In Plan Review",
    decision="CHANGES_REQUIRED",
)["to"] == "Todo"
assert find_transition(
    transitions,
    source="In Test Review",
    decision="TESTS_APPROVED",
)["to"] == "Implementation"
assert find_transition(
    transitions,
    source="In Test Review",
    decision="TESTS_CHANGES_REQUIRED",
)["to"] == "Test Implementation"
assert find_transition(
    transitions,
    source="In Test Review",
    decision="PLAN_INCOMPLETE",
)["to"] == "Todo"
assert find_transition(
    transitions,
    source="Implementation",
    decision="IMPLEMENTATION_COMPLETE",
    test_decision="Test required",
)["to"] == "Awaiting Acceptance"
assert find_transition(
    transitions,
    source="Implementation",
    decision="IMPLEMENTATION_COMPLETE",
    test_decision="Test not required",
)["to"] == "In Implementation Review"
assert find_transition(
    transitions,
    source="In Implementation Review",
    decision="APPROVE",
    mode="normal",
)["to"] == "Awaiting Acceptance"

for name in ("plan", "approval", "delivery", "result"):
    cfg = require_mapping(state_artifacts.get(name), f"state_artifacts.{name}")
    assert cfg.get("multiplicity") == "one", f"{name} must be a singleton mutable artifact/state"
assert state_artifacts["result"].get("modes") == ["spike"], "result artifact must be Spike-only"

plan_binding = require_mapping(bindings.get("plan"), "bindings.plan")
assert {"comment_id", "current_hash", "approved_hash", "decision"} <= set(
    require_list(plan_binding.get("fields"), "bindings.plan.fields")
)

tests_binding = require_mapping(bindings.get("tests"), "bindings.tests")
tests_fields = set(require_list(tests_binding.get("manifest_fields"), "bindings.tests.manifest_fields"))
assert {
    "paths",
    "content_sha256",
    "manifest_hash",
    "rerun_command",
    "manual_checks",
    "unverified",
    "test_lifetimes",
} <= tests_fields, "approved_tests_manifest must fully identify the approved test set"

lifetime_record = require_mapping(
    tests_binding.get("lifetime_record"),
    "bindings.tests.lifetime_record",
)
assert set(
    require_list(
        lifetime_record.get("classifications"),
        "bindings.tests.lifetime_record.classifications",
    )
) == {"transitional", "permanent_regression"}
assert {
    "test_id",
    "classification",
    "end_condition",
    "retention_reason",
} <= set(
    require_list(
        lifetime_record.get("fields"),
        "bindings.tests.lifetime_record.fields",
    )
), "test lifetime records must identify each test and preserve its lifecycle rationale"

candidate_binding = require_mapping(bindings.get("candidate"), "bindings.candidate")
assert {"baseline_sha", "candidate_sha", "candidate_ref"} <= set(
    require_list(candidate_binding.get("fields"), "bindings.candidate.fields")
)

acceptance_binding = require_mapping(bindings.get("acceptance"), "bindings.acceptance")
assert {"candidate_sha", "local_acceptance", "human_acceptance"} <= set(
    require_list(acceptance_binding.get("fields"), "bindings.acceptance.fields")
)

spike_binding = require_mapping(bindings.get("spike_result"), "bindings.spike_result")
assert {"current_result_hash", "reviewed_result_hash", "decision"} <= set(
    require_list(spike_binding.get("fields"), "bindings.spike_result.fields")
)
assert spike_binding.get("close_requires_current_reviewed_match") is True

expected_invalidations = {
    "plan_hash": {"plan_review"},
    "approved_tests_manifest": {"test_review"},
    "candidate_sha": {"implementation_review", "local_acceptance", "human_acceptance"},
    "spike_result_hash": {"result_review"},
}
for source, expected in expected_invalidations.items():
    cfg = require_mapping(invalidation.get(source), f"invalidation.{source}")
    actual = set(require_list(cfg.get("invalidates"), f"invalidation.{source}.invalidates"))
    assert expected <= actual, f"{source} must invalidate {sorted(expected)}"

assert migration.get("schema_field") == "workflow_schema"
assert migration.get("migration_id_field") == "migration_id"
assert migration.get("complete_field") == "migration_complete"
source_fields = set(require_list(migration.get("source_snapshot_fields"), "migration.source_snapshot_fields"))
assert {"workflow_schema", "legacy_plan_hash", "legacy_state_comment_ids"} <= source_fields
assert migration.get("resume_known_partial") is True
block_on = set(require_list(migration.get("block_on"), "migration.block_on"))
assert {
    "multiple_migration_ids",
    "unknown_origin",
    "source_snapshot_mismatch",
    "duplicate_state",
    "binding_conflict",
} <= block_on

for capability_name in (
    "local_git",
    "github_read",
    "github_write",
    "independent_reviewer",
    "strict_reviewer",
    "local_acceptance",
    "ci_observation",
):
    assert capability_name in capabilities, f"missing capability: {capability_name}"

# Scenario: a missing independent reviewer keeps the review at its durable status.
capability_result = evaluate_action_capabilities(
    actions,
    "test_review",
    {"github_read", "github_write"},
)
assert capability_result["result"] == "stay"
assert capability_result["missing"] == ["independent_reviewer"]

# Scenario: the strict profile adds its reviewer capability without changing workflow semantics.
strict_required = set(require_list(strict.get("required_capabilities"), "profiles.strict.required_capabilities"))
assert "strict_reviewer" in strict_required

# Scenario: each changed binding invalidates only the approvals derived from that binding.
assert "plan_review" in evaluate_invalidations(invalidation, {"plan_hash"})
assert "test_review" in evaluate_invalidations(invalidation, {"approved_tests_manifest"})
candidate_invalidations = evaluate_invalidations(invalidation, {"candidate_sha"})
assert {"implementation_review", "local_acceptance", "human_acceptance"} <= candidate_invalidations
assert "result_review" in evaluate_invalidations(invalidation, {"spike_result_hash"})

# Scenario: a known partial migration is resumable, while ambiguous or contradictory origins block.
assert evaluate_migration(
    migration,
    migration_ids=["migration-a"],
    source_snapshot_matches=True,
    origin_known=True,
    complete=False,
) == "resume_partial"
assert evaluate_migration(
    migration,
    migration_ids=["migration-a", "migration-b"],
    source_snapshot_matches=True,
    origin_known=True,
) == "BLOCKED"
assert evaluate_migration(
    migration,
    migration_ids=["migration-a"],
    source_snapshot_matches=True,
    origin_known=False,
) == "BLOCKED"
assert evaluate_migration(
    migration,
    migration_ids=["migration-a"],
    source_snapshot_matches=False,
    origin_known=True,
) == "BLOCKED"

# Scenario: Spike close requires a DECISION_READY bound to the current result version.
assert evaluate_spike_close(
    spike_binding,
    current_result_hash="result-v2",
    reviewed_result_hash="result-v1",
    review_decision="DECISION_READY",
) == "BLOCKED"
assert evaluate_spike_close(
    spike_binding,
    current_result_hash="result-v2",
    reviewed_result_hash="result-v2",
    review_decision="DECISION_READY",
) == "close_allowed"

# Scenario: remote checkpoint keeps candidate refs non-force and protects the default branch pre-acceptance.
assert evaluate_remote_checkpoint(
    remote_safety,
    candidate_ref_present=True,
    force=False,
    pre_write_readback=True,
    post_write_readback=True,
    target_is_default=False,
    acceptance_complete=False,
) == "checkpoint_allowed"
assert evaluate_remote_checkpoint(
    remote_safety,
    candidate_ref_present=True,
    force=True,
    pre_write_readback=True,
    post_write_readback=True,
    target_is_default=False,
    acceptance_complete=False,
) == "BLOCKED"
assert evaluate_remote_checkpoint(
    remote_safety,
    candidate_ref_present=True,
    force=False,
    pre_write_readback=True,
    post_write_readback=True,
    target_is_default=True,
    acceptance_complete=False,
) == "BLOCKED"

# Scenario: remote publish preserves the accepted candidate SHA and only retries once after readback.
assert evaluate_remote_publish(
    remote_safety,
    candidate_sha="candidate",
    publish_sha="candidate",
    target_is_ancestor=True,
    allowed_commit_sequence_matches=True,
    initial_write_failed=False,
    readback_target_sha="base",
    target_sha_before_write="base",
    origin_unchanged=True,
    diverged=False,
    retry_count=0,
) == "published"
assert evaluate_remote_publish(
    remote_safety,
    candidate_sha="candidate",
    publish_sha="different",
    target_is_ancestor=True,
    allowed_commit_sequence_matches=True,
    initial_write_failed=False,
    readback_target_sha="base",
    target_sha_before_write="base",
    origin_unchanged=True,
    diverged=False,
    retry_count=0,
) == "BLOCKED"
assert evaluate_remote_publish(
    remote_safety,
    candidate_sha="candidate",
    publish_sha="candidate",
    target_is_ancestor=True,
    allowed_commit_sequence_matches=True,
    initial_write_failed=True,
    readback_target_sha="base",
    target_sha_before_write="base",
    origin_unchanged=True,
    diverged=False,
    retry_count=0,
) == "retry_same_non_force_operation"
assert evaluate_remote_publish(
    remote_safety,
    candidate_sha="candidate",
    publish_sha="candidate",
    target_is_ancestor=True,
    allowed_commit_sequence_matches=True,
    initial_write_failed=True,
    readback_target_sha="base",
    target_sha_before_write="base",
    origin_unchanged=True,
    diverged=False,
    retry_count=1,
) == "handoff"
assert evaluate_remote_publish(
    remote_safety,
    candidate_sha="candidate",
    publish_sha="candidate",
    target_is_ancestor=True,
    allowed_commit_sequence_matches=True,
    initial_write_failed=True,
    readback_target_sha="advanced",
    target_sha_before_write="base",
    origin_unchanged=True,
    diverged=True,
    retry_count=0,
) == "BLOCKED"

# Scenario: local post-close sync runs only after the close core has succeeded.
assert evaluate_local_post_close_sync(
    local_post_close_sync,
    close_core_complete=False,
    fetch_succeeded=True,
    relation="behind",
    target_checked_out_here=True,
    current_worktree_clean=True,
    target_checked_out_elsewhere=False,
    prewrite_ref_unchanged=True,
    post_readback_matches=True,
) == {"outcome": "not_run", "reason": "close_core_incomplete"}

# Scenario: same is a no-op success, and only behind refs are eligible to advance.
assert evaluate_local_post_close_sync(
    local_post_close_sync,
    close_core_complete=True,
    fetch_succeeded=True,
    relation="same",
    target_checked_out_here=True,
    current_worktree_clean=True,
    target_checked_out_elsewhere=False,
    prewrite_ref_unchanged=True,
    post_readback_matches=True,
) == {"outcome": "already_synced", "reason": "same_sha"}
assert evaluate_local_post_close_sync(
    local_post_close_sync,
    close_core_complete=True,
    fetch_succeeded=True,
    relation="behind",
    target_checked_out_here=True,
    current_worktree_clean=True,
    target_checked_out_elsewhere=False,
    prewrite_ref_unchanged=True,
    post_readback_matches=True,
) == {"outcome": "synced", "mode": "ff_only_worktree"}

# Scenario: when the target branch is not checked out, a dirty current branch is untouched.
assert evaluate_local_post_close_sync(
    local_post_close_sync,
    close_core_complete=True,
    fetch_succeeded=True,
    relation="behind",
    target_checked_out_here=False,
    current_worktree_clean=False,
    target_checked_out_elsewhere=False,
    prewrite_ref_unchanged=True,
    post_readback_matches=True,
) == {"outcome": "synced", "mode": "cas_ref_update"}

# Scenario: unsafe local states are preserved and skipped rather than rewritten.
for relation, expected_reason in (
    ("ahead", "local_ahead"),
    ("diverged", "diverged"),
    ("unknown", "comparison_failed"),
):
    assert evaluate_local_post_close_sync(
        local_post_close_sync,
        close_core_complete=True,
        fetch_succeeded=True,
        relation=relation,
        target_checked_out_here=False,
        current_worktree_clean=False,
        target_checked_out_elsewhere=False,
        prewrite_ref_unchanged=True,
        post_readback_matches=True,
    ) == {"outcome": "skipped", "reason": expected_reason}
assert evaluate_local_post_close_sync(
    local_post_close_sync,
    close_core_complete=True,
    fetch_succeeded=True,
    relation="behind",
    target_checked_out_here=True,
    current_worktree_clean=False,
    target_checked_out_elsewhere=False,
    prewrite_ref_unchanged=True,
    post_readback_matches=True,
) == {"outcome": "skipped", "reason": "dirty_target_worktree"}
assert evaluate_local_post_close_sync(
    local_post_close_sync,
    close_core_complete=True,
    fetch_succeeded=True,
    relation="behind",
    target_checked_out_here=False,
    current_worktree_clean=True,
    target_checked_out_elsewhere=True,
    prewrite_ref_unchanged=True,
    post_readback_matches=True,
) == {"outcome": "skipped", "reason": "checked_out_in_other_worktree"}

# Scenario: fetch, concurrent-update, and readback failures remain non-destructive skips.
assert evaluate_local_post_close_sync(
    local_post_close_sync,
    close_core_complete=True,
    fetch_succeeded=False,
    relation="behind",
    target_checked_out_here=False,
    current_worktree_clean=True,
    target_checked_out_elsewhere=False,
    prewrite_ref_unchanged=True,
    post_readback_matches=True,
) == {"outcome": "skipped", "reason": "fetch_failed"}
assert evaluate_local_post_close_sync(
    local_post_close_sync,
    close_core_complete=True,
    fetch_succeeded=True,
    relation="behind",
    target_checked_out_here=False,
    current_worktree_clean=True,
    target_checked_out_elsewhere=False,
    prewrite_ref_unchanged=False,
    post_readback_matches=True,
) == {"outcome": "skipped", "reason": "concurrent_ref_update"}
assert evaluate_local_post_close_sync(
    local_post_close_sync,
    close_core_complete=True,
    fetch_succeeded=True,
    relation="behind",
    target_checked_out_here=False,
    current_worktree_clean=True,
    target_checked_out_elsewhere=False,
    prewrite_ref_unchanged=True,
    post_readback_matches=False,
) == {"outcome": "skipped", "reason": "post_readback_mismatch"}

# Scenario: post-close sync is best-effort and cannot replace or block CLOSE_COMPLETE.
assert local_post_close_sync.get("blocks_close_complete") is False
assert find_transition(
    transitions,
    source="Awaiting Acceptance",
    decision="CLOSE_COMPLETE",
)["to"] == "Done"

assert not (ROOT / "skills" / "remote-implementation-loop").exists(), (
    "remote-implementation-loop must be removed after migration to the canonical implementation-loop"
)
for obsolete in (
    ROOT / "skills" / "implementation-loop" / "tests" / "test_remote_adapter_contract.py",
    ROOT / "skills" / "implementation-loop" / "tests" / "test_linear_persistence_contract.py",
):
    assert not obsolete.exists(), f"obsolete Markdown-regex contract remains: {obsolete.relative_to(ROOT)}"

architecture = (ROOT / "agent-development-workflow.md").read_text(encoding="utf-8")
for phase_state_key in (
    "state_key: plan-review",
    "state_key: test-implementation",
    "state_key: test-review",
    "state_key: implementation-completion",
    "state_key: implementation-review",
    "state_key: close",
):
    assert phase_state_key not in architecture, (
        f"architecture document still owns detailed phase-state schema: {phase_state_key}"
    )

canonical = (ROOT / "skills" / "implementation-loop" / "SKILL.md").read_text(encoding="utf-8")
assert "workflow.toml" in canonical, "implementation-loop must explicitly consume workflow.toml at runtime"
assert "remote-implementation-loop" not in canonical, "canonical workflow must not delegate semantics to a remote skill"

instructions = (ROOT / "custom-instructions" / "openai-instructions.md").read_text(encoding="utf-8")
assert "implementation-loop" in instructions
assert "remote-implementation-loop" not in instructions, (
    "OpenAI routing must use the single canonical implementation-loop entry point"
)

ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
assert "test_workflow_toml_contract.py" in ci, "CI must execute the structural/scenario workflow contract"
assert "test_issue_creation_contract.py" in ci, "CI must execute the issue creation contract"
assert "test_remote_adapter_contract.py" not in ci
assert "test_linear_persistence_contract.py" not in ci

print(
    "[PASS] workflow.toml structure, scenarios, capability gates, bindings, "
    "invalidation, migration, and remote Git safety contract"
)


# HIR-281: Close backend selection must retain its recorded origin across environments.
close_selection = require_mapping(
    git_backends.get("close_selection"), "git_backends.close_selection"
)
assert close_selection.get("origin_delivery_field") == "close_origin"
assert set(require_list(close_selection.get("origin_values"), "close_selection.origin_values")) == {
    "local_origin", "remote_only", "unknown",
}
assert close_selection.get("persist_origin_before_backend_selection") is True
assert close_selection.get("origin_evidence_required") is True
assert close_selection.get("on_unknown_origin") == "BLOCKED"
assert close_selection.get("on_local_unavailable") == "BLOCKED"
assert close_selection.get("remote_switch_requires_separate_explicit_authorization") is True
assert close_selection.get("remote_switch_authorization_delivery_field") == "remote_close_authorized"
assert close_selection.get("preserve_existing_close_and_candidate_binding_on_stop") is True
assert {
    "reason", "observed_capabilities", "stop_point", "required_local_action",
} <= set(require_list(close_selection.get("stop_record_fields"), "close_selection.stop_record_fields"))


def evaluate_close_backend_selection(
    selection: dict[str, Any],
    *,
    origin: str,
    origin_evidence: bool,
    local_git_available: bool,
    github_read_write_available: bool,
    separate_remote_authorization: bool,
) -> str:
    if origin == "unknown" or not origin_evidence:
        return selection["on_unknown_origin"]
    if origin == "local_origin":
        if local_git_available:
            return "local"
        if not separate_remote_authorization:
            return selection["on_local_unavailable"]
        if not selection["remote_switch_requires_separate_explicit_authorization"]:
            fail("local-origin remote switch must require separate authorization")
        return "remote" if github_read_write_available else "BLOCKED"
    if origin == "remote_only":
        return "remote" if github_read_write_available else "BLOCKED"
    return selection["on_unknown_origin"]


# A local-origin Close never silently falls back to GitHub on capability failure.
for local_available, github_available, authorized, expected in (
    (True, True, False, "local"),
    (True, True, True, "local"),
    (False, True, False, "BLOCKED"),
    (False, False, False, "BLOCKED"),
    (False, True, True, "remote"),
    (False, False, True, "BLOCKED"),
):
    assert evaluate_close_backend_selection(
        close_selection,
        origin="local_origin",
        origin_evidence=True,
        local_git_available=local_available,
        github_read_write_available=github_available,
        separate_remote_authorization=authorized,
    ) == expected

# Remote-only is eligible independently, but absence of a local worktree
# alone is not proof that the Close was remote-only.
assert evaluate_close_backend_selection(
    close_selection, origin="remote_only", origin_evidence=True,
    local_git_available=False, github_read_write_available=True,
    separate_remote_authorization=False,
) == "remote"
for origin in ("unknown", "remote_only", "local_origin"):
    assert evaluate_close_backend_selection(
        close_selection, origin=origin, origin_evidence=False,
        local_git_available=False, github_read_write_available=True,
        separate_remote_authorization=False,
    ) == "BLOCKED"

remote_local_origin = require_mapping(
    remote_backend.get("local_origin_close"), "git_backends.remote.local_origin_close"
)
assert remote_local_origin.get("local_sync_delivery_field") == "local_origin_close_sync"
assert remote_local_origin.get("published_sha_readback_required") is True
assert remote_local_origin.get("local_sha_readback_required") is True
assert remote_local_origin.get("same_published_sha_required") is True
assert remote_local_origin.get("pending_outcome") == "AWAIT_LOCAL_SYNC"
assert remote_local_origin.get("pending_status") == "Awaiting Acceptance"
assert remote_local_origin.get("skip_blocks_close_complete") is True
assert remote_local_origin.get("reuse_published_candidate_on_resume") is True
assert remote_local_origin.get("duplicate_publish_on_resume_allowed") is False
assert {
    "outcome", "reason", "published_target_ref", "published_sha",
    "local_sha", "required_local_action",
} <= set(require_list(
    remote_local_origin.get("record_fields"), "remote.local_origin_close.record_fields"
))


def evaluate_close_completion(
    remote_sync: dict[str, Any],
    local_sync: dict[str, Any],
    *,
    origin: str,
    backend: str,
    core_complete: bool,
    local_sync_outcome: str,
    published_sha: str,
    local_sha: str | None,
    published_readback: bool,
    local_readback: bool,
) -> str:
    if not core_complete:
        return "BLOCKED"
    if origin == "local_origin" and backend == "remote":
        if (
            local_sync_outcome not in ("synced", "already_synced")
            or not published_readback
            or not local_readback
            or local_sha != published_sha
        ):
            return remote_sync["pending_outcome"]
        return "CLOSE_COMPLETE"
    if origin == "local_origin" and backend == "local":
        if local_sync_outcome == "skipped" and local_sync["blocks_close_complete"]:
            return "BLOCKED"
        return "CLOSE_COMPLETE"
    if origin == "remote_only" and backend == "remote":
        return "CLOSE_COMPLETE"
    return "BLOCKED"


# Remote continuation of a local-origin Close cannot mark Done while the
# local ref is absent, skipped, dirty, divergent, or not read back.
for outcome, local_sha, published_readback, local_readback in (
    ("not_run", None, True, False),
    ("skipped", "old", True, True),
    ("synced", "old", True, True),
    ("synced", "published", False, True),
    ("synced", "published", True, False),
):
    assert evaluate_close_completion(
        remote_local_origin, local_post_close_sync,
        origin="local_origin", backend="remote", core_complete=True,
        local_sync_outcome=outcome, published_sha="published", local_sha=local_sha,
        published_readback=published_readback, local_readback=local_readback,
    ) == "AWAIT_LOCAL_SYNC"
for outcome in ("synced", "already_synced"):
    assert evaluate_close_completion(
        remote_local_origin, local_post_close_sync,
        origin="local_origin", backend="remote", core_complete=True,
        local_sync_outcome=outcome, published_sha="published", local_sha="published",
        published_readback=True, local_readback=True,
    ) == "CLOSE_COMPLETE"

# The HIR-277 local-backend non-destructive skip and the existing remote-only
# completion contract must remain unchanged.
assert evaluate_close_completion(
    remote_local_origin, local_post_close_sync,
    origin="local_origin", backend="local", core_complete=True,
    local_sync_outcome="skipped", published_sha="published", local_sha="old",
    published_readback=True, local_readback=False,
) == "CLOSE_COMPLETE"
assert evaluate_close_completion(
    remote_local_origin, local_post_close_sync,
    origin="remote_only", backend="remote", core_complete=True,
    local_sync_outcome="not_applicable", published_sha="published", local_sha=None,
    published_readback=True, local_readback=False,
) == "CLOSE_COMPLETE"
assert evaluate_close_completion(
    remote_local_origin, local_post_close_sync,
    origin="local_origin", backend="remote", core_complete=False,
    local_sync_outcome="synced", published_sha="published", local_sha="published",
    published_readback=True, local_readback=True,
) == "BLOCKED"

# A resumed remote Close must reuse a read-back published candidate rather
# than generating or publishing a second SHA for the same accepted candidate.
def evaluate_remote_close_resume(
    cfg: dict[str, Any], *, candidate_sha: str, published_sha: str | None,
    target_sha: str | None, readback_succeeded: bool,
) -> str:
    if published_sha is None:
        return "PUBLISH_WITH_REMOTE_SAFETY"
    if not readback_succeeded or published_sha != candidate_sha:
        return "BLOCKED"
    if target_sha == candidate_sha and cfg["reuse_published_candidate_on_resume"]:
        return "RESUME_LOCAL_SYNC"
    return "BLOCKED"


assert evaluate_remote_close_resume(
    remote_local_origin, candidate_sha="accepted", published_sha="accepted",
    target_sha="accepted", readback_succeeded=True,
) == "RESUME_LOCAL_SYNC"
for published_sha, target_sha, readback in (
    ("accepted", "different", True),
    ("different", "accepted", True),
    ("accepted", "accepted", False),
):
    assert evaluate_remote_close_resume(
        remote_local_origin, candidate_sha="accepted",
        published_sha=published_sha, target_sha=target_sha,
        readback_succeeded=readback,
    ) == "BLOCKED"
