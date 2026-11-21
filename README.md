# Calendário de Provas

Junta num só sítio as provas de corrida, trail, triatlo e afins publicadas em:

| Site | Como é lido |
|---|---|
| Athleko | API JSON da página "Explorar" |
| Portugal Running | pedido do calendário EventOn (todos os meses de uma vez) |
| Racefinder | API pública da loja (cada prova é um produto com data) |
| ITRA | pesquisa do calendário filtrada por Portugal (provas qualificadas) |
| OriOasis | **não automático** (o site bloqueia acessos automáticos), ver abaixo |

As provas repetidas em vários sites são juntadas numa só (mesmo nome e data próxima), com o link de cada site.
"O meu calendário" fica na conta de cada pessoa (login por email, sem password) e aparece em qualquer dispositivo.
Sem Supabase configurado, fica no browser e passa-se entre dispositivos com um código.

## Estrutura

```
scraper/common.py     utilidades + tradução das categorias para tipos comuns
scraper/sources.py    um recolhedor por site
scraper/store.py      onde se guarda: Supabase (com chave) ou ficheiros locais (sem chave)
scraper/run.py        corre tudo, junta duplicados, grava as provas e gera site/index.html
site/app.html         a página (pesquisa, filtros, o meu calendário, login)
site/config.js        URL e chave pública do Supabase (vazio = modo local)
site/data/            dados do modo local (races.json + último resultado de cada site)
supabase/migrations/  estrutura da base de dados
.github/workflows/    recolha automática de 3 em 3 horas, grava no Supabase
vercel.json           o Vercel publica a pasta site/ tal como está
```

## Correr no PC

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python scraper\run.py
.venv\Scripts\python -m http.server 8765 --directory site
```

Depois abre http://localhost:8765.

`python scraper/run.py itra` corre só um site (os outros vêm da última recolha).

## Publicar online (GitHub + Supabase + Vercel)

1. **Supabase** (projeto `calendarioprovas`, já criado e com a estrutura aplicada: `supabase/migrations/`).
   - *Authentication → URL Configuration*: pôr o endereço do Vercel em **Site URL** e em **Redirect URLs**
     (sem isto, o link de entrada enviado por email não volta para o site).
   - `site/config.js` já tem o Project URL e a anon key (são públicos).
2. **GitHub** (repositório → *Settings → Secrets and variables → Actions → Secrets → New repository secret*):
   - nome `SUPABASE_SERVICE_KEY`, valor = **service_role key** do Supabase
     (*Project Settings → API Keys*, separador das chaves legacy, "service_role" → *Reveal*). É secreta: nunca no código.
   - *Actions → Atualizar provas → Run workflow* para a primeira recolha. Depois corre sozinho de 3 em 3 horas.
3. **Vercel**: *Add New → Project* → importar o repositório → *Deploy* (o `vercel.json` já diz para publicar a pasta `site/`).
   Cada `git push` para `main` publica uma versão nova. As provas não precisam de novo deploy: a página lê-as do Supabase.

Se um site falhar, a recolha mantém a última versão desse site e o rodapé da página indica a falha.
Primeira recolha: o Athleko enche aos poucos (4 páginas por execução), por isso demora umas horas a aparecer completo.

Login por email: o Supabase, sem servidor de email próprio, só envia poucos emails por hora e apenas para membros
da organização. Para mais pessoas, configurar um SMTP em *Authentication → Emails*.

## ITRA (atualizar a partir de um PC)

O ITRA está atrás de uma proteção (CloudFront/WAF) que recusa pedidos vindos de servidores como os do GitHub
Actions (responde HTTP 202). Por isso o workflow usa `SKIP_SOURCES: itra` e a página mostra a última recolha
ITRA guardada no Supabase, com a data no rodapé. Os pontos ITRA mudam pouco: atualizar 1x por mês chega.

Para atualizar, num PC com Python (a chave é a mesma service_role do segredo do GitHub, nunca a guardar no repositório):

```
set SUPABASE_URL=https://wtgjdtzvcogfsrhgixgv.supabase.co
set SUPABASE_SERVICE_KEY=<service_role key>
.venv\Scripts\python scraper\run.py itra
```

(No Claude Code, também se pode pedir para recolher o ITRA localmente e gravar na tabela `source_cache`.)

## Orientação (OriOasis)

O OriOasis está protegido contra acessos automáticos, por isso não é recolhido sozinho.
Se quiseres as provas de orientação na lista, cria `site/data/sources/orioasis.json` com este formato
(uma entrada por prova) e faz `git push`:

```json
[
  {"source": "orioasis", "source_id": "orioasis:123", "name": "Nome da prova", "date": "2027-01-18",
   "end_date": null, "location": "Local", "country": "Portugal", "types": ["Orientação"],
   "tags": [], "distances": [], "url": "https://www.orioasis.pt/...", "official_url": ""}
]
```

## Afinar

- Mais países no ITRA: edita `ITRA_COUNTRIES` em `scraper/sources.py` (ex.: `["PT", "ES"]`).
- Duplicados mal juntados ou por juntar: ajusta `GENERIC` e `similar()` em `scraper/run.py`.
- Se um site mudar o layout, o rodapé da página mostra "falhou hoje" para esse site; o recolhedor dele em `sources.py` precisa de ajuste.
