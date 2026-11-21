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
"O meu calendário" fica guardado no browser; usa o código de transferência para o levar do PC para o telemóvel.

## Estrutura

```
scraper/common.py     utilidades + tradução das categorias para tipos comuns
scraper/sources.py    um recolhedor por site
scraper/run.py        corre tudo, junta duplicados, grava site/data/races.json e site/index.html
site/app.html         a página (pesquisa, filtros, o meu calendário)
site/data/            dados gerados (races.json + último resultado de cada site)
.github/workflows/    atualização diária automática + publicação no GitHub Pages
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

## Publicar online (GitHub Pages, grátis)

> O plano decidido é passar para **GitHub + Vercel + Supabase com login** e depois juntar uma secção Strava.
> Está tudo descrito em `CLAUDE.md`. Os passos abaixo são a versão simples, que já funciona sem contas extra.

1. Cria um repositório no GitHub e envia esta pasta (`git push`).
2. No repositório: **Settings → Pages → Source: GitHub Actions**.
3. Em **Actions → Atualizar provas → Run workflow** corre a primeira vez.
4. A página fica em `https://<utilizador>.github.io/<repositório>/` e atualiza-se todos os dias às 05:17 UTC.

Se um site falhar num dia, a página continua a mostrar os dados da última recolha desse site e o rodapé indica a falha.

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
