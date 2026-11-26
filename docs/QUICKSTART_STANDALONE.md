# Phoenix standalone quick start (current runtime milestone)

Phoenix is being assembled as a local-first AI platform. The currently runnable standalone milestone is the dependency-free J browser workspace. It provides a local browser UI, workspace file editor, local terminal and chat against an OpenAI-compatible model endpoint.

This is **not yet** the packaged desktop release or the full FastAPI + React portable IDE.

## Requirements

- Python 3.10+
- A local OpenAI-compatible inference server. Ollama is the documented default.
- A model already downloaded by that server.

Example Ollama setup:

```bash
ollama pull qwen2.5:7b
ollama serve
```

## Check the machine

From the repository root:

```bash
python scripts/phoenix.py doctor --workspace .
python scripts/phoenix.py doctor --workspace . --probe-model
```

The doctor does not install software, change system settings, or transmit workspace contents. The optional model probe makes a short request to the local OpenAI-compatible `/models` endpoint.

## Start Phoenix

```bash
python scripts/phoenix.py start --workspace ./my-workspace --create-workspace
```

Open `http://127.0.0.1:8765` in your browser. Stop the server with Ctrl+C.

Override the model endpoint or model when needed:

```bash
python scripts/phoenix.py start \
  --workspace ./my-workspace \
  --endpoint http://127.0.0.1:11434/v1/chat/completions \
  --model qwen2.5:7b
```

## Security boundary

- The browser server binds to loopback only.
- The model endpoint must resolve to a loopback address.
- Workspace file access is rooted at the selected workspace.
- Shell commands run with the permissions of the OS account running Phoenix. This is **not a sandbox**. Review commands before execution and do not expose the UI port through a reverse proxy or network interface.
- Do not run Phoenix against a broad or sensitive directory such as your home directory or filesystem root unless you intentionally want the assistant UI to operate there.

## Verify the code

```bash
python -m unittest tests.test_j_cli tests.test_j_ui tests.test_j_ui_workspace tests.test_j_forge tests.test_phoenix
```

## What's still needed for the standalone product

The full portable FastAPI + React profile, reproducible Python/Node dependency assembly, first-run setup, desktop packaging, update/recovery, browser E2E tests and OS-specific installers are later release gates. The launcher deliberately does not claim those pieces are finished.
