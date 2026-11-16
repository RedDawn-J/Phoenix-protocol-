# J Headless CLI and Local UI

Run J without the React frontend, FastAPI backend, sign-in flow, or hosted AI API. The harness uses only Python's standard library. The browser workspace talks to a local OpenAI-compatible model endpoint, normally Ollama, through a loopback-only Python server.

## Requirements

- Python 3.10 or newer.
- A local OpenAI-compatible model server such as Ollama. The inference runtime and model are installed separately; the harness itself has no Python package dependencies.

For Ollama, start its service and download a model once:

```bash
ollama pull qwen2.5:7b
ollama serve
```

## Browser UI with shell and file editing

From the repository root, start the UI against the workspace you intend J to edit:

```bash
python scripts/j_ui_workspace.py --workspace /path/to/your/project
```

Open <http://127.0.0.1:8765>. The UI includes a workspace file browser, editable file buffer with a Save button, a local shell panel, and J chat. File reads and writes are confined to the selected workspace root. Shell commands run with the UI process's OS user permissions and use that workspace as their working directory.

The server binds to loopback, and write/shell requests accept only same-origin loopback browser requests. Keep the UI local: do not expose its port through a proxy or bind it to a network interface. Shell commands are powerful and run as your account; review each command before pressing Run. File changes are immediate when Save is pressed; use version control or backups for recovery.

The shell, file editor, and chat are available in the browser UI. The UI's shell does not require an extra flag. Choose the root deliberately; do not point it at `/`, your home directory, or another broad system folder.

## Local model configuration

The default endpoint and model are:

- endpoint: `http://127.0.0.1:11434/v1/chat/completions`
- model: `qwen2.5:7b`

Override endpoint/model with environment variables or flags:

```bash
J_CLI_ENDPOINT=http://127.0.0.1:11434/v1/chat/completions \
J_CLI_MODEL=qwen2.5:7b \
python scripts/j_ui_workspace.py --workspace .
```

The UI only accepts loopback model endpoints. A local model runtime and model weights are still required for inference; they are not bundled in the harness.

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

## CLI local tool mode

The command-line harness can browse and read the selected workspace. Writes and shell commands remain off unless explicitly enabled:

```bash
python scripts/j_cli.py --tool-mode --workspace . --message "Inspect the project and summarize its structure"
```

To enable file writes and shell commands in CLI tool mode:

```bash
python scripts/j_cli.py --tool-mode --workspace . --allow-write --allow-shell --message "Run the project tests and report the result"
```

CLI tools include `list_dir`, `read_file`, `write_file`, `run_command`, `grep`, and `find_files`. Use `--max-tool-steps` to bound the number of tool rounds.

## Scope and limits

- “No outside dependency” means no hosted backend/API and no third-party Python package. Local model runtime and weights are required for inference.
- The browser UI shell executes commands through the operating system shell with the same permissions as the Python process. It is local-only, not a sandbox. Keep it bound to loopback and review commands.
- Workspace file browsing/editing is scoped to the path passed with `--workspace`; symlinks that escape the root are excluded or rejected.
- The browser UI chat is conversational. Use the UI's terminal and editor controls to explicitly run commands and save file changes.
- For golden-set evaluation, see [`scripts/EVAL_HARNESS.md`](../scripts/EVAL_HARNESS.md).

## Tests

Run the dependency-free CLI and UI tests from the repository root:

```bash
python -m unittest tests.test_j_cli tests.test_j_ui tests.test_j_ui_workspace
```
