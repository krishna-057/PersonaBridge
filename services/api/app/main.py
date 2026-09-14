import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .storage import store


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


@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


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
    status: Literal["token_ready"]
    transport: Literal["webrtc_or_managed_realtime"]
    token_endpoint: str
    client_events: list[str]
    server_events: list[str]
    approval_boundary: str
    memory_boundary: str


class RealtimeTokenRequest(BaseModel):
    device_label: str | None = Field(default=None, max_length=120)


class RealtimeTokenResponse(BaseModel):
    session_id: UUID
    room_id: str
    token: str
    token_type: Literal["opaque_browser_join"]
    transport: Literal["browser_webrtc_shell"]
    participant_id: str
    expires_at: datetime
    issued_at: datetime
    device_label: str | None = None


class MemoryContractResponse(BaseModel):
    session_id: UUID
    memory_enabled: bool
    capture_mode: Literal["disabled", "candidate_review"]
    allowed_sources: list[str]
    excluded_sources: list[str]
    promotion_rule: str
    deletion_rule: str
    storage_target: str


class MemoryCandidateResponse(BaseModel):
    candidate_id: UUID
    session_id: UUID
    source_message_id: UUID
    source_type: Literal["user_message", "assistant_summary", "approved_tool_outcome"]
    summary: str
    status: Literal["active", "deleted"]
    created_at: datetime
    deleted_at: datetime | None = None


PROJECT_ROOT = Path(__file__).resolve().parents[3]
memory_store_setting = os.getenv("MEMORY_STORE_PATH", ".data/memory-candidates.json")
MEMORY_STORE_PATH = Path(memory_store_setting)
if not MEMORY_STORE_PATH.is_absolute():
    MEMORY_STORE_PATH = PROJECT_ROOT / MEMORY_STORE_PATH

sessions: dict[UUID, SessionResponse] = {}
messages: dict[UUID, list[MessageResponse]] = {}
approval_requests: dict[UUID, ApprovalRequestResponse] = {}
realtime_tokens: dict[str, RealtimeTokenResponse] = {}
memory_candidates: dict[UUID, MemoryCandidateResponse] = {}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def model_as_json_dict(model: BaseModel) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return jsonable_encoder(model)


def stored_model(table: str, model: BaseModel) -> None:
    store.request("POST", table, payload=model_as_json_dict(model))


def stored_rows(table: str, **filters: str) -> list[dict]:
    params = {key: f"eq.{value}" for key, value in filters.items()}
    params["select"] = "*"
    return store.request("GET", table, params=params)


def load_memory_candidates() -> None:
    if store.enabled:
        return
    if not MEMORY_STORE_PATH.exists():
        return

    try:
        raw_candidates = json.loads(MEMORY_STORE_PATH.read_text(encoding="utf8"))
    except (json.JSONDecodeError, OSError):
        return

    for raw_candidate in raw_candidates:
        candidate = MemoryCandidateResponse(**raw_candidate)
        memory_candidates[candidate.candidate_id] = candidate


def persist_memory_candidates() -> None:
    if store.enabled:
        return
    MEMORY_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = [
        model_as_json_dict(candidate)
        for candidate in sorted(memory_candidates.values(), key=lambda item: item.created_at)
    ]
    tmp_path = MEMORY_STORE_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf8")
    tmp_path.replace(MEMORY_STORE_PATH)


def require_session(session_id: UUID) -> SessionResponse:
    if store.enabled:
        rows = stored_rows("sessions", session_id=str(session_id))
        if not rows:
            raise HTTPException(status_code=404, detail="Session not found.")
        return SessionResponse(**rows[0])

    session = sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    return session


def store_session(session: SessionResponse) -> SessionResponse:
    if store.enabled:
        store.request(
            "POST",
            "sessions",
            payload=model_as_json_dict(session),
            prefer="resolution=merge-duplicates,return=representation",
        )
        return session

    sessions[session.session_id] = session
    return session


def update_session_status(session: SessionResponse, status: Literal["chat_ready", "voice_ready", "ended"]) -> SessionResponse:
    if hasattr(session, "model_copy"):
        return store_session(session.model_copy(update={"status": status}))
    return store_session(session.copy(update={"status": status}))


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
    if store.enabled:
        stored_model("messages", message)
        return message

    messages[session_id].append(message)
    return message


def should_skip_memory_candidate(content: str) -> bool:
    normalized = content.lower()
    excluded_terms = [
        "password",
        "passcode",
        "otp",
        "one-time code",
        "token",
        "api key",
        "secret",
        "credit card",
        "card number",
        "payment",
        "ssn",
    ]
    return any(term in normalized for term in excluded_terms)


def summarize_memory_candidate(content: str) -> str:
    collapsed = " ".join(content.split())
    if len(collapsed) <= 180:
        return collapsed
    return f"{collapsed[:177]}..."


def create_memory_candidate(session: SessionResponse, source_message: MessageResponse) -> MemoryCandidateResponse | None:
    if not session.memory_enabled or source_message.role != "user":
        return None
    if should_skip_memory_candidate(source_message.content):
        return None

    candidate = MemoryCandidateResponse(
        candidate_id=uuid4(),
        session_id=session.session_id,
        source_message_id=source_message.message_id,
        source_type="user_message",
        summary=summarize_memory_candidate(source_message.content),
        status="active",
        created_at=now_utc(),
    )
    if store.enabled:
        stored_model("memory_candidates", candidate)
        return candidate

    memory_candidates[candidate.candidate_id] = candidate
    persist_memory_candidates()
    return candidate


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
    if store.enabled:
        stored_model("approval_requests", request)
        return request

    approval_requests[request.request_id] = request
    return request


def assistant_reply(session: SessionResponse, user_content: str, approval_id: UUID | None) -> str:
    if approval_id is not None:
        return "I can prepare that action, but I need explicit approval before any external tool runs."

    memory_note = "I will not store this beyond the current session."
    if session.memory_enabled:
        memory_note = "I created reviewable memory candidates only for allowed user text, and you can delete them."

    return f"Noted. For now I can help structure the next step and keep the boundary clear. {memory_note}"


def realtime_contract_for(session_id: UUID) -> RealtimeContractResponse:
    return RealtimeContractResponse(
        session_id=session_id,
        room_id=f"personabridge:{session_id}",
        status="token_ready",
        transport="webrtc_or_managed_realtime",
        token_endpoint=f"/api/sessions/{session_id}/realtime-token",
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


def mint_realtime_token(session: SessionResponse, device_label: str | None) -> RealtimeTokenResponse:
    issued_at = now_utc()
    token = secrets.token_urlsafe(32)
    response = RealtimeTokenResponse(
        session_id=session.session_id,
        room_id=f"personabridge:{session.session_id}",
        token=token,
        token_type="opaque_browser_join",
        transport="browser_webrtc_shell",
        participant_id=f"browser:{uuid4()}",
        expires_at=issued_at + timedelta(minutes=5),
        issued_at=issued_at,
        device_label=device_label,
    )
    realtime_tokens[token] = response
    update_session_status(session, "voice_ready")
    return response


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
            "Create reviewable memory candidates only when consent is enabled; skip obvious secrets and keep "
            "source-message provenance for later classification."
        ),
        deletion_rule="Delete controls tombstone the candidate and remove user-visible summary text.",
        storage_target=("private Supabase tables behind the API" if store.enabled else f"local JSON candidate store at {MEMORY_STORE_PATH}"),
    )


load_memory_candidates()


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "storage": "supabase" if store.enabled else "memory",
        "memory_candidates": "supabase" if store.enabled else "file",
        "model_runtime": "stubbed",
    }


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
    store_session(session)
    if not store.enabled:
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


@app.post("/api/sessions/{session_id}/realtime-token", response_model=RealtimeTokenResponse)
def create_realtime_token(session_id: UUID, payload: RealtimeTokenRequest) -> RealtimeTokenResponse:
    session = require_session(session_id)
    if session.status == "ended":
        raise HTTPException(status_code=409, detail="Session has ended.")
    return mint_realtime_token(session, payload.device_label)


@app.get("/api/sessions/{session_id}/memory-contract", response_model=MemoryContractResponse)
def get_memory_contract(session_id: UUID) -> MemoryContractResponse:
    session = require_session(session_id)
    return memory_contract_for(session)


@app.get("/api/sessions/{session_id}/memory-candidates", response_model=list[MemoryCandidateResponse])
def list_memory_candidates(
    session_id: UUID,
    include_deleted: bool = Query(default=False),
) -> list[MemoryCandidateResponse]:
    require_session(session_id)
    if store.enabled:
        params = {
            "select": "*",
            "session_id": f"eq.{session_id}",
            "order": "created_at.asc",
        }
        if not include_deleted:
            params["status"] = "eq.active"
        return [MemoryCandidateResponse(**row) for row in store.request("GET", "memory_candidates", params=params)]

    candidates = [candidate for candidate in memory_candidates.values() if candidate.session_id == session_id and (include_deleted or candidate.status == "active")]
    return sorted(candidates, key=lambda candidate: candidate.created_at)


@app.delete("/api/memory-candidates/{candidate_id}", response_model=MemoryCandidateResponse)
def delete_memory_candidate(candidate_id: UUID) -> MemoryCandidateResponse:
    if store.enabled:
        rows = stored_rows("memory_candidates", candidate_id=str(candidate_id))
        if not rows:
            raise HTTPException(status_code=404, detail="Memory candidate not found.")
        candidate = MemoryCandidateResponse(**rows[0])
        if candidate.status == "deleted":
            return candidate
        updated_rows = store.request(
            "PATCH",
            "memory_candidates",
            params={"candidate_id": f"eq.{candidate_id}"},
            payload={"status": "deleted", "summary": "[deleted]", "deleted_at": now_utc().isoformat()},
        )
        return MemoryCandidateResponse(**updated_rows[0])

    candidate = memory_candidates.get(candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Memory candidate not found.")

    if candidate.status == "deleted":
        return candidate

    if hasattr(candidate, "model_copy"):
        updated = candidate.model_copy(update={"status": "deleted", "summary": "[deleted]", "deleted_at": now_utc()})
    else:
        updated = candidate.copy(update={"status": "deleted", "summary": "[deleted]", "deleted_at": now_utc()})

    memory_candidates[candidate_id] = updated
    persist_memory_candidates()
    return updated


@app.get("/api/sessions/{session_id}/messages", response_model=list[MessageResponse])
def list_messages(session_id: UUID) -> list[MessageResponse]:
    require_session(session_id)
    if store.enabled:
        rows = store.request(
            "GET",
            "messages",
            params={"select": "*", "session_id": f"eq.{session_id}", "order": "created_at.asc"},
        )
        return [MessageResponse(**row) for row in rows]
    return messages[session_id]


@app.post("/api/sessions/{session_id}/messages", response_model=list[MessageResponse])
def send_message(session_id: UUID, payload: SendMessageRequest) -> list[MessageResponse]:
    session = require_session(session_id)
    if session.status == "ended":
        raise HTTPException(status_code=409, detail="Session has ended.")

    user_message = append_message(session_id, "user", payload.content)
    create_memory_candidate(session, user_message)
    approval_request_id = None
    if sensitive_tool_for(payload.content):
        approval_request_id = create_approval_request(session_id, payload.content).request_id

    append_message(
        session_id,
        "assistant",
        assistant_reply(session, payload.content, approval_request_id),
        approval_request_id=approval_request_id,
    )
    return list_messages(session_id)


@app.get("/api/sessions/{session_id}/approvals", response_model=list[ApprovalRequestResponse])
def list_approvals(session_id: UUID) -> list[ApprovalRequestResponse]:
    require_session(session_id)
    if store.enabled:
        rows = store.request(
            "GET",
            "approval_requests",
            params={"select": "*", "session_id": f"eq.{session_id}", "order": "created_at.asc"},
        )
        return [ApprovalRequestResponse(**row) for row in rows]
    return [
        request
        for request in approval_requests.values()
        if request.session_id == session_id
    ]


@app.post("/api/approvals/{request_id}/decision", response_model=ApprovalRequestResponse)
def decide_approval(request_id: UUID, payload: ApprovalDecisionRequest) -> ApprovalRequestResponse:
    if store.enabled:
        rows = stored_rows("approval_requests", request_id=str(request_id))
        if not rows:
            raise HTTPException(status_code=404, detail="Approval request not found.")
        request = ApprovalRequestResponse(**rows[0])
        if request.status != "pending":
            raise HTTPException(status_code=409, detail="Approval request already decided.")
        updated_rows = store.request(
            "PATCH",
            "approval_requests",
            params={"request_id": f"eq.{request_id}"},
            payload={"status": payload.decision, "decided_at": now_utc().isoformat()},
        )
        return ApprovalRequestResponse(**updated_rows[0])

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
