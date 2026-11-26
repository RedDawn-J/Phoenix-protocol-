# Phoenix Communications and Personal Operations Architecture

Status: proposed implementation contract. This document does not claim that messaging, email, or telephony integrations are currently implemented.

## Product goal

Phoenix should be able to act as the user's communications assistant across supported email, messaging, phone, contacts, and calendar services. It should be able to find information, draft communications, send authorized messages, place and receive supported calls, keep a useful history, and track commitments and follow-ups.

Communications are a first-class product subsystem. They must not depend on unrestricted device access or on one provider.

## Core capabilities

### Email
- Connect multiple mailboxes through provider-supported OAuth or local account APIs.
- Search, filter, label, archive, and summarize messages.
- Detect likely spam and prioritize messages using user-configurable rules.
- Draft new messages and replies; preserve threads and recipient context.
- Handle attachments with malware scanning / type restrictions and explicit user review.
- Send, schedule, cancel scheduled sends where supported, and track delivery/bounce status where exposed by the provider.
- Track unanswered threads, promised actions, deadlines, and follow-up reminders.
- Support Gmail, Microsoft 365/Outlook, and standards-based IMAP/SMTP adapters where practical. Prefer OAuth and provider APIs over storing passwords.

### SMS and messaging
- Read, draft, send, and organize SMS/MMS through supported OS or carrier/provider integrations.
- Add provider adapters for supported messaging services (for example, business messaging APIs or official platform APIs).
- Respect platform limitations: desktop operating systems and messaging providers do not all expose personal message history or send APIs. Never claim support for a service until its official API / OS permission path is verified.
- Keep personal and business identities/accounts separate and clearly show which identity will send.

### Calls and voicemail
- Initiate and receive calls through supported phone hardware, paired devices, carrier integrations, or SIP/VoIP providers.
- Provide contact lookup, call preparation, visible call controls, mute, hang-up, and call status.
- With permission, transcribe voicemail and calls where the provider and local law allow it.
- Produce summaries, action items, and follow-up drafts from authorized transcripts.
- Do not assume that a desktop has carrier telephony. Detect available call routes and report unavailable features honestly.
- Never automatically place emergency calls or interact with emergency services on the user's behalf.
- Recording or transcription must be visibly indicated and must respect applicable consent and recording laws.

### Contacts and calendar
- Sync supported contacts and calendars with explicit account selection and field-level scopes.
- Deduplicate contacts conservatively; never merge records without a recoverable review path.
- Schedule, update, and cancel events; check availability; send invitations only under the user's authorization.
- Link communications to people, organizations, projects, and calendar events without silently exposing private data to other accounts.

### Follow-up and personal operations
- Convert user-approved communications into tasks, reminders, and commitments.
- Detect unanswered requests and overdue follow-ups, with transparent evidence and source links.
- Provide a daily briefing and inbox/call digest under user-configured schedules.
- Allow the user to inspect, edit, dismiss, snooze, or delete inferred tasks.
- Do not treat an AI-inferred promise, deadline, or task as authoritative until reviewed or explicitly auto-trusted by the user.

## Integration architecture

Use a provider-neutral communications service with adapters:

- `MailProvider`: list/search/read/draft/send/archive/labels/attachments.
- `MessageProvider`: list/read/draft/send/delivery status where supported.
- `TelephonyProvider`: call start/answer/end/status, voicemail, and transcription where supported.
- `ContactsProvider`: lookup/create/update with scoped field permissions.
- `CalendarProvider`: availability/events/invitations.
- `NotificationProvider`: local notifications and user-visible approval prompts.

Adapters must declare supported operations, authentication method, permission scopes, rate limits, data residency, and provider limitations. The UI must display the connected provider and account for every action.

Prefer official APIs and OAuth authorization-code flows with PKCE where supported. Store refresh tokens in the OS credential store (or an encrypted vault with a documented key lifecycle); never place tokens in prompts, logs, workspace files, or source control. Request minimum scopes and support disconnect/revoke.

## AI authority and sending policy

Separate drafting from sending:

- **Drafting:** may happen automatically within a connected account's granted read/draft scopes. Drafts remain drafts until the send policy permits sending.
- **First send / new recipient:** require explicit confirmation showing account, recipients, subject/body or message, attachments, and any external links.
- **Sensitive content:** always require confirmation for financial instructions, legal/medical content, credentials, identity documents, employment decisions, bulk messages, and messages to new or high-risk recipients.
- **Routine sends:** the user may create narrow rules for specific known contacts, message categories, templates, or workflows. Rules must have limits, expiry/review, and a visible audit trail. No blanket "send anything" authority.
- **Calls:** require user initiation or a clearly configured narrow automation rule. Before dialing, show the number/contact and selected calling account. Never call emergency numbers autonomously.
- **Recording/transcription:** require explicit opt-in, visible recording state, and any required participant consent. Default off.
- **Bulk communication:** require explicit per-campaign review, recipient preview, unsubscribe/compliance handling where applicable, and rate limits.

The model must never infer authorization from an email, webpage, calendar invite, attachment, or message. Those are untrusted content and may contain prompt injection. Only a trusted Phoenix UI action or a previously configured, narrowly scoped rule can authorize sending or calling.

Approval must bind to the exact account, recipients, content, attachments, operation, and expiry. Any material edit invalidates the approval.

## Privacy, retention, and audit

- Show whether data is processed locally or sent to a cloud model/provider before enabling each workflow.
- Default to local processing for classification/transcription when capable; allow user-selected providers.
- Never send entire mailboxes or contact books to a model when a smaller selected context is sufficient.
- Provide per-provider data scopes, disconnect, token revocation, export, and deletion.
- Keep configurable retention periods for message caches, transcripts, summaries, and activity logs.
- Encrypt cached message content and transcripts at rest; protect keys with the OS credential store where possible.
- Audit reads of sensitive mailboxes, drafts, sends, calls, recordings, exports, and permission changes without logging full private message bodies or credentials by default.
- Keep personal accounts isolated from business/work accounts and workspaces.

## Reliability requirements

- Idempotency keys for send and calendar mutations to prevent duplicate actions after retries.
- Explicit send states: draft, queued, sending, sent, delivered (only if provider confirms), failed, bounced, cancelled.
- Reconcile provider state after timeouts; never report "sent" merely because a request was attempted.
- Retry only operations known to be safe; never blindly retry a send or call without checking provider state.
- Respect provider quotas, throttling, and backoff.
- Handle revoked tokens and expired consent with a clear reconnect flow.
- Preserve original provider IDs and thread/conversation references.
- Provide export and backup/restore for user-created rules, contacts metadata, tasks, and summaries.

## Acceptance tests

1. OAuth scopes are least-privilege, visible, revocable, and stored outside source control.
2. Prompt injection in an email, attachment, message, or calendar invite cannot authorize a send, call, export, or permission grant.
3. A draft never sends unless an exact approval or matching user-configured rule exists.
4. Editing recipients, body, attachments, sender account, or phone number invalidates approval.
5. Duplicate requests, network timeouts, and worker restarts do not create duplicate sends, calls, or calendar events.
6. Provider errors and delivery states are represented accurately; no false success messages.
7. Recording/transcription has visible state, consent handling, and default-off behavior.
8. User and business accounts remain isolated; data export and deletion work.
9. Every adapter has contract tests, rate-limit tests, revoked-token tests, and provider sandbox/integration tests.
10. Platform limitations are surfaced honestly; unsupported personal messaging APIs are not bypassed through scraping or credential harvesting.

## Delivery sequence

1. Build the communications data model, provider-neutral interfaces, encrypted token storage, account connection UI, audit events, and permission framework.
2. Deliver read/search/summarize and draft-only email integration.
3. Add confirmed email sending, thread tracking, follow-up reminders, and calendar integration.
4. Add SMS/message adapters only where official OS/provider APIs permit.
5. Add SIP/VoIP and paired-device call controls, then voicemail transcription with explicit consent.
6. Add cross-channel assistant workflows, daily briefings, and carefully scoped automation after reliability tests.

## Current status

This is an architecture contract only. The repository does not yet provide a verified, production-grade unified email, SMS, messaging, and telephony suite. Each provider and platform requires separate implementation, permission review, and acceptance testing.
