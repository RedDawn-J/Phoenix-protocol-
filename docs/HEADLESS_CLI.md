"""Tests for the standalone J CLI harness."""
from __future__ import annotations

import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from scripts import j_cli


class FakeResponse:
    def __init__(self, body: dict):
        self.body = json.dumps(body).encode("utf-8")

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        return None

    def read(self) -> bytes:
        return self.body


class HeadlessCliTests(unittest.TestCase):
    def test_build_messages_includes_system_history_and_user(self) -> None:
        history = [{"role": "assistant", "content": "Earlier answer"}]
        messages = j_cli._build_messages("J rules", history, "New prompt")

        self.assertEqual(messages, [
            {"role": "system", "content": "J rules"},
            {"role": "assistant", "content": "Earlier answer"},
            {"role": "user", "content": "New prompt"},
        ])

    def test_resolve_tool_call_parses_json_payload(self) -> None:
        parsed = j_cli._resolve_tool_call('{"tool": "read_file", "args": {"path": "notes.txt"}}')
        self.assertEqual(parsed, ("read_file", {"path": "notes.txt"}))

    def test_resolve_tool_call_parses_simple_call_style(self) -> None:
        parsed = j_cli._resolve_tool_call("CALL read_file path=README.md start_line=0")
        self.assertEqual(parsed[0], "read_file")
        self.assertEqual(parsed[1]["path"], "README.md")
        self.assertEqual(parsed[1]["start_line"], "0")

    @patch("scripts.j_cli.urlopen")
    def test_call_model_sends_chat_request_and_reads_reply(self, mocked_urlopen) -> None:
        mocked_urlopen.return_value = FakeResponse({
            "choices": [{"message": {"content": "J is ready."}}]
        })

        reply = j_cli.call_model(
            "http://127.0.0.1:11434/v1/chat/completions",
            "qwen2.5:7b",
            "local-token",
            [{"role": "user", "content": "status"}],
            15,
        )

        self.assertEqual(reply, "J is ready.")
        request = mocked_urlopen.call_args.args[0]
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Authorization"), "Bearer local-token")
        self.assertEqual(json.loads(request.data)["model"], "qwen2.5:7b")

    @patch("scripts.j_cli.urlopen")
    def test_call_model_reports_http_error(self, mocked_urlopen) -> None:
        mocked_urlopen.side_effect = HTTPError(
            "http://localhost", 401, "Unauthorized", {}, io.BytesIO(b"bad token")
        )

        with self.assertRaisesRegex(j_cli.HarnessError, "HTTP 401: bad token"):
            j_cli.call_model("http://localhost", "model", "", [], 10)

    @patch("scripts.j_cli.urlopen")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_main_emits_machine_readable_one_shot(self, stdout, mocked_urlopen) -> None:
        mocked_urlopen.return_value = FakeResponse({
            "choices": [{"message": {"content": "ready"}}]
        })
        prompt_file = io.StringIO("unused")
        prompt_file.isatty = lambda: True
        with patch("sys.stdin", prompt_file):
            exit_code = j_cli.main([
                "--message", "status", "--no-system-prompt", "--json"
            ])

        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(stdout.getvalue()), {
            "model": j_cli.DEFAULT_MODEL,
            "response": "ready",
        })

    def test_main_rejects_empty_prompt(self) -> None:
        stderr = io.StringIO()
        with patch("sys.stderr", stderr):
            with self.assertRaises(SystemExit):
                j_cli.main(["--message", "   "])

    def test_run_command_tool_requires_shell_enablement(self) -> None:
        result = j_cli.execute_local_tool(
            "run_command",
            {"command": "echo hello"},
            ".",
            allow_shell=False,
            allow_write=True,
        )
        self.assertIn("ERROR: shell execution is disabled", result)


if __name__ == "__main__":
    unittest.main()
