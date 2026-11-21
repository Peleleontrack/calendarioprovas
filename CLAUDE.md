# Calendário de Provas: contexto para o Claude

Este ficheiro é lido automaticamente pelo Claude Code. Resume o que já foi feito,
porquê, e o que falta. Responde ao utilizador em português de Portugal.

## Objetivo

Um hub pessoal que junta provas de corrida, trail, triatlo e afins de vários sites
portugueses, ordenadas por data, sem duplicados, com "O meu calendário" para marcar
as provas que a pessoa quer fazer. Inscrições fazem-se sempre no site oficial (link).

## Estado atual (funciona)

- `scraper/` recolhe 4 sites, junta duplicados e gera `site/data/races.json` + `site/index.html`.
- `site/app.html` é a página (HTML/CSS/JS sem dependências): pesquisa, filtros
  (Portugal/Internacional, mês, site, tipo, pontos ITRA), lista por mês, "O meu calendário"
  em `localStorage`, código de transferência entre dispositivos, links "+ Google Calendar"
  e exportação `.ics`. `site/index.html` é gerado a partir dele (não editar à mão).
- `scraper/store.py`: com `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` grava no Supabase (tabelas `races`,
  `meta`, `source_cache`; função `replace_races`); sem eles, usa ficheiros em `site/data/`.
- `site/config.js`: URL + anon key do Supabase. Preenchido = a página lê do Supabase e tem login por
  email (magic link) com o calendário em `saved_races` (RLS por utilizador). Vazio = modo local.
- `.github/workflows/atualizar.yml` corre a recolha de 3 em 3 horas e grava no Supabase (sem commits).
- `vercel.json` publica `site/` sem build.
- Última recolha incluída: cerca de 790 provas (1100 entradas antes de juntar).

Correr: ver `README.md`. Em resumo: `pip install -r requirements.txt`, `python scraper/run.py`,
`python -m http.server 8765 --directory site`. `python scraper/run.py itra` corre só um site;
`python scraper/run.py none` só junta o que está em cache e regenera a página.

## Como cada site é lido (aprendido a custo, não repetir a investigação)

| Site | Método | Cuidados |
|---|---|---|
| Athleko | `GET https://www.athleko.pt/api/events.php?lang=pt&page=N` (JSON, ~30 por página, ~15 páginas) | **Limite de pedidos muito apertado**: ~4 pedidos seguidos e depois HTTP 429 durante ~10 min. Por isso a recolha é incremental: 4 páginas por execução, 8 s entre pedidos, progresso em `site/data/sources/athleko_state.json`. Nunca martelar com retries. Tem muitas provas do Brasil. |
| Portugal Running | Calendário EventOn. A API REST está bloqueada de propósito. Usa-se o mesmo AJAX da página: `POST /wp-admin/admin-ajax.php` com `action=eventon_get_events`, o shortcode da página (`data-sc`) com `focus_start/end_date_range` alargado e `event_count=0`, `nonce` (`"n"` dentro do JS LiteSpeed) e `nonceX` (`__litespeed_var_0__` no HTML). | Devolve ~400 provas de uma vez. Se mudarem o tema/plugin, isto parte primeiro. |
| Racefinder | WooCommerce Store API pública: `GET /wp-json/wc/store/v1/products?per_page=100&page=N`. Cada prova é um produto; a data está no atributo `pa_race-start-date` (dd/mm/aaaa). | O atributo acumula datas de edições antigas: fica-se só com as futuras. Sem localização na API. |
| ITRA | `POST https://itra.run/Races/RaceCalendar` com o token antiforgery da página e `Input.Country=PT`. Os resultados vêm num array JS `raceSearchJsonSidePopupNew` com HTML. | O filtro de datas é ignorado (vem todo o histórico desde 2012), filtra-se localmente. Pontos ITRA por distância vêm como imagens `/images/zero.svg` … `six.svg`; sem imagem = ainda não atribuídos. `green.svg`/`red.svg` são estado de resultados, não pontos. Só PT por agora (`ITRA_COUNTRIES`). |
| OriOasis (orientação) | **Não automatizado.** Tem desafio anti-bot da Cloudflare. O calendário da Federação (fpo.pt) aponta para lá, não há alternativa. | Não contornar a proteção. Opção prevista: ficheiro manual `site/data/sources/orioasis.json` (formato no README). |
| Strava | Não serve para descobrir provas (endpoint "Running Races" removido em 2021). Serve para as atividades do próprio utilizador: ver fase 2. | |

## Junção de duplicados (`scraper/run.py`)

- Agrupa entradas de sites diferentes com data próxima e nome parecido.
- Os nomes são normalizados (sem acentos, anos, números de edição, palavras vazias).
  `GENERIC` lista palavras que muitas provas partilham ("São Silvestre", "Meia Maratona",
  "Trilhos"...) e que não chegam para juntar: sem isto, "São Silvestre de Beja" juntava-se
  com "São Silvestre de Mirandela".
- Correspondência forte (2+ palavras distintivas em comum, ou iguais) aceita até 2 dias de diferença;
  correspondência fraca (um nome contido no outro) só até 1 dia.
- Cada prova juntada guarda `keys` (ids de todas as fontes, ex. `athleko:1188`), que é o que
  "O meu calendário" usa para reencontrar a prova mesmo que o id principal mude.
- Prioridade para nome/link principal: athleko > portugalrunning > racefinder > itra.

## Deploy: GitHub + Vercel + Supabase (com login) — código feito, ver README para os passos

Decisões já tomadas com o utilizador:
1. **GitHub**: repositório com o código. A recolha continua no **GitHub Actions** de 3 em 3 horas
   (o cron do Vercel no plano grátis só corre 1x/dia e tem timeouts curtos; a recolha demora
   minutos e o Athleko precisa de várias rondas por dia).
2. **Supabase**: projeto próprio e separado (o utilizador é que cria/autoriza; confirmar custo antes).
   - Tabela de provas: o scraper faz upsert com a service role key guardada como **secret do GitHub**
     (nunca no código). Leitura pública (RLS: `select` para `anon`).
   - Login por email (magic link, sem password).
   - Tabela das provas guardadas por utilizador, com RLS (cada um só vê as suas). Substitui o
     `localStorage` e o código de transferência; manter importação do `localStorage` antigo.
3. **Vercel**: aloja a página estática, que lê as provas do Supabase com a anon key.
   Deixa de ser preciso republicar quando os dados mudam. Retirar o deploy do GitHub Pages do workflow.

## Fase 2 (depois do deploy): secção Strava "Os meus resultados"

Pedido do utilizador: ligar a conta Strava, importar as atividades (sobretudo as marcadas como
prova), associar cada registo a uma prova do calendário e ver a evolução.

- OAuth do Strava com scope `activity:read_all` (ou `activity:read`). A troca de código por tokens
  e o refresh precisam do client secret: fazer numa **Supabase Edge Function** (ou função Vercel),
  nunca no browser. Guardar tokens numa tabela só acessível pelo próprio utilizador/servidor.
- O utilizador cria a app em https://www.strava.com/settings/api (Client ID + Secret).
  Apps novas ficam em modo de um só atleta (o dono): chega para uso pessoal.
- `GET /athlete/activities` paginado. Corridas com `workout_type == 1` são "Prova" no Strava.
  Campos úteis: `sport_type` (Run, TrailRun), `distance`, `moving_time`, `elapsed_time`,
  `total_elevation_gain`, `start_date_local`, `average_heartrate`.
- Associação: sugerir automaticamente quando uma atividade é no mesmo dia que uma prova do
  calendário; o utilizador confirma ou associa à mão.
- Evolução: ritmo por distância ao longo do tempo (5k, 10k, meia, maratona), trail curto/longo,
  ritmo vs D+, melhores marcas, km e D+ por ano. Cruzar com tipo/distância oficial/pontos ITRA.
- Regras do Strava: dados só mostrados ao próprio utilizador (fica atrás do login), link
  "Ver no Strava" em cada atividade, respeitar limites de pedidos. Atenção ao changelog da API
  (https://developers.strava.com/docs/changelog/): novo URL base `api-v3.strava.com` a partir de jan/2027.

## Cuidados

- Os sites são de terceiros: pedidos poucos e espaçados, User-Agent normal, nada de contornar
  proteções anti-bot ou logins.
- Se um site falhar, o `run.py` mantém a última recolha desse site e o rodapé da página mostra a falha.
- Design da página: tokens de cor em `:root` com modo escuro; fontes Barlow Condensed + Inter;
  o "dia" de cada prova desenhado como um dorsal. Manter o estilo ao acrescentar secções.
