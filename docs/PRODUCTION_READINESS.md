# Phoenix Production Readiness

This document is the release contract for Phoenix. A green unit-test job is necessary but does not, by itself, mean the product is production ready.

## Product definition

Phoenix is a local-first AI development environment built from the existing FastAPI/React IDE, portable SQLite profile, local model adapter, and headless CLI/workspace runtime. It is an application platform, not an operating-system kernel. Cloud integrations remain opt-in in portable mode.

## Integrated components

- **IDE:** React interface with editor, file tree, terminal, preview, AI coworker, audit and project panels.
- **API:** FastAPI service and route modules.
- **Portable data:** SQLite-backed profile and local workspace/snapshot roots.
- **Inference:** OpenAI-compatible local inference endpoint by default in the portable profile.
- **Runtime tools:** CLI, local browser workspace, Shards interpreter and J-Forge.
- **Integrity:** Chronicle/audit, code-integrity checks, Five Masters evaluation and destructive-operation controls.

## Release gates (all are required)

### Build and supply chain
- Reproducible Python environment with supported Python versions documented and locked.
- Frontend dependencies installed from the committed lockfile; production build succeeds.
- SBOM generated; dependency and license policies reviewed.
- Secret scanning, dependency vulnerability scanning and static analysis run in CI.
- Signed, checksummed release artifacts produced for every supported OS.

### Runtime and packaging
- One-command first-run bootstrap; no developer-only steps or hidden cloud dependency.
- Supported Windows, macOS and Linux launchers with graceful start, stop, restart, port selection and log collection.
- Installer/uninstaller, upgrade and rollback paths tested on clean machines.
- Data, configuration, logs, cache, and model assets stored in documented OS-appropriate directories.
- Health/doctor command diagnoses missing prerequisites and offers safe remediation.

### Security and privacy
- Loopback-only bind by default; explicit opt-in and authentication for remote access.
- First-run operator setup; no default or shipped credentials.
- Session rotation, expiry, revocation, CSRF protections and secure cookie policy verified.
- Workspace path traversal, symlink escape, upload size/type, archive extraction and command execution boundaries tested.
- Terminal and agent tools run with least privilege; no silent privilege elevation.
- Secrets encrypted at rest with a user-controlled recovery/rotation story; secrets never appear in logs.
- Cloud adapters disabled by default in portable mode and clearly disclosed before use.
- Threat model and security response process reviewed before public release.

### Data durability
- SQLite transactions, concurrency, migrations, indexes, backup, restore and corruption recovery tested.
- Workspace snapshots are atomic, bounded, integrity checked and safe against archive traversal.
- User/project ownership enforced on every data and file operation.
- Upgrade tests preserve user data and support rollback.

### AI and browser
- Local inference works without cloud credentials and degrades gracefully when the model server is absent.
- Provider routing, model selection, timeout, cancellation, streaming, rate limits and privacy mode tested.
- Agent tool calls are permissioned, observable, bounded and auditable.
- Browser integration has explicit permissions, isolated profiles, download controls and safe navigation policies.

### Quality and operations
- API contract and end-to-end tests cover first run, login, project CRUD, editing, terminal, AI, restart and backup/restore.
- Accessibility, keyboard navigation, responsive layouts and supported browser matrix verified.
- Structured logs, health endpoints, crash reports (opt-in), diagnostics and actionable errors available.
- Performance budgets and soak tests pass on minimum supported hardware.
- Release notes, operator docs, user guide, known limitations and recovery instructions published.

## Current verification boundary

The current GitHub Actions production gate compiles Python, runs backend and headless runtime tests, and builds the React frontend. This is a growing CI baseline. It does not yet establish signed installers, OS-level sandboxing, a complete browser engine, a security audit, or production operational readiness. Those remain explicit release blockers until implemented and tested on target machines.

## Working rule

Never mark a gate complete based only on code inspection or documentation. Attach a reproducible test, build artifact, or recorded manual acceptance result to each completed gate.
