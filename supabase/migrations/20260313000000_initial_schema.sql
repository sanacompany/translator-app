-- ============================================================
-- Freemium Audio Translation App - Initial Schema
-- ============================================================

-- ============================================================
-- 1. PROFILES TABLE
-- ============================================================

create table if not exists public.profiles (
  id                   uuid        not null references auth.users (id) on delete cascade,
  email                text,
  plan                 text        not null default 'free' check (plan in ('free', 'pro')),
  monthly_minutes_used numeric     not null default 0,
  monthly_reset_date   timestamptz,
  created_at           timestamptz not null default now(),
  updated_at           timestamptz not null default now(),
  constraint profiles_pkey primary key (id)
);

-- ============================================================
-- 2. TRANSLATION_HISTORY TABLE
-- ============================================================

create table if not exists public.translation_history (
  id              uuid        not null default gen_random_uuid(),
  user_id         uuid        not null references public.profiles (id) on delete cascade,
  source_text     text,
  translated_text text,
  source_lang     text,
  target_lang     text,
  mode            text        check (mode in ('mic', 'system')),
  created_at      timestamptz not null default now(),
  constraint translation_history_pkey primary key (id)
);

-- ============================================================
-- 3. USAGE_LOGS TABLE
-- ============================================================

create table if not exists public.usage_logs (
  id           uuid        not null default gen_random_uuid(),
  user_id      uuid        not null references public.profiles (id) on delete cascade,
  seconds_used integer     not null,
  mode         text,
  created_at   timestamptz not null default now(),
  constraint usage_logs_pkey primary key (id)
);

-- ============================================================
-- 4. ROW LEVEL SECURITY
-- ============================================================

alter table public.profiles          enable row level security;
alter table public.translation_history enable row level security;
alter table public.usage_logs        enable row level security;

-- profiles: read own row
create policy "profiles_select_own"
  on public.profiles
  for select
  using (auth.uid() = id);

-- profiles: update own row
create policy "profiles_update_own"
  on public.profiles
  for update
  using (auth.uid() = id)
  with check (auth.uid() = id);

-- translation_history: insert own rows
create policy "translation_history_insert_own"
  on public.translation_history
  for insert
  with check (auth.uid() = user_id);

-- translation_history: read own rows
create policy "translation_history_select_own"
  on public.translation_history
  for select
  using (auth.uid() = user_id);

-- usage_logs: insert own rows
create policy "usage_logs_insert_own"
  on public.usage_logs
  for insert
  with check (auth.uid() = user_id);

-- usage_logs: read own rows
create policy "usage_logs_select_own"
  on public.usage_logs
  for select
  using (auth.uid() = user_id);

-- ============================================================
-- 5. TRIGGER: auto-create profile on new user sign-up
-- ============================================================

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, email, plan, monthly_minutes_used, monthly_reset_date)
  values (
    new.id,
    new.email,
    'free',
    0,
    date_trunc('month', now()) + interval '1 month'
  )
  on conflict (id) do nothing;
  return new;
end;
$$;

-- drop existing trigger if present so this script is re-runnable
drop trigger if exists on_auth_user_created on auth.users;

create trigger on_auth_user_created
  after insert on auth.users
  for each row
  execute function public.handle_new_user();

-- ============================================================
-- 6. FUNCTION: increment_usage
--    Adds seconds to usage_logs and updates monthly_minutes_used.
--    Resets the counter first if monthly_reset_date has passed.
--    Free plan cap: 60 minutes (3600 seconds) per month.
-- ============================================================

create or replace function public.increment_usage(
  p_user_id uuid,
  p_seconds  int
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_plan                text;
  v_monthly_minutes     numeric;
  v_monthly_reset_date  timestamptz;
  v_free_cap_seconds    constant numeric := 3600; -- 60 minutes
  v_current_seconds     numeric;
  v_new_seconds         numeric;
  v_allowed_seconds     int;
  v_capped              boolean := false;
begin
  -- Lock the profile row for update
  select plan, monthly_minutes_used, monthly_reset_date
    into v_plan, v_monthly_minutes, v_monthly_reset_date
    from public.profiles
   where id = p_user_id
     for update;

  if not found then
    raise exception 'Profile not found for user %', p_user_id;
  end if;

  -- Reset monthly counter if reset date has passed
  if v_monthly_reset_date is null or now() >= v_monthly_reset_date then
    v_monthly_minutes    := 0;
    v_monthly_reset_date := date_trunc('month', now()) + interval '1 month';
  end if;

  v_current_seconds := v_monthly_minutes * 60;

  -- Determine how many seconds are actually allowed this call
  if v_plan = 'pro' then
    -- Unlimited for pro
    v_allowed_seconds := p_seconds;
  else
    -- Free tier: cap at 60 minutes total
    if v_current_seconds >= v_free_cap_seconds then
      -- Already at cap
      v_allowed_seconds := 0;
      v_capped          := true;
    elsif (v_current_seconds + p_seconds) > v_free_cap_seconds then
      -- Partial: only allow up to the cap
      v_allowed_seconds := (v_free_cap_seconds - v_current_seconds)::int;
      v_capped          := true;
    else
      v_allowed_seconds := p_seconds;
    end if;
  end if;

  v_new_seconds := v_current_seconds + v_allowed_seconds;

  -- Update profiles
  update public.profiles
     set monthly_minutes_used = v_new_seconds / 60.0,
         monthly_reset_date   = v_monthly_reset_date,
         updated_at           = now()
   where id = p_user_id;

  -- Log usage (only log if seconds were actually consumed)
  if v_allowed_seconds > 0 then
    insert into public.usage_logs (user_id, seconds_used)
    values (p_user_id, v_allowed_seconds);
  end if;

  return jsonb_build_object(
    'allowed_seconds',      v_allowed_seconds,
    'total_seconds_used',   v_new_seconds,
    'monthly_minutes_used', v_new_seconds / 60.0,
    'capped',               v_capped,
    'plan',                 v_plan,
    'reset_date',           v_monthly_reset_date
  );
end;
$$;

-- ============================================================
-- 7. HELPER: updated_at auto-stamp for profiles
-- ============================================================

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

drop trigger if exists profiles_set_updated_at on public.profiles;

create trigger profiles_set_updated_at
  before update on public.profiles
  for each row
  execute function public.set_updated_at();
