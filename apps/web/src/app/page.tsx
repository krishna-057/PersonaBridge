"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

type SessionStatus = "chat_ready" | "voice_ready" | "ended";
type MessageRole = "user" | "assistant" | "system";
type ApprovalStatus = "pending" | "approved" | "rejected";

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
  const [draft, setDraft] = useState("Help me plan a focused architecture study block.");
  const [displayName, setDisplayName] = useState("Krishna");
  const [memoryEnabled, setMemoryEnabled] = useState(false);
  const [statusMessage, setStatusMessage] = useState("Create a session to start the assistant console.");
  const [isSending, setIsSending] = useState(false);

  const pendingApprovals = useMemo(
    () => approvals.filter((approval) => approval.status === "pending"),
    [approvals]
  );

  const sessionId = session?.session_id;

  const refreshApprovals = useCallback(async (targetSessionId: string) => {
    const nextApprovals = await requestJson<ApprovalRequest[]>(`/api/sessions/${targetSessionId}/approvals`);
    setApprovals(nextApprovals);
  }, []);

  async function createSession() {
    setStatusMessage("Creating session...");
    setMessages([]);
    setApprovals([]);

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
      await refreshApprovals(created.session_id);
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "Could not create a session.");
    }
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
            <strong>{session?.memory_enabled ? "Enabled" : "Off"}</strong>
          </div>
          <p>
            Durable memory is gated by session consent. This scaffold keeps messages in memory until the storage model is
            added.
          </p>
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
