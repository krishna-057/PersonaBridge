"use client";

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";

type SessionStatus = "chat_ready" | "voice_ready" | "ended";
type MessageRole = "user" | "assistant" | "system";
type ApprovalStatus = "pending" | "approved" | "rejected";
type VoiceState = "idle" | "joining" | "ready" | "error";

type SessionResponse = {
  session_id: string;
  display_name: string;
  status: SessionStatus;
  memory_enabled: boolean;
  created_at: string;
};

type MessageResponse = {
  message_id: string;
  session_id: string;
  role: MessageRole;
  content: string;
  created_at: string;
  approval_request_id: string | null;
};

type ApprovalRequest = {
  request_id: string;
  session_id: string;
  tool_name: string;
  reason: string;
  status: ApprovalStatus;
  created_at: string;
  decided_at: string | null;
};

type RealtimeContract = {
  session_id: string;
  room_id: string;
  status: "token_ready";
  transport: "webrtc_or_managed_realtime";
  token_endpoint: string;
  client_events: string[];
  server_events: string[];
  approval_boundary: string;
  memory_boundary: string;
};

type RealtimeToken = {
  session_id: string;
  room_id: string;
  token: string;
  token_type: "opaque_browser_join";
  transport: "browser_webrtc_shell";
  participant_id: string;
  expires_at: string;
  issued_at: string;
  device_label: string | null;
};

type MemoryContract = {
  session_id: string;
  memory_enabled: boolean;
  capture_mode: "disabled" | "candidate_review";
  allowed_sources: string[];
  excluded_sources: string[];
  promotion_rule: string;
  deletion_rule: string;
  storage_target: string;
};

type MemoryCandidate = {
  candidate_id: string;
  session_id: string;
  source_message_id: string;
  source_type: "user_message" | "assistant_summary" | "approved_tool_outcome";
  summary: string;
  status: "active" | "deleted";
  created_at: string;
  deleted_at: string | null;
};

const apiBaseUrl = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8200").replace(/\/$/, "");

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers
    }
  });

  if (!response.ok) {
    throw new Error(`API request failed with ${response.status}`);
  }

  return response.json() as Promise<T>;
}

function formatClock(value: string) {
  return new Intl.DateTimeFormat("en", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  }).format(new Date(value));
}

export default function PersonaBridgeHome() {
  const [session, setSession] = useState<SessionResponse | null>(null);
  const [messages, setMessages] = useState<MessageResponse[]>([]);
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([]);
  const [realtimeContract, setRealtimeContract] = useState<RealtimeContract | null>(null);
  const [memoryContract, setMemoryContract] = useState<MemoryContract | null>(null);
  const [memoryCandidates, setMemoryCandidates] = useState<MemoryCandidate[]>([]);
  const [roomToken, setRoomToken] = useState<RealtimeToken | null>(null);
  const [voiceState, setVoiceState] = useState<VoiceState>("idle");
  const [draft, setDraft] = useState("Help me plan a focused architecture study block.");
  const [displayName, setDisplayName] = useState("Krishna");
  const [memoryEnabled, setMemoryEnabled] = useState(false);
  const [statusMessage, setStatusMessage] = useState("Create a session to start the assistant console.");
  const [isSending, setIsSending] = useState(false);
  const localStreamRef = useRef<MediaStream | null>(null);

  const pendingApprovals = useMemo(
    () => approvals.filter((approval) => approval.status === "pending"),
    [approvals]
  );

  const sessionId = session?.session_id;

  const stopLocalAudio = useCallback(() => {
    localStreamRef.current?.getTracks().forEach((track) => track.stop());
    localStreamRef.current = null;
  }, []);

  async function refreshContracts(targetSessionId: string) {
    const [nextRealtimeContract, nextMemoryContract] = await Promise.all([
      requestJson<RealtimeContract>(`/api/sessions/${targetSessionId}/realtime-contract`),
      requestJson<MemoryContract>(`/api/sessions/${targetSessionId}/memory-contract`)
    ]);
    setRealtimeContract(nextRealtimeContract);
    setMemoryContract(nextMemoryContract);
  }

  const refreshApprovals = useCallback(async (targetSessionId: string) => {
    const nextApprovals = await requestJson<ApprovalRequest[]>(`/api/sessions/${targetSessionId}/approvals`);
    setApprovals(nextApprovals);
  }, []);

  const refreshMemoryCandidates = useCallback(async (targetSessionId: string) => {
    const nextCandidates = await requestJson<MemoryCandidate[]>(
      `/api/sessions/${targetSessionId}/memory-candidates`
    );
    setMemoryCandidates(nextCandidates);
  }, []);

  async function createSession() {
    setStatusMessage("Creating session...");
    setMessages([]);
    setApprovals([]);
    setMemoryCandidates([]);
    setRealtimeContract(null);
    setMemoryContract(null);
    setRoomToken(null);
    setVoiceState("idle");
    stopLocalAudio();

    try {
      const created = await requestJson<SessionResponse>("/api/sessions", {
        method: "POST",
        body: JSON.stringify({
          display_name: displayName,
          memory_enabled: memoryEnabled
        })
      });
      setSession(created);
      setStatusMessage("Session ready.");

      const seedMessages = await requestJson<MessageResponse[]>(`/api/sessions/${created.session_id}/messages`);
      setMessages(seedMessages);
      await refreshContracts(created.session_id);
      await refreshApprovals(created.session_id);
      await refreshMemoryCandidates(created.session_id);
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "Could not create a session.");
    }
  }

  async function startVoiceRoom() {
    if (!sessionId || !realtimeContract) {
      return;
    }

    setVoiceState("joining");
    setStatusMessage("Requesting microphone and room token...");
    stopLocalAudio();

    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error("This browser does not expose microphone capture.");
      }

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      localStreamRef.current = stream;
      const audioTrack = stream.getAudioTracks()[0];
      const deviceLabel = audioTrack?.label || "browser microphone";
      const token = await requestJson<RealtimeToken>(realtimeContract.token_endpoint, {
        method: "POST",
        body: JSON.stringify({ device_label: deviceLabel })
      });
      const nextSession = await requestJson<SessionResponse>(`/api/sessions/${sessionId}`);
      setRoomToken(token);
      setSession(nextSession);
      setVoiceState("ready");
      setStatusMessage("Voice shell ready with a scoped room token.");
    } catch (error) {
      stopLocalAudio();
      setRoomToken(null);
      setVoiceState("error");
      setStatusMessage(error instanceof Error ? error.message : "Could not start the voice shell.");
    }
  }

  function leaveVoiceRoom() {
    stopLocalAudio();
    setRoomToken(null);
    setVoiceState("idle");
    setStatusMessage("Local microphone stopped. The session remains available for chat.");
  }

  async function sendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!sessionId || draft.trim().length === 0) {
      return;
    }

    setIsSending(true);
    setStatusMessage("Sending message...");

    try {
      const nextMessages = await requestJson<MessageResponse[]>(`/api/sessions/${sessionId}/messages`, {
        method: "POST",
        body: JSON.stringify({ content: draft })
      });
      setMessages(nextMessages);
      setDraft("");
      await refreshApprovals(sessionId);
      await refreshMemoryCandidates(sessionId);
      setStatusMessage("Assistant response received.");
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "Could not send the message.");
    } finally {
      setIsSending(false);
    }
  }

  async function decideApproval(requestId: string, decision: "approved" | "rejected") {
    if (!sessionId) {
      return;
    }

    setStatusMessage(`${decision === "approved" ? "Approving" : "Rejecting"} request...`);
    try {
      await requestJson<ApprovalRequest>(`/api/approvals/${requestId}/decision`, {
        method: "POST",
        body: JSON.stringify({ decision })
      });
      await refreshApprovals(sessionId);
      setStatusMessage("Approval queue updated.");
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "Could not update the approval.");
    }
  }

  async function deleteMemoryCandidate(candidateId: string) {
    if (!sessionId) {
      return;
    }

    setStatusMessage("Deleting memory candidate...");
    try {
      await requestJson<MemoryCandidate>(`/api/memory-candidates/${candidateId}`, {
        method: "DELETE"
      });
      await refreshMemoryCandidates(sessionId);
      setStatusMessage("Memory candidate deleted.");
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "Could not delete the memory candidate.");
    }
  }

  useEffect(() => {
    if (!sessionId) {
      return;
    }

    const interval = window.setInterval(() => {
      void refreshApprovals(sessionId).catch(() => {
        setStatusMessage("Approval refresh failed.");
      });
    }, 5000);

    return () => window.clearInterval(interval);
  }, [refreshApprovals, sessionId]);

  useEffect(() => {
    return () => stopLocalAudio();
  }, [stopLocalAudio]);

  return (
    <main className="workspace-shell">
      <section className="conversation-panel" aria-label="PersonaBridge conversation">
        <div className="topbar">
          <div>
            <span>PersonaBridge</span>
            <strong>{session ? session.display_name : "New session"}</strong>
          </div>
          <button type="button" onClick={createSession}>
            {session ? "New Session" : "Start"}
          </button>
        </div>

        <div className="session-strip" aria-label="Session status">
          <label>
            <span>Name</span>
            <input
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              disabled={Boolean(session)}
              maxLength={80}
            />
          </label>
          <label className="toggle-row">
            <input
              type="checkbox"
              checked={memoryEnabled}
              onChange={(event) => setMemoryEnabled(event.target.checked)}
              disabled={Boolean(session)}
            />
            <span>Memory consent</span>
          </label>
          <div>
            <span>Status</span>
            <strong>{session?.status.replace("_", " ") ?? "idle"}</strong>
          </div>
          <div>
            <span>Pending approvals</span>
            <strong>{pendingApprovals.length}</strong>
          </div>
          <div>
            <span>Memories</span>
            <strong>{memoryCandidates.length}</strong>
          </div>
        </div>

        <div className="message-list" aria-label="Messages">
          {messages.length === 0 ? <p className="empty-state">{statusMessage}</p> : null}
          {messages.map((message) => (
            <article className="message-row" data-role={message.role} key={message.message_id}>
              <div>
                <strong>{message.role}</strong>
                <time>{formatClock(message.created_at)}</time>
              </div>
              <p>{message.content}</p>
            </article>
          ))}
        </div>

        <form className="composer" onSubmit={sendMessage}>
          <textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            disabled={!sessionId || isSending}
            placeholder="Send a message"
            rows={3}
          />
          <button type="submit" disabled={!sessionId || isSending || draft.trim().length === 0}>
            {isSending ? "Sending" : "Send"}
          </button>
        </form>
      </section>

      <aside className="control-panel" aria-label="Memory and approvals">
        <section className="panel-block">
          <div className="panel-header">
            <span>Memory</span>
            <strong>
              {memoryContract?.capture_mode.replace("_", " ") ?? "Off"} / {memoryCandidates.length}
            </strong>
          </div>
          <p>
            {memoryContract?.promotion_rule ??
              "Durable memory is gated by session consent. This scaffold keeps messages in memory until the storage model is added."}
          </p>
          {memoryContract ? (
            <dl className="contract-list">
              <div>
                <dt>Target</dt>
                <dd>{memoryContract.storage_target}</dd>
              </div>
              <div>
                <dt>Excluded</dt>
                <dd>{memoryContract.excluded_sources.length} source types</dd>
              </div>
            </dl>
          ) : null}
          <div className="memory-candidate-list" aria-label="Memory candidates">
            {memoryCandidates.length === 0 ? <p className="empty-state">No active memory candidates.</p> : null}
            {memoryCandidates.map((candidate) => (
              <article className="memory-candidate-row" key={candidate.candidate_id}>
                <div>
                  <strong>{candidate.source_type.replace("_", " ")}</strong>
                  <time>{formatClock(candidate.created_at)}</time>
                </div>
                <p>{candidate.summary}</p>
                <button type="button" onClick={() => deleteMemoryCandidate(candidate.candidate_id)}>
                  Delete
                </button>
              </article>
            ))}
          </div>
        </section>

        <section className="panel-block">
          <div className="panel-header">
            <span>Realtime</span>
            <strong>{voiceState === "ready" ? "Voice ready" : realtimeContract?.status.replace("_", " ") ?? "Not started"}</strong>
          </div>
          <p>{realtimeContract?.memory_boundary ?? "Voice/video joins the same session boundary after the room contract exists."}</p>
          <div className="voice-shell" data-state={voiceState}>
            <div>
              <span>Voice shell</span>
              <strong>{voiceState}</strong>
            </div>
            <div className="voice-actions">
              <button
                type="button"
                onClick={startVoiceRoom}
                disabled={!sessionId || !realtimeContract || voiceState === "joining" || voiceState === "ready"}
              >
                {voiceState === "joining" ? "Joining" : "Join Voice"}
              </button>
              <button type="button" onClick={leaveVoiceRoom} disabled={voiceState !== "ready"}>
                Leave
              </button>
            </div>
          </div>
          {realtimeContract ? (
            <dl className="contract-list">
              <div>
                <dt>Room</dt>
                <dd>{roomToken?.room_id ?? realtimeContract.room_id}</dd>
              </div>
              <div>
                <dt>Events</dt>
                <dd>
                  {realtimeContract.client_events.length} client / {realtimeContract.server_events.length} server
                </dd>
              </div>
              <div>
                <dt>Token</dt>
                <dd>{roomToken ? `expires ${formatClock(roomToken.expires_at)}` : realtimeContract.token_endpoint}</dd>
              </div>
              <div>
                <dt>Device</dt>
                <dd>{roomToken?.device_label ?? "not joined"}</dd>
              </div>
            </dl>
          ) : null}
        </section>

        <section className="panel-block">
          <div className="panel-header">
            <span>Approvals</span>
            <strong>{approvals.length}</strong>
          </div>
          {approvals.length === 0 ? <p className="empty-state">No tool requests yet.</p> : null}
          {approvals.map((approval) => (
            <article className="approval-row" data-status={approval.status} key={approval.request_id}>
              <div>
                <strong>{approval.tool_name}</strong>
                <span>{approval.status}</span>
              </div>
              <p>{approval.reason}</p>
              {approval.status === "pending" ? (
                <div className="approval-actions">
                  <button type="button" onClick={() => decideApproval(approval.request_id, "approved")}>
                    Approve
                  </button>
                  <button type="button" onClick={() => decideApproval(approval.request_id, "rejected")}>
                    Reject
                  </button>
                </div>
              ) : null}
            </article>
          ))}
        </section>

        <section className="panel-block">
          <div className="panel-header">
            <span>Runtime</span>
            <strong>{apiBaseUrl}</strong>
          </div>
          <p>{statusMessage}</p>
        </section>
      </aside>
    </main>
  );
}
