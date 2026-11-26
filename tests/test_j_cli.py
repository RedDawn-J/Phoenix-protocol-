#!/usr/bin/env python3
"""Offline J headless harness with optional local tool execution.

This version intentionally stays in the standard library. It talks to a local
OpenAI-compatible endpoint (such as Ollama) when available, and can also run a
small built-in tool loop against the local workspace when `--tool-mode` is used.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, TextIO
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_ENDPOINT = "http://127.0.0.1:11434/v1/chat/completions"
DEFAULT_MODEL = "qwen2.5:7b"
DEFAULT_TIMEOUT = 120


class HarnessError(RuntimeError):
    """An actionable failure during local CLI execution."""


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


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        first = text.find("\n")
        if first != -1:
            text = text[first + 1 :]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
    return text.strip()


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


def _resolve_tool_call(text: str) -> tuple[str, dict[str, Any]] | None:
    """Parse a JSON tool call or a simple CALL style tool call."""
    candidate = _strip_fences(text)
    if not candidate:
        return None

    json_match = re.search(r"\{\s*['\"]tool['\"]\s*:\s*['\"]([^'\"]+)['\"]", candidate, flags=re.S)
    if json_match:
        try:
            payload = json.loads(candidate)
            if isinstance(payload, dict) and "tool" in payload:
                return payload["tool"], payload.get("args", {})
        except json.JSONDecodeError:
            pass

    simple_match = re.search(r"(?i)\b(?:call|tool)\s+([a-zA-Z0-9_]+)\s*(.*)", candidate)
    if simple_match:
        tool_name = simple_match.group(1)
        rest = simple_match.group(2).strip()
        args: dict[str, Any] = {}
        for item in re.findall(r"([A-Za-z0-9_\-]+)\s*=\s*(?:\"([^\"]*)\"|([^\s]+))", rest):
            key, quoted, bare = item
            value = quoted if quoted is not None else bare
            args[key] = value
        if not args and rest:
            args["value"] = rest
        return tool_name, args

    return None


def _tool_list_dir(path: str) -> str:
    base = Path(path)
    if not base.exists():
        return f"ERROR: path does not exist: {path}"
    if not base.is_dir():
        return f"ERROR: path is not a directory: {path}"
    entries = sorted(p.name for p in base.iterdir())
    return "\n".join(entries) if entries else "(empty directory)"


def _tool_read_file(path: str, start_line: Any = None, end_line: Any = None) -> str:
    file_path = Path(path)
    if not file_path.exists():
        return f"ERROR: file does not exist: {path}"
    if not file_path.is_file():
        return f"ERROR: path is not a file: {path}"
    lines = file_path.read_text(encoding="utf-8").splitlines()
    if start_line is not None or end_line is not None:
        start = int(start_line) if start_line is not None else 0
        end = int(end_line) if end_line is not None else len(lines)
        if start < 0:
            start = 0
        if end < start:
            end = start
        lines = lines[start:end]
    return "\n".join(lines)


def _tool_write_file(path: str, content: Any) -> str:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(str(content), encoding="utf-8")
    return f"OK wrote {file_path}"


def _tool_run_command(command: str, timeout: int = 30) -> str:
    try:
        proc = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        out = proc.stdout.strip()
        err = proc.stderr.strip()
        if out and err:
            return f"STDOUT:\n{out}\n\nSTDERR:\n{err}"
        if out:
            return out
        if err:
            return err
        return f"EXIT {proc.returncode}"
    except subprocess.TimeoutExpired:
        return f"ERROR: command timed out after {timeout}s"


def _tool_grep(pattern: str, path: str, max_matches: int = 50) -> str:
    target = Path(path)
    if not target.exists():
        return f"ERROR: path does not exist: {path}"
    if target.is_dir():
        return "ERROR: grep expects a file path"
    text = target.read_text(encoding="utf-8", errors="replace")
    matches: list[str] = []
    for index, line in enumerate(text.splitlines(), 1):
        if re.search(pattern, line):
            matches.append(f"{index}: {line}")
            if len(matches) >= int(max_matches):
                break
    return "\n".join(matches) if matches else f"NO MATCHES for {pattern}"


def execute_local_tool(tool_name: str, args: dict[str, Any], workspace: str, allow_shell: bool, allow_write: bool) -> str:
    if tool_name == "list_dir":
        return _tool_list_dir(args.get("path", workspace))
    if tool_name == "read_file":
        return _tool_read_file(args.get("path"), args.get("start_line"), args.get("end_line"))
    if tool_name == "write_file":
        if not allow_write:
            return "ERROR: writes are disabled in this session"
        return _tool_write_file(args.get("path"), args.get("content", ""))
    if tool_name == "run_command":
        if not allow_shell:
            return "ERROR: shell execution is disabled in this session"
        return _tool_run_command(args.get("command", ""), int(args.get("timeout", 30)))
    if tool_name == "grep":
        return _tool_grep(args.get("pattern", ""), args.get("path", workspace), int(args.get("max_matches", 50)))
    if tool_name == "find_files":
        root = Path(args.get("path", workspace))
        pattern = args.get("pattern", "*")
        if not root.exists():
            return f"ERROR: path does not exist: {root}"
        matches = []
        for candidate in root.rglob(pattern):
            if candidate.is_file():
                matches.append(str(candidate.relative_to(root) if root != candidate else candidate))
        return "\n".join(matches) if matches else "NO FILES FOUND"
    return f"ERROR: unknown tool {tool_name}"


def _run_tool_loop(
    args: argparse.Namespace,
    system: str,
    prompt: str,
    stdin: TextIO,
) -> int:
    workspace = str((Path(args.workspace).resolve() if args.workspace else Path.cwd()))
    history: list[dict[str, str]] = []
    steps = 0
    while steps < max(1, args.max_tool_steps):
        user_text = prompt if steps == 0 else "Continue from the tool results."
        model_messages = _build_messages(system, history, user_text)
        try:
            response = call_model(args.endpoint, args.model, args.api_key, model_messages, args.timeout)
        except HarnessError as exc:
            print(f"FAIL: {exc}", file=sys.stderr)
            return 1

        tool_call = _resolve_tool_call(response)
        if tool_call is None:
            _emit_response(response, args.model, args.json)
            return 0

        tool_name, tool_args = tool_call
        tool_result = execute_local_tool(
            tool_name,
            tool_args,
            workspace,
            args.allow_shell,
            args.allow_write,
        )
        history.extend([
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": response},
            {"role": "tool", "content": f"TOOL: {tool_name}\nARGS: {json.dumps(tool_args, ensure_ascii=False)}\nRESULT:\n{tool_result}"},
        ])
        prompt = "Continue by using the tool result or provide the final answer."
        steps += 1
        if steps >= args.max_tool_steps:
            final = "Tool loop reached the max step limit without a final answer."
            _emit_response(final, args.model, args.json)
            return 0
    return 0


def _run_once(args: argparse.Namespace, system: str, user_text: str) -> int:
    if not user_text.strip():
        raise HarnessError("prompt is empty")
    if args.tool_mode:
        return _run_tool_loop(args, system, user_text, sys.stdin)
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
    print("J headless · /clear resets context · /exit quits · /tools shows supported local tools", file=sys.stderr)
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
        if user_text == "/tools":
            print("local tool names: list_dir, read_file, write_file, run_command, grep, find_files", file=sys.stderr)
            continue
        if args.tool_mode:
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
            tool_call = _resolve_tool_call(response)
            if tool_call is not None:
                tool_name, tool_args = tool_call
                tool_result = execute_local_tool(
                    tool_name,
                    tool_args,
                    str((Path(args.workspace).resolve() if args.workspace else Path.cwd())),
                    args.allow_shell,
                    args.allow_write,
                )
                history.extend([
                    {"role": "user", "content": user_text},
                    {"role": "assistant", "content": response},
                    {"role": "tool", "content": f"TOOL: {tool_name}\nARGS: {json.dumps(tool_args, ensure_ascii=False)}\nRESULT:\n{tool_result}"},
                ])
                print(tool_result, file=sys.stderr)
                continue
            history.extend([
                {"role": "user", "content": user_text},
                {"role": "assistant", "content": response},
            ])
            _emit_response(response, args.model, args.json)
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
        description=(
            "Run J without the browser or backend. This harness can talk to a local "
            "OpenAI-compatible endpoint or execute a tool loop against the local workspace."
        )
    )
    parser.add_argument("--message", help="one-shot prompt; otherwise read stdin or start the REPL")
    parser.add_argument("--endpoint", default=os.environ.get("J_CLI_ENDPOINT", DEFAULT_ENDPOINT))
    parser.add_argument("--model", default=os.environ.get("J_CLI_MODEL", DEFAULT_MODEL))
    parser.add_argument("--api-key", default=os.environ.get("J_CLI_API_KEY", ""),
                        help="optional bearer token; may also be set with J_CLI_API_KEY")
    parser.add_argument("--system-prompt", type=Path, help="system prompt file (default: repository AGENTS.md)")
    parser.add_argument("--no-system-prompt", action="store_true", help="omit AGENTS.md from the request")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="request timeout in seconds")
    parser.add_argument("--json", action="store_true", help="emit one JSON object per response")
    parser.add_argument("--tool-mode", action="store_true", help="enable local file/shell tools within the current workspace")
    parser.add_argument("--workspace", default=os.environ.get("J_CLI_WORKSPACE", str(Path.cwd())), help="workspace root for local tools")
    parser.add_argument("--allow-shell", action="store_true", help="allow run_command tool in tool mode")
    parser.add_argument("--allow-write", action="store_true", help="allow write_file tool in tool mode")
    parser.add_argument("--max-tool-steps", type=int, default=8, help="max tool loop iterations before stopping")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.timeout < 1:
        parser.error("--timeout must be positive")
    if args.message is not None and not args.message.strip():
        parser.error("--message must not be empty")
    if args.max_tool_steps < 1:
        parser.error("--max-tool-steps must be positive")
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
