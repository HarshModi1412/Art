-- ============================================================================
-- One Tap Manager — product media + variants
--
-- Run once in Supabase (SQL Editor -> New query -> paste -> Run). Additive and
-- idempotent; safe to run alongside schema.sql / products.sql / site.sql /
-- inventory.sql, and safe to re-run.
--
-- Why this exists
-- ---------------
-- `video_url` was never in a migration, and `options` / `variants` are new.
-- The backend keeps anything the table cannot hold in the per-account JSON
-- sidecar, so the app works without this file — but the values then live
-- outside the database, where nothing else can query them. Running this puts
-- them back in real columns.
--
--   options  = the axes, e.g. [{"name":"Size","values":["S","M","L"]},
--                              {"name":"Colour","values":["Black","Blue"]}]
--   variants = the matrix those axes expand into, one row per combination,
--              each with its own id, sku, stock and optional price override.
--              The product's own `stock` column stays the roll-up of these,
--              so every existing query keeps reading a correct total.
-- ============================================================================

alter table if exists public.products
    add column if not exists video_url text  default '';
alter table if exists public.products
    add column if not exists options   jsonb default '[]'::jsonb;
alter table if exists public.products
    add column if not exists variants  jsonb default '[]'::jsonb;

-- media the seller uploads (logos, hero art, clips, product photos) is stored
-- in Supabase Storage; this table is the index so a redeploy cannot orphan it
create table if not exists public.media (
    id           text primary key,          -- the filename, e.g. 9f2c….jpg
    email        text not null,
    kind         text not null default 'image',   -- image | video
    content_type text default '',
    bytes        integer default 0,
    created_at   timestamptz not null default now()
);
create index if not exists media_email_idx on public.media(email);

alter table public.media enable row level security;
