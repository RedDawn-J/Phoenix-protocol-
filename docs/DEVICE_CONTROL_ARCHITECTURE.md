# Phoenix Device Control and Privileged Operations Architecture

Status: proposed implementation contract. This document does not claim that privileged device control is implemented.

## Product goal

Phoenix is intended to be a local-first AI workstation that can inspect and operate the host device, integrate supported peripherals, automate applications, and perform administrative maintenance with the owner's authority.

The AI assistant must be capable, tool-using, multimodal, and able to coordinate long-running workflows. It must not itself run as root/Administrator or receive an unrestricted privileged shell.

## Security boundary

Use three separate processes / trust zones:

1. **Phoenix UI and AI orchestrator (unprivileged):** browser, chat, model routing, planning, retrieval, and normal workspace operations. Treat model output, webpages, documents, plugins, and tool results as untrusted input.
2. **Phoenix user agent (unprivileged):** per-user device discovery, notifications, app launching, accessibility integration, media devices, and user-scoped automation.
3. **Phoenix privileged broker (small OS service):** installed separately and explicitly elevated by the device owner. Exposes a narrow, versioned local IPC API. It performs only named operations implemented by reviewed handlers.

The broker must never expose a generic `exec(command)`, arbitrary script, arbitrary file-write, or model-supplied path operation. Do not run the model server, browser, plugin host, or AI orchestrator with elevated privileges.

## Capability model

Capabilities are explicit, independently grantable, revocable, and scoped:

- `system.read`: OS version, hardware inventory, resource usage, process metadata, service status, and diagnostic logs.
- `files.user`: read/write within user-approved roots.
- `files.system.read`: read selected system diagnostics; deny secrets and credential stores by default.
- `apps.launch`: launch allowlisted installed applications as the logged-in user.
- `apps.control`: accessibility/UI automation with visible status and user-session boundaries.
- `devices.camera`, `devices.microphone`, `devices.audio`, `devices.display`, `devices.bluetooth`, `devices.usb`: separate device permissions, with OS permission prompts where available.
- `network.inspect`: read-only adapter and connection diagnostics.
- `system.settings`: specific supported settings changes, each represented by a typed operation.
- `system.services`: start/stop/restart only explicitly selected services through typed operations.
- `software.install`: install signed packages from approved sources, requiring a fresh owner confirmation.
- `system.admin`: exceptional maintenance operations, individually described and confirmed; never a blanket AI grant.

No capability is granted merely because a user asks the AI to do something. First use requires a clear permission prompt describing the resource, purpose, scope, duration, and consequences.

## Approval policy

Classify every tool operation before execution:

- **Read-only, low impact:** may run automatically if its capability is already granted.
- **Reversible user-level change:** may run automatically only when the user has enabled that workflow; otherwise ask.
- **Privileged or externally visible change:** require a just-in-time confirmation showing the exact operation and target.
- **Destructive, security-sensitive, financial, credential, account, firewall, disk, boot, or security-control change:** require explicit confirmation for each operation, never inferred from broad consent.
- **Untrusted-content initiated action:** webpage/document/email/plugin content cannot authorize an operation. The assistant must summarize the proposed action and obtain confirmation from the user through trusted Phoenix UI.

Approval tokens must be short-lived, single-use, bound to the operation, arguments, requesting user/session, and broker method. Changing any argument invalidates approval.

## Broker protocol requirements

- Local IPC only: Unix domain socket with restrictive ownership/permissions on Linux/macOS; named pipe with ACLs on Windows.
- Authenticate the calling user and verify OS peer credentials where supported.
- Versioned JSON or typed RPC schemas; reject unknown methods and fields.
- Strict argument validation, canonical path resolution, symlink/reparse-point defenses, and TOCTOU-aware file handling.
- Explicit allowlists; deny by default.
- No network listener and no browser-accessible broker endpoint.
- Rate limits, request size limits, timeouts, cancellation, and bounded output.
- Structured audit records for requester, capability, method, target, approval, result, and timestamp. Never log secrets or raw microphone/camera content.
- Broker binaries and updates must be signed; updates must fail closed on signature verification errors.
- Separate user data from system configuration; provide rollback where feasible.

## AI assistant contract

The assistant may:
- Plan multi-step tasks and explain intended effects.
- Use browser, files, terminal, speech, vision, and device tools when their capabilities are available.
- Ask for permission at the moment it needs a new capability.
- Execute approved workflows, report partial failures, and offer rollback.
- Maintain user-controlled memory and a searchable, provenance-aware activity history.

The assistant may not:
- Treat prompt text, a webpage, a file, or tool output as permission.
- silently elevate itself, disable security controls, hide activity, or persist privileged access.
- execute arbitrary root commands or pass unreviewed model-generated scripts to the broker.
- capture camera/microphone, record screens, or collect device telemetry without visible state and the relevant permission.
- silently exfiltrate data to remote model providers. Show the destination/provider and data-sharing mode.

## Platform adapters

Implement separate adapters for Windows, macOS, and Linux. Do not assume identical permission models.

- Windows: user-session agent plus a narrowly scoped Windows service; UAC for installation and high-impact administration; named pipes with ACLs.
- macOS: user agent plus a signed helper installed through the supported privileged-helper mechanism; TCC permissions for camera, microphone, accessibility, screen recording, and automation.
- Linux: user agent plus optional systemd service/polkit actions; avoid setuid helpers and broad sudoers rules; use D-Bus/portal APIs where appropriate.

Device support must be capability-detected. Unsupported hardware or OS APIs should be reported as unavailable, not simulated.

## Required acceptance tests

1. AI process runs as the normal user even when the broker is installed.
2. Broker rejects unknown methods, extra fields, invalid paths, symlink escapes, expired/replayed approvals, and requests from another user.
3. Prompt injection in a webpage or document cannot grant permissions or invoke privileged methods.
4. Every privileged action produces an audit event and a visible user notification.
5. Camera/microphone/screen capture cannot start without OS permission and visible Phoenix state.
6. Revoking a capability takes effect immediately.
7. Broker crash or unavailable service fails closed; ordinary Phoenix functions remain usable.
8. Install, upgrade, uninstall, and recovery are tested on clean Windows, macOS, and Linux machines.
9. Fuzz and adversarial tests cover every broker method and platform adapter.
10. No release may claim full-device or administrative support until the relevant platform acceptance suite passes.

## Delivery sequence

1. Ship the unprivileged user agent, capability registry, permission UI, and audit trail.
2. Implement read-only system inventory and device discovery.
3. Add user-level app, file, audio, and accessibility integrations.
4. Add the privileged broker with one typed operation at a time, beginning with narrowly scoped diagnostics.
5. Add maintenance operations and signed installers only after threat modeling and platform-specific tests.
6. Expand the assistant's tool catalog as each capability passes acceptance tests.

## Current status

This is an architecture contract only. The current repository has local runtime, browser/workspace, terminal, and AI foundations, but it does not yet provide a production-grade privileged broker or complete cross-platform device integration. Do not advertise unrestricted root access or full-device integration as currently available.
