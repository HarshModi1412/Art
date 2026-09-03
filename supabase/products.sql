-- ============================================================================
-- Smart CafeX — Product Management (canonical products + platform aliases)
--
-- Run once in Supabase (SQL Editor -> New query -> paste -> Run). Additive and
-- idempotent, safe to run alongside schema.sql / inventory.sql. The backend
-- uses the service_role key (bypasses RLS); RLS is on with no anon policies.
--
-- Canonical products are what the seller actually sells (e.g. "ABC"). Each can
-- have platform aliases — the name the same product carries on a sales channel
-- (e.g. "DRF" on Amazon). Sales rows are rolled up from aliases to the
-- canonical product across the app, and Supply links inventory to the canonical
-- product. When Supabase is unset the backend falls back to per-account JSON.
-- ============================================================================

-- ---------- canonical products ----------
create table if not exists public.products (
    id          text primary key,
    email       text not null,
    name        text not null,               -- canonical product name (e.g. ABC)
    category    text default '',
    sku         text default '',             -- seller's own SKU
    price       numeric,                      -- selling price (₹)
    unit_cost   numeric,                      -- cost / COGS per unit (₹)
    status      text not null default 'active',   -- active | archived
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now()
);
create index if not exists products_email_idx on public.products(email);

-- ---------- platform aliases (name as it appears in sales data) ----------
create table if not exists public.product_aliases (
    id          text primary key,
    email       text not null,
    product_id  text not null references public.products(id) on delete cascade,
    alias       text not null,               -- e.g. DRF
    platform    text default '',             -- Amazon, Shopify, Flipkart, ...
    created_at  timestamptz not null default now()
);
create index if not exists product_aliases_email_idx on public.product_aliases(email);
-- one alias name maps to exactly one canonical product per seller
create unique index if not exists product_aliases_unique_idx
    on public.product_aliases(email, lower(alias));

-- ---------- RLS: on, restrictive (service_role bypasses) ----------
alter table public.products        enable row level security;
alter table public.product_aliases enable row level security;
