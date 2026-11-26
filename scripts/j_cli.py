#!/usr/bin/env python3
"""Run J headlessly against a local OpenAI-compatible chat endpoint."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import TextIO
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_ENDPOINT = "http://127.0.0.1:11434/v1/chat/completions"
DEFAULT_MODEL = "qwen2.5:7b"
DEFAULT_TIMEOUT = 120


class HarnessError(RuntimeError):
    """An actionable failure while calling the local model endpoint."""


def _default_system_prompt() -> Path:
    return Path(__file__).resolve().parents[1] / "AGENTS.md"


def _load_system_prompt(path: Path | None, disabled: bool) -> str:
    if disabled:
        return ""
    prompt_path = path or _default_system_prompt()
    try:
        return prompt_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise HarnessError(f"cannot read system prompt {prompt_path}: {exc}") from exc


def _build_messages(system: str, history: list[dict[str, str]], user_text: str) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.extend(history)
    messages.append({"role": "user", "content": user_text})
    return messages


def call_model(
    endpoint: str,
    model: str,
    api_key: str,
    messages: list[dict[str, str]],
    timeout: int,
) -> str:
    """Send one chat-completions request and return the assistant text."""
    payload = json.dumps({"model": model, "messages": messages}).encode("utf-8")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = Request(endpoint, data=payload, headers=headers, method="POST")

    try:
        with urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise HarnessError(f"model endpoint returned HTTP {exc.code}: {detail}") from exc
    except (URLError, TimeoutError) as exc:
        raise HarnessError(f"cannot reach model endpoint {endpoint}: {exc}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HarnessError(f"model endpoint returned invalid JSON: {exc}") from exc

    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise HarnessError("model response is missing choices[0].message.content") from exc
    if not isinstance(content, str):
        raise HarnessError("model response content must be a string")
    return content


def _emit_response(text: str, model: str, as_json: bool) -> None:
    if as_json:
        print(json.dumps({"model": model, "response": text}, ensure_ascii=False))
    else:
        print(text)


def _run_once(args: argparse.Namespace, system: str, user_text: str) -> int:
    if not user_text.strip():
        raise HarnessError("prompt is empty")
    response = call_model(
        args.endpoint,
        args.model,
        args.api_key,
        _build_messages(system, [], user_text),
        args.timeout,
    )
    _emit_response(response, args.model, args.json)
    return 0


def _run_interactive(args: argparse.Namespace, system: str, stdin: TextIO) -> int:
    history: list[dict[str, str]] = []
    print("J headless · /clear resets context · /exit quits", file=sys.stderr)
    while True:
        try:
            user_text = input("you> ").strip()
        except EOFError:
            print(file=sys.stderr)
            return 0
        if not user_text:
            continue
        if user_text in {"/exit", "/quit"}:
            return 0
        if user_text == "/clear":
            history.clear()
            print("context cleared", file=sys.stderr)
            continue
        try:
            response = call_model(
                args.endpoint,
                args.model,
                args.api_key,
                _build_messages(system, history, user_text),
                args.timeout,
            )
        except HarnessError as exc:
            print(f"FAIL: {exc}", file=sys.stderr)
            continue
        history.extend([
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": response},
        ])
        _emit_response(response, args.model, args.json)
    return 0


def _read_prompt(args: argparse.Namespace, stdin: TextIO) -> str | None:
    if args.message is not None:
        return args.message
    if stdin.isatty():
        return None
    return stdin.read()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run J without the browser or backend, using a local chat-completions model."
    )
    parser.add_argument("--message", help="one-shot prompt; otherwise read stdin or start the REPL")
    parser.add_argument("--endpoint", default=os.environ.get("J_CLI_ENDPOINT", DEFAULT_ENDPOINT))
    parser.add_argument("--model", default=os.environ.get("J_CLI_MODEL", DEFAULT_MODEL))
    parser.add_argument("--api-key", default=os.environ.get("J_CLI_API_KEY", ""),
                        help="optional bearer token; may also be set with J_CLI_API_KEY")
    parser.add_argument("--system-prompt", type=Path, help="system prompt file (default: repository AGENTS.md)")
    parser.add_argument("--no-system-prompt", action="store_true", help="omit AGENTS.md from the request")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="request timeout in seconds")
    parser.add_argument("--json", action="store_true", help="emit one JSON object per response (NDJSON in REPL mode)")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.timeout < 1:
        parser.error("--timeout must be positive")
    if args.message is not None and not args.message.strip():
        parser.error("--message must not be empty")
    try:
        system = _load_system_prompt(args.system_prompt, args.no_system_prompt)
        prompt = _read_prompt(args, sys.stdin)
        if prompt is None:
            return _run_interactive(args, system, sys.stdin)
        return _run_once(args, system, prompt)
    except HarnessError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
