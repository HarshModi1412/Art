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


-- ============================================================================
-- Inventory / Supply Management (see supabase/inventory.sql for the same DDL)
-- ============================================================================
-- ============================================================================

-- ---------- inventory items ----------
create table if not exists public.inventory (
    id             text primary key,               -- app-generated hex id
    email          text not null,
    name           text not null,                  -- item / material name
    category       text default '',
    unit_label     text default 'unit',            -- pcs, kg, box, ...
    current_stock  numeric not null default 0,
    lead_time_days numeric not null default 0,     -- supplier lead time
    safety_stock   numeric not null default 0,
    moq            numeric not null default 0,      -- minimum order quantity
    ordering_cost  numeric,                         -- EOQ "S": cost per order (₹)
    holding_cost   numeric,                         -- EOQ "H": cost/unit/year (₹)
    unit_cost      numeric,                         -- purchase price per unit (₹)
    reorder_qty    numeric,                         -- manual override; null = EOQ auto
    supplier_name  text default '',
    supplier_phone text default '',
    supplier_email text default '',
    created_at     timestamptz not null default now(),
    updated_at     timestamptz not null default now()
);
create index if not exists inventory_email_idx on public.inventory(email);

-- ---------- product -> inventory recipe (bill of materials) ----------
-- "For one <product> sold, consume <qty_per_unit> of <inventory item>."
create table if not exists public.product_inventory_map (
    id           text primary key,
    email        text not null,
    product      text not null,                     -- product name as it appears in Sales
    inventory_id text not null references public.inventory(id) on delete cascade,
    qty_per_unit numeric not null default 1,
    created_at   timestamptz not null default now()
);
create index if not exists pim_email_idx on public.product_inventory_map(email);
create unique index if not exists pim_unique_idx
    on public.product_inventory_map(email, lower(product), inventory_id);

-- ---------- waste / spoilage log ----------
create table if not exists public.inventory_waste (
    id           text primary key,
    email        text not null,
    inventory_id text,
    item_name    text default '',
    qty          numeric not null default 0,
    reason       text default '',
    ts           timestamptz not null default now()
);
create index if not exists waste_email_idx on public.inventory_waste(email, ts);

-- ---------- purchase orders (replaces the JSON PO list) ----------
create table if not exists public.purchase_orders (
    id           text primary key,                  -- = po_number
    email        text not null,
    po_number    text not null,
    status       text not null default 'open',
    n_items      integer not null default 0,
    total_qty    numeric not null default 0,
    total_amount numeric,
    suppliers    jsonb not null default '[]'::jsonb,
    lines        jsonb not null default '[]'::jsonb,
    insight_id   text,
    created_at   timestamptz not null default now()
);
create index if not exists po_email_idx on public.purchase_orders(email, created_at);

-- ---------- RLS: on, restrictive by default (service_role bypasses) ----------
alter table public.inventory             enable row level security;
alter table public.product_inventory_map enable row level security;
alter table public.inventory_waste       enable row level security;
alter table public.purchase_orders       enable row level security;
-- No anon/authenticated policies => those roles get no access. The backend
-- uses the service_role key, which is exempt from RLS.


-- ============================================================================
-- Product Management (see supabase/products.sql for the same DDL)
-- ============================================================================
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
