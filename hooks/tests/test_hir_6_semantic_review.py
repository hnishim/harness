#!/usr/bin/env python3
"""HIR-6 behavioral tests for semantic prose review hooks."""

from __future__ import annotations

import io
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock


HOOKS_DIR = Path(__file__).resolve().parents[1] / "runtime"
SEMANTIC_REVIEW = HOOKS_DIR / "semantic-review.py"
PRE_HOOK = HOOKS_DIR / "textlint-pretool-hook.py"
POST_HOOK = HOOKS_DIR / "textlint-posttool-hook.py"
TEXTLINT_BOUNDARY = HOOKS_DIR / "textlint-boundary.py"

EXPECTED_RULE_IDS = {
    "unsupported_fact_assertion",
    "fact_inference_judgment_mix",
    "unsupported_intent_attribution",
    "unnecessary_blame",
    "unclear_purpose_or_action",
    "insufficient_decision_support",
}


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"{path.name} could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def interaction_payload(findings: list[dict]) -> bytes:
    output = json.dumps({"findings": findings}, ensure_ascii=False)
    return json.dumps(
        {
            "id": "int_test",
            "status": "completed",
            "steps": [
                {
                    "type": "model_output",
                    "content": [{"type": "text", "text": output}],
                }
            ],
        },
        ensure_ascii=False,
    ).encode("utf-8")


class SemanticReviewHelperTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module(SEMANTIC_REVIEW, "hir6_semantic_review")
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_dir = Path(self.temp_dir.name) / "state"
        self.env = {
            "GEMINI_API_KEY": "test-api-key",
            "TEXTLINT_HOOK_STATE_DIR": str(self.state_dir),
        }

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def rules(self) -> list[dict]:
        return list(getattr(self.module, "SEMANTIC_RULES"))

    def call_review(self, text: str = "Review target", **kwargs):
        payload = kwargs.pop(
            "payload",
            {"session_id": "session-1", "turn_id": "turn-1", "tool_use_id": "tool-1"},
        )
        subject = kwargs.pop("subject", "fixture:document")
        with mock.patch.dict(os.environ, self.env, clear=False):
            return self.module.review_text(text, payload=payload, subject=subject, **kwargs)

    def test_initial_rules_are_the_six_semantic_contracts(self) -> None:
        rules = self.rules()
        ids = {rule["rule_id"] for rule in rules}
        self.assertEqual(ids, EXPECTED_RULE_IDS)
        self.assertEqual(len(ids), len(rules))
        for rule in rules:
            self.assertTrue(str(rule.get("description", "")).strip())
            self.assertTrue(str(rule.get("criteria", "")).strip())

    def test_request_uses_interactions_structured_output_and_does_not_store(self) -> None:
        captured: dict[str, object] = {}

        def fake_open(_self, request, data=None, timeout=None):
            captured["request"] = request
            captured["timeout"] = timeout
            return io.BytesIO(interaction_payload([]))

        with mock.patch.object(urllib.request.OpenerDirector, "open", new=fake_open):
            result = self.call_review()

        self.assertEqual(result, {"decision": "clean", "findings": []})
        request = captured["request"]
        self.assertIsInstance(request, urllib.request.Request)
        self.assertEqual(
            request.full_url,
            "https://generativelanguage.googleapis.com/v1beta/interactions",
        )
        self.assertEqual(request.get_header("X-goog-api-key"), "test-api-key")
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["model"], "gemini-3.8-flash")
        self.assertIs(body["store"], False)
        self.assertEqual(body["response_format"]["type"], "text")
        self.assertEqual(body["response_format"]["mime_type"], "application/json")
        schema = body["response_format"]["schema"]
        self.assertEqual(schema["type"], "object")
        self.assertIn("findings", schema["required"])
        self.assertNotIn("test-api-key", json.dumps(body))
        self.assertIsInstance(captured["timeout"], (int, float))
        self.assertGreater(captured["timeout"], 0)
        self.assertLess(captured["timeout"], 120)

    def test_structured_finding_is_returned_with_rule_reason_and_excerpt(self) -> None:
        finding = {
            "rule_id": "unsupported_fact_assertion",
            "reason": "根拠が示されていない断定です。",
            "excerpt": "必ず成功する。",
            "suggestion": "根拠を明示するか、推測として表現する。",
        }

        def fake_open(_self, request, data=None, timeout=None):
            return io.BytesIO(interaction_payload([finding]))

        with mock.patch.object(urllib.request.OpenerDirector, "open", new=fake_open):
            result = self.call_review()

        self.assertEqual(result["decision"], "repair")
        self.assertEqual(result["findings"], [finding])

    def test_unknown_rule_id_fails_open(self) -> None:
        finding = {
            "rule_id": "unknown-rule",
            "reason": "unknown",
            "excerpt": "target",
            "suggestion": "",
        }

        def fake_open(_self, request, data=None, timeout=None):
            return io.BytesIO(interaction_payload([finding]))

        with mock.patch.object(urllib.request.OpenerDirector, "open", new=fake_open):
            self.assertIsNone(self.call_review(subject="fixture:unknown-rule"))

    def test_malformed_structured_response_fails_open(self) -> None:
        malformed = json.dumps(
            {
                "status": "completed",
                "steps": [
                    {
                        "type": "model_output",
                        "content": [{"type": "text", "text": "{\"findings\": \"not-a-list\"}"}],
                    }
                ],
            }
        ).encode("utf-8")

        def fake_open(_self, request, data=None, timeout=None):
            return io.BytesIO(malformed)

        with mock.patch.object(urllib.request.OpenerDirector, "open", new=fake_open):
            self.assertIsNone(self.call_review(subject="fixture:malformed"))

    def test_missing_api_key_skips_network_and_fails_open(self) -> None:
        def fail_if_called(*_args, **_kwargs):
            raise AssertionError("network must not be called without GEMINI_API_KEY")

        with mock.patch.dict(
            os.environ,
            {"TEXTLINT_HOOK_STATE_DIR": str(self.state_dir)},
            clear=True,
        ), mock.patch.object(urllib.request.OpenerDirector, "open", new=fail_if_called):
            result = self.module.review_text(
                "Review target",
                payload={"session_id": "s"},
                subject="fixture:missing-key",
            )
        self.assertIsNone(result)

    def test_retryable_network_failure_retries_only_once(self) -> None:
        calls = 0

        def fake_open(_self, request, data=None, timeout=None):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise urllib.error.URLError("temporary")
            return io.BytesIO(interaction_payload([]))

        with mock.patch.object(urllib.request.OpenerDirector, "open", new=fake_open):
            result = self.call_review(subject="fixture:network-retry")

        self.assertEqual(result["decision"], "clean")
        self.assertEqual(calls, 2)

    def test_retryable_5xx_retries_only_once(self) -> None:
        calls = 0

        def fake_open(_self, request, data=None, timeout=None):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise urllib.error.HTTPError(
                    request.full_url,
                    503,
                    "unavailable",
                    hdrs=None,
                    fp=None,
                )
            return io.BytesIO(interaction_payload([]))

        with mock.patch.object(urllib.request.OpenerDirector, "open", new=fake_open):
            result = self.call_review(subject="fixture:503")

        self.assertEqual(result["decision"], "clean")
        self.assertEqual(calls, 2)

    def test_nonretryable_4xx_is_not_retried(self) -> None:
        calls = 0

        def fake_open(_self, request, data=None, timeout=None):
            nonlocal calls
            calls += 1
            raise urllib.error.HTTPError(
                request.full_url,
                401,
                "unauthorized",
                hdrs=None,
                fp=None,
            )

        with mock.patch.object(urllib.request.OpenerDirector, "open", new=fake_open):
            result = self.call_review(subject="fixture:401")

        self.assertIsNone(result)
        self.assertEqual(calls, 1)

    def test_same_finding_repetition_switches_from_repair_to_report(self) -> None:
        finding = {
            "rule_id": "unsupported_fact_assertion",
            "reason": "same",
            "excerpt": "same target",
            "suggestion": "revise minimally",
        }

        def fake_open(_self, request, data=None, timeout=None):
            return io.BytesIO(interaction_payload([finding]))

        payload = {"session_id": "same-session"}
        with mock.patch.object(urllib.request.OpenerDirector, "open", new=fake_open):
            first = self.call_review(payload=payload, subject="fixture:same-finding")
            second = self.call_review(payload=payload, subject="fixture:same-finding")

        self.assertEqual(first["decision"], "repair")
        self.assertEqual(second["decision"], "report")
        self.assertEqual(second["findings"], [finding])


class HookSubprocessIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.runtime = self.root / "runtime"
        self.runtime.mkdir()
        self.config = self.root / ".textlintrc.json"
        self.config.write_text("{}\n", encoding="utf-8")
        self.textlint = self.root / "textlint"
        self.state_dir = self.root / "state"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def install_textlint(self, body: str) -> None:
        self.textlint.write_text("#!/bin/sh\nset -eu\n" + body, encoding="utf-8")
        self.textlint.chmod(self.textlint.stat().st_mode | stat.S_IXUSR)

    def install_runtime(self, hook: Path, semantic_body: str) -> Path:
        target_hook = self.runtime / hook.name
        shutil.copy2(hook, target_hook)
        shutil.copy2(TEXTLINT_BOUNDARY, self.runtime / TEXTLINT_BOUNDARY.name)
        if hook == PRE_HOOK:
            shutil.copy2(POST_HOOK, self.runtime / POST_HOOK.name)
        (self.runtime / "semantic-review.py").write_text(semantic_body, encoding="utf-8")
        return target_hook

    def env(self) -> dict[str, str]:
        return {
            **os.environ,
            "TEXTLINT_BIN": str(self.textlint),
            "TEXTLINT_CONFIG": str(self.config),
            "TEXTLINT_HOOK_STATE_DIR": str(self.state_dir),
            "GEMINI_API_KEY": "fixture-key",
        }

    def run_hook(self, hook: Path, payload: dict) -> str:
        result = subprocess.run(
            ["/usr/bin/python3", str(hook)],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            env=self.env(),
            check=True,
        )
        return result.stdout

    @staticmethod
    def repair_semantic_module(marker: Path | None = None) -> str:
        marker_line = ""
        if marker is not None:
            marker_line = (
                "from pathlib import Path\n"
                f"Path({str(marker)!r}).write_text('called', encoding='utf-8')\n"
            )
        return (
            marker_line
            + "def review_text(*args, **kwargs):\n"
            + "    return {\n"
            + "        'decision': 'repair',\n"
            + "        'findings': [{\n"
            + "            'rule_id': 'unsupported_fact_assertion',\n"
            + "            'reason': '根拠のない断定です。',\n"
            + "            'excerpt': '必ず成功する。',\n"
            + "            'suggestion': '推測として表現する。',\n"
            + "        }],\n"
            + "    }\n"
        )

    @staticmethod
    def report_semantic_module() -> str:
        return (
            "def review_text(*args, **kwargs):\n"
            "    return {\n"
            "        'decision': 'report',\n"
            "        'findings': [{\n"
            "            'rule_id': 'unsupported_fact_assertion',\n"
            "            'reason': '根拠のない断定です。',\n"
            "            'excerpt': '必ず成功する。',\n"
            "            'suggestion': '推測として表現する。',\n"
            "        }],\n"
            "    }\n"
        )

    def notion_payload(self) -> dict:
        return {
            "session_id": "pre-session",
            "turn_id": "pre-turn",
            "tool_use_id": "pre-tool",
            "tool_name": "mcp__codex_apps__notion_notion_create_pages",
            "tool_input": {"pages": [{"content": "この案は必ず成功する。"}]},
        }

    def test_pretool_semantic_finding_denies_without_direct_rewrite(self) -> None:
        self.install_textlint(
            'target=""\nfor arg in "$@"; do target="$arg"; done\nexit 0\n'
        )
        hook = self.install_runtime(PRE_HOOK, self.repair_semantic_module())
        output = json.loads(self.run_hook(hook, self.notion_payload()))
        hook_output = output["hookSpecificOutput"]
        self.assertEqual(hook_output["hookEventName"], "PreToolUse")
        self.assertEqual(hook_output["permissionDecision"], "deny")
        self.assertNotIn("updatedInput", hook_output)
        serialized = json.dumps(output, ensure_ascii=False)
        self.assertIn("unsupported_fact_assertion", serialized)
        self.assertIn("根拠のない断定", serialized)

    def test_pretool_nontarget_tool_does_not_call_semantic_review(self) -> None:
        marker = self.root / "semantic-called"
        self.install_textlint("exit 0\n")
        hook = self.install_runtime(PRE_HOOK, self.repair_semantic_module(marker))
        payload = {
            "session_id": "nontarget-session",
            "tool_name": "mcp__codex_apps__read_page",
            "tool_input": {"page_id": "example"},
        }
        self.assertEqual(self.run_hook(hook, payload), "")
        self.assertFalse(marker.exists())

    def test_posttool_textlint_residual_skips_semantic_review(self) -> None:
        marker = self.root / "semantic-called"
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
printf '[{"filePath":"%s","messages":[{"ruleId":"textlint-residual","line":1,"column":1,"message":"residual"}]}]\n' "$target"
exit 1
'''
        )
        hook = self.install_runtime(POST_HOOK, self.repair_semantic_module(marker))
        target = self.root / "residual.md"
        target.write_text("Residual text", encoding="utf-8")
        payload = {
            "session_id": "post-session",
            "turn_id": "post-turn",
            "tool_use_id": "post-tool",
            "tool_name": "exec_command",
            "tool_input": {"cmd": f"touch {target}"},
            "tool_response": {"exit_code": 0},
            "cwd": str(self.root),
        }
        output = json.loads(self.run_hook(hook, payload))
        self.assertFalse(marker.exists())
        self.assertIn(
            "textlint-residual",
            output["hookSpecificOutput"]["additionalContext"],
        )

    def test_posttool_clean_file_emits_semantic_repair_context(self) -> None:
        self.install_textlint(
            r'''
target=""
fix=0
for arg in "$@"; do
  [ "$arg" = "--fix" ] && fix=1
  target="$arg"
done
if [ "$fix" -eq 1 ]; then
  exit 0
fi
printf '%s\n' '[]'
exit 0
'''
        )
        hook = self.install_runtime(POST_HOOK, self.repair_semantic_module())
        target = self.root / "clean.md"
        target.write_text("この案は必ず成功する。", encoding="utf-8")
        payload = {
            "session_id": "post-session",
            "turn_id": "post-turn",
            "tool_use_id": "post-tool",
            "tool_name": "exec_command",
            "tool_input": {"cmd": f"touch {target}"},
            "tool_response": {"exit_code": 0},
            "cwd": str(self.root),
        }
        output = json.loads(self.run_hook(hook, payload))
        self.assertTrue(output["continue"])
        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("unsupported_fact_assertion", context)
        self.assertIn("根拠のない断定", context)
        self.assertIn(str(target), context)

    def test_posttool_report_decision_stops_requesting_another_repair(self) -> None:
        self.install_textlint(
            r'''
target=""
fix=0
for arg in "$@"; do
  [ "$arg" = "--fix" ] && fix=1
  target="$arg"
done
if [ "$fix" -eq 1 ]; then
  exit 0
fi
printf '%s\n' '[]'
exit 0
'''
        )
        hook = self.install_runtime(POST_HOOK, self.report_semantic_module())
        target = self.root / "report.md"
        target.write_text("この案は必ず成功する。", encoding="utf-8")
        payload = {
            "session_id": "post-session",
            "turn_id": "post-turn",
            "tool_use_id": "post-tool",
            "tool_name": "exec_command",
            "tool_input": {"cmd": f"touch {target}"},
            "tool_response": {"exit_code": 0},
            "cwd": str(self.root),
        }
        output = json.loads(self.run_hook(hook, payload))
        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("unsupported_fact_assertion", context)
        self.assertIn("ユーザー", context)
        self.assertNotIn("最小修正を通常のwrite toolで行ってください", context)

    def test_posttool_no_candidate_does_not_call_semantic_review(self) -> None:
        marker = self.root / "semantic-called"
        self.install_textlint("exit 0\n")
        hook = self.install_runtime(POST_HOOK, self.repair_semantic_module(marker))
        payload = {
            "session_id": "post-session",
            "tool_name": "mcp__codex_apps__read_page",
            "tool_input": {"path": "ignored.md"},
            "tool_response": {"success": True},
            "cwd": str(self.root),
        }
        output = json.loads(self.run_hook(hook, payload))
        self.assertEqual(output, {"continue": True})
        self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
