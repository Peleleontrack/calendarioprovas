-- Calendário de Provas: estrutura inicial
-- Provas (públicas, escritas só pela recolha automática), cache por site e provas guardadas por utilizador.

-- ---------------------------------------------------------------------------
-- Provas juntadas (o que a página mostra)
-- ---------------------------------------------------------------------------
create table if not exists public.races (
  id            text primary key,          -- id da fonte principal, ex. 'athleko:1188'
  keys          text[] not null,           -- ids de todas as fontes juntadas
  name          text not null,
  date          date not null,
  end_date      date,
  location      text not null default '',
  country       text not null default '',
  types         text[] not null default '{}',
  distances     text[] not null default '{}',
  official_url  text not null default '',
  sources       jsonb not null default '[]',
  itra          jsonb,
  updated_at    timestamptz not null default now()
);
create index if not exists races_date_idx on public.races (date);
create index if not exists races_keys_idx on public.races using gin (keys);

alter table public.races enable row level security;
drop policy if exists "Provas são públicas" on public.races;
create policy "Provas são públicas" on public.races for select to anon, authenticated using (true);

-- ---------------------------------------------------------------------------
-- Estado da última recolha (data, sucesso/falha por site)
-- ---------------------------------------------------------------------------
create table if not exists public.meta (
  key        text primary key,
  value      jsonb not null,
  updated_at timestamptz not null default now()
);
alter table public.meta enable row level security;
drop policy if exists "Meta é pública" on public.meta;
create policy "Meta é pública" on public.meta for select to anon, authenticated using (true);

-- ---------------------------------------------------------------------------
-- Última recolha de cada site (para manter os dados quando um site falha)
-- e progresso do Athleko. Só a recolha automática lê e escreve (sem políticas = sem acesso público).
-- ---------------------------------------------------------------------------
create table if not exists public.source_cache (
  source     text primary key,
  items      jsonb not null default '[]',
  state      jsonb,
  updated_at timestamptz not null default now()
);
alter table public.source_cache enable row level security;

-- ---------------------------------------------------------------------------
-- Substitui todas as provas de uma vez (numa transação), chamada pela recolha.
-- ---------------------------------------------------------------------------
create or replace function public.replace_races(payload jsonb, meta_value jsonb)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare n integer;
begin
  delete from public.races where true;
  insert into public.races (id, keys, name, date, end_date, location, country, types, distances, official_url, sources, itra)
  select r.id, r.keys, r.name, r.date, r.end_date, coalesce(r.location, ''), coalesce(r.country, ''),
         coalesce(r.types, '{}'), coalesce(r.distances, '{}'), coalesce(r.official_url, ''),
         coalesce(r.sources, '[]'), r.itra
  from jsonb_populate_recordset(null::public.races, payload) as r
  on conflict (id) do nothing;
  get diagnostics n = row_count;
  insert into public.meta (key, value, updated_at) values ('last_run', meta_value, now())
  on conflict (key) do update set value = excluded.value, updated_at = now();
  return n;
end;
$$;
revoke all on function public.replace_races(jsonb, jsonb) from public, anon, authenticated;
grant execute on function public.replace_races(jsonb, jsonb) to service_role;

-- ---------------------------------------------------------------------------
-- Provas guardadas no "O meu calendário" (cada utilizador só vê as suas)
-- ---------------------------------------------------------------------------
create table if not exists public.saved_races (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null default auth.uid() references auth.users (id) on delete cascade,
  main_key    text not null,               -- primeiro id conhecido da prova
  keys        text[] not null,
  snapshot    jsonb not null,              -- cópia da prova para o caso de desaparecer dos sites
  created_at  timestamptz not null default now(),
  unique (user_id, main_key)
);
create index if not exists saved_races_user_idx on public.saved_races (user_id);

alter table public.saved_races enable row level security;
drop policy if exists "Ver as minhas provas" on public.saved_races;
drop policy if exists "Guardar as minhas provas" on public.saved_races;
drop policy if exists "Atualizar as minhas provas" on public.saved_races;
drop policy if exists "Apagar as minhas provas" on public.saved_races;
create policy "Ver as minhas provas" on public.saved_races for select to authenticated using ((select auth.uid()) = user_id);
create policy "Guardar as minhas provas" on public.saved_races for insert to authenticated with check ((select auth.uid()) = user_id);
create policy "Atualizar as minhas provas" on public.saved_races for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "Apagar as minhas provas" on public.saved_races for delete to authenticated using ((select auth.uid()) = user_id);
