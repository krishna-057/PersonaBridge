# PersonaBridge Architecture

PersonaBridge is a modular full-stack prototype with a thin web console and a FastAPI backend. It focuses on the contract between a personal session, messages, memory consent, and approval-gated actions.

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
  +--> short-lived browser room tokens
  +--> local durable memory candidate store
  +--> future realtime/model adapters
```

## Implemented Components

| Component | Responsibility |
| --- | --- |
| `apps/web` | Provides the operator-facing chat console, memory consent control, memory candidate review/deletion, approval queue, and browser microphone room shell. |
| `services/api` | Owns session state, message append flow, memory candidate creation/deletion, approval decisions, read-only contract descriptions, and short-lived room token minting. |
| `CONTRACTS.md` | Defines the realtime room and memory rules that provider/storage integrations must satisfy. |
| `scripts/check-workspace.mjs` | Verifies the workspace and expected contract markers without requiring external services. |

## State Boundaries

The API stores sessions, messages, and approval requests in process memory. This keeps the workflow runnable without database setup. Memory candidates are the first durable resource: they are written to a local JSON file under `.data/` by default. That gives the deletion workflow a persisted record without introducing PostgreSQL before the retention rules are visible.

## Realtime Boundary

Voice/video is not connected to a provider yet. The project exposes a realtime room contract and a provider-neutral token endpoint for each session so a browser can prove microphone permission and room readiness before a managed room or model SDK is added.

1. Web console creates a session.
2. Browser requests microphone access through a user action.
3. API mints a five-minute opaque browser join token for `personabridge:{session_id}` and marks the session `voice_ready`.
4. Browser holds the local audio stream and token as the voice shell state.
5. A future adapter exchanges that token for a real WebRTC, LiveKit, or model-provider room join.
6. Final transcript events append to the same message lifecycle.
7. Audio/model events still pass through the approval and memory boundaries before any sensitive action.

The contract deliberately separates streaming deltas from final transcript messages. The UI can render assistant deltas for responsiveness, but the durable message boundary should only store final ordered messages.

The current token is opaque and stored only in process memory. It is a local development boundary, not authentication infrastructure. A production provider adapter should replace it with a signed or provider-issued credential while keeping the same session, approval, and memory semantics.

## Memory Boundary

Memory consent controls whether a session may produce memory candidates. It does not mean every message is automatically remembered.

When memory is disabled, chat remains session-local in the current implementation. When memory is enabled, future storage may create candidate memories from final user text, assistant summaries, and approved rememberable tool outcomes. Raw audio/video, rejected approvals, secrets, one-time credentials, and device diagnostics remain excluded.

The durable memory candidate slice creates reviewable records only from allowed user-authored final text while memory consent is enabled. Candidate deletion tombstones the record and removes the visible summary, preserving enough audit shape for later storage migration without retaining the deleted memory text.

PostgreSQL and pgvector remain the intended long-term storage path. The local file store is a replaceable adapter for the first deletion workflow, not the final recall architecture.

## Permission Boundary

Messages that look like external actions create an `approval_gate` request. Today this is a simple keyword classifier, not a security system. It exists to keep the API shape honest: future tools must depend on an approved request instead of executing directly from an assistant message.
