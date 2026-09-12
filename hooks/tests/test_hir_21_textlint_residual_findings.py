#!/usr/bin/env python3
"""HIR-21 behavioral tests for residual textlint findings."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


HOOKS_DIR = Path(__file__).resolve().parents[1] / "runtime"
POST_HOOK = HOOKS_DIR / "textlint-posttool-hook.py"


class ResidualTextlintFindingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.config = self.root / ".textlintrc.json"
        self.config.write_text("{}\n", encoding="utf-8")
        self.state_dir = self.root / "state"
        self.env = {
            **os.environ,
            "TEXTLINT_CONFIG": str(self.config),
            "TEXTLINT_HOOK_STATE_DIR": str(self.state_dir),
        }

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def install_textlint(self, body: str) -> None:
        fake = self.root / "textlint"
        fake.write_text("#!/bin/sh\nset -eu\n" + body, encoding="utf-8")
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        self.env["TEXTLINT_BIN"] = str(fake)

    def run_post(
        self,
        path: Path,
        *,
        session: str = "session-1",
        turn: str = "turn-1",
        tool_use: str = "tool-1",
    ) -> dict:
        payload = {
            "session_id": session,
            "turn_id": turn,
            "tool_use_id": tool_use,
            "tool_name": "exec_command",
            "tool_input": {"cmd": f"touch {path}"},
            "tool_response": {"exit_code": 0},
            "cwd": str(self.root),
        }
        result = subprocess.run(
            ["/usr/bin/python3", str(POST_HOOK)],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            env=self.env,
            check=True,
        )
        return json.loads(result.stdout)

    def test_auto_fix_remains_and_clean_output_shape_is_unchanged(self) -> None:
        self.install_textlint(
            r'''
target=""
fix=0
for arg in "$@"; do
  [ "$arg" = "--fix" ] && fix=1
  target="$arg"
done
if [ "$fix" -eq 1 ]; then
  sed -i '' 's/MacOS/macOS/g' "$target" 2>/dev/null || sed -i 's/MacOS/macOS/g' "$target"
  exit 0
fi
printf '%s\n' '[]'
exit 0
'''
        )
        path = self.root / "clean.md"
        path.write_text("MacOS\n", encoding="utf-8")

        output = self.run_post(path)

        self.assertEqual(path.read_text(encoding="utf-8"), "macOS\n")
        self.assertEqual(output, {"continue": True})

    def test_residual_finding_emits_schema_valid_posttool_context(self) -> None:
        self.install_textlint(
            r'''
target=""
fix=0
for arg in "$@"; do
  [ "$arg" = "--fix" ] && fix=1
  target="$arg"
done
if [ "$fix" -eq 1 ]; then
  exit 1
fi
printf '[{"filePath":"%s","messages":[{"ruleId":"generic-residual-rule","line":1,"column":1,"message":"generic residual message"}]}]\n' "$target"
exit 1
'''
        )
        path = self.root / "residual.md"
        path.write_text("Residual target\n", encoding="utf-8")

        output = self.run_post(path)

        self.assertTrue(output["continue"])
        self.assertEqual(output["hookSpecificOutput"]["hookEventName"], "PostToolUse")
        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn(str(path), context)
        self.assertIn("generic-residual-rule", context)
        self.assertIn("1:1", context)
        self.assertIn("generic residual message", context)
        self.assertIn("Residual target", context)

    def test_residual_finding_after_multiline_mdx_region_uses_source_coordinates(self) -> None:
        self.install_textlint(
            r'''
target=""
fix=0
for arg in "$@"; do
  [ "$arg" = "--fix" ] && fix=1
  target="$arg"
done
if [ "$fix" -eq 1 ]; then
  exit 1
fi
line=$(awk '/Residual target/{print NR; exit}' "$target")
printf '[{"filePath":"%s","messages":[{"ruleId":"after-protected-region","line":%s,"column":1,"message":"after protected region"}]}]\n' "$target" "$line"
exit 1
'''
        )
        path = self.root / "coordinate.mdx"
        path.write_text(
            "Intro\n"
            "```js\n"
            "const MacOS = 1;\n"
            "const Other = 2;\n"
            "```\n"
            "Residual target\n",
            encoding="utf-8",
        )

        output = self.run_post(path)
        context = output["hookSpecificOutput"]["additionalContext"]

        self.assertIn("after-protected-region", context)
        self.assertIn("6:1", context)
        self.assertIn("Residual target", context)

    def test_identical_residual_finding_twice_stops_requesting_another_edit(self) -> None:
        self.install_textlint(
            r'''
target=""
fix=0
for arg in "$@"; do
  [ "$arg" = "--fix" ] && fix=1
  target="$arg"
done
if [ "$fix" -eq 1 ]; then
  exit 1
fi
printf '[{"filePath":"%s","messages":[{"ruleId":"stuck-rule","line":1,"column":1,"message":"still stuck"}]}]\n' "$target"
exit 1
'''
        )
        path = self.root / "stuck.md"
        path.write_text("Residual target\n", encoding="utf-8")

        first = self.run_post(path, turn="turn-1", tool_use="tool-1")
        second = self.run_post(path, turn="turn-2", tool_use="tool-2")

        first_context = first["hookSpecificOutput"]["additionalContext"]
        second_context = second["hookSpecificOutput"]["additionalContext"]
        self.assertIn("stuck-rule", first_context)
        self.assertIn("stuck-rule", second_context)
        self.assertNotEqual(first_context, second_context)
        self.assertIn("ユーザー", second_context)

    def test_retry_limit_stops_after_three_context_repair_requests(self) -> None:
        counter = self.root / "lint-count"
        self.install_textlint(
            f'''
target=""
fix=0
for arg in "$@"; do
  [ "$arg" = "--fix" ] && fix=1
  target="$arg"
done
if [ "$fix" -eq 1 ]; then
  exit 1
fi
count=0
[ -f "{counter}" ] && count=$(cat "{counter}")
count=$((count + 1))
printf '%s' "$count" > "{counter}"
printf '[{{"filePath":"%s","messages":[{{"ruleId":"changing-rule-%s","line":1,"column":1,"message":"still residual"}}]}}]\n' "$target" "$count"
exit 1
'''
        )
        path = self.root / "limit.md"
        path.write_text("Residual target\n", encoding="utf-8")

        outputs = [
            self.run_post(path, turn=f"turn-{index}", tool_use=f"tool-{index}")
            for index in range(1, 5)
        ]
        contexts = [item["hookSpecificOutput"]["additionalContext"] for item in outputs]

        self.assertIn("changing-rule-1", contexts[0])
        self.assertIn("changing-rule-2", contexts[1])
        self.assertIn("changing-rule-3", contexts[2])
        self.assertIn("changing-rule-4", contexts[3])
        self.assertIn("ユーザー", contexts[3])
        self.assertNotEqual(contexts[2], contexts[3])

    def test_clean_result_clears_residual_retry_state(self) -> None:
        mode = self.root / "mode"
        mode.write_text("finding", encoding="utf-8")
        self.install_textlint(
            f'''
target=""
fix=0
for arg in "$@"; do
  [ "$arg" = "--fix" ] && fix=1
  target="$arg"
done
if [ "$fix" -eq 1 ]; then
  [ "$(cat "{mode}")" = "clean" ] && exit 0
  exit 1
fi
if [ "$(cat "{mode}")" = "clean" ]; then
  printf '%s\n' '[]'
  exit 0
fi
printf '[{{"filePath":"%s","messages":[{{"ruleId":"reset-rule","line":1,"column":1,"message":"residual"}}]}}]\n' "$target"
exit 1
'''
        )
        path = self.root / "reset.md"
        path.write_text("Residual target\n", encoding="utf-8")

        first = self.run_post(path, turn="turn-1", tool_use="tool-1")
        mode.write_text("clean", encoding="utf-8")
        clean = self.run_post(path, turn="turn-2", tool_use="tool-2")
        mode.write_text("finding", encoding="utf-8")
        after_reset = self.run_post(path, turn="turn-3", tool_use="tool-3")

        self.assertIn("reset-rule", first["hookSpecificOutput"]["additionalContext"])
        self.assertEqual(clean, {"continue": True})
        self.assertIn("reset-rule", after_reset["hookSpecificOutput"]["additionalContext"])
        self.assertNotIn("ユーザー", after_reset["hookSpecificOutput"]["additionalContext"])

    def test_state_storage_failure_reports_finding_without_retrying(self) -> None:
        broken_state = self.root / "state-as-file"
        broken_state.write_text("not a directory", encoding="utf-8")
        self.env["TEXTLINT_HOOK_STATE_DIR"] = str(broken_state)
        self.install_textlint(
            r'''
target=""
fix=0
for arg in "$@"; do
  [ "$arg" = "--fix" ] && fix=1
  target="$arg"
done
if [ "$fix" -eq 1 ]; then
  exit 1
fi
printf '[{"filePath":"%s","messages":[{"ruleId":"state-failure-rule","line":1,"column":1,"message":"residual"}]}]\n' "$target"
exit 1
'''
        )
        path = self.root / "state-failure.md"
        path.write_text("Residual target\n", encoding="utf-8")

        output = self.run_post(path)
        context = output["hookSpecificOutput"]["additionalContext"]

        self.assertIn("state-failure-rule", context)
        self.assertIn(str(path), context)
        self.assertIn("ユーザー", context)


if __name__ == "__main__":
    unittest.main()
