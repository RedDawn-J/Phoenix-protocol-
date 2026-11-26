# Security Policy

Phoenix is local-first, but local software still processes valuable code, credentials, and personal data. Treat the runtime as privileged software.

## Safe deployment defaults

- Keep the backend and headless workspace bound to loopback unless remote access has been deliberately designed, authenticated, and tested.
- Do not expose the integrated terminal or workspace control plane to an untrusted network.
- Configure a strong, unique `OVERRIDE_PASSWORD` before enabling destructive-operation overrides. Portable installs leave this feature disabled until configured.
- Store provider credentials through the encrypted key vault or the operating system's secret store; do not commit secrets, database files, workspaces, or local key files.
- Portable mode disables cloud adapters by default. Review and explicitly enable each adapter before use.

## Secret/key rotation note

The portable integration branch removes `backend/.keys_secret` from the working tree and keeps it ignored. Because the file existed in repository history, deletion in a new commit does not erase historical copies. Before a public production release, determine whether that historical value was used, rotate `KEYS_ENCRYPTION_SECRET`, re-encrypt or re-enter stored provider credentials, and scrub affected Git history if the value was real. Coordinate a history rewrite with all collaborators before doing it.

## Reporting

Do not publish exploitable details or credentials in public issues. Report suspected vulnerabilities privately to the repository owner with affected commit, impact, reproduction steps, and a proposed mitigation. Revoke exposed credentials immediately; do not wait for triage.
