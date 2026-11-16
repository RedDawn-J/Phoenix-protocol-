# J Headless CLI

Run J from a terminal or automation job without starting the React frontend, FastAPI server, or MongoDB. The harness sends chat-completions requests to a local OpenAI-compatible endpoint; by default that is Ollama on `127.0.0.1:11434`.

This is a local model chat harness, not a local copy of the Gauntlet agent runtime. It does not execute tools, change workspace files, access the backend database, or invoke the hosted API. The repo's existing `scripts/eval_run.py` remains the golden-set evaluation runner.

## Requirements

- Python 3.10 or newer.
- A local OpenAI-compatible model server. Ollama is the default endpoint. For Ollama, start its service and pull a model before running the harness.
- No additional Python package; the client uses the standard library.

Example Ollama setup:

```bash
ollama pull qwen2.5:7b
ollama serve
```

## One-shot prompt

From the repository root:

```bash
python scripts/j_cli.py --message "Explain the project structure"
```

The repository `AGENTS.md` is loaded as the system prompt by default. Override the model or endpoint when your local server uses different values:

```bash
python scripts/j_cli.py \
  --endpoint http://127.0.0.1:11434/v1/chat/completions \
  --model qwen2.5:7b \
  --message "Summarize this specification"
```

Pass a prompt over stdin for scripts and pipelines:

```bash
cat task.txt | python scripts/j_cli.py
```

Or omit `--message` in a terminal to start an interactive REPL:

```bash
python scripts/j_cli.py
```

Enter `/clear` to discard the current in-memory conversation or `/exit` to leave. Conversation history is kept only for the lifetime of that process; it is not written to disk or sent to the Gauntlet database.

## Machine-readable output

`--json` emits a JSON object with `model` and `response` fields. In interactive mode it emits newline-delimited JSON, one object per answer:

```bash
printf '%s\n' 'Return the word READY.' | python scripts/j_cli.py --json
```

Example output:

```json
{"model":"qwen2.5:7b","response":"READY"}
```

Failures are written to stderr and return a nonzero exit status. The harness never silently substitutes a mock response.

## Configuration

| Option | Environment variable | Default | Purpose |
|---|---|---|---|
| `--endpoint` | `J_CLI_ENDPOINT` | `http://127.0.0.1:11434/v1/chat/completions` | OpenAI-compatible chat completions URL |
| `--model` | `J_CLI_MODEL` | `qwen2.5:7b` | Model identifier understood by the local server |
| `--api-key` | `J_CLI_API_KEY` | empty | Optional bearer token for local servers that require one |
| `--system-prompt` | — | repository `AGENTS.md` | Alternate system prompt file |
| `--no-system-prompt` | — | off | Send no system message |
| `--timeout` | — | `120` seconds | Per-request timeout; must be positive |
| `--json` | — | off | Print machine-readable responses |

The `--api-key` option is optional for local servers. If the endpoint requires authentication, provide the token through the environment rather than putting it in shell history:

```bash
export J_CLI_API_KEY='your-local-endpoint-token'
python scripts/j_cli.py --message "Check readiness"
```

The endpoint can be overridden for any OpenAI-compatible server, including remote services, but the default is loopback-only. Do not send sensitive workspace material to an endpoint you have not approved.

## Limits and safety boundary

- The harness only sends the system prompt and prompt/conversation text to the configured endpoint.
- It has no tool loop, shell access, filesystem-editing feature, or automatic workspace scan.
- It does not start or configure Ollama; start the model server separately.
- For the full backend agent workflow, use the FastAPI application. For golden evaluation, use `scripts/eval_run.py` and `scripts/EVAL_HARNESS.md`.

## Tests

Run the dependency-free CLI tests from the repository root:

```bash
python -m unittest tests.test_j_cli
```
