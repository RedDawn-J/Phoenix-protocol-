# J headless CLI

This is the local, dependency-light harness for the repository. It runs without the browser, backend service, or hosted AI provider. It speaks to a local OpenAI-compatible endpoint such as Ollama when present, and it can also execute a small local tool loop against the current workspace when `--tool-mode` is enabled.

## Quick start

From the repository root:

```bash
python scripts/j_cli.py --message "Explain the project structure"
```

Pipe a prompt from stdin:

```bash
printf '%s\n' "Summarize this repo" | python scripts/j_cli.py
```

Open an interactive REPL:

```bash
python scripts/j_cli.py
```

## Local model requirement

The harness does not bundle a model runtime. To get real responses, run a local model server such as Ollama first:

```bash
ollama pull qwen2.5:7b
ollama serve
```

Then run:

```bash
python scripts/j_cli.py --message "Give me a concise status report"
```

Default endpoint and model:

- endpoint: `http://127.0.0.1:11434/v1/chat/completions`
- model: `qwen2.5:7b`

These can be overridden with:

```bash
python scripts/j_cli.py \
  --endpoint http://127.0.0.1:11434/v1/chat/completions \
  --model qwen2.5:7b \
  --message "Check readiness"
```

## Full local capabilities

The harness supports a local tool loop for tasks that do not require the full FastAPI app. Enable it with `--tool-mode`:

```bash
python scripts/j_cli.py --tool-mode --workspace . --allow-shell --allow-write --message "Inspect the repo and summarize the key files"
```

The tool loop understands these operations:

- `list_dir`
- `read_file`
- `write_file`
- `run_command`
- `grep`
- `find_files`

The model can emit these as either a JSON object or a simple CALL-form command, for example:

```json
{"tool":"read_file","args":{"path":"README.md","start_line":0,"end_line":80}}
```

or:

```text
CALL read_file path=README.md start_line=0 end_line=80
```

This version is intentionally standard-library-only and never silently mocks a result. If the model server is down, the CLI exits with a clear error to stderr.

## JSON output

```bash
python scripts/j_cli.py --message "Return READY." --json
```

Output:

```json
{"model":"qwen2.5:7b","response":"READY."}
```

## Safety boundary

- The CLI only operates against the configured endpoint and the chosen workspace.
- Shell execution and writes require explicit flags: `--allow-shell` and `--allow-write`.
- The harness does not start a backend service or touch the repo’s core agent substrate.
- For the full Gauntlet agent loop, use the repository backend and existing AI routes; for local offline work, use this CLI harness.
