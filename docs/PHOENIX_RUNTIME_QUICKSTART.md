# Phoenix Runtime Quickstart

Phoenix currently boots its local-first headless workspace from the repository's Python runtime. This is the first integrated developer runtime; it is not yet a signed desktop installer.

## Requirements

- Python 3.10 or newer.
- A local OpenAI-compatible inference server for AI chat (Ollama is one option).
- A workspace directory you trust. The integrated terminal runs as your OS user and is not a sandbox.

## Diagnose the checkout

From the repository root:

```bash
python -m scripts.phoenix doctor
python -m unittest tests.test_j_cli tests.test_j_ui tests.test_j_ui_workspace tests.test_j_forge tests.test_phoenix -v
```

The doctor checks Python, required runtime files/modules, the selected workspace and loopback-only model endpoint configuration. Add `--probe-model` to make a short request to the local model server. The test command runs the dependency-free CLI, browser UI, Shards, J-Forge and launcher suites.

## Start the browser workspace

```bash
python -m scripts.phoenix start --workspace ./workspace --create-workspace --port 8765
```

Open `http://127.0.0.1:8765`. Configure the local model with:

- `J_CLI_ENDPOINT` — OpenAI-compatible `/v1/chat/completions` URL (default `http://127.0.0.1:11434/v1/chat/completions`).
- `J_CLI_MODEL` — model identifier (default `qwen2.5:7b`).
- `J_CLI_API_KEY` — optional bearer token for the local endpoint.

Or pass `--endpoint`, `--model`, and `--api-key` to the `start` command. Bind only to loopback.

## Other runtime commands

```bash
python -m scripts.j_cli --message "Explain this repository"
python -m scripts.j_forge --help
```

## Security boundary

The browser interface is a local control surface, not a sandbox. Shell commands execute with the current OS user's permissions. Keep the server bound to loopback, use a dedicated workspace, and review shell commands before running them. Do not expose the UI to a LAN or the public internet.

## Current scope

The launcher composes the existing CLI, browser workspace, bounded Shards interpreter and J-Forge tools. The full FastAPI/React portable profile is a separate integration target and must not be assumed to boot until its MongoDB-free startup, SQLite persistence, local authentication and model routing are covered by integration tests.
