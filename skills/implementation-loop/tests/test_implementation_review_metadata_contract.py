#!/usr/bin/env python3
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(rel: str) -> str:
    path = ROOT / rel
    assert path.is_file(), f"missing required artifact: {rel}"
    return path.read_text(encoding="utf-8")


def require_regex(text: str, pattern: str, description: str) -> None:
    assert re.search(pattern, text, flags=re.DOTALL), f"missing semantic contract: {description}"


canonical = read("skills/implementation-loop/SKILL.md")
implementation = read("skills/implementation-loop/references/implementation.md")
reviewer_light = read("agents/reviewer-lightweight.toml")
reviewer_strict = read("agents/reviewer.toml")

# Test-not-required Implementation Review must leave a structured durable
# envelope in Linear. Each minimum field from the approved Plan is required as
# a field, not merely as prose or an alternative keyword.
require_regex(
    implementation,
    r"Implementation Review.{0,3200}Review Comment.{0,2400}"
    r"`issue`.{0,500}`phase`.{0,500}Implementation Review.{0,500}"
    r"`test_decision`.{0,400}Test not required.{0,700}"
    r"`candidate_commit`.{0,900}"
    r"`review_targets`.{0,900}"
    r"`verification_evidence`.{0,900}"
    r"`decision`.{0,700}"
    r"`findings`.{0,700}"
    r"`blocker`",
    "Implementation Review Comment records every Plan-step-8 durable metadata field",
)

# Canonical Review Result / persistence rules must preserve the same identity
# and branch metadata for Implementation Review rather than nulling it.
require_regex(
    canonical,
    r"Implementation Review.{0,2200}"
    r"test_decision.{0,500}Test not required",
    "Implementation Review preserves test_decision=Test not required",
)
require_regex(
    canonical,
    r"Implementation Review.{0,3200}"
    r"(review_context|Review Context).{0,1200}"
    r"review_targets.{0,900}"
    r"verification_evidence",
    "Implementation Review carries structured reviewed targets and verification evidence",
)
require_regex(
    canonical,
    r"(phase|フェーズ).{0,500}(issue|対象Issue).{0,900}"
    r"Implementation Review.{0,1600}"
    r"test_decision.{0,600}candidate_commit.{0,1200}"
    r"(review_context|Review Context|review_targets).{0,1000}"
    r"(Comment|保存)",
    "Implementation Review identity, branch metadata, and evidence context are persisted together",
)

for reviewer in (reviewer_light, reviewer_strict):
    require_regex(
        reviewer,
        r"Implementation Review.{0,2400}"
        r"test_decision.{0,600}Test not required",
        "reviewer returns Test not required for Implementation Review",
    )
    require_regex(
        reviewer,
        r"Implementation Review.{0,3200}"
        r"(review_context|Review Context).{0,1000}"
        r"review_targets.{0,900}"
        r"verification_evidence",
        "reviewer returns structured reviewed targets and verification evidence",
    )
    require_regex(
        reviewer,
        r"(phase|フェーズ).{0,900}(issue|対象Issue).{0,1200}"
        r"Implementation Review.{0,1800}"
        r"test_decision.{0,700}candidate_commit",
        "reviewer keeps issue, phase, test decision, and candidate identity in the canonical result",
    )

print("[PASS] Implementation Review durable metadata contract")
