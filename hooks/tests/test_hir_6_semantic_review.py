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
    text = json.dumps({"findings": findings}, ensure_ascii=False)
    return json.dumps(
        {
            "id": "int_test",
            "status": "completed",
            "steps": [
                {
                    "type": "model_output",
                    "content": [{"type": "text", "text": text}],
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

    def review(self, text: str = "Review target", *, subject: str = "fixture:document", payload=None):
        payload = payload or {"session_id": "session-1"}
        with mock.patch.dict(os.environ, self.env, clear=False):
            return self.module.review_text(text, payload=payload, subject=subject)

    def test_rule_contract(self) -> None:
        rules = list(self.module.SEMANTIC_RULES)
        self.assertEqual({item["rule_id"] for item in rules}, EXPECTED_RULE_IDS)
        self.assertEqual(len(rules), len(EXPECTED_RULE_IDS))
        for item in rules:
            self.assertTrue(str(item.get("description", "")).strip())
            self.assertTrue(str(item.get("criteria", "")).strip())

    def test_interactions_request_and_structured_finding_contract(self) -> None:
        captured = {}
        finding = {
            "rule_id": "unsupported_fact_assertion",
            "reason": "根拠が示されていない断定です。",
            "excerpt": "必ず成功する。",
            "suggestion": "推測として表現する。",
        }

        def fake_open(_self, request, data=None, timeout=None):
            captured["request"] = request
            captured["timeout"] = timeout
            return io.BytesIO(interaction_payload([finding]))

        with mock.patch.object(urllib.request.OpenerDirector, "open", new=fake_open):
            result = self.review()

        request = captured["request"]
        self.assertEqual(request.full_url, "https://generativelanguage.googleapis.com/v1beta/interactions")
        self.assertEqual(request.get_header("X-goog-api-key"), "test-api-key")
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["model"], "gemini-3.8-flash")
        self.assertIs(body["store"], False)
        self.assertEqual(body["response_format"]["type"], "text")
        self.assertEqual(body["response_format"]["mime_type"], "application/json")
        self.assertEqual(body["response_format"]["schema"]["type"], "object")
        self.assertIn("findings", body["response_format"]["schema"]["required"])
        self.assertNotIn("test-api-key", json.dumps(body))
        self.assertGreater(captured["timeout"], 0)
        self.assertLess(captured["timeout"], 120)
        self.assertEqual(result, {"decision": "repair", "findings": [finding]})

    def test_invalid_response_or_rule_fails_open(self) -> None:
        responses = [
            json.dumps(
                {
                    "status": "completed",
                    "steps": [
                        {
                            "type": "model_output",
                            "content": [{"type": "text", "text": '{"findings":"not-a-list"}'}],
                        }
                    ],
                }
            ).encode(),
            interaction_payload(
                [
                    {
                        "rule_id": "unknown-rule",
                        "reason": "unknown",
                        "excerpt": "target",
                        "suggestion": "",
                    }
                ]
            ),
        ]
        for index, response in enumerate(responses):
            with self.subTest(index=index):
                def fake_open(_self, request, data=None, timeout=None, response=response):
                    return io.BytesIO(response)

                with mock.patch.object(urllib.request.OpenerDirector, "open", new=fake_open):
                    self.assertIsNone(self.review(subject=f"fixture:invalid-{index}"))

    def test_missing_key_and_empty_text_do_not_call_network(self) -> None:
        def fail_if_called(*_args, **_kwargs):
            raise AssertionError("network must not be called")

        with mock.patch.object(urllib.request.OpenerDirector, "open", new=fail_if_called):
            with mock.patch.dict(
                os.environ,
                {"TEXTLINT_HOOK_STATE_DIR": str(self.state_dir)},
                clear=True,
            ):
                self.assertIsNone(
                    self.module.review_text(
                        "Review target",
                        payload={"session_id": "missing-key"},
                        subject="fixture:missing-key",
                    )
                )
            self.assertIsNone(self.review(" \n\t", subject="fixture:empty"))

    def test_network_retry_and_nonretryable_4xx(self) -> None:
        calls = 0

        def retry_once(_self, request, data=None, timeout=None):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise urllib.error.URLError("temporary")
            return io.BytesIO(interaction_payload([]))

        with mock.patch.object(urllib.request.OpenerDirector, "open", new=retry_once):
            self.assertEqual(self.review(subject="fixture:network-retry")["decision"], "clean")
        self.assertEqual(calls, 2)

        calls = 0

        def no_retry(_self, request, data=None, timeout=None):
            nonlocal calls
            calls += 1
            raise urllib.error.HTTPError(request.full_url, 401, "unauthorized", None, None)

        with mock.patch.object(urllib.request.OpenerDirector, "open", new=no_retry):
            self.assertIsNone(self.review(subject="fixture:401"))
        self.assertEqual(calls, 1)

    def test_retryable_5xx_retries_once(self) -> None:
        calls = 0

        def fake_open(_self, request, data=None, timeout=None):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise urllib.error.HTTPError(request.full_url, 503, "unavailable", None, None)
            return io.BytesIO(interaction_payload([]))

        with mock.patch.object(urllib.request.OpenerDirector, "open", new=fake_open):
            self.assertEqual(self.review(subject="fixture:503")["decision"], "clean")
        self.assertEqual(calls, 2)

    def test_same_and_changing_findings_are_bounded(self) -> None:
        same = {
            "rule_id": "unsupported_fact_assertion",
            "reason": "same",
            "excerpt": "same target",
            "suggestion": "revise minimally",
        }

        def same_open(_self, request, data=None, timeout=None):
            return io.BytesIO(interaction_payload([same]))

        payload = {"session_id": "same-session"}
        with mock.patch.object(urllib.request.OpenerDirector, "open", new=same_open):
            first = self.review(payload=payload, subject="fixture:same")
            second = self.review(payload=payload, subject="fixture:same")
        self.assertEqual([first["decision"], second["decision"]], ["repair", "report"])

        calls = 0

        def changing_open(_self, request, data=None, timeout=None):
            nonlocal calls
            calls += 1
            return io.BytesIO(
                interaction_payload(
                    [
                        {
                            "rule_id": "unsupported_fact_assertion",
                            "reason": f"reason-{calls}",
                            "excerpt": f"target-{calls}",
                            "suggestion": "revise minimally",
                        }
                    ]
                )
            )

        payload = {"session_id": "changing-session"}
        with mock.patch.object(urllib.request.OpenerDirector, "open", new=changing_open):
            results = [
                self.review(payload=payload, subject="fixture:changing")
                for _ in range(4)
            ]
        self.assertEqual(
            [item["decision"] for item in results],
            ["repair", "repair", "repair", "report"],
        )


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

    def clean_textlint(self) -> None:
        self.install_textlint(
            'target=""\nfix=0\nfor arg in "$@"; do [ "$arg" = "--fix" ] && fix=1; target="$arg"; done\n'
            "if [ \"$fix\" -eq 1 ]; then exit 0; fi\nprintf '%s\\n' '[]'\nexit 0\n"
        )

    def install_runtime(self, hook: Path, semantic_body: str) -> Path:
        target = self.runtime / hook.name
        shutil.copy2(hook, target)
        shutil.copy2(TEXTLINT_BOUNDARY, self.runtime / TEXTLINT_BOUNDARY.name)
        if hook == PRE_HOOK:
            shutil.copy2(POST_HOOK, self.runtime / POST_HOOK.name)
        (self.runtime / "semantic-review.py").write_text(semantic_body, encoding="utf-8")
        return target

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
    def semantic_module(decision: str = "repair", marker: Path | None = None, capture: Path | None = None) -> str:
        imports = "from pathlib import Path\n" if marker or capture else ""
        lines = [imports, "def review_text(text, *args, **kwargs):\n"]
        if marker:
            lines.append(f"    Path({str(marker)!r}).write_text('called', encoding='utf-8')\n")
        if capture:
            lines.append(f"    Path({str(capture)!r}).write_text(text, encoding='utf-8')\n")
        if decision == "clean":
            lines.append("    return {'decision': 'clean', 'findings': []}\n")
        else:
            lines.append(
                "    return {'decision': '" + decision + "', 'findings': [{"
                "'rule_id': 'unsupported_fact_assertion', "
                "'reason': '根拠のない断定です。', "
                "'excerpt': '必ず成功する。', "
                "'suggestion': '推測として表現する。'}]}\n"
            )
        return "".join(lines)

    def notion_payload(self, content: str = "この案は必ず成功する。") -> dict:
        return {
            "session_id": "pre-session",
            "tool_name": "mcp__codex_apps__notion_notion_create_pages",
            "tool_input": {"pages": [{"content": content}]},
        }

    def post_payload(self, target: Path, exit_code: int = 0) -> dict:
        return {
            "session_id": "post-session",
            "tool_name": "exec_command",
            "tool_input": {"cmd": f"touch {target}"},
            "tool_response": {"exit_code": exit_code},
            "cwd": str(self.root),
        }

    def test_pretool_reviews_textlint_fixed_text_then_denies_without_rewrite(self) -> None:
        capture = self.root / "semantic-input"
        self.install_textlint(
            'target=""\nfor arg in "$@"; do target="$arg"; done\n'
            "sed -i '' 's/MacOS/macOS/g' \"$target\" 2>/dev/null || sed -i 's/MacOS/macOS/g' \"$target\"\nexit 0\n"
        )
        hook = self.install_runtime(PRE_HOOK, self.semantic_module("repair", capture=capture))
        output = json.loads(self.run_hook(hook, self.notion_payload("MacOS is always safe.")))
        specific = output["hookSpecificOutput"]
        self.assertEqual(specific["permissionDecision"], "deny")
        self.assertNotIn("updatedInput", specific)
        self.assertIn("unsupported_fact_assertion", json.dumps(output, ensure_ascii=False))
        self.assertEqual(capture.read_text(encoding="utf-8"), "macOS is always safe.")

    def test_pretool_empty_and_nontarget_skip_semantic_review(self) -> None:
        marker = self.root / "semantic-called"
        self.install_textlint("exit 0\n")
        hook = self.install_runtime(PRE_HOOK, self.semantic_module(marker=marker))
        self.assertEqual(self.run_hook(hook, self.notion_payload(" \n\t")), "")
        self.assertFalse(marker.exists())
        payload = {
            "session_id": "pre-session",
            "tool_name": "mcp__codex_apps__read_page",
            "tool_input": {"page_id": "example"},
        }
        self.assertEqual(self.run_hook(hook, payload), "")
        self.assertFalse(marker.exists())

    def test_posttool_textlint_residual_skips_semantic_review(self) -> None:
        marker = self.root / "semantic-called"
        self.install_textlint(
            'target=""\nfix=0\nfor arg in "$@"; do [ "$arg" = "--fix" ] && fix=1; target="$arg"; done\n'
            "if [ \"$fix\" -eq 1 ]; then exit 1; fi\n"
            "printf '[{\"filePath\":\"%s\",\"messages\":[{\"ruleId\":\"textlint-residual\",\"line\":1,\"column\":1,\"message\":\"residual\"}]}]\\n' \"$target\"\nexit 1\n"
        )
        hook = self.install_runtime(POST_HOOK, self.semantic_module(marker=marker))
        target = self.root / "residual.md"
        target.write_text("Residual text", encoding="utf-8")
        output = json.loads(self.run_hook(hook, self.post_payload(target)))
        self.assertFalse(marker.exists())
        self.assertIn("textlint-residual", output["hookSpecificOutput"]["additionalContext"])

    def test_posttool_repair_and_report_contexts(self) -> None:
        self.clean_textlint()
        target = self.root / "clean.md"
        target.write_text("この案は必ず成功する。", encoding="utf-8")
        repair_hook = self.install_runtime(POST_HOOK, self.semantic_module("repair"))
        repair = json.loads(self.run_hook(repair_hook, self.post_payload(target)))
        repair_context = repair["hookSpecificOutput"]["additionalContext"]
        self.assertIn("unsupported_fact_assertion", repair_context)
        self.assertIn(str(target), repair_context)

        report_hook = self.install_runtime(POST_HOOK, self.semantic_module("report"))
        report = json.loads(self.run_hook(report_hook, self.post_payload(target)))
        report_context = report["hookSpecificOutput"]["additionalContext"]
        self.assertIn("ユーザー", report_context)
        self.assertNotIn("最小修正を通常のwrite toolで行ってください", report_context)

    def test_posttool_unsupported_failed_and_no_candidate_skip_semantic_review(self) -> None:
        marker = self.root / "semantic-called"
        self.clean_textlint()
        hook = self.install_runtime(POST_HOOK, self.semantic_module(marker=marker))

        unsupported = self.root / "unsupported.py"
        unsupported.write_text("print('hello')\n", encoding="utf-8")
        self.assertEqual(
            json.loads(self.run_hook(hook, self.post_payload(unsupported))),
            {"continue": True},
        )
        self.assertFalse(marker.exists())

        failed = self.root / "failed.md"
        failed.write_text("Review target", encoding="utf-8")
        self.assertEqual(
            json.loads(self.run_hook(hook, self.post_payload(failed, exit_code=1))),
            {"continue": True},
        )
        self.assertFalse(marker.exists())

        no_candidate = {
            "session_id": "post-session",
            "tool_name": "mcp__codex_apps__read_page",
            "tool_input": {"path": "ignored.md"},
            "tool_response": {"success": True},
            "cwd": str(self.root),
        }
        self.assertEqual(json.loads(self.run_hook(hook, no_candidate)), {"continue": True})
        self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
