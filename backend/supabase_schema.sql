create table if not exists public.portal_users (
  username text primary key,
  password_hash text not null,
  role text not null check (role in ('admin', 'manager', 'viewer')),
  totp_secret text not null,
  mfa_enabled boolean not null default true,
  mfa_verified boolean not null default false,
  failed_attempts integer not null default 0,
  locked_until timestamptz,
  last_login timestamptz,
  created_at timestamptz not null default now()
);

create table if not exists public.audit_events (
  id bigint generated always as identity primary key,
  timestamp timestamptz not null default now(),
  event_type text not null,
  username text,
  ip text,
  detail text not null default '',
  success boolean
);

create index if not exists audit_events_username_timestamp_idx
  on public.audit_events (username, timestamp desc);

create table if not exists public.portal_files (
  id text primary key,
  department text not null,
  subdepartment text not null,
  data_type text not null,
  data jsonb not null,
  filename text not null,
  uploaded_by text not null,
  uploaded_at double precision not null,
  file_path text not null
);

create index if not exists portal_files_slot_idx
  on public.portal_files (department, subdepartment, data_type, uploaded_at);

create index if not exists portal_files_uploaded_at_idx
  on public.portal_files (uploaded_at);

create or replace function public.record_failed_login(
  target_username text,
  lockout_after integer,
  lock_until timestamptz
)
returns integer
language plpgsql
as $$
declare
  attempts integer;
begin
  update public.portal_users
  set failed_attempts = failed_attempts + 1,
      locked_until = case
        when failed_attempts + 1 >= lockout_after then lock_until
        else locked_until
      end
  where username = target_username
  returning failed_attempts into attempts;

  return coalesce(attempts, 0);
end;
$$;

revoke all on function public.record_failed_login(text, integer, timestamptz)
  from public, anon, authenticated;
grant execute on function public.record_failed_login(text, integer, timestamptz)
  to service_role;

alter table public.portal_users enable row level security;
alter table public.audit_events enable row level security;
alter table public.portal_files enable row level security;

revoke all on public.portal_users, public.audit_events, public.portal_files
  from anon, authenticated;
grant all on public.portal_users, public.audit_events, public.portal_files
  to service_role;
grant usage, select on sequence public.audit_events_id_seq to service_role;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'portal-uploads',
  'portal-uploads',
  false,
  26214400,
  array[
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-excel'
  ]
)
on conflict (id) do update set
  public = false,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;
