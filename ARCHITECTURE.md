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
  +--> future realtime/model adapters
```

## Implemented Components

| Component | Responsibility |
| --- | --- |
| `apps/web` | Provides the operator-facing chat console, memory consent control, and approval queue. |
| `services/api` | Owns session state, message append flow, and approval decisions. |
| `scripts/check-workspace.mjs` | Verifies the scaffold and expected contract markers without requiring external services. |

## State Boundaries

The initial API stores sessions, messages, and approval requests in process memory. This is deliberate for the scaffold because it keeps the first workflow runnable without database setup. It also makes the eventual persistence task clearer: move the same three resources into PostgreSQL with an explicit memory-retention policy.

## Realtime Boundary

Voice/video is not in the first slice. The project will add a realtime room only after the chat and approval lifecycle is visible. The expected next shape is:

1. Web console creates a session.
2. API mints a short-lived realtime session token.
3. Browser joins a WebRTC or managed realtime room.
4. Audio/model events still pass through the approval and memory boundaries before any sensitive action.

## Permission Boundary

Messages that look like external actions create an `approval_gate` request. Today this is a simple keyword classifier, not a security system. It exists to keep the API shape honest: future tools must depend on an approved request instead of executing directly from an assistant message.
