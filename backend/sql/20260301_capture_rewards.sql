create extension if not exists pgcrypto;

alter table if exists public.profiles
  add column if not exists points integer not null default 0;

create table if not exists public.user_stats (
  user_id uuid primary key references auth.users(id) on delete cascade,
  points_total integer not null default 0,
  collected_families text[] not null default '{}',
  updated_at timestamptz not null default timezone('utc', now())
);

alter table if exists public.user_stats
  add column if not exists points_total integer not null default 0;

alter table if exists public.user_stats
  add column if not exists collected_families text[] not null default '{}';

alter table if exists public.user_stats
  add column if not exists updated_at timestamptz not null default timezone('utc', now());

create table if not exists public.user_captures (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  airline text not null,
  aircraft_family text not null,
  flight_number text,
  capture_points integer not null default 5,
  confidence double precision,
  phase text,
  phase_confidence double precision,
  result jsonb not null,
  match jsonb,
  feed jsonb,
  enrichment jsonb,
  observer_lat double precision,
  observer_lon double precision,
  radius_km double precision,
  frames_processed integer,
  requested_mode text,
  effective_mode text,
  fallback_reason text,
  created_at timestamptz not null default timezone('utc', now())
);

alter table if exists public.user_captures
  add column if not exists user_id uuid references auth.users(id) on delete cascade;

alter table if exists public.user_captures
  add column if not exists airline text;

alter table if exists public.user_captures
  add column if not exists aircraft_family text;

alter table if exists public.user_captures
  add column if not exists flight_number text;

alter table if exists public.user_captures
  add column if not exists capture_points integer not null default 5;

alter table if exists public.user_captures
  add column if not exists confidence double precision;

alter table if exists public.user_captures
  add column if not exists phase text;

alter table if exists public.user_captures
  add column if not exists phase_confidence double precision;

alter table if exists public.user_captures
  add column if not exists result jsonb;

alter table if exists public.user_captures
  add column if not exists match jsonb;

alter table if exists public.user_captures
  add column if not exists feed jsonb;

alter table if exists public.user_captures
  add column if not exists enrichment jsonb;

alter table if exists public.user_captures
  add column if not exists observer_lat double precision;

alter table if exists public.user_captures
  add column if not exists observer_lon double precision;

alter table if exists public.user_captures
  add column if not exists radius_km double precision;

alter table if exists public.user_captures
  add column if not exists frames_processed integer;

alter table if exists public.user_captures
  add column if not exists requested_mode text;

alter table if exists public.user_captures
  add column if not exists effective_mode text;

alter table if exists public.user_captures
  add column if not exists fallback_reason text;

alter table if exists public.user_captures
  add column if not exists created_at timestamptz not null default timezone('utc', now());

create table if not exists public.reward_ledger (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  capture_id uuid references public.user_captures(id) on delete set null,
  points integer not null,
  reason text not null,
  created_at timestamptz not null default timezone('utc', now())
);

alter table if exists public.reward_ledger
  add column if not exists user_id uuid references auth.users(id) on delete cascade;

alter table if exists public.reward_ledger
  add column if not exists capture_id uuid references public.user_captures(id) on delete set null;

alter table if exists public.reward_ledger
  add column if not exists points integer not null default 0;

alter table if exists public.reward_ledger
  add column if not exists reason text not null default 'gemini_capture';

alter table if exists public.reward_ledger
  add column if not exists created_at timestamptz not null default timezone('utc', now());

alter table public.user_stats enable row level security;
alter table public.user_captures enable row level security;
alter table public.reward_ledger enable row level security;

drop policy if exists "user_stats_select_own" on public.user_stats;
create policy "user_stats_select_own"
  on public.user_stats
  for select
  to authenticated
  using (auth.uid() = user_id);

drop policy if exists "user_stats_insert_own" on public.user_stats;
create policy "user_stats_insert_own"
  on public.user_stats
  for insert
  to authenticated
  with check (auth.uid() = user_id);

drop policy if exists "user_stats_update_own" on public.user_stats;
create policy "user_stats_update_own"
  on public.user_stats
  for update
  to authenticated
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

drop policy if exists "user_captures_select_own" on public.user_captures;
create policy "user_captures_select_own"
  on public.user_captures
  for select
  to authenticated
  using (auth.uid() = user_id);

drop policy if exists "user_captures_insert_own" on public.user_captures;
create policy "user_captures_insert_own"
  on public.user_captures
  for insert
  to authenticated
  with check (auth.uid() = user_id);

drop policy if exists "reward_ledger_select_own" on public.reward_ledger;
create policy "reward_ledger_select_own"
  on public.reward_ledger
  for select
  to authenticated
  using (auth.uid() = user_id);

drop policy if exists "reward_ledger_insert_own" on public.reward_ledger;
create policy "reward_ledger_insert_own"
  on public.reward_ledger
  for insert
  to authenticated
  with check (auth.uid() = user_id);

create index if not exists user_captures_user_created_idx
  on public.user_captures (user_id, created_at desc);

create index if not exists reward_ledger_user_created_idx
  on public.reward_ledger (user_id, created_at desc);
