-- ============================================================================
-- Content_seller / Cafe_X — Supabase schema
--
-- Run this once in your Supabase project:  SQL Editor -> New query -> paste ->
-- Run.  Then create the private Storage bucket (see the bottom of this file).
--
-- Everything is keyed to the account email (lower-cased). The FastAPI backend
-- connects with the service_role key, which bypasses Row Level Security, so
-- these tables are only ever reached server-side. RLS is still enabled with
-- restrictive policies so nothing is exposed if the anon key is ever used.
-- ============================================================================

-- ---------- accounts (replaces data/user.csv) ----------
create table if not exists public.users (
    email         text primary key,
    password_hash text not null,
    plan          text not null default 'free',
    created_at    timestamptz not null default now()
);

-- ---------- login sessions (replaces the in-memory dict) ----------
-- token_hash = sha256(bearer token). The raw token is NEVER stored.
-- Rows survive restarts/redeploys, so a logged-in user stays logged in.
create table if not exists public.sessions (
    token_hash text primary key,
    email      text not null references public.users(email) on delete cascade,
    created_at timestamptz not null default now(),
    expires_at timestamptz
);
create index if not exists sessions_email_idx on public.sessions(email);

-- ---------- AI usage / rate limiting (replaces usage_logs.csv) ----------
create table if not exists public.usage_logs (
    id      bigint generated always as identity primary key,
    email   text not null,
    feature text not null,
    ts      timestamptz not null default now()
);
create index if not exists usage_logs_lookup_idx on public.usage_logs(email, feature, ts);

-- ---------- per-account JSON state (replaces state.json) ----------
-- Holds smart_data, smart_decisions, smart_tasks, product_type,
-- content_current_suggestion, position_strategy, encrypted
-- commerce_connections, and the _dataset_keys list.
create table if not exists public.user_state (
    email      text primary key,
    state      jsonb not null default '{}'::jsonb,
    updated_at timestamptz not null default now()
);

-- ---------- purchase ledger (replaces purchases.csv) ----------
create table if not exists public.purchases (
    id            bigint generated always as identity primary key,
    email         text not null,
    product       text not null,
    credits_total integer not null default 0,
    credits_used  integer not null default 0,
    amount_inr    integer not null default 0,
    order_id      text,
    payment_id    text,
    created       timestamptz not null default now()
);
create index if not exists purchases_lookup_idx on public.purchases(email, product);

-- ---------- feedback (replaces feedback.csv) ----------
create table if not exists public.feedback (
    id      bigint generated always as identity primary key,
    email   text,
    product text,
    vote    text,
    ts      timestamptz not null default now()
);

-- ---------- app config (stores a generated Fernet key if CS_SECRET_KEY unset) ----------
create table if not exists public.app_config (
    key   text primary key,
    value text
);

-- ---------- RLS: on, restrictive by default (service_role bypasses) ----------
alter table public.users       enable row level security;
alter table public.sessions    enable row level security;
alter table public.usage_logs  enable row level security;
alter table public.user_state  enable row level security;
alter table public.purchases   enable row level security;
alter table public.feedback    enable row level security;
alter table public.app_config  enable row level security;
-- No policies are created for the anon/authenticated roles, so those roles get
-- no access at all. The backend uses the service_role key, which is exempt.

-- ============================================================================
-- Storage bucket for the per-account DataFrame blobs (encrypted Parquet).
-- The SQL below creates a PRIVATE bucket named "user-datasets". If your project
-- restricts inserting into storage.buckets from SQL, create it instead in the
-- dashboard:  Storage -> New bucket -> name "user-datasets" -> Public = OFF.
-- ============================================================================
insert into storage.buckets (id, name, public)
values ('user-datasets', 'user-datasets', false)
on conflict (id) do nothing;
