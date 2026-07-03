-- Sotto premium-transcription waitlist.
-- Public (anon) can INSERT a signup; nobody but the project owner can read the rows.

create extension if not exists pgcrypto;

create table if not exists public.waitlist (
  id             uuid primary key default gen_random_uuid(),
  email          text not null,
  name           text,
  use_case       text,          -- what they'd transcribe
  media_type     text,          -- audio / video / both
  hours_per_month text,         -- rough volume estimate
  languages      text,          -- languages they need
  source         text default 'landing',
  user_agent     text,
  created_at     timestamptz not null default now(),
  constraint waitlist_email_format check (email ~* '^[^@\s]+@[^@\s]+\.[^@\s]+$')
);

-- one signup per email (case-insensitive)
create unique index if not exists waitlist_email_unique on public.waitlist (lower(email));

alter table public.waitlist enable row level security;

-- allow anonymous inserts from the public form; no select/update/delete for anon
drop policy if exists "anon can join waitlist" on public.waitlist;
create policy "anon can join waitlist"
  on public.waitlist for insert
  to anon
  with check (true);

grant insert on public.waitlist to anon;
