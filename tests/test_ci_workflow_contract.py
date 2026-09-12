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


def indentation(line: str) -> int:
    return len(line) - len(line.lstrip())


def nested_block(lines: list[str], key: str, parent_indent: int = -1) -> tuple[list[str], int]:
    target = f"{key}:"
    for index, line in enumerate(lines):
        if line.strip() != target:
            continue
        key_indent = indentation(line)
        if key_indent <= parent_indent:
            continue

        block: list[str] = []
        for child in lines[index + 1 :]:
            if not child.strip() or child.lstrip().startswith("#"):
                block.append(child)
                continue
            if indentation(child) <= key_indent:
                break
            block.append(child)
        return block, key_indent

    fail(f"missing YAML block: {key}")


def event_targets_main(on_block: list[str], event: str) -> bool:
    event_block, event_indent = nested_block(on_block, event)

    for index, line in enumerate(event_block):
        stripped = line.strip()
        if not stripped.startswith("branches:"):
            continue
        if indentation(line) <= event_indent:
            continue

        value = stripped.removeprefix("branches:").strip()
        if value:
            if value.startswith("[") and value.endswith("]"):
                branches = [item.strip().strip("'\"") for item in value[1:-1].split(",")]
                return "main" in branches
            return False

        branch_indent = indentation(line)
        for child in event_block[index + 1 :]:
            if not child.strip() or child.lstrip().startswith("#"):
                continue
            if indentation(child) <= branch_indent:
                break
            if re.match(r"^\s*-\s*main\s*$", child):
                return True
        return False

    return False


def main() -> int:
    text = load_workflow()
    lines = text.splitlines()

    on_block, on_indent = nested_block(lines, "on")
    if on_indent != 0:
        fail("on must be a top-level workflow key")

    for event in ("pull_request", "push"):
        if not event_targets_main(on_block, event):
            fail(f"{event} must target main")

    if not any(re.match(r"^\s*runs-on:\s*ubuntu-latest\s*$", line) for line in lines):
        fail("workflow must use ubuntu-latest")

    if not any(
        re.match(r"^\s*(?:-\s*)?uses:\s*actions/checkout@", line)
        for line in lines
    ):
        fail("workflow must check out the repository")

    run_commands = {
        match.group(1).strip()
        for line in lines
        if (match := re.match(r"^\s*(?:-\s*)?run:\s*(.+?)\s*$", line))
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
