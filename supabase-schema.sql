-- ============================================
-- GATHER APP — Supabase Database Schema
-- Cities: Warsaw & Kraków (expandable)
-- Model: Free one-time events, Premium for recurring
-- ============================================

-- Enable required extensions
create extension if not exists "uuid-ossp";
create extension if not exists "postgis";

-- ============================================
-- CITIES
-- ============================================
create table public.cities (
  id uuid primary key default uuid_generate_v4(),
  name text not null unique,
  country text not null default 'Poland',
  lat double precision not null,
  lng double precision not null,
  zoom_level int not null default 13,
  active boolean not null default true,
  created_at timestamptz not null default now()
);

-- ============================================
-- PROFILES (extends Supabase auth.users)
-- ============================================
create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text not null,
  avatar_url text,
  bio text,
  city_id uuid references public.cities(id),
  is_premium boolean not null default false,
  premium_until timestamptz,
  stripe_customer_id text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- ============================================
-- CATEGORIES
-- ============================================
create table public.categories (
  id uuid primary key default uuid_generate_v4(),
  name text not null unique,       -- e.g. 'Sports', 'Board Games'
  icon text not null,              -- emoji or icon name
  color text not null default '#6366f1',
  sort_order int not null default 0
);

-- ============================================
-- ACTIVITIES (the core table)
-- ============================================
create type activity_frequency as enum ('one_time', 'daily', 'weekly', 'biweekly', 'monthly');
create type activity_language as enum ('en', 'pl', 'en_pl', 'other');
create type activity_source as enum ('user', 'scraped_google', 'scraped_facebook', 'scraped_meetup', 'scraped_eventbrite', 'manual_seed');
create type activity_status as enum ('active', 'cancelled', 'completed', 'draft');

create table public.activities (
  id uuid primary key default uuid_generate_v4(),
  title text not null,
  description text,
  category_id uuid not null references public.categories(id),
  city_id uuid not null references public.cities(id),
  host_id uuid references public.profiles(id),

  -- Location
  lat double precision not null,
  lng double precision not null,
  location_name text,              -- "Cafe Botanica", "Pole Mokotowskie"
  address text,

  -- Timing
  frequency activity_frequency not null default 'one_time',
  starts_at timestamptz not null,
  ends_at timestamptz,
  duration_minutes int default 120,
  recurrence_day int,              -- 0=Sun..6=Sat for weekly events
  recurrence_time time,            -- e.g. '18:00' for weekly events

  -- Capacity & pricing
  max_participants int,
  price_cents int default 0,       -- 0 = free
  currency text default 'PLN',

  -- Metadata
  lang activity_language not null default 'pl',
  source activity_source not null default 'user',
  source_url text,                 -- original link if scraped
  image_url text,
  status activity_status not null default 'active',
  is_business boolean not null default false,

  -- Timestamps
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Spatial index for fast map queries
create index idx_activities_location on public.activities using gist (
  st_setsrid(st_makepoint(lng, lat), 4326)
);
create index idx_activities_city on public.activities(city_id);
create index idx_activities_category on public.activities(category_id);
create index idx_activities_status on public.activities(status);
create index idx_activities_starts_at on public.activities(starts_at);

-- ============================================
-- PARTICIPANTS (join/leave activities)
-- ============================================
create table public.participants (
  id uuid primary key default uuid_generate_v4(),
  activity_id uuid not null references public.activities(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  joined_at timestamptz not null default now(),
  unique(activity_id, user_id)
);

create index idx_participants_activity on public.participants(activity_id);
create index idx_participants_user on public.participants(user_id);

-- ============================================
-- SAVED / BOOKMARKED ACTIVITIES
-- ============================================
create table public.saved_activities (
  id uuid primary key default uuid_generate_v4(),
  activity_id uuid not null references public.activities(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  saved_at timestamptz not null default now(),
  unique(activity_id, user_id)
);

-- ============================================
-- ROW LEVEL SECURITY
-- ============================================

-- Profiles: public read, own write
alter table public.profiles enable row level security;

create policy "Profiles are viewable by everyone"
  on public.profiles for select using (true);

create policy "Users can update own profile"
  on public.profiles for update using (auth.uid() = id);

create policy "Users can insert own profile"
  on public.profiles for insert with check (auth.uid() = id);

-- Activities: public read, host can write
alter table public.activities enable row level security;

create policy "Activities are viewable by everyone"
  on public.activities for select using (status = 'active');

create policy "Authenticated users can create activities"
  on public.activities for insert
  with check (auth.uid() = host_id);

create policy "Hosts can update own activities"
  on public.activities for update
  using (auth.uid() = host_id);

create policy "Hosts can delete own activities"
  on public.activities for delete
  using (auth.uid() = host_id);

-- Participants: public read, own write
alter table public.participants enable row level security;

create policy "Participants are viewable by everyone"
  on public.participants for select using (true);

create policy "Users can join activities"
  on public.participants for insert
  with check (auth.uid() = user_id);

create policy "Users can leave activities"
  on public.participants for delete
  using (auth.uid() = user_id);

-- Saved activities: own only
alter table public.saved_activities enable row level security;

create policy "Users can view own saved"
  on public.saved_activities for select
  using (auth.uid() = user_id);

create policy "Users can save activities"
  on public.saved_activities for insert
  with check (auth.uid() = user_id);

create policy "Users can unsave activities"
  on public.saved_activities for delete
  using (auth.uid() = user_id);

-- Categories & Cities: public read
alter table public.categories enable row level security;
create policy "Categories are viewable by everyone"
  on public.categories for select using (true);

alter table public.cities enable row level security;
create policy "Cities are viewable by everyone"
  on public.cities for select using (true);

-- ============================================
-- FUNCTIONS
-- ============================================

-- Auto-create profile on signup
create or replace function public.handle_new_user()
returns trigger as $$
begin
  insert into public.profiles (id, display_name, avatar_url)
  values (
    new.id,
    coalesce(new.raw_user_meta_data->>'display_name', split_part(new.email, '@', 1)),
    new.raw_user_meta_data->>'avatar_url'
  );
  return new;
end;
$$ language plpgsql security definer;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- Get participant count for an activity
create or replace function public.get_participant_count(activity_uuid uuid)
returns int as $$
  select count(*)::int from public.participants where activity_id = activity_uuid;
$$ language sql stable;

-- Check if user has joined an activity
create or replace function public.has_joined(activity_uuid uuid, user_uuid uuid)
returns boolean as $$
  select exists(
    select 1 from public.participants
    where activity_id = activity_uuid and user_id = user_uuid
  );
$$ language sql stable;

-- Enforce freemium: block recurring events for non-premium users
create or replace function public.check_freemium_limit()
returns trigger as $$
begin
  if new.frequency != 'one_time' then
    if not exists (
      select 1 from public.profiles
      where id = new.host_id and is_premium = true
    ) then
      raise exception 'Premium subscription required to create recurring events. One-time events are always free!';
    end if;
  end if;
  return new;
end;
$$ language plpgsql security definer;

create trigger enforce_freemium
  before insert or update on public.activities
  for each row execute procedure public.check_freemium_limit();

-- Updated_at auto-update
create or replace function public.update_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger set_updated_at
  before update on public.activities
  for each row execute procedure public.update_updated_at();

create trigger set_updated_at_profiles
  before update on public.profiles
  for each row execute procedure public.update_updated_at();

-- ============================================
-- SEED DATA: Categories
-- ============================================
insert into public.categories (name, icon, color, sort_order) values
  ('Sports & Fitness', '⚽', '#ef4444', 1),
  ('Board Games', '🎲', '#f97316', 2),
  ('Music', '🎵', '#eab308', 3),
  ('Art & Craft', '🎨', '#84cc16', 4),
  ('Language Exchange', '🗣️', '#22c55e', 5),
  ('Outdoor & Nature', '🌿', '#14b8a6', 6),
  ('Tech & Coding', '💻', '#3b82f6', 7),
  ('Food & Cooking', '🍳', '#8b5cf6', 8),
  ('Photography', '📸', '#ec4899', 9),
  ('Dancing', '💃', '#f43f5e', 10),
  ('Book Club', '📚', '#6366f1', 11),
  ('Yoga & Wellness', '🧘', '#a855f7', 12),
  ('Trading Cards', '🃏', '#0ea5e9', 13),
  ('Running', '🏃', '#10b981', 14),
  ('Volunteering', '🤝', '#f59e0b', 15);

-- ============================================
-- SEED DATA: Cities
-- ============================================
insert into public.cities (name, country, lat, lng, zoom_level) values
  ('Warsaw', 'Poland', 52.2297, 21.0122, 13),
  ('Kraków', 'Poland', 50.0647, 19.9450, 13);
