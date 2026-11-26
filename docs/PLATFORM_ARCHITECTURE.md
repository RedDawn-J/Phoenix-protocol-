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


## Clean architecture contract

### Architectural rules

Phoenix is a modular application platform, not a single process that owns every capability. Keep domain logic independent from HTTP, UI, provider SDKs, and operating-system APIs. Dependencies point inward toward stable contracts; adapters point outward. A module may call another module only through its published interface, never by reaching into its private storage or importing another module's implementation details.

The first release remains a modular monolith at the deployment boundary where that is operationally simpler, but it must not become a code monolith. Each bounded context has its own package, public interface, persistence ownership, tests, and lifecycle. Split a context into a separate process only when isolation, scaling, or platform privilege requires it.

### Bounded contexts and ownership

| Context | Owns | Must not own |
| --- | --- | --- |
| Runtime / lifecycle | startup, shutdown, health, configuration, process supervision | product workflows or provider credentials |
| Identity / access | users, sessions, grants, approval records | raw model prompts or provider business logic |
| Workspace | projects, files, snapshots, workspace boundaries | device administration or communications accounts |
| Persistence | database adapters, transactions, schema versions, backup/restore | domain decisions |
| Intelligence | model routing, context assembly, agent planning, tool selection | direct unrestricted OS or network execution |
| Tool execution | typed tool registry, validation, policy checks, execution records | arbitrary model-generated shell commands by default |
| Device integration | capability discovery and OS-specific adapters | AI policy or user identity authority |
| Privileged broker | narrow typed privileged operations and audit | model inference, browser content, general-purpose command execution |
| Communications | mailbox, messaging, telephony, contacts, calendar adapters | OS root authority or unrelated workspace persistence |
| Browser | browsing sessions, navigation policy, downloads, page isolation | secret storage or privileged host access |
| UI / API | transport, presentation, request validation | domain rules and direct database access |

### Dependency direction

1. Domain modules define typed entities, interfaces, invariants, and domain errors.
2. Application services orchestrate domain operations and policy decisions.
3. Adapters implement interfaces for SQLite, MongoDB, model providers, mail providers, telephony, browsers, and operating-system APIs.
4. FastAPI routes and UI components are delivery adapters; they call application services and never implement business rules themselves.
5. The runtime composition root constructs concrete adapters and injects them. Domain packages must not import FastAPI, React, provider SDKs, or OS-specific libraries.

### Package layout target

Keep the current code operational during migration. Move code by bounded context in small reviewed changes rather than a giant directory shuffle. The target ownership map is:

- `backend/phoenix/runtime/` — lifecycle, configuration composition, health, shutdown.
- `backend/phoenix/identity/` — authentication, sessions, roles, grants.
- `backend/phoenix/workspaces/` — project and workspace domain/application services.
- `backend/phoenix/persistence/` — repository contracts, SQLite/Mongo adapters, migrations, backup.
- `backend/phoenix/intelligence/` — model gateway, agent orchestration, context and memory.
- `backend/phoenix/tools/` — typed tool contracts, registry, execution policy, audit.
- `backend/phoenix/devices/` — capability registry and unprivileged platform adapters.
- `backend/phoenix/broker_protocol/` — versioned IPC contracts only; privileged helper remains a separately packaged process.
- `backend/phoenix/communications/` — provider-neutral email, messaging, telephony, contacts, calendar, follow-up services.
- `backend/phoenix/browser/` — browser sessions, profiles, navigation and download policy.
- `backend/phoenix/api/` — HTTP/WebSocket transport and dependency wiring.
- `frontend/src/features/<context>/` — feature-owned UI, hooks, API clients and tests; shared visual primitives remain in `components/ui/`.

This is a target ownership map, not permission to create empty packages. A package is introduced only with working implementation, tests, and a migration plan for its current callers.

### Contracts and immutability

- Public interfaces use explicit request/response types, stable error codes, and semantic versions.
- Breaking contract changes require a new version and a compatibility window; silently changing a shared schema is prohibited.
- Released artifacts are immutable and identified by version, source commit, build provenance, and cryptographic checksum.
- Runtime configuration is validated once at startup and exposed as an immutable configuration object. Secrets are references to a credential store, never values copied into logs or model context.
- Persisted records carry stable identifiers, ownership, creation/update timestamps, and schema version where applicable.
- Events are append-only; corrections are new events referencing the prior event rather than rewriting audit history.
- Plugin/provider capabilities are declared and negotiated. Unsupported operations fail explicitly; adapters may not simulate success.

### Persistence and migrations

- `MIGRATIONLOG.md` is the canonical substrate/developer journal, as defined by `AGENTS.md`; it records engineering milestones and lessons.
- `MIGRATION_LOG.md` is the product-level runtime/schema migration timeline, as defined by its own header; it records product migrations separately from the developer journal.
- Both histories are append-only and have distinct purposes. Do not merge, delete, or rewrite historical entries to make the files look uniform.
- Database schema migrations live beside the persistence implementation, are numbered, deterministic, transactional where supported, and safe to re-run only when explicitly designed as idempotent.
- Each migration records an identifier, checksum, timestamp, and completion status in the database. Startup checks schema compatibility and refuses unsafe downgrade or unknown future versions.
- A migration must include forward behavior, backup/restore expectations, rollback or forward-repair strategy, and tests against both an empty database and a copy of the previous schema.
- Workspace migration logs remain separate, append-only records under each workspace's `.gauntlet/migration.log.md`.
- No schema or data migration is complete until its code, tests, and product migration-log entry land together.

### Cross-cutting quality gates

Every bounded context owns unit and contract tests. Adapter tests verify provider/OS semantics. Integration tests exercise the real composition root and lifecycle. Security tests cover authorization, path confinement, secret redaction, prompt-injection boundaries, replay, cancellation, and audit. CI must run formatting/lint, static checks, unit/contract tests, backend integration tests, frontend production build, and package smoke tests without suppressing failures.

### Implementation discipline

Do not create placeholder modules, empty classes, fake provider responses, TODO-only handlers, or interfaces with no working adapter. When an integration is not yet implemented, document it as planned in architecture/readiness material; do not add a fake runtime surface. Keep compatibility shims temporary, tested, and assigned a removal milestone. Avoid broad renames until the replacement path is working and the old path has a tested migration.
