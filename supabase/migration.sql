-- Cecil AI – Supabase Database Schema
-- Run this in Supabase SQL Editor (Dashboard → SQL Editor → New Query)
-- ═══════════════════════════════════════════════════════════════════

-- ── Profiles (auto-linked to auth.users) ────────────────────────
create table if not exists public.profiles (
  id uuid references auth.users on delete cascade primary key,
  email text,
  display_name text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- ── Conversations ───────────────────────────────────────────────
create table if not exists public.conversations (
  id uuid default gen_random_uuid() primary key,
  user_id uuid references public.profiles(id) on delete cascade not null,
  title text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- ── Messages ────────────────────────────────────────────────────
create table if not exists public.messages (
  id uuid default gen_random_uuid() primary key,
  conversation_id uuid references public.conversations(id) on delete cascade not null,
  role text not null check (role in ('user', 'assistant', 'system')),
  content text not null,
  metadata jsonb default '{}',
  created_at timestamptz default now()
);

-- ── User Reports ────────────────────────────────────────────────
create table if not exists public.user_reports (
  id uuid default gen_random_uuid() primary key,
  user_id uuid references public.profiles(id) on delete cascade not null,
  conversation_id uuid references public.conversations(id) on delete set null,
  filename text not null,
  title text,
  report_html text,
  report_type text default 'html',
  created_at timestamptz default now()
);

-- ── User Settings ───────────────────────────────────────────────
create table if not exists public.user_settings (
  user_id uuid references public.profiles(id) on delete cascade primary key,
  settings jsonb default '{}',
  updated_at timestamptz default now()
);

-- ═══════════════════════════════════════════════════════════════════
-- Row Level Security
-- ═══════════════════════════════════════════════════════════════════

alter table public.profiles enable row level security;
alter table public.conversations enable row level security;
alter table public.messages enable row level security;
alter table public.user_reports enable row level security;
alter table public.user_settings enable row level security;

-- Profiles
create policy "Users can view own profile"
  on public.profiles for select using (auth.uid() = id);
create policy "Users can update own profile"
  on public.profiles for update using (auth.uid() = id);

-- Conversations
create policy "Users can view own conversations"
  on public.conversations for select using (auth.uid() = user_id);
create policy "Users can create conversations"
  on public.conversations for insert with check (auth.uid() = user_id);
create policy "Users can update own conversations"
  on public.conversations for update using (auth.uid() = user_id);
create policy "Users can delete own conversations"
  on public.conversations for delete using (auth.uid() = user_id);

-- Messages (access scoped through conversation ownership)
create policy "Users can view own messages"
  on public.messages for select using (
    conversation_id in (select id from public.conversations where user_id = auth.uid())
  );
create policy "Users can create messages"
  on public.messages for insert with check (
    conversation_id in (select id from public.conversations where user_id = auth.uid())
  );

-- User Reports
create policy "Users can view own reports"
  on public.user_reports for select using (auth.uid() = user_id);
create policy "Users can create reports"
  on public.user_reports for insert with check (auth.uid() = user_id);
create policy "Users can delete own reports"
  on public.user_reports for delete using (auth.uid() = user_id);

-- User Settings
create policy "Users can view own settings"
  on public.user_settings for select using (auth.uid() = user_id);
create policy "Users can upsert own settings"
  on public.user_settings for insert with check (auth.uid() = user_id);
create policy "Users can update own settings"
  on public.user_settings for update using (auth.uid() = user_id);

-- ═══════════════════════════════════════════════════════════════════
-- Auto-create profile on signup trigger
-- ═══════════════════════════════════════════════════════════════════

create or replace function public.handle_new_user()
returns trigger as $$
begin
  insert into public.profiles (id, email, display_name)
  values (new.id, new.email, split_part(new.email, '@', 1));
  return new;
end;
$$ language plpgsql security definer;

-- Drop trigger if exists, then create
drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ═══════════════════════════════════════════════════════════════════
-- Indexes for performance
-- ═══════════════════════════════════════════════════════════════════

create index if not exists idx_conversations_user_id on public.conversations(user_id);
create index if not exists idx_conversations_updated_at on public.conversations(updated_at desc);
create index if not exists idx_messages_conversation_id on public.messages(conversation_id);
create index if not exists idx_messages_created_at on public.messages(created_at);
create index if not exists idx_user_reports_user_id on public.user_reports(user_id);

-- ═══════════════════════════════════════════════════════════════════
-- Storage – chat-attachments bucket for uploaded files & images
-- ═══════════════════════════════════════════════════════════════════

-- Create the storage bucket (public so URLs work directly in <img> tags)
insert into storage.buckets (id, name, public)
values ('chat-attachments', 'chat-attachments', true)
on conflict (id) do nothing;

-- Allow authenticated users to upload files to their own folder
create policy "Users can upload own attachments"
  on storage.objects for insert
  with check (
    bucket_id = 'chat-attachments'
    and auth.uid()::text = (storage.foldername(name))[1]
  );

-- Allow anyone to read (public bucket, URLs contain unguessable UUIDs)
create policy "Public read for chat-attachments"
  on storage.objects for select
  using (bucket_id = 'chat-attachments');

-- Allow users to delete their own attachments
create policy "Users can delete own attachments"
  on storage.objects for delete
  using (
    bucket_id = 'chat-attachments'
    and auth.uid()::text = (storage.foldername(name))[1]
  );
