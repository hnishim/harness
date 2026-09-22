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
assert evaluate_migration(migration, migration_ids=["migration-a"], source_snapshot_matches=True, origin_known=True) == "resume_partial"
assert evaluate_migration(migration, migration_ids=["migration-a", "migration-b"], source_snapshot_matches=True, origin_known=True) == "BLOCKED"
assert evaluate_migration(migration, migration_ids=["migration-a"], source_snapshot_matches=True, origin_known=False) == "BLOCKED"


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

# HIR-306-CONTRACT-01: the Close instruction must require the safety gate
# before removal, while keeping completed publication and Done independent
# from any later local-only cleanup. Real macOS process-use checks remain
# an explicit local-acceptance boundary, not a claimed CI result.
close_contract = (ROOT / "skills" / "implementation-loop"
                  / "references" / "close.md").read_text(encoding="utf-8")
for required in (
    "git worktree list --porcelain",
    "git worktree remove",
    "--ignored",
    "未公開",
    "他プロセス",
    "delivery",
):
    assert required in close_contract, required
assert "worktree" in close_contract.split("## Done・作業ブランチ整理", 1)[-1]
