"""Tests for the Phoenix launcher and local prerequisite doctor."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import phoenix


class PhoenixDoctorTests(unittest.TestCase):
    def test_reports_missing_workspace(self) -> None:
        checks = phoenix.check_environment(
            Path("/path/that/does/not/exist"),
            "http://127.0.0.1:11434/v1/chat/completions",
            "qwen2.5:7b",
        )
        workspace = next(item for item in checks if item["name"] == "workspace")
        self.assertFalse(workspace["ok"])

    def test_rejects_non_loopback_model_endpoint(self) -> None:
        with patch("scripts.phoenix.socket.getaddrinfo",
                   return_value=[(2, 1, 6, "", ("203.0.113.10", 11434))]):
            checks = phoenix.check_environment(
                Path.cwd(),
                "http://model.example:11434/v1/chat/completions",
                "qwen2.5:7b",
            )
        endpoint = next(item for item in checks if item["name"] == "model_endpoint")
        self.assertFalse(endpoint["ok"])

    def test_accepts_loopback_model_endpoint(self) -> None:
        with patch("scripts.phoenix.socket.getaddrinfo",
                   return_value=[(2, 1, 6, "", ("127.0.0.1", 11434))]):
            self.assertTrue(phoenix._is_loopback_endpoint(
                "http://127.0.0.1:11434/v1/chat/completions"
            ))

    def test_workspace_can_be_created_only_when_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "new-workspace"
            args = type("Args", (), {
                "workspace": str(target),
                "create_workspace": False,
                "endpoint": "http://127.0.0.1:11434/v1/chat/completions",
                "model": "qwen2.5:7b",
                "port": 8765,
                "timeout": 120,
                "api_key": "",
                "system_prompt": None,
            })()
            self.assertEqual(phoenix.start(args), 2)
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
