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
            "GEMINI_API_KEY": "environment-key-must-be-ignored",
            "TEXTLINT_HOOK_STATE_DIR": str(self.state_dir),
        }

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def review(self, text: str = "Review target", *, subject: str = "fixture:document", payload=None):
        payload = payload or {"session_id": "session-1"}
        keychain_result = subprocess.CompletedProcess(
            ["/usr/bin/security", "find-generic-password"], 0,
            stdout="keychain-test-secret\n", stderr="",
        )
        with mock.patch.dict(os.environ, self.env, clear=False):
            with mock.patch.object(subprocess, "run", return_value=keychain_result):
                return self.module.review_text(text, payload=payload, subject=subject)

    def test_rule_contract(self) -> None:
        rules = list(self.module.SEMANTIC_RULES)
        rule_ids = [item["rule_id"] for item in rules]
        self.assertTrue(EXPECTED_RULE_IDS.issubset(set(rule_ids)))
        self.assertEqual(len(rule_ids), len(set(rule_ids)))
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
        self.assertEqual(request.get_header("X-goog-api-key"), "keychain-test-secret")
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["model"], "gemini-flash-latest")
        self.assertIs(body["store"], False)
        self.assertEqual(body["response_format"]["type"], "text")
        self.assertEqual(body["response_format"]["mime_type"], "application/json")
        self.assertEqual(body["response_format"]["schema"]["type"], "object")
        self.assertIn("findings", body["response_format"]["schema"]["required"])
        self.assertNotIn("keychain-test-secret", json.dumps(body))
        self.assertNotIn("environment-key-must-be-ignored", json.dumps(body))
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
            with mock.patch.dict(os.environ, self.env, clear=False):
                with mock.patch.object(
                    subprocess, "run",
                    return_value=subprocess.CompletedProcess(
                        ["security"], 44, stdout="", stderr="keychain unavailable"
                    ),
                ):
                    self.assertIsNone(
                        self.module.review_text(
                            "Review target",
                            payload={"session_id": "missing-key"},
                            subject="fixture:missing-key",
                        )
                    )
            self.assertIsNone(self.review(" \n\t", subject="fixture:empty"))

    def test_keychain_lookup_contract_and_environment_independence(self) -> None:
        keychain = mock.Mock(
            return_value=subprocess.CompletedProcess(
                ["security"], 0, stdout="keychain-test-secret\n", stderr=""
            )
        )
        captured = {}

        def fake_open(_self, request, data=None, timeout=None):
            captured["request"] = request
            return io.BytesIO(interaction_payload([]))

        with mock.patch.dict(os.environ, self.env, clear=False):
            with mock.patch.object(subprocess, "run", keychain):
                with mock.patch.object(urllib.request.OpenerDirector, "open", new=fake_open):
                    result = self.module.review_text(
                        "Review target",
                        payload={"session_id": "keychain-contract"},
                        subject="fixture:keychain-contract",
                    )
        self.assertEqual(result["decision"], "clean")
        keychain.assert_called_once()
        args, kwargs = keychain.call_args
        self.assertEqual(
            args[0],
            ["/usr/bin/security", "find-generic-password",
             "-s", "my.gemini-api.codex-hooks", "-a", "api-key", "-w"],
        )
        self.assertGreater(kwargs["timeout"], 0)
        self.assertLess(kwargs["timeout"], 120)
        self.assertEqual(captured["request"].get_header("X-goog-api-key"), "keychain-test-secret")
        self.assertNotEqual(captured["request"].get_header("X-goog-api-key"), self.env["GEMINI_API_KEY"])

    def test_keychain_failures_fail_open_without_network_or_env_fallback(self) -> None:
        failures = (
            subprocess.CompletedProcess(["security"], 44, stdout="", stderr="denied"),
            subprocess.CompletedProcess(["security"], 0, stdout=" \n", stderr=""),
            subprocess.TimeoutExpired(["security"], timeout=1),
            OSError("security unavailable"),
        )
        with mock.patch.dict(os.environ, self.env, clear=False):
            for index, failure in enumerate(failures):
                with self.subTest(index=index):
                    kwargs = {"side_effect": failure} if isinstance(failure, Exception) else {"return_value": failure}
                    with mock.patch.object(subprocess, "run", **kwargs):
                        with mock.patch.object(
                            urllib.request.OpenerDirector, "open",
                            side_effect=AssertionError("network called without Keychain credential"),
                        ) as network:
                            self.assertIsNone(
                                self.module.review_text(
                                    "Review target",
                                    payload={"session_id": f"keychain-failure-{index}"},
                                    subject=f"fixture:keychain-failure-{index}",
                                )
                            )
                            network.assert_not_called()

    def test_keychain_secret_and_security_stderr_not_recorded(self) -> None:
        secret = "keychain-test-secret"
        diagnostic = Path(self.temp_dir.name) / "diagnostic.jsonl"
        finding = {
            "rule_id": "unsupported_fact_assertion",
            "reason": "根拠がありません。",
            "excerpt": "必ず成功する。",
            "suggestion": "断定を避ける。",
        }

        def fake_open(_self, request, data=None, timeout=None):
            return io.BytesIO(interaction_payload([finding]))

        env = {**self.env, "TEXTLINT_HOOK_DIAGNOSTIC_LOG": str(diagnostic)}
        with mock.patch.dict(os.environ, env, clear=False):
            with mock.patch.object(
                subprocess, "run",
                return_value=subprocess.CompletedProcess(
                    ["security"], 0, stdout=secret + "\n",
                    stderr="SECURITY_STDERR_SENSITIVE",
                ),
            ):
                with mock.patch.object(urllib.request.OpenerDirector, "open", new=fake_open):
                    result = self.module.review_text(
                        "この案は必ず成功する。",
                        payload={"session_id": "secret-redaction"},
                        subject="fixture:secret-redaction",
                    )
        self.assertEqual(result["decision"], "repair")
        self.assertNotIn(secret, json.dumps(result, ensure_ascii=False))
        self.assertNotIn("SECURITY_STDERR_SENSITIVE", json.dumps(result, ensure_ascii=False))
        artifacts = list(self.state_dir.rglob("*")) if self.state_dir.exists() else []
        if diagnostic.exists():
            artifacts.append(diagnostic)
        for artifact in artifacts:
            if artifact.is_file():
                recorded = artifact.read_text(encoding="utf-8")
                self.assertNotIn(secret, recorded)
                self.assertNotIn("SECURITY_STDERR_SENSITIVE", recorded)
                self.assertNotIn("この案は必ず成功する。", recorded)

    def test_same_finding_stop_skips_subsequent_api_calls(self) -> None:
        finding = {
            "rule_id": "unsupported_fact_assertion",
            "reason": "unsupported",
            "excerpt": "必ず成功する。",
            "suggestion": "根拠を示す。",
        }
        calls = 0

        def fake_open(_self, request, data=None, timeout=None):
            nonlocal calls
            calls += 1
            return io.BytesIO(interaction_payload([finding]))

        payload = {"session_id": "same-stop"}
        with mock.patch.object(urllib.request.OpenerDirector, "open", new=fake_open):
            decisions = [
                self.review(
                    "必ず成功する。",
                    payload=payload,
                    subject="fixture:same-stop",
                )
                for _ in range(5)
            ]
        self.assertEqual(
            [item["decision"] if item is not None else None for item in decisions],
            ["repair", "report", None, None, None],
        )
        self.assertEqual(calls, 2, "停止後の入力はGemini APIを再呼出ししない")

    def test_changed_finding_retry_limit_skips_subsequent_api_calls(self) -> None:
        calls = 0

        def fake_open(_self, request, data=None, timeout=None):
            nonlocal calls
            calls += 1
            finding = {
                "rule_id": "unsupported_fact_assertion",
                "reason": f"reason-{calls}",
                "excerpt": f"excerpt-{calls}",
                "suggestion": "根拠を示す。",
            }
            return io.BytesIO(interaction_payload([finding]))

        payload = {"session_id": "limit-stop"}
        with mock.patch.object(urllib.request.OpenerDirector, "open", new=fake_open):
            decisions = [
                self.review(
                    "検証する必要があります。",
                    payload=payload,
                    subject="fixture:limit-stop",
                )
                for _ in range(7)
            ]
        self.assertEqual(
            [item["decision"] if item is not None else None for item in decisions],
            ["repair", "repair", "repair", "report", None, None, None],
        )
        self.assertEqual(calls, 4, "回数上限後の入力はGemini APIを再呼出ししない")

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

    def test_pretool_textlint_unchanged_semantic_finding_denies_without_rewrite(self) -> None:
        capture = self.root / "reviewed-unchanged-text"
        self.clean_textlint()
        hook = self.install_runtime(
            PRE_HOOK, self.semantic_module("repair", capture=capture)
        )
        content = "この案は必ず成功する。"
        output = json.loads(self.run_hook(hook, self.notion_payload(content)))
        specific = output["hookSpecificOutput"]
        self.assertEqual(specific["hookEventName"], "PreToolUse")
        self.assertEqual(specific["permissionDecision"], "deny")
        self.assertNotIn("updatedInput", specific)
        self.assertIn("unsupported_fact_assertion", json.dumps(output, ensure_ascii=False))
        self.assertIn("最小修正", json.dumps(output, ensure_ascii=False))
        self.assertEqual(capture.read_text(encoding="utf-8"), content)

    def test_pretool_textlint_unchanged_semantic_clean_allows_without_rewrite(self) -> None:
        marker = self.root / "semantic-reviewed"
        self.clean_textlint()
        hook = self.install_runtime(
            PRE_HOOK, self.semantic_module("clean", marker=marker)
        )
        output = self.run_hook(hook, self.notion_payload("既存の事実を確認しました。"))
        self.assertTrue(marker.exists(), "textlint無変更でもsemantic reviewを実施する")
        if output.strip():
            specific = json.loads(output)["hookSpecificOutput"]
            self.assertEqual(specific["permissionDecision"], "allow")
            self.assertNotIn("updatedInput", specific)
        else:
            self.assertEqual(output, "")

    def test_pretool_after_semantic_stop_does_not_deny_again(self) -> None:
        self.clean_textlint()
        state = self.root / "semantic-decision-count"
        stub = (
            "from pathlib import Path\n"
            f"_state = Path({str(state)!r})\n"
            "def review_text(text, *args, **kwargs):\n"
            "    n = int(_state.read_text()) if _state.exists() else 0\n"
            "    _state.write_text(str(n + 1))\n"
            "    if n >= 2:\n"
            "        return None\n"
            "    finding = {'rule_id': 'unsupported_fact_assertion',"
            " 'reason': '根拠がありません。', 'excerpt': '必ず成功する。',"
            " 'suggestion': '根拠を示す。'}\n"
            "    return {'decision': 'repair' if n == 0 else 'report',"
            " 'findings': [finding]}\n"
        )
        hook = self.install_runtime(PRE_HOOK, stub)
        payload = self.notion_payload("この案は必ず成功する。")
        first = json.loads(self.run_hook(hook, payload))["hookSpecificOutput"]
        second = json.loads(self.run_hook(hook, payload))["hookSpecificOutput"]
        third = self.run_hook(hook, payload)
        self.assertEqual(first["permissionDecision"], "deny")
        self.assertNotEqual(second.get("permissionDecision"), "deny")
        self.assertNotIn("updatedInput", second)
        self.assertEqual(third, "", "停止済みの次入力でdenyを再開しない")

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

    def test_posttool_after_semantic_stop_does_not_request_repair_again(self) -> None:
        self.clean_textlint()
        target = self.root / "semantic-stopped.md"
        target.write_text("この案は必ず成功する。", encoding="utf-8")
        state = self.root / "semantic-decision-count"
        stub = (
            "from pathlib import Path\n"
            f"_state = Path({str(state)!r})\n"
            "def review_text(text, *args, **kwargs):\n"
            "    n = int(_state.read_text()) if _state.exists() else 0\n"
            "    _state.write_text(str(n + 1))\n"
            "    if n >= 2:\n"
            "        return None\n"
            "    finding = {'rule_id': 'unsupported_fact_assertion',"
            " 'reason': '根拠がありません。', 'excerpt': '必ず成功する。',"
            " 'suggestion': '根拠を示す。'}\n"
            "    return {'decision': 'repair' if n == 0 else 'report',"
            " 'findings': [finding]}\n"
        )
        hook = self.install_runtime(POST_HOOK, stub)
        payload = self.post_payload(target)
        first = json.loads(self.run_hook(hook, payload))["hookSpecificOutput"]["additionalContext"]
        second = json.loads(self.run_hook(hook, payload))["hookSpecificOutput"]["additionalContext"]
        third = json.loads(self.run_hook(hook, payload))
        self.assertIn("最小修正", first)
        self.assertIn("ユーザー", second)
        self.assertNotIn("最小修正を通常のwrite toolで行ってください", second)
        self.assertEqual(third, {"continue": True}, "停止済みの次入力で追加修正を要求しない")

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


    def test_pretool_semantic_failure_keeps_deterministic_textlint_fix(self) -> None:
        self.install_textlint(
            'target=""\nfor arg in "$@"; do target="$arg"; done\n'
            "sed -i '' 's/MacOS/macOS/g' \"$target\" 2>/dev/null || sed -i 's/MacOS/macOS/g' \"$target\"\nexit 0\n"
        )
        hook = self.install_runtime(
            PRE_HOOK, "def review_text(text, *args, **kwargs):\n    return None\n"
        )
        output = json.loads(self.run_hook(hook, self.notion_payload("MacOS is clear.")))
        specific = output["hookSpecificOutput"]
        self.assertEqual(specific["permissionDecision"], "allow")
        self.assertEqual(specific["updatedInput"]["pages"][0]["content"], "macOS is clear.")

    def test_posttool_unverified_textlint_clean_does_not_call_semantic_api(self) -> None:
        marker = self.root / "semantic-called"
        self.install_textlint(
            'target=""\nfor arg in "$@"; do target="$arg"; done\n'
            'printf "%s\\n" "{malformed json"\nexit 1\n'
        )
        hook = self.install_runtime(POST_HOOK, self.semantic_module(marker=marker))
        target = self.root / "undetermined.md"
        target.write_text("Review target", encoding="utf-8")
        self.assertEqual(
            json.loads(self.run_hook(hook, self.post_payload(target))),
            {"continue": True},
        )
        self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
