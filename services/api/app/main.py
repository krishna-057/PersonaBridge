import os
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3200").split(",")
    if origin.strip()
]

app = FastAPI(title="PersonaBridge API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CreateSessionRequest(BaseModel):
    display_name: str = Field(default="Personal room", min_length=1, max_length=80)
    memory_enabled: bool = False


class SessionResponse(BaseModel):
    session_id: UUID
    display_name: str
    status: Literal["chat_ready", "voice_ready", "ended"]
    memory_enabled: bool
    created_at: datetime


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    client_message_id: str | None = Field(default=None, max_length=120)


class MessageResponse(BaseModel):
    message_id: UUID
    session_id: UUID
    role: Literal["user", "assistant", "system"]
    content: str
    created_at: datetime
    approval_request_id: UUID | None = None


class ApprovalRequestResponse(BaseModel):
    request_id: UUID
    session_id: UUID
    tool_name: str
    reason: str
    status: Literal["pending", "approved", "rejected"]
    created_at: datetime
    decided_at: datetime | None = None


class ApprovalDecisionRequest(BaseModel):
    decision: Literal["approved", "rejected"]


class RealtimeContractResponse(BaseModel):
    session_id: UUID
    room_id: str
    status: Literal["contract_only"]
    transport: Literal["webrtc_or_managed_realtime"]
    token_endpoint: str | None
    client_events: list[str]
    server_events: list[str]
    approval_boundary: str
    memory_boundary: str


class MemoryContractResponse(BaseModel):
    session_id: UUID
    memory_enabled: bool
    capture_mode: Literal["disabled", "candidate_review"]
    allowed_sources: list[str]
    excluded_sources: list[str]
    promotion_rule: str
    deletion_rule: str
    storage_target: str


sessions: dict[UUID, SessionResponse] = {}
messages: dict[UUID, list[MessageResponse]] = {}
approval_requests: dict[UUID, ApprovalRequestResponse] = {}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def require_session(session_id: UUID) -> SessionResponse:
    session = sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    return session


def append_message(
    session_id: UUID,
    role: Literal["user", "assistant", "system"],
    content: str,
    approval_request_id: UUID | None = None,
) -> MessageResponse:
    message = MessageResponse(
        message_id=uuid4(),
        session_id=session_id,
        role=role,
        content=content,
        created_at=now_utc(),
        approval_request_id=approval_request_id,
    )
    messages[session_id].append(message)
    return message


def sensitive_tool_for(content: str) -> str | None:
    normalized = content.lower()
    if any(term in normalized for term in ["email", "send", "calendar", "book", "delete", "payment"]):
        return "approval_gate"
    return None


def create_approval_request(session_id: UUID, content: str) -> ApprovalRequestResponse:
    request = ApprovalRequestResponse(
        request_id=uuid4(),
        session_id=session_id,
        tool_name="approval_gate",
        reason=f"User message asks for an external action: {content[:140]}",
        status="pending",
        created_at=now_utc(),
    )
    approval_requests[request.request_id] = request
    return request


def assistant_reply(session: SessionResponse, user_content: str, approval_id: UUID | None) -> str:
    if approval_id is not None:
        return "I can prepare that action, but I need explicit approval before any external tool runs."

    memory_note = "I will not store this beyond the current session."
    if session.memory_enabled:
        memory_note = "I can use this session as a candidate for future memory once durable memory storage is added."

    return f"Noted. For now I can help structure the next step and keep the boundary clear. {memory_note}"


def realtime_contract_for(session_id: UUID) -> RealtimeContractResponse:
    return RealtimeContractResponse(
        session_id=session_id,
        room_id=f"personabridge:{session_id}",
        status="contract_only",
        transport="webrtc_or_managed_realtime",
        token_endpoint=None,
        client_events=[
            "room.join.requested",
            "audio.input.started",
            "transcript.user.final",
            "approval.decision",
        ],
        server_events=[
            "room.token.issued",
            "transcript.assistant.delta",
            "approval.requested",
            "memory.candidate.created",
            "session.ended",
        ],
        approval_boundary="Realtime actions reuse approval request resources before any external tool executes.",
        memory_boundary="Raw audio is not remembered; only final text or approved summaries can become memory candidates.",
    )


def memory_contract_for(session: SessionResponse) -> MemoryContractResponse:
    return MemoryContractResponse(
        session_id=session.session_id,
        memory_enabled=session.memory_enabled,
        capture_mode="candidate_review" if session.memory_enabled else "disabled",
        allowed_sources=[
            "user-authored final text messages",
            "assistant summaries from memory-enabled sessions",
            "approved rememberable tool outcomes",
        ],
        excluded_sources=[
            "raw audio or video frames",
            "pending or rejected approval requests",
            "secrets, payment data, authentication codes, and one-time credentials",
            "browser or device diagnostics",
        ],
        promotion_rule=(
            "Create memory candidates only when consent is enabled; a future worker must classify, redact, "
            "and attach provenance before durable storage."
        ),
        deletion_rule="Delete user-visible memory records and matching embedding rows together.",
        storage_target="future PostgreSQL memory tables plus optional pgvector embeddings",
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "storage": "memory", "model_runtime": "stubbed"}


@app.post("/api/sessions", response_model=SessionResponse)
def create_session(payload: CreateSessionRequest) -> SessionResponse:
    session_id = uuid4()
    session = SessionResponse(
        session_id=session_id,
        display_name=payload.display_name,
        status="chat_ready",
        memory_enabled=payload.memory_enabled,
        created_at=now_utc(),
    )
    sessions[session_id] = session
    messages[session_id] = []
    append_message(
        session_id,
        "system",
        "Session started. Chat is available; voice, durable memory, and tool execution are explicit later boundaries.",
    )
    return session


@app.get("/api/sessions/{session_id}", response_model=SessionResponse)
def get_session(session_id: UUID) -> SessionResponse:
    return require_session(session_id)


@app.get("/api/sessions/{session_id}/realtime-contract", response_model=RealtimeContractResponse)
def get_realtime_contract(session_id: UUID) -> RealtimeContractResponse:
    require_session(session_id)
    return realtime_contract_for(session_id)


@app.get("/api/sessions/{session_id}/memory-contract", response_model=MemoryContractResponse)
def get_memory_contract(session_id: UUID) -> MemoryContractResponse:
    session = require_session(session_id)
    return memory_contract_for(session)


@app.get("/api/sessions/{session_id}/messages", response_model=list[MessageResponse])
def list_messages(session_id: UUID) -> list[MessageResponse]:
    require_session(session_id)
    return messages[session_id]


@app.post("/api/sessions/{session_id}/messages", response_model=list[MessageResponse])
def send_message(session_id: UUID, payload: SendMessageRequest) -> list[MessageResponse]:
    session = require_session(session_id)
    if session.status == "ended":
        raise HTTPException(status_code=409, detail="Session has ended.")

    append_message(session_id, "user", payload.content)
    approval_request_id = None
    if sensitive_tool_for(payload.content):
        approval_request_id = create_approval_request(session_id, payload.content).request_id

    append_message(
        session_id,
        "assistant",
        assistant_reply(session, payload.content, approval_request_id),
        approval_request_id=approval_request_id,
    )
    return messages[session_id]


@app.get("/api/sessions/{session_id}/approvals", response_model=list[ApprovalRequestResponse])
def list_approvals(session_id: UUID) -> list[ApprovalRequestResponse]:
    require_session(session_id)
    return [
        request
        for request in approval_requests.values()
        if request.session_id == session_id
    ]


@app.post("/api/approvals/{request_id}/decision", response_model=ApprovalRequestResponse)
def decide_approval(request_id: UUID, payload: ApprovalDecisionRequest) -> ApprovalRequestResponse:
    request = approval_requests.get(request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Approval request not found.")
    if request.status != "pending":
        raise HTTPException(status_code=409, detail="Approval request already decided.")

    if hasattr(request, "model_copy"):
        updated = request.model_copy(update={"status": payload.decision, "decided_at": now_utc()})
    else:
        updated = request.copy(update={"status": payload.decision, "decided_at": now_utc()})
    approval_requests[request_id] = updated
    return updated
