# PersonaBridge

PersonaBridge is a full-stack prototype for consent-aware AI conversations. It demonstrates how chat, reviewable memory, short-lived voice-room access, and approval-gated actions can share one session boundary without exposing provider credentials to the browser.

## What Works

- Create isolated personal sessions with memory disabled by default.
- Send chat messages through a Next.js client and FastAPI service.
- Create, list, and delete persisted memory candidates when the user opts in.
- Detect sensitive-action intent and require an explicit approve or reject decision.
- Request browser microphone access and mint a five-minute, session-scoped room token.
- Inspect the realtime and memory contracts exposed by the API.

The assistant response and room token are local stubs. The project focuses on the application boundaries around an AI provider; it does not claim to provide a production model or WebRTC integration.

## Architecture

```text
Next.js web console (localhost:3200)
              |
              | REST/JSON
              v
FastAPI service (localhost:8200)
  |-- in-memory sessions, transcripts, and approvals
  |-- JSON-backed reviewable memory candidates
  `-- provider-neutral realtime room contract
```

The API owns session state and permission decisions. The browser owns microphone permission and never receives server credentials. Memory consent permits candidate creation, not automatic permanent retention.

See [ARCHITECTURE.md](ARCHITECTURE.md) for component boundaries, [CONTRACTS.md](CONTRACTS.md) for API and lifecycle rules, and [DECISIONS.md](DECISIONS.md) for design tradeoffs.

## Tech Stack

- Next.js 16, React 19, and TypeScript
- Python 3.10+ and FastAPI
- Browser MediaDevices API
- Local JSON persistence for reviewable memory candidates

## Run Locally

Prerequisites: Node.js 20.9+ and Python 3.10+.

```powershell
npm install
python -m pip install -r services/api/requirements.txt
```

Start the API and web app in separate terminals:

```powershell
npm run dev:api
npm run dev:web
```

Open `http://localhost:3200`. The API documentation is available at `http://localhost:8200/docs`.
The checked-in defaults work without environment configuration; `.env.example` lists the available overrides.

## Quick Demo

1. Enable **Memory consent**, enter a name, and start a session.
2. Send a normal message and confirm that a reviewable memory candidate appears.
3. Delete the candidate and confirm that it disappears from the active list.
4. Send a message such as `Please email this plan` and approve or reject the generated action request.
5. Select **Join Voice**, grant microphone access, and inspect the short-lived room token metadata.

Local memory data is written to `.data/memory-candidates.json`. Set `MEMORY_STORE_PATH` to override that location.

## API Surface

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/sessions` | Create a session and record memory consent. |
| `GET` | `/api/sessions/{session_id}` | Read session state. |
| `GET`, `POST` | `/api/sessions/{session_id}/messages` | Read or append conversation messages. |
| `GET` | `/api/sessions/{session_id}/approvals` | List action approval requests. |
| `POST` | `/api/approvals/{request_id}/decision` | Approve or reject an action request. |
| `GET` | `/api/sessions/{session_id}/memory-candidates` | List active memory candidates. |
| `DELETE` | `/api/memory-candidates/{candidate_id}` | Tombstone a memory candidate. |
| `GET` | `/api/sessions/{session_id}/realtime-contract` | Read the realtime integration contract. |
| `POST` | `/api/sessions/{session_id}/realtime-token` | Mint a short-lived local room token. |

## Validate

```powershell
npm run check
npm run build -w @personabridge/web
python -m compileall services/api/app
```

## Current Limitations

- Sessions, transcripts, approvals, and room tokens reset when the API restarts.
- The local room token is an architecture boundary, not production authentication.
- No external language model, WebRTC provider, tool executor, PostgreSQL database, or vector search is connected yet.
