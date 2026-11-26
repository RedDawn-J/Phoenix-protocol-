# Migration Log — Sovereign Shards · Gauntlet DevSpace

> Append-only build timeline for the Gauntlet DevSpace product itself
> (not user workspaces — those live at `.gauntlet/migration.log.md` inside
> each project). Every entry is code-signed and dated. Do not edit older
> entries; add a new one instead.

_initialized 2026-06-11T04:05:00+00:00 by **E1 (main agent)**_

---

## 2026-05-23T00:00:00+00:00 — v1.0 MVP — Sovereign Shards Cloud IDE
_signed: **E1 (main agent)**_  `mvp` `architecture`

**Problem.** User wanted to refine the `sovereign-shards/cloud` repo into a top-tier dev environment with an AI coworker that obeys the Five Masters Gauntlet.

**Fix.** Built FastAPI backend + React shell from scratch — Monaco editor with custom "sovereign" theme, xterm.js terminal with `INTEGRITY HALT` interlock, AI Coworker right panel (Chat/Refine/Gauntlet/Logs), Five Masters AST engine ported from upstream `core/fivemasters.py`, destructive-pattern scanner with password override, Emergent Google OAuth.

**Why.** Sovereign Shards brand demanded a command-center HUD aesthetic, not a generic dark dashboard. Build it once, right — cyan/orange/viridian palette, Exo 2 + JetBrains Mono, glassmorphic panels, deterministic motion (no bouncy springs).

**Next step.** Wire LLM failover chain.

---

## 2026-05-23T18:00:00+00:00 — LLM Failover Chain
_signed: **E1 (main agent)**_  `feature` `llm`

**Problem.** Emergent Universal Key budget exhausted mid-build; AI panel went dark. Single-provider LLM call was a single point of failure.

**Fix.** Implemented `_chain_call` — Universal Key runs first, then cascades through user BYO keys (same provider → cross-provider), 2 full passes, per-task chains for chat/refine/governance. Endpoint `GET /api/ai/chain` returns the resolved chain (ARMED/SKIP per step).

**Why.** Sovereign Infrastructure pillar — "if it can't prove integrity, it halts." Falling silent because one key was exhausted is the opposite of sovereign.

**Next step.** Surface chain telemetry visually.

---

## 2026-05-23T20:00:00+00:00 — Chain Telemetry Strip
_signed: **E1 (main agent)**_  `feature` `ui`

**Problem.** Failover happened invisibly — operators couldn't see which provider was actually answering.

**Fix.** Added bottom HUD strip showing last 5 LLM calls as instrument-panel pills (task glyph CHT/RFN/GNT · source/provider · latency ms · ↻N fallback count). Latest pill flashes 1px cyan stroke. Backed by `GET /api/ai/telemetry` + Mongo `llm_telemetry` collection populated by `_chain_call`.

**Why.** Verifiable Execution pillar — make the LLM behaviour visible like an aircraft cockpit.

**Next step.** Add GitHub integration.

---

## 2026-05-25T06:00:00+00:00 — Full GitHub Suite + 100-point Audit + Mobile
_signed: **E1 (main agent)**_  `feature` `github` `audit` `mobile`

**Problem.** No GitHub integration. No way to measure project quality. UI was unusable on phones.

**Fix.**
1. PAT-based GitHub: connect/disconnect, repo browser, clone, create+push, link, push, pull, open PR. Tokens encrypted at rest in the same Fernet vault as LLM keys.
2. Deterministic 100-point Project Audit: Five Masters AST 40 + destructive 15 + docs 10 + tests 10 + types 10 + hygiene 10 + deps 5. Grade S→F. **Opt-in refactor only — J proposes, user APPLYs.**
3. `.gauntletignore` seeded into new projects, respected by auditor.
4. File upload (multi), per-file download, full-project zip.
5. BYO agents API (`/api/agents`) + Fernet-encrypted endpoint keys.
6. Mobile shell < 900px: drawers + bottom dock (FILES / TERM / J).

**Why.** User asked for the full git suite (a–e) plus mobile fix. Audit rubric enforces Sovereign Shards philosophy without nagging.

**Next step.** Give J real tools so he can actually mutate files from chat.

---

## 2026-05-30T09:43:00+00:00 — Agentic Tooling — J Can Now Build Things
_signed: **E1 (main agent)**_  `feature` `agent` `tools`

**Problem.** J could TALK about files but couldn't TOUCH them. User: "HUGE freaking problem . J has no ability to really create folders or files when i tell him to."

**Fix.** Built `POST /api/ai/agent` ReAct-style tool-call loop. 20 tools across 6 categories — filesystem CRUD, search, run_command, git, github, gauntlet, audit, web_fetch, ask_user, done. Each tool call surfaces in chat as a collapsible card with args + result + OK/ERROR/BLOCKED badge. Safety rails: destructive scanner on `delete_file` and `run_command`, prompt requires `ask_user` before >5 mutations, path traversal hardened in every tool.

**Why.** Talking is not building. Verifiable Execution requires verifiable side effects.

**Next step.** Ingest large folders and zips reliably.

---

## 2026-05-30T18:23:00+00:00 — GitHub Panel Blank — Promise.all Trap
_signed: **E1 (main agent)**_  `bug` `frontend`

**Problem.** User: "The git icon does nothing." Production panel rendered blank. Root cause: `Promise.all([githubStatus(), gitStatus()])` — if either threw, neither piece of state was set, leaving the panel with default empty values.

**Fix.** Replaced `Promise.all` with sequential try/catch around each call so a single failure can't blank both. Wrapped panel in a React error boundary that shows a `RETRY` button instead of a void.

**Why.** Defensive coding (Hamilton). One I/O guard per call site, not one for the batch.

**Next step.** Large folder ingestion + zip builds.

---

## 2026-06-11T03:55:00+00:00 — Zip Ingestion + Auto-Build Tools
_signed: **E1 (main agent)**_  `feature` `tools`

**Problem.** User: "J has to be able to ingest large folders through the upload function and reliably build and compile from zip files." Existing `upload_file` was single-file; `run_command` timeout was 30s (too short for `npm install`); no project-type detection.

**Fix.**
1. `POST /api/projects/{id}/upload_zip` — extracts a `.zip` with auto-strip of single top-level folder (GitHub-style), 500MB total / 100MB per-file cap, junk-dir filter, path-traversal safe.
2. `POST /api/projects/{id}/upload_folder` — multi-file upload preserving relative paths from browser folder picker.
3. New J tools: `detect_project` (classifies node/python/rust/go/java/ruby/php/make/docker + suggested commands), `install_deps`, `build_project`, `extract_zip`.
4. `run_command` default timeout 30s → 120s, max 600s for long builds.
5. FileTree gained drag-drop ingestion with cyan overlay, folder picker, and percentage progress bar.

**Why.** Real dev work means real codebases. A "build environment" that can't unzip a project is a chat box with delusions of grandeur.

**Next step.** Auto migration logs.

---

## 2026-06-11T04:05:00+00:00 — Code-Signed Migration Log
_signed: **E1 (main agent)**_  `feature` `governance`

**Problem.** User: "add a migration log section that keeps build timelines listing the problems faced how and why they were fixed and what the next step should be in the build... when J creates them make sure they are signed and dated. If you could make the code do it instead of the llm that would be exquisite."

**Fix.** Built `core/migration_log.py` — append-only markdown at `.gauntlet/migration.log.md` inside each project workspace, written by deterministic Python code (zero LLM involvement, zero hallucination risk). Hooks: agent loop logs every milestone tool call (signed `J`), audit logs every run (signed `SYSTEM`), session starts get a marker, manual entries via `POST /api/projects/{id}/migration_log` signed with the user's name. New `GET /api/projects/{id}/migration_log` returns the rendered file. Each entry: ISO-8601 UTC timestamp + `_signed: **<who>**_` + tags + problem/fix/why/next-step + structured `extra` JSON block.

**Why.** Verifiable Execution — code-signed entries can be audited and trusted. LLM-generated logs can be elegant fiction; code-generated logs are receipts. Travels with the workspace (zip download, git push, etc.).

**Next step.** Surface the log in the UI as a new AI Coworker tab so users can read their own build history without curl. Add a "Pin entry" button so important milestones float above the auto-noise.

---

## 2026-11-26T17:05:00+00:00 — Architecture hardening and build-gate repair
_signed: **Phoenix engineering**_  `architecture` `ci` `migration`

**Problem.** The active production-gate run passed Python compilation, portable backend tests, headless runtime tests, and static-server security tests, but the React production build failed because three effects captured non-memoized refresh functions. The repository also contains two root-level migration histories without a clearly enforced canonical policy, while the portable SQLite adapter still needs deeper transaction/concurrency contract coverage.

**Fix.** Memoized the Chronicle, GitHub, and Live Preview refresh callbacks with explicit dependencies so effects can depend on stable callbacks rather than suppressing hook lint rules. Established this file as the canonical product migration history while preserving the legacy `MIGRATIONLOG.md` history and appending a matching maintenance record there. The architecture contract now defines module boundaries, versioned interfaces, data ownership, migration discipline, and release immutability.

**Why.** A clean build must be deterministic rather than achieved by disabling lint. Migration history must remain append-only and auditable. Stable module boundaries prevent the IDE, runtime, persistence, device broker, and communications providers from collapsing into a single application monolith.

**Next step.** Re-run the full production gate; then address any remaining build diagnostics and add migration/concurrency contract tests before treating portable persistence as production-grade.

---

## 2026-11-26T17:12:00+00:00 — Versioned SQLite schema migrations
_signed: **Phoenix engineering**_  `persistence` `sqlite` `migration`

**Problem.** The portable SQLite adapter created its document table opportunistically at connection startup. It had no schema version, immutable migration checksum, or explicit rejection of databases created by a newer build. The shared SQLite connection also had no process-local serialization lock despite being used across worker threads.

**Fix.** Added a complete migration runner and initial versioned document-store migration. Fresh databases are initialized transactionally; existing unversioned document stores are adopted without dropping data. Applied migration names/checksums are recorded and verified, future schema versions fail closed, and the connection now uses a re-entrant lock plus explicit SQLite durability/concurrency pragmas. Added regression tests for fresh initialization, legacy adoption, checksum drift, and future-version rejection.

**Why.** Portable user data must survive upgrades without silent schema drift. Schema evolution needs reproducible, reviewable history and safe startup behavior; SQLite access must serialize use of its shared connection.

**Next step.** Run the backend and full production gate against the migration runner, then add backup/restore and interrupted-upgrade tests before claiming portable persistence is production ready.

---

## 2026-11-26T17:15:00+00:00 — Migration history ownership clarification
_signed: **Phoenix engineering**_  `governance` `documentation`

**Problem.** The prior architecture edit described MIGRATIONLOG.md as a legacy history. That conflicts with AGENTS.md and README.md, which identify MIGRATIONLOG.md as the canonical substrate/developer journal. MIGRATION_LOG.md has a separate product-level migration purpose in its own header.

**Fix.** Clarified that the two root files are distinct append-only records: MIGRATIONLOG.md owns the developer/substrate journal; MIGRATION_LOG.md owns product runtime/schema migration entries. No historical entries were removed or rewritten.

**Why.** A clean architecture needs one owner and one purpose per record. Similar filenames do not make separate histories duplicates.

**Next step.** Keep both records synchronized with changes in their respective scopes and link each from the relevant engineering documentation.

---

## 2026-11-26T17:12:27+00:00 — Migration regression suite wired into CI
_signed: **Phoenix engineering**_  `ci` `persistence` `verification`

**Problem.** The new SQLite migration regression tests existed but were not part of the production-gate command, and their import path was not explicit when collected by pytest.

**Fix.** Added deterministic backend-root path setup to the migration test module and extended the production workflow to run the portable-profile suite together with the SQLite migration suite. The full backend history suite remains a separate release gate and is not represented as complete.

**Why.** A migration runner without automated execution is only an unverified code path. The CI gate must test the schema initialization and upgrade behavior it is intended to protect.

**Next step.** Confirm the latest workflow completes successfully, then expand persistence verification to interrupted migrations, concurrent access, and backup/restore.

---

---

## 2026-11-26T17:18:20+00:00 — Transactional portable persistence and recovery
_signed: **Phoenix engineering**_  `sqlite` `persistence` `recovery` `tests`

**Problem.** The portable SQLite adapter exposed a Mongo-shaped interface but had non-atomic read/modify/write operations, incomplete update/query coverage, a placeholder index method, and no database-level backup/restore path. Concurrent updates could lose increments, while unsupported query behavior could silently diverge from the cloud adapter.

**Fix.** Reworked the adapter around transactional update/upsert/delete operations using `BEGIN IMMEDIATE`; added a documented operator subset with explicit errors for unsupported operations; implemented real JSON-expression indexes, multi-document writes, distinct queries, aggregation stages, and integrity-checked atomic backup/restore. Added regression tests for concurrent increments, nested queries/projections, update-many, aggregation, index validation, backup round-trip, and overwrite protection. Updated the platform architecture and production-readiness contract to state the exact supported surface and remaining release gates.

**Why.** Portable persistence must be predictable, recoverable, and honest about compatibility. A narrow tested adapter is safer than a broad fake MongoDB clone. Atomic transactions and verified backups protect user data without coupling domain logic to SQLite.

**Next step.** Verify the production CI run, add multi-process and crash-injection coverage, and then route further persistence work through the documented repository boundary.

---

## 2026-11-26T17:20:02.873+00:00 — Persistence recovery and concurrency regression coverage
_signed: **Phoenix engineering**_  `tests` `sqlite` `migration`

**Problem.** Transactional persistence changes needed proof beyond same-process concurrency. Migration failure must leave no partially created schema objects or applied-version records, and restore must reject corrupt input without publishing a destination file.

**Fix.** Added multi-process increment stress coverage using four independent SQLite clients, migration DDL rollback coverage, and corrupt-backup rejection coverage. The tests exercise SQLite write-lock coordination, migration transaction rollback, and atomic restore publication.

**Why.** Correctness must hold across process boundaries and failed upgrades, not only in a single happy-path test. A restore operation must never replace a valid database with unverified bytes.

**Next step.** Wait for the latest production-gate run and repair any failures; add kill/crash injection and platform-level backup verification before marking recovery production-ready.
