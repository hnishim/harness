#!/usr/bin/env python3
"""Inject validated Active Policies into UserPromptSubmit context."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REQUIRED = ("Page ID", "Name", "Policy", "Context", "Feedback Count", "Last Edited")

def cache_path() -> Path:
    return Path.home() / ".cache" / "decision-log" / "policies.json"

def diagnostic(message: str) -> None:
    print(f"active-policy-hook: {message}", file=sys.stderr)

def valid_policy(item: Any) -> bool:
    return (
        isinstance(item, dict)
        and item.get("Status") in ("Active", "Inactive")
        and all(item.get(key) not in (None, "") for key in REQUIRED)
    )

def load_policies(path: Path) -> list[dict[str, Any]] | None:
    try:
        with path.open("r", encoding="utf-8") as stream:
            value = json.load(stream)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        diagnostic(f"cache unavailable or malformed: {exc}")
        return None
    if not isinstance(value, list) or not all(valid_policy(item) for item in value):
        diagnostic("cache schema is invalid")
        return None
    active = [item for item in value if item["Status"] == "Active"]
    return sorted(active, key=lambda item: str(item["Page ID"]))

def main() -> int:
    policies = load_policies(cache_path())
    if policies is None or not policies:
        return 0
    lines = ["Active Policies:"]
    for policy in policies:
        lines.append(f"- {policy['Name']}: {policy['Policy']}")
        if policy["Context"]:
            lines.append(f"  Context: {policy['Context']}")
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": "\n".join(lines)}}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
