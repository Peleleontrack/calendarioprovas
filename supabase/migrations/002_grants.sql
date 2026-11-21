-- Projetos Supabase novos não dão permissões automáticas sobre tabelas novas à API.
-- As regras RLS (001_init.sql) continuam a decidir que linhas cada um vê.

grant usage on schema public to anon, authenticated, service_role;

-- provas e estado da recolha: leitura pública
grant select on public.races, public.meta to anon, authenticated;

-- calendário pessoal: só com sessão iniciada (e as políticas limitam às próprias linhas)
grant select, insert, update, delete on public.saved_races to authenticated;

-- a recolha automática (chave service_role) escreve tudo
grant select, insert, update, delete on public.races, public.meta, public.source_cache, public.saved_races to service_role;
