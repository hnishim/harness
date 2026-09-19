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


# HIR-284: the accepted control plane does not yet support this behavior.
# These scenario tests deliberately fail on main until Implementation-phase
# repair is implemented without changing the issue's Linear Status.
repair = table(data, "approved_test_repair")
assert repair.get("status") == "Implementation"
assert repair.get("decision") == "APPROVED_TEST_DEFECT"
assert repair.get("required_test_decision") == "Test required"
assert repair.get("stage_field") == "test_repair_stage"
assert repair.get("initial_stage") == "diagnosed"
assert repair.get("on_uncertain_diagnosis") == "BLOCKED"
assert repair.get("on_inconsistent_binding") == "BLOCKED"
assert repair.get("on_repeated_event") == "resume_existing"
assert repair.get("on_plan_change") == "normal_replan"
assert repair.get("checkpoint_scope") == "test_and_test_configuration_only"
assert repair.get("requires_new_manifest_review") is True
assert repair.get("reuse_old_ci_as_current_pass") is False
assert repair.get("allow_force_or_history_rewrite") is False
assert repair.get("default_branch_update_before_acceptance") is False
assert repair.get("on_missing_reviewer") == "stay"
assert repair.get("on_partial_write") == "readback_and_resume"
assert repair.get("review_is_read_only") is True
assert repair.get("repair_precedes_implementation_complete") is True

required_predicates = set(require_list(repair.get("requires"), "approved_test_repair.requires"))
assert required_predicates == {
    "confirmed_test_defect",
    "plan_unchanged",
    "approved_test_binding_matches",
    "candidate_provenance_known",
}
assert {
    "plan_comment_id",
    "approved_plan_hash",
    "test_decision",
    "baseline_sha",
    "candidate_ref",
    "candidate_sha",
    "allowed_checkpoint_shas",
    "implementation_changes",
} <= set(require_list(repair.get("preserves"), "approved_test_repair.preserves"))
assert "plan_review" not in set(require_list(repair.get("invalidates"), "approved_test_repair.invalidates"))
assert {
    "approved_tests_manifest",
    "test_review",
    "implementation_review",
    "local_acceptance",
    "human_acceptance",
} <= set(require_list(repair.get("invalidates"), "approved_test_repair.invalidates"))
assert {
    "repair_id",
    "original_plan_hash",
    "old_manifest_hash",
    "old_test_review_decision",
    "defect_evidence",
    "candidate_sha",
    "affected_paths",
    "approval_binding",
} <= set(require_list(repair.get("event_fields"), "approved_test_repair.event_fields"))
assert {
    "latest_issue",
    "approved_plan_hash",
    "new_approved_manifest_hash",
    "candidate_sha",
    "approved_test_content_sha256",
    "checkpoint_provenance",
} <= set(require_list(repair.get("resume_requires"), "approved_test_repair.resume_requires"))
assert repair["decision"] in set(require_list(table(data, "events").get("append_only"), "events.append_only"))

# The regular first-time Test Implementation / Test Review route is preserved.
# A repair must never be modeled by another Linear Status transition.
assert not any(
    t.get("from") == "Implementation" and t.get("decision") == repair["decision"]
    for t in transitions
)

stages = table(repair, "stages")
expected_stages = {"diagnosed", "test_changes_pending", "review_pending", "approved"}
assert expected_stages <= set(stages)
for stage in expected_stages:
    config = require_mapping(stages[stage], f"approved_test_repair.stages.{stage}")
    assert config.get("linear_status") == "Implementation"
    assert config.get("implementation_complete_allowed") is False
    assert config.get("acceptance_allowed") is False
    assert config.get("close_allowed") is False
assert stages["review_pending"].get("required_capabilities") == ["independent_reviewer"]
assert stages["review_pending"].get("on_missing_capability") == "stay"
assert "repository_write" not in stages["review_pending"]["required_capabilities"]
assert {"linear_read", "linear_write", "repository_read", "repository_write"} <= set(
    require_list(
        stages["test_changes_pending"].get("required_capabilities"),
        "approved_test_repair.stages.test_changes_pending.required_capabilities",
    )
)

repair_transitions = require_list(repair.get("transitions"), "approved_test_repair.transitions")


def repair_step(stage: str, decision: str, capabilities_available: set[str]) -> dict[str, str]:
    matches = [
        t for t in repair_transitions
        if t.get("from") == stage and t.get("decision") == decision
    ]
    assert len(matches) == 1, (stage, decision, len(matches))
    transition = require_mapping(matches[0], "approved_test_repair.transitions entry")
    assert transition.get("linear_status") == "Implementation"
    capability_stage = "review_pending" if decision == "TESTS_APPROVED" else stage
    cfg = require_mapping(stages[capability_stage], f"approved_test_repair.stages.{capability_stage}")
    missing = set(cfg.get("required_capabilities", [])) - capabilities_available
    if missing:
        return {"status": "Implementation", "stage": cfg["on_missing_capability"]}
    return {"status": transition["linear_status"], "stage": transition["to"]}


full_capabilities = {
    "linear_read", "linear_write", "repository_read", "repository_write",
    "independent_reviewer",
}
# The entire repair remains within one Implementation Status.
assert repair_step("diagnosed", "BEGIN_TEST_CHANGES", full_capabilities) == {
    "status": "Implementation", "stage": "test_changes_pending",
}
assert repair_step("test_changes_pending", "SUBMIT_TEST_REVIEW", full_capabilities) == {
    "status": "Implementation", "stage": "review_pending",
}
assert repair_step("review_pending", "TESTS_CHANGES_REQUIRED", full_capabilities) == {
    "status": "Implementation", "stage": "test_changes_pending",
}
assert repair_step("review_pending", "TESTS_APPROVED", full_capabilities) == {
    "status": "Implementation", "stage": "approved",
}
assert repair_step("approved", "RESUME_IMPLEMENTATION", full_capabilities) == {
    "status": "Implementation", "stage": "resolved",
}
assert repair_step("review_pending", "TESTS_APPROVED", full_capabilities - {"independent_reviewer"}) == {
    "status": "Implementation", "stage": "stay",
}

# Only evidence-backed test defects can enter this exception. An uncertain cause
# or altered Plan cannot be used to soften approved assertions.
def repair_diagnosis(
    *,
    status: str = "Implementation",
    test_decision: str = "Test required",
    fault: str = "approved_test",
    defect_evidence: bool = True,
    plan_unchanged: bool = True,
    approved_test_binding_matches: bool = True,
    candidate_provenance_known: bool = True,
    prior_event: bool = False,
) -> str:
    if status != repair["status"] or test_decision != repair["required_test_decision"]:
        return "BLOCKED"
    conditions = {
        "confirmed_test_defect": fault == "approved_test" and defect_evidence,
        "plan_unchanged": plan_unchanged,
        "approved_test_binding_matches": approved_test_binding_matches,
        "candidate_provenance_known": candidate_provenance_known,
    }
    if not all(conditions[predicate] for predicate in required_predicates):
        return repair["on_plan_change"] if not plan_unchanged else repair["on_uncertain_diagnosis"]
    if prior_event:
        return repair["on_repeated_event"]
    return repair["initial_stage"]


assert repair_diagnosis() == "diagnosed"
assert repair_diagnosis(prior_event=True) == "resume_existing"
for rejected in (
    {"fault": "implementation"},
    {"fault": "unknown"},
    {"defect_evidence": False},
    {"approved_test_binding_matches": False},
    {"candidate_provenance_known": False},
    {"status": "In Test Review"},
    {"test_decision": "Test not required"},
):
    assert repair_diagnosis(**rejected) == "BLOCKED", rejected
assert repair_diagnosis(plan_unchanged=False) == "normal_replan"

# No old manifest/CI/acceptance may be mistaken for a fresh approval, and no
# implementation path may be edited in a test-only repair checkpoint.
assert repair.get("requires_new_manifest_review") is True
assert repair.get("reuse_old_ci_as_current_pass") is False
assert {"local_acceptance", "human_acceptance", "test_review"} <= set(repair["invalidates"])
assert repair.get("checkpoint_scope") == "test_and_test_configuration_only"
assert repair.get("allow_force_or_history_rewrite") is False
assert repair.get("default_branch_update_before_acceptance") is False
assert {"candidate_sha", "new_approved_manifest_hash"} <= set(repair["resume_requires"])


# HIR-284 review findings: exercise actual approval/delivery state changes rather
# than merely checking the presence of TOML keys. The fixture distinguishes an
# old independently reviewed manifest and candidate from the repaired versions.
def start_repair_state(old: dict[str, Any]) -> dict[str, Any]:
    assert old["status"] == repair["status"]
    assert old["test_decision"] == repair["required_test_decision"]
    assert old["approved_manifest"] == old["current_manifest"]
    assert old["reviewed_manifest"] == old["approved_manifest"]
    assert old["reviewed_candidate"] == old["candidate_sha"]
    new = old.copy()
    new["repair_stage"] = repair["initial_stage"]
    new["repair_id"] = "repair-unique-284"
    for invalidated in require_list(repair["invalidates"], "approved_test_repair.invalidates"):
        if invalidated == "approved_tests_manifest":
            new["approved_manifest"] = None
        elif invalidated == "test_review":
            new["reviewed_manifest"] = None
            new["reviewed_candidate"] = None
        elif invalidated == "implementation_review":
            new["implementation_review"] = None
        elif invalidated in ("local_acceptance", "human_acceptance"):
            new[invalidated] = None
        else:
            fail(f"unexpected invalidation target: {invalidated}")
    if repair.get("reuse_old_ci_as_current_pass") is False:
        new["ci"] = "not_run_for_repaired_manifest"
    assert new["plan_hash"] == old["plan_hash"]
    assert new["baseline_sha"] == old["baseline_sha"]
    assert new["candidate_sha"] == old["candidate_sha"]
    assert new["implementation_changes"] == old["implementation_changes"]
    return new


original = {
    "status": "Implementation",
    "test_decision": "Test required",
    "plan_hash": "plan-v1",
    "baseline_sha": "base",
    "candidate_sha": "candidate-v1",
    "implementation_changes": {"src/main.py": "source-v1"},
    "current_manifest": "manifest-v1",
    "approved_manifest": "manifest-v1",
    "reviewed_manifest": "manifest-v1",
    "reviewed_candidate": "candidate-v1",
    "implementation_review": "old-review",
    "local_acceptance": "old-local-pass",
    "human_acceptance": "old-human-pass",
    "ci": "old-ci-pass",
}
repair_state = start_repair_state(original)
assert repair_state["repair_stage"] == "diagnosed"
assert repair_state["approved_manifest"] is None
assert repair_state["reviewed_manifest"] is None
assert repair_state["local_acceptance"] is None
assert repair_state["human_acceptance"] is None
assert repair_state["ci"] != "old-ci-pass"
assert repair_state["plan_hash"] == "plan-v1"
assert repair_state["implementation_changes"] == original["implementation_changes"]


# Repair checkpoint changes only explicitly scoped tests; the candidate SHA
# changes while the implementation and baseline are retained.
def checkpoint_repaired_tests(
    state: dict[str, Any],
    *,
    changed_paths: set[str],
    allowed_test_paths: set[str],
    force: bool = False,
) -> dict[str, Any] | None:
    if repair.get("checkpoint_scope") != "test_and_test_configuration_only":
        return None
    if force and repair.get("allow_force_or_history_rewrite") is False:
        return None
    if not changed_paths or not changed_paths <= allowed_test_paths:
        return None
    next_state = state.copy()
    next_state["candidate_sha"] = "candidate-v2"
    next_state["current_manifest"] = "manifest-v2"
    next_state["repair_stage"] = "review_pending"
    next_state["ci"] = "not_run_for_repaired_manifest"
    return next_state


assert checkpoint_repaired_tests(
    repair_state, changed_paths={"src/main.py"}, allowed_test_paths={"tests/fake.py"}
) is None
assert checkpoint_repaired_tests(
    repair_state, changed_paths={"tests/fake.py"}, allowed_test_paths={"tests/fake.py"},
    force=True,
) is None
pending = checkpoint_repaired_tests(
    repair_state, changed_paths={"tests/fake.py"}, allowed_test_paths={"tests/fake.py"}
)
assert pending is not None
assert pending["candidate_sha"] == "candidate-v2"
assert pending["implementation_changes"] == original["implementation_changes"]
assert pending["approved_manifest"] is None
assert pending["reviewed_manifest"] is None


def accept_repaired_tests(
    state: dict[str, Any],
    *,
    reviewer_available: bool,
    reviewed_manifest: str,
    reviewed_candidate: str,
) -> dict[str, Any] | None:
    if state["repair_stage"] != "review_pending":
        return None
    if not reviewer_available or not repair.get("requires_new_manifest_review"):
        return None
    if reviewed_manifest != state["current_manifest"] or reviewed_candidate != state["candidate_sha"]:
        return None
    if reviewed_manifest == original["approved_manifest"]:
        return None
    next_state = state.copy()
    next_state["reviewed_manifest"] = reviewed_manifest
    next_state["reviewed_candidate"] = reviewed_candidate
    next_state["approved_manifest"] = reviewed_manifest
    next_state["repair_stage"] = "approved"
    return next_state


assert accept_repaired_tests(
    pending, reviewer_available=False, reviewed_manifest="manifest-v2",
    reviewed_candidate="candidate-v2",
) is None
assert accept_repaired_tests(
    pending, reviewer_available=True, reviewed_manifest="manifest-v1",
    reviewed_candidate="candidate-v2",
) is None
assert accept_repaired_tests(
    pending, reviewer_available=True, reviewed_manifest="manifest-v2",
    reviewed_candidate="candidate-v1",
) is None
approved = accept_repaired_tests(
    pending, reviewer_available=True, reviewed_manifest="manifest-v2",
    reviewed_candidate="candidate-v2",
)
assert approved is not None
assert approved["approved_manifest"] == approved["reviewed_manifest"] == "manifest-v2"
assert approved["reviewed_candidate"] == "candidate-v2"
assert approved["ci"] != "old-ci-pass"
assert approved["human_acceptance"] is None


# Check the Implementation route's precedence across all uncompleted repair
# stages. Neither a Status-only completion nor an old Review approval may pass.
def attempt_repair_operation(
    state: dict[str, Any], decision: str, *,
    reviewer_available: bool = True, verified: set[str] | None = None,
) -> str:
    stage = state.get("repair_stage")
    if stage in stages:
        gate = require_mapping(stages[stage], f"approved_test_repair.stages.{stage}")
        if decision == "IMPLEMENTATION_COMPLETE" and not gate["implementation_complete_allowed"]:
            return "BLOCKED"
        if decision == "ACCEPTANCE" and not gate["acceptance_allowed"]:
            return "BLOCKED"
        if decision == "CLOSE_COMPLETE" and not gate["close_allowed"]:
            return "BLOCKED"
        if decision == "TESTS_APPROVED" and not reviewer_available:
            return repair["on_missing_reviewer"]
        if decision == "RESUME_IMPLEMENTATION":
            if stage != "approved":
                return "BLOCKED"
            required = set(require_list(repair["resume_requires"], "approved_test_repair.resume_requires"))
            if not required <= (verified or set()):
                return "BLOCKED"
            if state["approved_manifest"] != state["current_manifest"]:
                return repair["on_inconsistent_binding"]
            if state["reviewed_manifest"] != state["approved_manifest"]:
                return repair["on_inconsistent_binding"]
            if state["reviewed_candidate"] != state["candidate_sha"]:
                return repair["on_inconsistent_binding"]
            return repair_step(stage, decision, full_capabilities)["stage"]
    return "normal_implementation" if decision == "IMPLEMENTATION_COMPLETE" else "BLOCKED"


for snapshot in (repair_state, pending, approved):
    for forbidden in ("IMPLEMENTATION_COMPLETE", "ACCEPTANCE", "CLOSE_COMPLETE"):
        assert attempt_repair_operation(snapshot, forbidden) == "BLOCKED", (snapshot, forbidden)
assert attempt_repair_operation(pending, "TESTS_APPROVED", reviewer_available=False) == "stay"
assert attempt_repair_operation(pending, "RESUME_IMPLEMENTATION") == "BLOCKED"
required_recheck = set(repair["resume_requires"])
assert attempt_repair_operation(approved, "RESUME_IMPLEMENTATION", verified=required_recheck) == "resolved"
assert attempt_repair_operation(approved, "RESUME_IMPLEMENTATION",
                                verified=required_recheck - {"approved_test_content_sha256"}) == "BLOCKED"
stale_candidate = {**approved, "candidate_sha": "unreviewed-v3"}
assert attempt_repair_operation(stale_candidate, "RESUME_IMPLEMENTATION",
                                verified=required_recheck) == "BLOCKED"
stale_manifest = {**approved, "current_manifest": "manifest-v3"}
assert attempt_repair_operation(stale_manifest, "RESUME_IMPLEMENTATION",
                                verified=required_recheck) == "BLOCKED"
resolved = {**approved, "repair_stage": "resolved"}
assert attempt_repair_operation(resolved, "IMPLEMENTATION_COMPLETE") == "normal_implementation"


# Restart and partial writes: an existing event is reused by repair_id. The
# latest approval and delivery bindings must agree with that event; missing
# writes are repairable, contradictory writes are not.
def reconcile_partial_repair(
    *,
    event: dict[str, str],
    approval: dict[str, str | None],
    delivery: dict[str, str | None],
    duplicate_events: int = 1,
) -> str:
    if duplicate_events != 1:
        return repair["on_inconsistent_binding"]
    repair_id = event["repair_id"]
    for snapshot in (approval, delivery):
        if snapshot["repair_id"] not in (None, repair_id):
            return repair["on_inconsistent_binding"]
        if snapshot["original_plan_hash"] not in (None, event["original_plan_hash"]):
            return repair["on_inconsistent_binding"]
        if snapshot["old_manifest_hash"] not in (None, event["old_manifest_hash"]):
            return repair["on_inconsistent_binding"]
    if approval["repair_id"] is None or delivery["repair_id"] is None:
        return repair["on_partial_write"]
    if approval["current_manifest"] != delivery["current_manifest"]:
        return repair["on_inconsistent_binding"]
    if delivery["repair_stage"] not in stages:
        return repair["on_inconsistent_binding"]
    if delivery["repair_stage"] == "approved" and approval["approved_manifest"] is None:
        return repair["on_inconsistent_binding"]
    return repair["on_repeated_event"]


event = {
    "repair_id": "repair-unique-284", "original_plan_hash": "plan-v1",
    "old_manifest_hash": "manifest-v1",
}
approval_snapshot = {
    **event, "current_manifest": "manifest-v2", "approved_manifest": None,
}
delivery_snapshot = {
    **event, "current_manifest": "manifest-v2", "repair_stage": "review_pending",
}
assert reconcile_partial_repair(event=event, approval=approval_snapshot,
                                delivery=delivery_snapshot) == "resume_existing"
assert reconcile_partial_repair(event=event, approval={**approval_snapshot, "repair_id": None},
                                delivery=delivery_snapshot) == "readback_and_resume"
assert reconcile_partial_repair(event=event, approval=approval_snapshot,
                                delivery={**delivery_snapshot, "repair_id": None}) == "readback_and_resume"
assert reconcile_partial_repair(event=event, approval=approval_snapshot,
                                delivery={**delivery_snapshot, "repair_id": "different-id"}) == "BLOCKED"
assert reconcile_partial_repair(event=event, approval=approval_snapshot,
                                delivery={**delivery_snapshot, "current_manifest": "other-manifest"}) == "BLOCKED"
assert reconcile_partial_repair(event=event, approval=approval_snapshot,
                                delivery={**delivery_snapshot, "repair_stage": "approved"}) == "BLOCKED"
assert reconcile_partial_repair(event=event, approval=approval_snapshot,
                                delivery=delivery_snapshot, duplicate_events=2) == "BLOCKED"
