create table if not exists public.sessions (
  session_id uuid primary key,
  display_name text not null check (char_length(display_name) between 1 and 80),
  status text not null check (status in ('chat_ready', 'voice_ready', 'ended')),
  memory_enabled boolean not null default false,
  created_at timestamptz not null default now()
);

create table if not exists public.messages (
  message_id uuid primary key,
  session_id uuid not null references public.sessions(session_id) on delete cascade,
  role text not null check (role in ('user', 'assistant', 'system')),
  content text not null check (char_length(content) <= 2000),
  created_at timestamptz not null default now(),
  approval_request_id uuid null
);

create table if not exists public.approval_requests (
  request_id uuid primary key,
  session_id uuid not null references public.sessions(session_id) on delete cascade,
  tool_name text not null,
  reason text not null,
  status text not null check (status in ('pending', 'approved', 'rejected')),
  created_at timestamptz not null default now(),
  decided_at timestamptz null
);

alter table public.messages
  drop constraint if exists messages_approval_request_id_fkey;
alter table public.messages
  add constraint messages_approval_request_id_fkey
  foreign key (approval_request_id) references public.approval_requests(request_id) on delete set null;

create table if not exists public.memory_candidates (
  candidate_id uuid primary key,
  session_id uuid not null references public.sessions(session_id) on delete cascade,
  source_message_id uuid not null references public.messages(message_id) on delete cascade,
  source_type text not null check (source_type in ('user_message', 'assistant_summary', 'approved_tool_outcome')),
  summary text not null,
  status text not null check (status in ('active', 'deleted')),
  created_at timestamptz not null default now(),
  deleted_at timestamptz null
);

create index if not exists messages_session_created_idx
  on public.messages(session_id, created_at);
create index if not exists approvals_session_created_idx
  on public.approval_requests(session_id, created_at);
create index if not exists memory_candidates_session_created_idx
  on public.memory_candidates(session_id, created_at);

alter table public.sessions enable row level security;
alter table public.messages enable row level security;
alter table public.approval_requests enable row level security;
alter table public.memory_candidates enable row level security;

revoke all on public.sessions from anon, authenticated;
revoke all on public.messages from anon, authenticated;
revoke all on public.approval_requests from anon, authenticated;
revoke all on public.memory_candidates from anon, authenticated;
