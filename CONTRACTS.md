# PersonaBridge Realtime And Memory Contracts

This document defines the next PersonaBridge boundary before any realtime model SDK, managed room provider, durable memory store, or tool executor is added. The goal is to keep the first realtime slice compatible with the existing chat, consent, and approval workflow instead of creating a parallel voice-only path.

## Realtime Session Contract

Every realtime room belongs to one PersonaBridge session.

| Field | Contract |
| --- | --- |
| Session owner | Existing `session_id` from `POST /api/sessions`. |
| Room identity | `personabridge:{session_id}` until a room provider requires a different opaque ID. |
| Browser transport | WebRTC or a managed realtime room. Plain WebSocket is acceptable only for text/model events, not low-latency audio. |
| Token lifetime | Short-lived browser token, minted by the API only after a session exists. |
| Session state | `chat_ready` before room token minting, `voice_ready` after a browser can join, `ended` after teardown. |
| Event ordering | Transcript and approval events must be append-only per session. Audio deltas may be streaming, but final transcript messages must preserve session order. |

### Client To Server Events

| Event | Payload | Rule |
| --- | --- | --- |
| `room.join.requested` | `session_id`, optional device metadata | API validates the session before a token is minted. |
| `audio.input.started` | `session_id`, local timestamp | Diagnostic only; raw audio is not stored as memory. |
| `transcript.user.final` | `session_id`, text, source segment ID | Becomes a normal user message. |
| `approval.decision` | `request_id`, decision | Uses the existing approval decision API semantics. |

### Server To Client Events

| Event | Payload | Rule |
| --- | --- | --- |
| `room.token.issued` | token, expiry, room ID | Token is short-lived and scoped to one session. |
| `transcript.assistant.delta` | text delta, segment ID | UI may stream this, but final text is persisted as one assistant message. |
| `approval.requested` | approval request resource | The assistant cannot execute a sensitive tool until this is approved. |
| `memory.candidate.created` | candidate ID, summary | Emitted only when memory consent is enabled. |
| `session.ended` | reason, timestamp | Browser leaves the room and stops media tracks. |

## Memory Contract

Memory is opt-in at session creation and remains separate from raw chat storage.

| Area | Contract |
| --- | --- |
| Consent source | `memory_enabled` on the session. |
| Default mode | Disabled. Messages stay session-local unless durable transcript storage is added later. |
| Enabled mode | The API may create memory candidates, not automatic permanent memories. |
| Storage target | Future PostgreSQL tables for memory records plus optional pgvector embeddings. |
| User control | A later task must add list/delete controls before durable memory is enabled by default. |

### Allowed Memory Sources

- User-authored final text messages.
- Assistant summaries explicitly derived from a session with memory enabled.
- Approved tool outcomes, only when the approved tool contract marks the output as rememberable.

### Excluded Memory Sources

- Raw audio/video frames.
- Pending or rejected approval requests.
- Secrets, payment data, authentication codes, and one-time credentials.
- Incidental browser/device diagnostics.

### Promotion Rule

When `memory_enabled` is false, no memory candidates are created. When it is true, a session can produce candidates, but a future durable memory worker must still classify, redact, and attach provenance before writing long-term records.

### Deletion Rule

Memory deletion must remove the user-visible memory record and any matching embedding row. Transcript deletion and memory deletion are separate operations because a transcript may be retained for audit while a derived memory is removed.

## Deferred Implementation

- No realtime provider token is minted yet.
- No OpenAI Realtime credentials are required yet.
- No memory rows or embeddings are written yet.
- No tool executes from a realtime event without an approved request ID.
