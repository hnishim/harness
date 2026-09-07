#!/usr/bin/env python3
"""Tests for removing the UserPromptSubmit Active Policy hook."""

from __future__ import annotations

import json
import shlex
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


HOOKS_TEMPLATE = Path(__file__).resolve().parents[1] / "hooks.json.tmpl"
RUNTIME_DIR = HOOKS_TEMPLATE.parent / "runtime"
RUNTIME_PLACEHOLDER = "__HOOKS_RUNTIME__"


class ActivePolicyHookRemovalTests(unittest.TestCase):
    @contextmanager
    def rendered_hooks_config(self) -> Iterator[dict]:
        with tempfile.TemporaryDirectory() as temporary_directory:
            runtime_path = Path(temporary_directory) / "runtime"
            runtime_path.symlink_to(RUNTIME_DIR, target_is_directory=True)
            rendered = HOOKS_TEMPLATE.read_text(encoding="utf-8").replace(
                RUNTIME_PLACEHOLDER, str(runtime_path)
            )
            self.assertTrue(runtime_path.is_absolute())
            yield json.loads(rendered)

    def test_hooks_template_renders_as_json(self) -> None:
        with self.rendered_hooks_config() as config:
            self.assertIsInstance(config, dict)

    def test_user_prompt_submit_hook_is_absent(self) -> None:
        with self.rendered_hooks_config() as config:
            self.assertNotIn("UserPromptSubmit", config["hooks"])

    def test_expected_tool_hooks_and_runtime_files_are_present(self) -> None:
        with self.rendered_hooks_config() as config:
            hooks_config = config["hooks"]
            self.assertEqual(len(hooks_config["PreToolUse"]), 2)
            self.assertEqual(len(hooks_config["PostToolUse"]), 1)

            for event_name in ("PreToolUse", "PostToolUse"):
                for hook_group in hooks_config[event_name]:
                    for hook in hook_group["hooks"]:
                        command_parts = shlex.split(hook["command"])
                        runtime_file = Path(command_parts[-1])
                        self.assertTrue(
                            runtime_file.is_absolute(),
                            f"{event_name} command must reference an absolute runtime path",
                        )
                        self.assertTrue(runtime_file.is_file(), str(runtime_file))

    def test_active_policy_user_prompt_runtime_file_is_removed(self) -> None:
        self.assertFalse(
            (RUNTIME_DIR / "active-policy-user-prompt-hook.py").exists()
        )


if __name__ == "__main__":
    unittest.main()
