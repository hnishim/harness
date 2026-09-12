#!/usr/bin/env python3

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"

EXPECTED_COMMANDS = [
    "python3 hooks/tests/test_gh_normal_context_guard.py",
    "python3 hooks/tests/test_textlint_boundaries.py",
    "python3 skills/implementation-loop/tests/test_remote_adapter_contract.py",
    "bash custom-instructions/tests/test-openai-routing-contract.sh",
    "python3 tests/test_ci_workflow_contract.py",
]


def fail(message: str) -> None:
    raise AssertionError(message)


def load_workflow() -> str:
    if not WORKFLOW.is_file():
        fail(f"missing workflow: {WORKFLOW.relative_to(ROOT)}")
    return WORKFLOW.read_text(encoding="utf-8")


def block_lines(lines: list[str], key: str, indent: int) -> list[str]:
    pattern = re.compile(rf"^\s{{{indent}}}{re.escape(key)}:\s*$")
    start = None
    for index, line in enumerate(lines):
        if pattern.match(line):
            start = index
            break
    if start is None:
        fail(f"missing YAML block: {key}")

    block: list[str] = []
    for line in lines[start + 1 :]:
        if not line.strip() or line.lstrip().startswith("#"):
            block.append(line)
            continue
        current_indent = len(line) - len(line.lstrip())
        if current_indent <= indent:
            break
        block.append(line)
    return block


def event_targets_main(on_block: list[str], event: str) -> bool:
    event_pattern = re.compile(rf"^\s{{2}}{re.escape(event)}:\s*$")
    start = None
    for index, line in enumerate(on_block):
        if event_pattern.match(line):
            start = index
            break
    if start is None:
        return False

    event_block: list[str] = []
    for line in on_block[start + 1 :]:
        if not line.strip() or line.lstrip().startswith("#"):
            event_block.append(line)
            continue
        current_indent = len(line) - len(line.lstrip())
        if current_indent <= 2:
            break
        event_block.append(line)

    for index, line in enumerate(event_block):
        if re.match(r"^\s{4}branches:\s*\[\s*main\s*\]\s*$", line):
            return True
        if re.match(r"^\s{4}branches:\s*$", line):
            for child in event_block[index + 1 :]:
                if not child.strip() or child.lstrip().startswith("#"):
                    continue
                child_indent = len(child) - len(child.lstrip())
                if child_indent <= 4:
                    break
                if re.match(r"^\s{6}-\s*main\s*$", child):
                    return True
    return False


def main() -> int:
    text = load_workflow()
    lines = text.splitlines()

    on_block = block_lines(lines, "on", 0)
    for event in ("pull_request", "push"):
        if not event_targets_main(on_block, event):
            fail(f"{event} must target main")

    if not any(re.match(r"^\s*runs-on:\s*ubuntu-latest\s*$", line) for line in lines):
        fail("workflow must use ubuntu-latest")

    if not any(re.match(r"^\s*uses:\s*actions/checkout@", line) for line in lines):
        fail("workflow must check out the repository")

    run_commands = {
        match.group(1).strip()
        for line in lines
        if (match := re.match(r"^\s*run:\s*(.+?)\s*$", line))
    }
    missing_commands = [command for command in EXPECTED_COMMANDS if command not in run_commands]
    if missing_commands:
        fail("missing workflow commands: " + ", ".join(missing_commands))

    lowered = text.lower()
    if "secrets." in lowered:
        fail("workflow must not depend on GitHub secrets")
    if "macos-latest" in lowered:
        fail("workflow must not use macos-latest")
    if any(re.match(r"^\s*matrix:\s*", line) for line in lines):
        fail("workflow must not define a matrix")

    print("[PASS] GitHub Actions workflow contract")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as error:
        print(f"[FAIL] {error}", file=sys.stderr)
        raise SystemExit(1)
