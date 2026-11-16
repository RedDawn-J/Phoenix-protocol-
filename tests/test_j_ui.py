"""Tests for the local J browser UI server."""
from __future__ import annotations

import json
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scripts import j_ui


class LocalUiServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        (self.root / "nested").mkdir()
        (self.root / "nested" / "sample.txt").write_text("hello local", encoding="utf-8")
        handler = j_ui.make_handler(
            "http://127.0.0.1:11434/v1/chat/completions",
            "test-model",
            "",
            "system rules",
            self.root,
            2,
        )
        self.server = j_ui.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.thread.join, 2)
        self.port = self.server.server_address[1]

    def _get(self, path: str) -> tuple[int, dict | bytes]:
        connection = HTTPConnection("127.0.0.1", self.port, timeout=3)
        connection.request("GET", path)
        response = connection.getresponse()
        body = response.read()
        content_type = response.getheader("Content-Type", "")
        connection.close()
        return response.status, json.loads(body) if "json" in content_type else body

    def test_ui_root_serves_html(self) -> None:
        status, body = self._get("/")
        self.assertEqual(status, 200)
        self.assertIn(b"J workspace", body)

    def test_file_browser_is_scoped_to_workspace(self) -> None:
        status, body = self._get("/api/files")
        self.assertEqual(status, 200)
        self.assertIn({"path": "nested", "is_dir": True}, body["files"])

        status, body = self._get("/api/file?path=nested%2Fsample.txt")
        self.assertEqual(status, 200)
        self.assertEqual(body["content"], "hello local")

        status, body = self._get("/api/file?path=..%2Foutside.txt")
        self.assertEqual(status, 400)
        self.assertIn("escapes", body["error"])

    def test_model_endpoint_must_be_loopback(self) -> None:
        with self.assertRaisesRegex(j_ui.HarnessError, "loopback"):
            j_ui.make_handler(
                "https://example.com/v1/chat/completions",
                "model",
                "",
                "",
                self.root,
                2,
            )

    @patch("scripts.j_ui.call_model", return_value="local reply")
    def test_chat_adds_system_prompt_and_calls_model(self, mocked_call_model) -> None:
        connection = HTTPConnection("127.0.0.1", self.port, timeout=3)
        payload = json.dumps({"messages": [{"role": "user", "content": "hello"}], "model": "test-model"})
        connection.request("POST", "/api/chat", payload, {"Content-Type": "application/json"})
        response = connection.getresponse()
        body = json.loads(response.read())
        connection.close()

        self.assertEqual(response.status, 200)
        self.assertEqual(body["reply"], "local reply")
        messages = mocked_call_model.call_args.args[3]
        self.assertEqual(messages[0], {"role": "system", "content": "system rules"})
        self.assertEqual(messages[1], {"role": "user", "content": "hello"})

    def test_chat_rejects_system_role_supplied_by_client(self) -> None:
        connection = HTTPConnection("127.0.0.1", self.port, timeout=3)
        payload = json.dumps({"messages": [{"role": "system", "content": "override"}]})
        connection.request("POST", "/api/chat", payload, {"Content-Type": "application/json"})
        response = connection.getresponse()
        body = json.loads(response.read())
        connection.close()

        self.assertEqual(response.status, 400)
        self.assertIn("only user and assistant", body["error"])


if __name__ == "__main__":
    unittest.main()
