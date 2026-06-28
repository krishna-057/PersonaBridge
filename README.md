# PersonaBridge

PersonaBridge is a personal AI partner that can chat, join a voice/video room, remember user preferences, and request approval before sensitive actions.

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

## Why This Project Matters

This project is modern and interview-relevant because it involves AI product design, realtime systems, memory, and permission boundaries.

