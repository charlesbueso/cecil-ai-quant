-- Cecil AI – Chat Attachments Storage Bucket
-- Run this in Supabase SQL Editor (Dashboard → SQL Editor → New Query)
-- ═══════════════════════════════════════════════════════════════════
-- This creates a Supabase Storage bucket for persisting uploaded files
-- (images, CSVs, PDFs, etc.) attached to chat messages.
-- ═══════════════════════════════════════════════════════════════════

-- 1. Create the storage bucket (public so URLs work directly in <img> tags)
insert into storage.buckets (id, name, public)
values ('chat-attachments', 'chat-attachments', true)
on conflict (id) do nothing;

-- 2. Allow authenticated users to upload files to their own folder
--    Files are stored as: {user_id}/{upload_id}_{filename}
create policy "Users can upload own attachments"
  on storage.objects for insert
  with check (
    bucket_id = 'chat-attachments'
    and auth.uid()::text = (storage.foldername(name))[1]
  );

-- 3. Allow anyone to read (public bucket, URLs contain unguessable UUIDs)
create policy "Public read for chat-attachments"
  on storage.objects for select
  using (bucket_id = 'chat-attachments');

-- 4. Allow users to delete their own attachments
create policy "Users can delete own attachments"
  on storage.objects for delete
  using (
    bucket_id = 'chat-attachments'
    and auth.uid()::text = (storage.foldername(name))[1]
  );
