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

## Next Scaling Questions

- What gets persisted: full transcripts, summaries, memories, or explicit user facts?
- How should realtime voice events map back to the same message and approval lifecycle?
- Should approvals expire, require re-authentication, or include per-tool scopes?
- What data should be deleted when a user disables memory?
