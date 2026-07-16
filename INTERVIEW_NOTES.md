# PersonaBridge Interview Notes

Key topics:

- Why WebRTC/realtime media instead of normal request-response chat.
- Memory design and what should not be remembered.
- Tool permission model.
- How to avoid pretending the AI can perform human-only actions.

## First Slice Talking Points

- The scaffold proves the session and permission boundary before model integration. This avoids coupling product safety decisions to a specific AI provider SDK too early.
- Memory consent is captured when a session starts, but durable memory is not implemented yet. In an interview, this is easier to defend than silently storing everything and adding privacy rules later.
- Approval requests are modeled separately from messages so future tools can require an approved request ID before execution.
- The assistant response is a stub because the first architecture question is not model quality; it is whether the app has a clear place for chat, memory, and human approval.
- Realtime and memory contracts are now explicit before provider integration. This lets the team explain how WebRTC/model events map back into ordered messages, approval requests, and memory candidates.
- The voice shell proves microphone permission and API-minted room readiness without pretending a managed realtime provider is already connected.
- The short-lived opaque room token is a replaceable adapter boundary: in production it becomes a signed/provider-issued credential, but the session authority remains in the API.

## Next Scaling Questions

- What gets persisted: full transcripts, summaries, memories, or explicit user facts?
- How should realtime voice events map back to the same message and approval lifecycle?
- Should the first provider adapter use WebRTC directly, LiveKit, or OpenAI Realtime sessions?
- Should approvals expire, require re-authentication, or include per-tool scopes?
- What data should be deleted when a user disables memory?
- Should memory promotion be synchronous on final transcript events, queued through a worker, or fully user-reviewed?
