"""Recolhe as provas de todos os sites, junta duplicados e grava site/data/races.json.

Uso:  python scraper/run.py            (todos os sites)
      python scraper/run.py itra       (só um site; os outros vêm da última recolha)
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
import traceback
from difflib import SequenceMatcher
from pathlib import Path

from common import TYPES, strip_accents
import store
from sources import ALL

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "site" / "data" / "sources"
OUT = ROOT / "site" / "data" / "races.json"

# Ordem de preferência para o nome/link principal de uma prova juntada
PRIORITY = ["athleko", "portugalrunning", "racefinder", "itra", "orioasis"]
SOURCE_LABELS = {
    "athleko": "Athleko",
    "portugalrunning": "Portugal Running",
    "racefinder": "Racefinder",
    "itra": "ITRA",
    "orioasis": "OriOasis",
}

# Palavras que não ajudam a distinguir provas
STOP = {
    "de", "da", "do", "das", "dos", "e", "a", "o", "em", "na", "no", "the", "of", "and",
    "edicao", "ed", "corrida", "prova", "run", "race", "running", "trail", "km", "k",
    "international", "internacional", "grande", "premio", "gp", "i", "ii", "iii", "iv", "v",
    "vi", "vii", "viii", "ix", "x", "xi", "xii", "xiii", "xiv", "xv", "xvi", "xvii", "xviii",
    "xix", "xx", "xxi", "xxii", "xxiii", "xxiv", "xxv", "xxx", "a", "o", "ª", "º",
}


def tokens(name: str) -> set[str]:
    n = strip_accents(name.lower())
    n = re.sub(r"['’`´]", "", n)            # D'Aire -> daire
    n = re.sub(r"\b(19|20)\d{2}\b", " ", n)          # anos
    n = re.sub(r"\b\d+\s*(a|o|ª|º)?\b\.?", " ", n)   # 11.ª, 3º, números soltos
    n = re.sub(r"[^a-z0-9]+", " ", n)
    return {t for t in n.split() if t not in STOP and len(t) > 1}


# Palavras comuns a muitas provas diferentes: não chegam para dizer que duas são a mesma
GENERIC = {
    "sao", "silvestre", "meia", "maratona", "meiamaratona", "half", "marathon", "ultra",
    "trilhos", "trilho", "natal", "xmas", "christmas", "noturna", "noturno", "night", "cidade",
    "vila", "campeonato", "regional", "distrital", "nacional", "estrada", "caminhada", "btt",
    "solidaria", "solidario", "kids", "jovem", "santa", "santo", "senhora", "por", "terras",
    "festa", "festas", "classica", "volta", "milha", "milhas", "mile", "summer", "winter",
    "series", "circuito", "taca", "open", "challenge", "fun", "family", "familia",
    "estafetas", "duatlo", "triatlo", "aquatlo", "orientacao", "cross", "mato", "corta",
    "off", "road", "sky", "serra", "atletismo", "region", "regiao", "skyrace", "endurance", "longo", "curto", "medio", "sprint",
}


def _tok_match(a: str, b: str) -> bool:
    if a == b:
        return True
    return len(a) >= 5 and len(b) >= 5 and SequenceMatcher(None, a, b).ratio() >= 0.88


def similar(a: dict, b: dict, days: int) -> bool:
    ta, tb = a["_tok"], b["_tok"]
    if not ta or not tb:
        return False
    da, db = ta - GENERIC, tb - GENERIC
    if not da or not db:
        # nome só com palavras genéricas ("Meia Maratona 2026"): exige nome igual e mesmo dia
        return ta == tb and days == 0
    inter = sum(1 for x in da if any(_tok_match(x, y) for y in db))
    if inter == 0:
        return False
    small = min(len(da), len(db))
    if inter >= 2 or (inter == len(da) == len(db)):
        return True                       # forte: até 2 dias de diferença
    if days <= 1 and inter == small:
        return True                       # um nome está contido no outro
    return days <= 1 and inter / len(da | db) >= 0.5


def days_apart(a: str, b: str) -> int:
    return abs((dt.date.fromisoformat(a) - dt.date.fromisoformat(b)).days)


def merge(races: list[dict]) -> list[dict]:
    for r in races:
        r["_tok"] = tokens(r["name"])
    races.sort(key=lambda r: (r["date"], PRIORITY.index(r["source"])))
    groups: list[list[dict]] = []
    for r in races:
        placed = False
        # só compara com grupos próximos na data (lista está ordenada)
        for g in reversed(groups[-400:]):
            head = g[0]
            if days_apart(head["date"], r["date"]) > 2:
                if head["date"] < r["date"]:
                    # grupos mais antigos que isto não interessam
                    if days_apart(head["date"], r["date"]) > 40:
                        break
                continue
            if any(x["source"] == r["source"] for x in g):
                continue
            if any(similar(x, r, days_apart(x["date"], r["date"])) for x in g):
                g.append(r)
                placed = True
                break
        if not placed:
            groups.append([r])

    merged = []
    for g in groups:
        g.sort(key=lambda x: PRIORITY.index(x["source"]))
        main = g[0]
        types = {t for x in g for t in x["types"]}
        dists: list[str] = []
        for x in g:
            for d in x["distances"]:
                if d not in dists:
                    dists.append(d)
        end = max((x["end_date"] or x["date"]) for x in g)
        merged.append(
            {
                "id": main["source_id"],
                "keys": [x["source_id"] for x in g],
                "name": main["name"],
                "date": min(x["date"] for x in g),
                "end_date": end if end != min(x["date"] for x in g) else None,
                "location": next((x["location"] for x in g if x["location"]), ""),
                "country": next((x["country"] for x in g if x["country"]), ""),
                "types": [t for t in TYPES if t in types],
                "distances": dists[:12],
                "official_url": next((x["official_url"] for x in g if x["official_url"]), ""),
                "sources": [{"site": x["source"], "label": SOURCE_LABELS[x["source"]], "url": x["url"]} for x in g],
                "itra": next((x["itra"] for x in g if x.get("itra")), None),
            }
        )
    merged.sort(key=lambda r: (r["date"], r["name"].lower()))
    return merged


def build_page() -> None:
    """site/app.html tem só o conteúdo; aqui embrulha-se num documento HTML completo."""
    body = (ROOT / "site" / "app.html").read_text(encoding="utf-8")
    page = (
        '<!doctype html>\n<html lang="pt-PT">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        "<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}"
        "body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>\n"
        "</head>\n<body>\n" + body + "\n</body>\n</html>\n"
    )
    (ROOT / "site" / "index.html").write_text(page, encoding="utf-8")


def main(only: list[str]) -> int:
    print("Destino:", "Supabase" if store.remote() else "ficheiros locais", flush=True)
    status = {}
    for name, fn in ALL.items():
        if only and name not in only:
            status[name] = "cache"
            continue
        try:
            items = fn()
            if not items:
                raise RuntimeError("0 provas devolvidas")
            store.save_cache(name, items=items)
            status[name] = f"ok ({len(items)})"
        except Exception as e:  # um site em baixo não pode estragar os outros
            traceback.print_exc()
            status[name] = f"erro: {e}"[:200]
        print(f"{name:16s} {status[name]}", flush=True)

    races = []
    updated = {}
    for name in ALL:
        c = store.load_cache(name)
        if c and c.get("items"):
            races += c["items"]
            updated[name] = c["updated_at"]
    # orientação: ficheiro mantido à mão no repositório (ver README)
    manual = CACHE / "orioasis.json"
    if manual.exists():
        races += json.loads(manual.read_text(encoding="utf-8"))
        updated["orioasis"] = dt.datetime.fromtimestamp(manual.stat().st_mtime, dt.timezone.utc).isoformat(timespec="minutes")

    yesterday = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    races = [r for r in races if (r.get("end_date") or r["date"]) >= yesterday and r["name"]]
    merged = merge(races)
    meta = {
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"),
        "status": status,
        "updated": updated,
    }
    store.publish(merged, meta)
    dup = len(races) - len(merged)
    print(f"\n{len(races)} entradas -> {len(merged)} provas ({dup} duplicados juntados)")
    build_page()
    return 0 if any(s.startswith("ok") for s in status.values()) or only else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
