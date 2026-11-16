"""Tests for the local J file editor and terminal UI."""
from __future__ import annotations

import json
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scripts import j_ui_workspace


class LocalWorkspaceUiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name).resolve()
        (self.root / "nested").mkdir()
        (self.root / "nested" / "sample.txt").write_text("hello local", encoding="utf-8")
        handler = j_ui_workspace.make_workspace_handler(
            "http://127.0.0.1:11434/v1/chat/completions",
            "test-model",
            "",
            "system rules",
            self.root,
            2,
        )
        self.server = j_ui_workspace.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.thread.join, 2)
        self.port = self.server.server_address[1]

    def _request(self, method: str, path: str, payload: dict | None = None, headers: dict | None = None):
        connection = HTTPConnection("127.0.0.1", self.port, timeout=5)
        body = json.dumps(payload) if payload is not None else None
        request_headers = {"Content-Type": "application/json", **(headers or {})}
        connection.request(method, path, body=body, headers=request_headers)
        response = connection.getresponse()
        result = json.loads(response.read())
        status = response.status
        connection.close()
        return status, result

    def test_root_serves_editor_and_terminal(self) -> None:
        connection = HTTPConnection("127.0.0.1", self.port, timeout=5)
        connection.request("GET", "/")
        response = connection.getresponse()
        body = response.read().decode("utf-8")
        connection.close()
        self.assertEqual(response.status, 200)
        self.assertIn("file-editor", body)
        self.assertIn("shell-command-input", body)
        self.assertIn("save-file-btn", body)

    def test_workspace_file_write_and_read(self) -> None:
        status, body = self._request("POST", "/api/file/write", {"path": "nested/changed.txt", "content": "updated"})
        self.assertEqual(status, 200)
        self.assertEqual(body["path"], "nested/changed.txt")
        self.assertEqual((self.root / "nested" / "changed.txt").read_text(encoding="utf-8"), "updated")

        status, body = self._request("GET", "/api/file?path=nested%2Fchanged.txt")
        self.assertEqual(status, 200)
        self.assertEqual(body["content"], "updated")

    def test_write_rejects_path_outside_workspace(self) -> None:
        status, body = self._request("POST", "/api/file/write", {"path": "../outside.txt", "content": "bad"})
        self.assertEqual(status, 400)
        self.assertIn("escapes", body["error"])

    def test_shell_runs_in_workspace_root(self) -> None:
        status, body = self._request("POST", "/api/command", {"command": "pwd"})
        self.assertEqual(status, 200)
        self.assertEqual(body["exit_code"], 0)
        self.assertEqual(body["output"].strip(), str(self.root))

    def test_shell_rejects_empty_command(self) -> None:
        status, body = self._request("POST", "/api/command", {"command": "  "})
        self.assertEqual(status, 400)
        self.assertIn("non-empty", body["error"])

    def test_mutation_rejects_cross_origin(self) -> None:
        status, body = self._request(
            "POST",
            "/api/file/write",
            {"path": "blocked.txt", "content": "no"},
            {"Origin": "http://attacker.example"},
        )
        self.assertEqual(status, 403)
        self.assertIn("same-origin", body["error"])
        self.assertFalse((self.root / "blocked.txt").exists())

    @patch("scripts.j_ui_workspace.call_model", return_value="local reply")
    def test_chat_endpoint_remains_available(self, mocked_call_model) -> None:
        status, body = self._request("POST", "/api/chat", {"messages": [{"role": "user", "content": "hello"}]})
        self.assertEqual(status, 200)
        self.assertEqual(body["reply"], "local reply")


if __name__ == "__main__":
    unittest.main()
