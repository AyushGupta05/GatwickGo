create extension if not exists pgcrypto;

alter table if exists public.profiles
  enable row level security;

alter table if exists public.user_stats
  enable row level security;

alter table if exists public.user_stats
  add column if not exists points_total integer not null default 0;

alter table if exists public.user_stats
  add column if not exists collected_families text[] not null default '{}';

alter table if exists public.user_stats
  add column if not exists updated_at timestamptz not null default timezone('utc', now());

drop policy if exists "profiles_select_own" on public.profiles;
create policy "profiles_select_own"
  on public.profiles
  for select
  to authenticated
  using (auth.uid() = user_id);

drop policy if exists "profiles_insert_own" on public.profiles;
create policy "profiles_insert_own"
  on public.profiles
  for insert
  to authenticated
  with check (auth.uid() = user_id);

drop policy if exists "profiles_update_own" on public.profiles;
create policy "profiles_update_own"
  on public.profiles
  for update
  to authenticated
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

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

alter table if exists public.aircraft_families
  enable row level security;

drop policy if exists "aircraft_families_select_all" on public.aircraft_families;
create policy "aircraft_families_select_all"
  on public.aircraft_families
  for select
  to authenticated
  using (true);

drop function if exists public.award_capture_progress(integer, text);
create or replace function public.award_capture_progress(
  p_points integer,
  p_family_code text default null
)
returns table (
  user_id uuid,
  points_total integer,
  collected_families text[],
  updated_at timestamptz
)
language plpgsql
security definer
set search_path = public
as $$
declare
  v_user_id uuid := auth.uid();
begin
  if v_user_id is null then
    raise exception 'AUTH_REQUIRED';
  end if;

  insert into public.user_stats (user_id, points_total, collected_families, updated_at)
  values (v_user_id, 0, '{}'::text[], timezone('utc', now()))
  on conflict (user_id) do nothing;

  return query
  update public.user_stats
     set points_total = greatest(coalesce(user_stats.points_total, 0) + greatest(coalesce(p_points, 0), 0), 0),
         collected_families = case
           when p_family_code is null or btrim(p_family_code) = '' or upper(btrim(p_family_code)) = 'UNKNOWN'
             then coalesce(user_stats.collected_families, '{}'::text[])
           when btrim(p_family_code) = any(coalesce(user_stats.collected_families, '{}'::text[]))
             then coalesce(user_stats.collected_families, '{}'::text[])
           else array_append(coalesce(user_stats.collected_families, '{}'::text[]), btrim(p_family_code))
         end,
         updated_at = timezone('utc', now())
   where user_stats.user_id = v_user_id
   returning user_stats.user_id,
             user_stats.points_total,
             user_stats.collected_families,
             user_stats.updated_at;
end;
$$;

grant usage on schema public to authenticated;
grant select, insert, update on table public.profiles to authenticated;
grant select, insert, update on table public.user_stats to authenticated;
grant select on table public.aircraft_families to authenticated;
grant execute on function public.award_capture_progress(integer, text) to authenticated;

create or replace function public.handle_auth_user_bootstrap()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_display_name text;
begin
  v_display_name := coalesce(
    nullif(new.raw_user_meta_data ->> 'display_name', ''),
    nullif(split_part(coalesce(new.email, ''), '@', 1), ''),
    'Gatwick GO User'
  );

  insert into public.profiles (user_id, display_name, created_at)
  values (new.id, v_display_name, coalesce(new.created_at, timezone('utc', now())))
  on conflict (user_id) do nothing;

  insert into public.user_stats (user_id, points_total, collected_families, updated_at)
  values (new.id, 0, '{}'::text[], timezone('utc', now()))
  on conflict (user_id) do nothing;

  return new;
end;
$$;

drop trigger if exists on_auth_user_created_bootstrap on auth.users;
create trigger on_auth_user_created_bootstrap
  after insert on auth.users
  for each row execute procedure public.handle_auth_user_bootstrap();

insert into public.profiles (user_id, display_name, created_at)
select
  u.id,
  coalesce(
    nullif(u.raw_user_meta_data ->> 'display_name', ''),
    nullif(split_part(coalesce(u.email, ''), '@', 1), ''),
    'Gatwick GO User'
  ),
  coalesce(u.created_at, timezone('utc', now()))
from auth.users u
left join public.profiles p
  on p.user_id = u.id
where p.user_id is null;

insert into public.user_stats (user_id, points_total, collected_families, updated_at)
select
  u.id,
  0,
  '{}'::text[],
  timezone('utc', now())
from auth.users u
left join public.user_stats s
  on s.user_id = u.id
where s.user_id is null;
