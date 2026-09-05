-- =========================================================================
-- Website Builder migration.
--
-- Run this once in the Supabase SQL editor. Everything is additive and
-- idempotent, so it is safe to re-run and safe to run on a live database.
-- Until it is run, the backend keeps the new storefront fields in per-account
-- JSON state instead, so nothing breaks while the migration is pending.
-- =========================================================================

-- 1. Storefront fields on the existing product catalogue -------------------
alter table if exists public.products add column if not exists description  text        default '';
alter table if exists public.products add column if not exists image_url    text        default '';
alter table if exists public.products add column if not exists images       jsonb       default '[]'::jsonb;
alter table if exists public.products add column if not exists highlights   jsonb       default '[]'::jsonb;
alter table if exists public.products add column if not exists mrp          numeric;
alter table if exists public.products add column if not exists stock        integer     default 0;
alter table if exists public.products add column if not exists track_stock  boolean     default true;
alter table if exists public.products add column if not exists listed       boolean     default true;
alter table if exists public.products add column if not exists unit_label   text        default '';

-- 2. One site per seller ---------------------------------------------------
create table if not exists public.sites (
  email      text primary key,
  handle     text unique not null,
  published  boolean     not null default false,
  config     jsonb       not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists sites_handle_idx    on public.sites (handle);
create index if not exists sites_published_idx on public.sites (published);

-- The service key bypasses RLS, and the backend is the only writer, but RLS
-- stays on so a leaked anon key can never read a seller's draft site.
alter table public.sites enable row level security;

-- 3. Shopper accounts and orders live in the seller's JSON state today.
--    Promote them to tables here when order volume makes that worthwhile;
--    backend/core/storefront.py is the only module that would change.
