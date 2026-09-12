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

# Test-not-required Implementation Review must leave enough durable metadata in
# Linear for a fresh Chat/resume/Close execution to reconstruct exactly which
# branch, candidate, artifact/diff, and Verification evidence was approved.
require_regex(
    implementation,
    r"Implementation Review.{0,2400}Review Comment.{0,1800}"
    r"(test_decision|Test not required).{0,800}"
    r"(candidate_commit|candidate SHA).{0,900}"
    r"(diff/artifact|review_targets|review対象diff|review対象artifact).{0,900}"
    r"(Verification evidence|verification_evidence).{0,900}"
    r"(decision|判定).{0,700}"
    r"(findings|finding).{0,700}"
    r"(blocker|BLOCKED)",
    "Implementation Review Comment records test decision, candidate, targets, verification, decision, findings, and blocker",
)

# Canonical Review metadata must carry Test not required for Implementation
# Review rather than null, and persist the reviewed targets/evidence alongside
# the current candidate.
require_regex(
    canonical,
    r"Implementation Review.{0,1800}test_decision.{0,500}Test not required",
    "Implementation Review preserves test_decision=Test not required",
)
require_regex(
    canonical,
    r"Implementation Review.{0,2400}"
    r"(review_context|Review Context).{0,900}"
    r"(review_targets|diff/artifact).{0,900}"
    r"(verification_evidence|Verification evidence)",
    "Implementation Review carries durable review targets and verification evidence",
)
require_regex(
    canonical,
    r"candidate_commit.{0,1200}"
    r"(Review Context|review_context|review_targets).{0,900}"
    r"(Comment|保存)",
    "Implementation Review metadata is persisted to the Review Comment",
)

for reviewer in (reviewer_light, reviewer_strict):
    require_regex(
        reviewer,
        r"Implementation Review.{0,2200}test_decision.{0,600}Test not required",
        "reviewer returns Test not required for Implementation Review",
    )
    require_regex(
        reviewer,
        r"Implementation Review.{0,2600}"
        r"(review_context|Review Context).{0,900}"
        r"(review_targets|diff/artifact).{0,900}"
        r"(verification_evidence|Verification evidence)",
        "reviewer returns durable reviewed targets and verification evidence",
    )

print("[PASS] Implementation Review durable metadata contract")
