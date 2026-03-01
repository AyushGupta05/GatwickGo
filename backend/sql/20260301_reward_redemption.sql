create extension if not exists pgcrypto;

alter table if exists public.rewards
  enable row level security;

alter table if exists public.reward_claims
  enable row level security;

create unique index if not exists reward_claims_user_reward_idx
  on public.reward_claims (user_id, reward_id);

drop policy if exists "rewards_select_active" on public.rewards;
create policy "rewards_select_active"
  on public.rewards
  for select
  to authenticated
  using (coalesce(is_active, true) = true);

drop policy if exists "reward_claims_select_own" on public.reward_claims;
create policy "reward_claims_select_own"
  on public.reward_claims
  for select
  to authenticated
  using (auth.uid() = user_id);

drop policy if exists "reward_claims_insert_own" on public.reward_claims;
create policy "reward_claims_insert_own"
  on public.reward_claims
  for insert
  to authenticated
  with check (auth.uid() = user_id);

drop function if exists public.redeem_reward(bigint);
create or replace function public.redeem_reward(p_reward_id bigint)
returns table (
  claim_id uuid,
  reward_id bigint,
  status text,
  claimed_at timestamptz,
  promo_code text,
  points_total integer,
  already_redeemed boolean
)
language plpgsql
security definer
set search_path = public
as $$
declare
  v_user_id uuid := auth.uid();
  v_reward public.rewards%rowtype;
  v_claim public.reward_claims%rowtype;
  v_points_total integer;
begin
  if v_user_id is null then
    raise exception 'AUTH_REQUIRED';
  end if;

  select *
    into v_reward
    from public.rewards
   where id = p_reward_id
     and coalesce(is_active, true) = true
   limit 1;

  if not found then
    raise exception 'REWARD_NOT_FOUND';
  end if;

  insert into public.user_stats (user_id, points_total, collected_families, updated_at)
  values (v_user_id, 0, '{}', timezone('utc', now()))
  on conflict (user_id) do nothing;

  select coalesce(points_total, 0)
    into v_points_total
    from public.user_stats
   where user_id = v_user_id
   for update;

  select *
    into v_claim
    from public.reward_claims
   where user_id = v_user_id
     and reward_id = p_reward_id
   limit 1;

  if found then
    return query
    select
      v_claim.id,
      v_claim.reward_id,
      coalesce(v_claim.status, 'claimed'),
      v_claim.claimed_at,
      upper(substr(replace(v_claim.id::text, '-', ''), 1, 10)),
      coalesce(v_points_total, 0),
      true;
    return;
  end if;

  if coalesce(v_points_total, 0) < coalesce(v_reward.cost_points, 0) then
    raise exception 'INSUFFICIENT_POINTS';
  end if;

  insert into public.reward_claims (user_id, reward_id, claimed_at, status)
  values (v_user_id, p_reward_id, timezone('utc', now()), 'claimed')
  returning *
    into v_claim;

  update public.user_stats
     set points_total = coalesce(v_points_total, 0) - coalesce(v_reward.cost_points, 0),
         updated_at = timezone('utc', now())
   where user_id = v_user_id
  returning points_total
    into v_points_total;

  return query
  select
    v_claim.id,
    v_claim.reward_id,
    coalesce(v_claim.status, 'claimed'),
    v_claim.claimed_at,
    upper(substr(replace(v_claim.id::text, '-', ''), 1, 10)),
    coalesce(v_points_total, 0),
    false;
end;
$$;

grant execute on function public.redeem_reward(bigint) to authenticated;
