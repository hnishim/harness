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


def require_regex(text: str, pattern: str, description: str) -> None:
    assert re.search(pattern, text, flags=re.DOTALL), f"missing semantic contract: {description}"


def forbid_regex(text: str, pattern: str, description: str) -> None:
    assert not re.search(pattern, text, flags=re.DOTALL), f"obsolete semantic contract remains: {description}"


canonical = read("skills/implementation-loop/SKILL.md")
implementation = read("skills/implementation-loop/references/implementation.md")
close_ref = read("skills/implementation-loop/references/close.md")
spike = read("skills/implementation-loop/references/spike.md")
remote = read("skills/remote-implementation-loop/SKILL.md")
architecture = read("agent-development-workflow.md")

# HIR-262: Human Acceptance waiting is a first-class workflow Status instead of
# a durable substate hidden inside In Implementation Review.
require_regex(
    canonical,
    r"\|\s*`Awaiting Acceptance`\s*\|.{0,300}references/implementation\.md",
    "Awaiting Acceptance routes to the canonical implementation/acceptance reference",
)
require_regex(
    implementation,
    r"`Test required`.{0,1800}(checkpoint|Checkpoint).{0,1000}`Awaiting Acceptance`",
    "Test required reaches Awaiting Acceptance after the candidate checkpoint without Implementation Review",
)
require_regex(
    implementation,
    r"`Test not required`.{0,3200}Implementation Review.{0,2200}`APPROVE`.{0,1200}`Awaiting Acceptance`",
    "Test not required reaches Awaiting Acceptance only after current-candidate Implementation Review approval",
)
require_regex(
    implementation,
    r"Awaiting Acceptance.{0,2600}Human Acceptance",
    "Awaiting Acceptance owns the Human Acceptance waiting semantics",
)

# In Implementation Review remains a Review Status: normal issues use it only
# for Test-not-required Implementation Review, while Spike keeps Result Review.
require_regex(
    canonical,
    r"通常Issue.{0,900}`In Implementation Review`.{0,1800}`Test not required`.{0,1600}Implementation Review",
    "normal In Implementation Review is limited to Test-not-required Implementation Review",
)
require_regex(
    spike,
    r"`In Implementation Review`.{0,1800}Result Review",
    "Spike Result Review remains on In Implementation Review",
)
forbid_regex(
    canonical,
    r"`Test required`.{0,1000}`In Implementation Review`.{0,1400}Human Acceptance待ち",
    "Test required must not keep Human Acceptance waiting inside In Implementation Review",
)

# Close starts from the explicit acceptance-wait Status and preserves the
# existing candidate-bound Review rules.
require_regex(
    close_ref,
    r"通常Issue.{0,1600}Status.{0,500}`Awaiting Acceptance`",
    "normal Close entry requires Awaiting Acceptance",
)
require_regex(
    close_ref,
    r"`Test required`.{0,700}Implementation Review.{0,300}(Close条件にしない|前提にしない|要求しない|不要)",
    "Test required Close still does not require Implementation Review",
)
require_regex(
    close_ref,
    r"`Test not required`.{0,1300}(candidate_commit|対象candidate SHA|review対象candidate SHA).{0,700}`APPROVE`",
    "Test not required Close still requires approval bound to the current candidate",
)

# The remote adapter must stop at the same canonical acceptance Status when a
# local-only acceptance boundary cannot be executed remotely.
require(remote, "Awaiting Acceptance")
require_regex(
    remote,
    r"Local Acceptance.{0,2200}(実行できない|利用できない|local-only).{0,1800}`Awaiting Acceptance`",
    "remote Local Acceptance handoff keeps the issue in Awaiting Acceptance",
)

# The architecture document mirrors the lifecycle and must no longer describe
# Human Acceptance as an In Implementation Review substate.
require(architecture, "Awaiting Acceptance")
forbid_regex(
    architecture,
    r"In Implementation Review\s*/\s*Human Acceptance",
    "architecture must not retain In Implementation Review / Human Acceptance as the current lifecycle",
)

# Local Acceptance remains an execution boundary, not a Linear Status.
forbid_regex(
    canonical,
    r"\|\s*`Local Acceptance`\s*\|",
    "Local Acceptance must not be added to the canonical Status routing table",
)

print("[PASS] Awaiting Acceptance status contract")
