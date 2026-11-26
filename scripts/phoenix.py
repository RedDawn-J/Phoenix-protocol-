#!/usr/bin/env python3
"""Phoenix local runtime launcher and prerequisite doctor.

This launcher currently supervises the dependency-free J browser workspace.
It does not claim to package the full FastAPI + React IDE yet.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENDPOINT = os.environ.get(
    "J_CLI_ENDPOINT", "http://127.0.0.1:11434/v1/chat/completions"
)
DEFAULT_MODEL = os.environ.get("J_CLI_MODEL", "qwen2.5:7b")


def _is_loopback_endpoint(endpoint: str) -> bool:
    try:
        parsed = urlparse(endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return False
        addresses = socket.getaddrinfo(
            parsed.hostname,
            parsed.port or (443 if parsed.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
        return bool(addresses) and all(
            ipaddress.ip_address(item[4][0]).is_loopback for item in addresses
        )
    except (OSError, ValueError):
        return False


def check_environment(workspace: Path, endpoint: str, model: str) -> list[dict[str, Any]]:
    """Return actionable local runtime checks without changing the machine."""
    checks: list[dict[str, Any]] = []

    checks.append({
        "name": "python",
        "ok": sys.version_info >= (3, 10),
        "detail": f"{sys.version.split()[0]} (requires Python 3.10+)",
    })
    checks.append({
        "name": "runtime_files",
        "ok": (ROOT / "scripts" / "j_ui_workspace.py").is_file()
              and (ROOT / "scripts" / "j_cli.py").is_file(),
        "detail": "J browser workspace and CLI sources are present",
    })

    resolved_workspace = workspace.expanduser().resolve()
    checks.append({
        "name": "workspace",
        "ok": resolved_workspace.is_dir(),
        "detail": str(resolved_workspace) if resolved_workspace.is_dir()
                  else f"Directory does not exist: {resolved_workspace}",
    })
    checks.append({
        "name": "model_endpoint",
        "ok": bool(_is_loopback_endpoint(endpoint)),
        "detail": endpoint if _is_loopback_endpoint(endpoint)
                  else "Endpoint must resolve to a loopback address (localhost/127.0.0.1/::1)",
    })
    checks.append({
        "name": "model_selection",
        "ok": bool(model.strip()),
        "detail": model.strip() or "Set J_CLI_MODEL or pass --model",
    })
    return checks


def probe_model(endpoint: str, timeout: float = 2.0) -> tuple[bool, str]:
    """Probe the OpenAI-compatible /models route; never send workspace data."""
    parsed = urlparse(endpoint)
    models_url = endpoint.rsplit("/chat/completions", 1)[0] + "/models"
    try:
        request = Request(models_url, headers={"Accept": "application/json"})
        with urlopen(request, timeout=timeout) as response:
            if 200 <= response.status < 300:
                return True, f"Model endpoint reachable ({models_url})"
            return False, f"Model endpoint returned HTTP {response.status}"
    except HTTPError as exc:
        return False, f"Model endpoint returned HTTP {exc.code}"
    except (URLError, TimeoutError, OSError) as exc:
        return False, f"Model endpoint not reachable: {exc}"


def _print_checks(checks: list[dict[str, Any]], as_json: bool) -> int:
    if as_json:
        print(json.dumps({"ok": all(item["ok"] for item in checks), "checks": checks}, indent=2))
    else:
        for item in checks:
            marker = "OK" if item["ok"] else "BLOCKED"
            print(f"[{marker:7}] {item['name']}: {item['detail']}")
        if all(item["ok"] for item in checks):
            print("\nPhoenix local runtime prerequisites look good.")
        else:
            print("\nResolve the BLOCKED checks before starting Phoenix.")
    return 0 if all(item["ok"] for item in checks) else 1


def doctor(args: argparse.Namespace) -> int:
    checks = check_environment(Path(args.workspace), args.endpoint, args.model)
    if args.probe_model and _is_loopback_endpoint(args.endpoint):
        ok, detail = probe_model(args.endpoint)
        checks.append({"name": "model_service", "ok": ok, "detail": detail})
    return _print_checks(checks, args.json)


def start(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).expanduser().resolve()
    if not workspace.exists():
        if not args.create_workspace:
            print(f"Workspace does not exist: {workspace}", file=sys.stderr)
            print("Pass --create-workspace to create it.", file=sys.stderr)
            return 2
        workspace.mkdir(parents=True, exist_ok=True)

    checks = check_environment(workspace, args.endpoint, args.model)
    status = _print_checks(checks, False)
    if status:
        return status

    command = [
        sys.executable, "-m", "scripts.j_ui_workspace",
        "--host", "127.0.0.1",
        "--port", str(args.port),
        "--endpoint", args.endpoint,
        "--model", args.model,
        "--workspace", str(workspace),
        "--timeout", str(args.timeout),
    ]
    if args.api_key:
        command.extend(["--api-key", args.api_key])
    if args.system_prompt:
        command.extend(["--system-prompt", str(Path(args.system_prompt).expanduser().resolve())])

    print(f"\nStarting Phoenix local workspace at http://127.0.0.1:{args.port}")
    print("Stop with Ctrl+C. Shell commands run with your OS account permissions.")
    try:
        return subprocess.call(command, cwd=ROOT)
    except KeyboardInterrupt:
        return 130


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Phoenix local-first runtime launcher (headless browser workspace milestone)."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor_parser = subparsers.add_parser("doctor", help="check local runtime prerequisites")
    doctor_parser.add_argument("--workspace", default=str(Path.cwd()))
    doctor_parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    doctor_parser.add_argument("--model", default=DEFAULT_MODEL)
    doctor_parser.add_argument("--probe-model", action="store_true",
                               help="make a short GET request to the local /models endpoint")
    doctor_parser.add_argument("--json", action="store_true")
    doctor_parser.set_defaults(handler=doctor)

    start_parser = subparsers.add_parser("start", help="start the local browser workspace")
    start_parser.add_argument("--workspace", default=str(Path.cwd()))
    start_parser.add_argument("--create-workspace", action="store_true")
    start_parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    start_parser.add_argument("--model", default=DEFAULT_MODEL)
    start_parser.add_argument("--api-key", default=os.environ.get("J_CLI_API_KEY", ""))
    start_parser.add_argument("--system-prompt", default=None)
    start_parser.add_argument("--port", type=int, default=8765)
    start_parser.add_argument("--timeout", type=int, default=120)
    start_parser.set_defaults(handler=start_parser_handler)
    return parser


def start_parser_handler(args: argparse.Namespace) -> int:
    if not 1 <= args.port <= 65535:
        print("--port must be between 1 and 65535", file=sys.stderr)
        return 2
    if args.timeout < 1:
        print("--timeout must be positive", file=sys.stderr)
        return 2
    return start(args)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
