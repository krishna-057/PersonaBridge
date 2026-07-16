# PersonaBridge

PersonaBridge is a personal AI partner that can chat, join a voice/video room, remember user preferences, and request approval before sensitive actions.

## Current Slice

The current implemented slice is a local full-stack scaffold with a provider-neutral voice room shell:

- `apps/web`: Next.js console for starting a personal session, sending chat messages, toggling memory consent, reviewing approval requests, and running a browser voice shell that requests microphone access and mints a scoped room token.
- `services/api`: FastAPI boundary for sessions, messages, approval decisions, realtime token minting, and read-only realtime/memory contracts.
- `CONTRACTS.md`: The documented realtime room and memory promotion rules that future provider integrations must satisfy.
- `scripts/check-workspace.mjs`: dependency-light scaffold validation for the required files and API contract markers.

The assistant response is intentionally stubbed. It proves the user-facing workflow, permission boundary, and realtime/memory contract shape before adding external model credentials, managed realtime media, or durable memory.

## Architecture Focus

- Realtime AI conversation
- Voice/video transport
- Long-term memory
- Permission-gated tools
- Human-in-the-loop workflows

## Proposed Stack

| Layer | Choice | Why |
| --- | --- | --- |
| Frontend | Next.js | Fast full-stack product UI and routing. |
| Realtime media | LiveKit or WebRTC | Better fit for low-latency audio/video than plain HTTP. |
| AI | OpenAI Realtime API | Natural voice interaction and low-latency model responses. |
| Memory | PostgreSQL + pgvector | Combines durable relational data with semantic retrieval. |
| Coordination | Redis | Useful for session state and lightweight queues. |

## Local Development

```powershell
cd projects\03-personabridge
npm install
npm run dev:web
python -m uvicorn services.api.app.main:app --reload --port 8200
```

The web app defaults to `http://localhost:3200` and the API defaults to `http://localhost:8200`.

## First API Contract

| Capability | Endpoint | Purpose |
| --- | --- | --- |
| Create session | `POST /api/sessions` | Starts a personal room with memory consent captured up front. |
| Read session | `GET /api/sessions/{session_id}` | Returns session state for the web console. |
| List messages | `GET /api/sessions/{session_id}/messages` | Shows the current conversation transcript. |
| Send message | `POST /api/sessions/{session_id}/messages` | Adds a user message and stubbed assistant response. |
| List approvals | `GET /api/sessions/{session_id}/approvals` | Shows pending external-action requests. |
| Decide approval | `POST /api/approvals/{request_id}/decision` | Records approve/reject before any future tool execution. |
| Read realtime contract | `GET /api/sessions/{session_id}/realtime-contract` | Shows the room, event, token, approval, and memory rules for a future voice session. |
| Mint realtime room token | `POST /api/sessions/{session_id}/realtime-token` | Issues a five-minute browser join token and promotes the session to `voice_ready`. |
| Read memory contract | `GET /api/sessions/{session_id}/memory-contract` | Shows consent-derived memory capture mode, allowed sources, excluded sources, and storage target. |

## Intentional Deferrals

- Realtime provider integration is not connected yet; the browser shell stops at microphone capture and a short-lived API-minted room token.
- OpenAI Realtime API credentials are not required for the scaffold.
- Durable memory and vector search are deferred until the memory schema and deletion controls are implemented.
- Approval decisions are recorded, but no external tools execute yet.

## Why This Project Matters

This project is modern and interview-relevant because it involves AI product design, realtime systems, memory, and permission boundaries.
