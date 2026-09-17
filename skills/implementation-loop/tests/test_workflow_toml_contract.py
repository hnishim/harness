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
} <= tests_fields, "approved_tests_manifest must fully identify the approved test set"

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
