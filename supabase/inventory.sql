-- ============================================================================
-- Smart CafeX — Inventory / Supply Management schema
--
-- Run this once in your Supabase project (SQL Editor -> New query -> paste ->
-- Run). It is additive and idempotent (create table if not exists), so it is
-- safe to run on top of schema.sql. The FastAPI backend connects with the
-- service_role key (bypasses RLS); RLS is still enabled with no anon policies.
--
-- Everything is keyed to the account email (lower-cased), matching the rest of
-- the schema. When Supabase is NOT configured the backend falls back to the
-- per-account JSON state, so the app keeps working in local dev.
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
