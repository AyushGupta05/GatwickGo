create extension if not exists pgcrypto;

alter table if exists public.user_stats
  add column if not exists points_total integer not null default 0;

alter table if exists public.user_stats
  add column if not exists collected_families text[] not null default '{}';

alter table if exists public.user_stats
  add column if not exists updated_at timestamptz not null default timezone('utc', now());

create table if not exists public.user_aircraft_collection (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  dedupe_key text not null,
  flight_number text,
  airline text,
  detected_model text not null,
  aircraft_family_code text,
  aircraft_family_display_name text,
  family_rarity text,
  match_score double precision not null,
  source_mode text not null,
  captured_at timestamptz not null default timezone('utc', now()),
  metadata jsonb
);

alter table if exists public.user_aircraft_collection
  add column if not exists user_id uuid references auth.users(id) on delete cascade;

alter table if exists public.user_aircraft_collection
  add column if not exists dedupe_key text;

alter table if exists public.user_aircraft_collection
  add column if not exists flight_number text;

alter table if exists public.user_aircraft_collection
  add column if not exists airline text;

alter table if exists public.user_aircraft_collection
  add column if not exists detected_model text;

alter table if exists public.user_aircraft_collection
  add column if not exists aircraft_family_code text;

alter table if exists public.user_aircraft_collection
  add column if not exists aircraft_family_display_name text;

alter table if exists public.user_aircraft_collection
  add column if not exists family_rarity text;

alter table if exists public.user_aircraft_collection
  add column if not exists match_score double precision;

alter table if exists public.user_aircraft_collection
  add column if not exists source_mode text;

alter table if exists public.user_aircraft_collection
  add column if not exists captured_at timestamptz not null default timezone('utc', now());

alter table if exists public.user_aircraft_collection
  add column if not exists metadata jsonb;

alter table public.user_aircraft_collection
  enable row level security;

drop policy if exists "user_aircraft_collection_select_own" on public.user_aircraft_collection;
create policy "user_aircraft_collection_select_own"
  on public.user_aircraft_collection
  for select
  to authenticated
  using (auth.uid() = user_id);

drop policy if exists "user_aircraft_collection_insert_own" on public.user_aircraft_collection;
create policy "user_aircraft_collection_insert_own"
  on public.user_aircraft_collection
  for insert
  to authenticated
  with check (auth.uid() = user_id);

drop policy if exists "user_aircraft_collection_update_own" on public.user_aircraft_collection;
create policy "user_aircraft_collection_update_own"
  on public.user_aircraft_collection
  for update
  to authenticated
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

grant usage on schema public to authenticated;
grant select, insert, update on table public.user_aircraft_collection to authenticated;

create unique index if not exists user_aircraft_collection_user_dedupe_idx
  on public.user_aircraft_collection (user_id, dedupe_key);

create index if not exists user_aircraft_collection_user_captured_idx
  on public.user_aircraft_collection (user_id, captured_at desc);
