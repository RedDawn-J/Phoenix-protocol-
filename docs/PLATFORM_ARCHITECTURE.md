# Phoenix Protocol — Platform Architecture

## Product target

Phoenix Protocol is a local-first, standalone AI computing environment. The first shippable target is a portable application that runs on a user's machine, opens in a local browser, stores its workspace and state locally, and uses a locally hosted model by default. It is not an operating system kernel, and it must not be described as one.

The repository already contains several substantial foundations. This document defines how they fit together and what must be proven before calling the product a standalone release.

## Existing building blocks

| Layer | Existing implementation | Current boundary |
| --- | --- | --- |
| Local assistant CLI | `scripts/j_cli.py` | Local OpenAI-compatible endpoint; tool use is opt-in |
| Browser workspace | `scripts/j_ui_workspace.py` | Loopback HTTP UI with file browser, editor, terminal and chat |
| Product/compiler tools | `scripts/j_forge.py`, `scripts/shardsc.py` | Generates starter artifacts and runs bounded Shards IR |
| Full IDE backend | `backend/server.py`, `backend/routes/` | FastAPI application; cloud and portable profiles coexist |
| Portable persistence | `backend/sqlite_store.py`, `backend/config.py` | SQLite-backed profile with local paths |
| Local model adapter | `backend/llm_chain.py` | OpenAI-compatible local inference endpoint |
| Desktop web IDE | `frontend/` | React app; packaging and portable first-run flow remain release work |
| Governance and audit | `backend/core/` | CIG, Chronicle, Five Masters and destructive-operation controls |

The existing headless CLI/UI path is the quickest independently runnable experience. The FastAPI + React path is the richer IDE and needs a separately verified portable assembly.

## Runtime boundaries

1. **Host shell** — starts the application as the current OS user. It must never silently elevate privileges.
2. **Local application server** — binds to loopback by default. Network exposure is an explicit deployment choice, not a default.
3. **Workspace** — every file operation is resolved beneath one selected workspace root. Symlinks and traversal must not escape that root.
4. **Persistence** — portable profile uses SQLite and shard-local data directories. No MongoDB service is required in portable mode.
5. **Inference** — local OpenAI-compatible endpoint is the default. Cloud providers are opt-in adapters and must be visibly disclosed.
6. **Tools** — file writes and command execution require explicit enablement. Tool calls are bounded and auditable.
7. **Browser** — the browser UI is a local control surface, not a security boundary. Shell commands execute with the host user's permissions.

## Branch consolidation findings

The repository contains overlapping work in the portable profile, standalone CLI, headless harness and operations CLI branches. These must be compared by behavior and tests, not merged by branch name or file count. Conflict snapshot branches are historical evidence, not integration targets.

The `codex/phoenix-platform-foundation` branch is an integration workspace. It deliberately leaves `main` untouched while the runtime and release gates are established.

## Release gates

### Gate A — repeatable local development
- Standard-library CLI and browser harness tests pass on supported Python versions.
- Every CI test failure is visible; no `|| true` masking.
- The browser UI binds to loopback and enforces workspace-root boundaries.
- Local model unavailability is reported as unavailable, never simulated as a successful response.

### Gate B — portable full-stack profile
- FastAPI starts with `J_CLOUD_PROFILE=portable` and no MongoDB credentials.
- SQLite persistence survives restart.
- Local auth can initialize, login, logout and reject expired sessions.
- Cloud adapters are disabled unless explicitly enabled.
- API health reports readiness without disclosing credentials.

### Gate C — packaged desktop distribution
- A reproducible assembly process bundles or provisions Python, Node (if needed), backend dependencies, frontend assets and Git.
- First-run setup selects a workspace, checks local model availability and explains optional cloud adapters.
- Installer/update/uninstall behavior is tested on each supported OS.
- Signing, checksums, upgrade safety and data-preserving uninstall are documented.

### Gate D — security and operational proof
- Threat model covers local web origins, CSRF, path traversal, symlinks, terminal execution, process lifetime and secret storage.
- Browser control plane is not exposed to LAN/WAN by default.
- Destructive actions require explicit confirmation and are logged.
- Backup/restore and recovery from interrupted writes are tested.
- End-to-end tests cover fresh install, first boot, workspace CRUD, restart, model response and clean uninstall.

## Immediate engineering sequence

1. Make the existing headless runtime continuously testable.
2. Add a single portable launcher/doctor that checks prerequisites and reports exact blockers.
3. Consolidate portable profile and CLI capabilities without touching substrate-owned modules outside the designated orchestrator.
4. Build a reproducible desktop assembly around the proven local runtime.
5. Add a browser integration and security test suite before enabling remote access.

## Non-goals for the first release

- Replacing Windows, macOS or Linux.
- Claiming the Shards IR is native machine code.
- Claiming the local browser terminal is a sandbox.
- Bundling model weights by default; users choose and download models separately.
- Enabling cloud APIs or transmitting workspace contents without an explicit opt-in.
