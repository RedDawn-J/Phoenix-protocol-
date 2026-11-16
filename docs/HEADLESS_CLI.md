# J Headless CLI and Local UI

Run J without the React frontend, FastAPI backend, sign-in flow, or hosted AI API. The harness uses only Python's standard library. The local browser UI talks to a local OpenAI-compatible model endpoint, normally Ollama, through a loopback-only Python server.

## Requirements

- Python 3.10 or newer.
- A local OpenAI-compatible model server such as Ollama. The inference runtime and model are installed separately; the harness itself has no Python package dependencies.

For Ollama, start its service and download a model once:

```bash
ollama pull qwen2.5:7b
ollama serve
```

## Browser UI

From the repository root, start the UI server:

```bash
python scripts/j_ui.py
```

Open <http://127.0.0.1:8765>. The server binds to loopback by default and the model endpoint is also restricted to loopback; it is not exposed to your network.

Choose a workspace root when starting the UI if you want to browse and attach files:

```bash
python scripts/j_ui.py --workspace /path/to/your/project
```

The UI includes local conversation history, model selection, connection status, file browsing, file attachments, and responsive chat layout. Conversation history is stored in the browser's local storage. Attached file contents are sent to the configured local model endpoint as conversation context.

To use another local OpenAI-compatible endpoint or model:

```bash
J_CLI_ENDPOINT=http://127.0.0.1:11434/v1/chat/completions \
J_CLI_MODEL=qwen2.5:7b \
python scripts/j_ui.py --workspace .
```

Press `Ctrl+C` in the server terminal to stop it.

## CLI usage

One-shot prompt:

```bash
python scripts/j_cli.py --message "Explain the project structure"
```

Pipe a prompt from stdin:

```bash
printf '%s\n' "Summarize this repo" | python scripts/j_cli.py
```

Interactive REPL:

```bash
python scripts/j_cli.py
```

Enter `/clear` to clear the in-memory conversation or `/exit` to leave. `--json` emits machine-readable output:

```bash
python scripts/j_cli.py --message "Return READY." --json
```

## Local CLI tool mode

The command-line harness can browse and read the selected workspace. Writes and shell commands remain off unless explicitly enabled:

```bash
python scripts/j_cli.py --tool-mode --workspace . --message "Inspect the project and summarize its structure"
```

To enable file writes and shell commands for a trusted local task, pass the corresponding explicit flags:

```bash
python scripts/j_cli.py --tool-mode --workspace . --allow-write --allow-shell --message "Run the project tests and report the result"
```

Tools available in CLI tool mode: `list_dir`, `read_file`, `write_file`, `run_command`, `grep`, and `find_files`. Use `--max-tool-steps` to bound the number of tool rounds.

## Configuration

| Setting | Default | Description |
|---|---|---|
| `J_CLI_ENDPOINT` / `--endpoint` | `http://127.0.0.1:11434/v1/chat/completions` | Local OpenAI-compatible endpoint |
| `J_CLI_MODEL` / `--model` | `qwen2.5:7b` | Model identifier |
| `J_CLI_API_KEY` / `--api-key` | empty | Optional bearer token for the local endpoint |
| `--system-prompt` | repository `AGENTS.md` | Alternate system prompt file |
| `--no-system-prompt` | off | Omit the system message in CLI mode |
| `--timeout` | 120 seconds | Per-request timeout |

## Scope and limits

- “No outside dependency” means no hosted backend/API and no third-party Python package. A local model runtime and model weights are still required for inference.
- The browser UI is chat-and-context only; the CLI tool mode is separate. The UI does not execute shell commands or modify workspace files.
- The UI limits workspace browsing to the root provided at startup and caps individual context files at 200 KB.
- For golden-set evaluation, see [`scripts/EVAL_HARNESS.md`](../scripts/EVAL_HARNESS.md).

## Tests

Run the dependency-free CLI tests from the repository root:

```bash
python -m unittest tests.test_j_cli
```
