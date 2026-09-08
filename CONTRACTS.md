# PersonaBridge Realtime And Memory Contracts

This document defines PersonaBridge's provider-neutral boundaries for realtime sessions, memory, and tool approvals. These contracts keep future provider integrations compatible with the existing chat, consent, and approval workflow instead of creating a parallel voice-only path.

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

## Room Token Slice

The first implementation mints a provider-neutral browser join token instead of integrating a realtime SDK immediately.

| Field | Current Rule |
| --- | --- |
| Endpoint | `POST /api/sessions/{session_id}/realtime-token` |
| Request | Optional `device_label` captured from the browser microphone track. |
| Response token | Opaque `opaque_browser_join` value scoped to one session and one participant. |
| Expiry | Five minutes after issue time. |
| Session effect | Updates the session status from `chat_ready` to `voice_ready`. |
| Browser shell | Requests microphone access only from a user action, keeps tracks local, and stops them on leave/new session. |
| Provider adapter | Deferred. A future adapter should exchange or replace this token with a WebRTC, LiveKit, or model-provider credential. |

This token is a local architecture boundary, not production authentication. The important constraint is that realtime room access is minted by the API after session validation and before any audio/model provider is joined.

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
| Storage target | Local JSON candidate store for this slice; future PostgreSQL tables plus optional pgvector embeddings. |
| User control | Active candidates must be listable and deletable before semantic recall is enabled. |

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

## Memory Candidate Slice

The first durable memory implementation creates local reviewable candidates, not permanent recalled memories.

| Field | Current Rule |
| --- | --- |
| List endpoint | `GET /api/sessions/{session_id}/memory-candidates` |
| Delete endpoint | `DELETE /api/memory-candidates/{candidate_id}` |
| Store | JSON file at `.data/memory-candidates.json` unless `MEMORY_STORE_PATH` is set. |
| Creation trigger | Final user text submitted through `POST /api/sessions/{session_id}/messages` when session memory consent is enabled. |
| Source provenance | Each candidate keeps the source message ID and session ID. |
| Secret handling | Obvious secrets, credentials, one-time codes, and payment identifiers are skipped instead of written as candidates. |
| Delete behavior | Deletion tombstones the candidate, removes the visible summary text, and keeps a deletion timestamp. |

The API returns only active candidates by default. Deleted tombstones can remain in the local store so a later PostgreSQL migration can preserve audit shape while still removing user-visible memory content.

## Deferred Integrations

- The API mints a local opaque room token; no external realtime provider credential is issued yet.
- No OpenAI or other model-provider credentials are required.
- No PostgreSQL memory rows, embeddings, or semantic recall are written yet.
- Approval decisions are recorded, but no external tool executor is connected yet.
