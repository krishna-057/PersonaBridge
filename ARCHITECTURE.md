# PersonaBridge Architecture

PersonaBridge starts as a modular full-stack app with a thin web console and a FastAPI backend. The first slice focuses on the contract between a personal session, messages, memory consent, and approval-gated actions.

```text
Next.js web console
  |
  | session, message, approval HTTP calls
  v
FastAPI session API
  |
  +--> message transcript boundary
  +--> memory consent flag
  +--> approval request queue
  +--> realtime and memory contract views
  +--> future realtime/model adapters
```

## Implemented Components

| Component | Responsibility |
| --- | --- |
| `apps/web` | Provides the operator-facing chat console, memory consent control, and approval queue. |
| `services/api` | Owns session state, message append flow, approval decisions, and read-only contract descriptions. |
| `CONTRACTS.md` | Defines the realtime room and memory rules that provider/storage integrations must satisfy. |
| `scripts/check-workspace.mjs` | Verifies the scaffold and expected contract markers without requiring external services. |

## State Boundaries

The initial API stores sessions, messages, and approval requests in process memory. This is deliberate for the scaffold because it keeps the first workflow runnable without database setup. It also makes the eventual persistence task clearer: move the same three resources into PostgreSQL with an explicit memory-retention policy.

## Realtime Boundary

Voice/video is not connected to a provider yet. The project now exposes a contract-only realtime room view for each session so the next slice has a stable target. The expected next shape is:

1. Web console creates a session.
2. API mints a short-lived realtime session token for `personabridge:{session_id}`.
3. Browser joins a WebRTC or managed realtime room.
4. Final transcript events append to the same message lifecycle.
5. Audio/model events still pass through the approval and memory boundaries before any sensitive action.

The contract deliberately separates streaming deltas from final transcript messages. The UI can render assistant deltas for responsiveness, but the durable message boundary should only store final ordered messages.

## Memory Boundary

Memory consent controls whether a session may produce memory candidates. It does not mean every message is automatically remembered.

When memory is disabled, chat remains session-local in the current implementation. When memory is enabled, future storage may create candidate memories from final user text, assistant summaries, and approved rememberable tool outcomes. Raw audio/video, rejected approvals, secrets, one-time credentials, and device diagnostics remain excluded.

The next durable memory task should add explicit storage tables and deletion controls before any automatic long-term recall is enabled.

## Permission Boundary

Messages that look like external actions create an `approval_gate` request. Today this is a simple keyword classifier, not a security system. It exists to keep the API shape honest: future tools must depend on an approved request instead of executing directly from an assistant message.
