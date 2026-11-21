"""Utilidades partilhadas pelos recolhedores."""
from __future__ import annotations

import html
import re
import time
import unicodedata

import requests

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8"})
    return s


def get(s: requests.Session, url: str, *, retries: int = 3, **kw) -> requests.Response:
    """GET com algumas tentativas e pausa entre elas (sites pequenos, sê gentil)."""
    last = None
    timeout = kw.pop("timeout", 45)
    for i in range(retries):
        wait = 2 * (i + 1)
        try:
            r = s.get(url, timeout=timeout, **kw)
            if r.status_code == 200:
                return r
            last = RuntimeError(f"HTTP {r.status_code} em {url}")
            if r.status_code == 429:  # demasiados pedidos: espera bastante mais
                wait = int(r.headers.get("Retry-After", 0) or 0) or 30 * (i + 1)
        except requests.RequestException as e:  # noqa: PERF203
            last = e
        if i < retries - 1:
            time.sleep(wait)
    raise last  # type: ignore[misc]


def clean(text: str | None) -> str:
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )


# ---------------------------------------------------------------------------
# Tipos de prova normalizados
# ---------------------------------------------------------------------------
# Cada site usa etiquetas diferentes; tudo é traduzido para estes tipos.
TYPES = [
    "Estrada",
    "Trail",
    "Ultra",
    "Caminhada",
    "Triatlo",
    "Duatlo",
    "Natação",
    "Ciclismo",
    "Obstáculos",
    "Kids",
    "Orientação",
]

_TYPE_RULES: list[tuple[str, str]] = [
    # (regex sobre etiqueta sem acentos em minúsculas, tipo)
    (r"ultra", "Ultra"),
    (r"backyard", "Ultra"),
    (r"trail|sky|montanha|uphill|corta.?mato|cross", "Trail"),
    (r"caminhad|marcha|walking|cãominhad|caominhad", "Caminhada"),
    (r"triat|ironman|70\.3|aquatl", "Triatlo"),
    (r"duat", "Duatlo"),
    (r"nata|swim|aguas abertas|open water", "Natação"),
    (r"cicl|btt|bike|gravel|cycling|bicicleta", "Ciclismo"),
    (r"obstac|ocr|hyrox|hybrid|hibrid|spartan", "Obstáculos"),
    (r"kids|crianc|jovem|jovens|infant", "Kids"),
    (r"orienta", "Orientação"),
    (
        r"estrada|road|maratona|marathon|meia|half|\b\d+([.,]\d+)? ?k(m)?\b|silvestre|noturn|night run|milha|mile",
        "Estrada",
    ),
]


def normalize_types(tags: list[str]) -> list[str]:
    out: set[str] = set()
    for t in tags:
        low = strip_accents(t.lower())
        for pattern, typ in _TYPE_RULES:
            if re.search(pattern, low):
                out.add(typ)
                break
    # "Ultra" é uma variante de trail na maioria dos casos
    if "Ultra" in out and "Estrada" not in out:
        out.add("Trail")
    return [t for t in TYPES if t in out]


def _guess_types(tags: list[str], name: str) -> list[str]:
    found = normalize_types(tags)
    if not found:
        found = normalize_types([name])
    running = {"Estrada", "Trail", "Ultra", "Obstáculos", "Triatlo", "Duatlo"}
    generic_run = any(re.search(r"\bcorrida\b|\brun\b", strip_accents(t.lower())) for t in tags + [name])
    if generic_run and not running & set(found):
        found = [t for t in TYPES if t in set(found) | {"Estrada"}]
    return found


def race(
    *,
    source: str,
    source_id: str,
    name: str,
    date: str,
    url: str,
    end_date: str | None = None,
    location: str = "",
    country: str = "",
    tags: list[str] | None = None,
    distances: list[str] | None = None,
    official_url: str = "",
    types: list[str] | None = None,
) -> dict:
    tags = [clean(t) for t in (tags or []) if clean(t)]
    return {
        "source": source,
        "source_id": f"{source}:{source_id}",
        "name": clean(name),
        "date": date,
        "end_date": end_date if end_date and end_date != date else None,
        "location": clean(location),
        "country": clean(country) or "",
        "types": types if types is not None else _guess_types(tags, name),
        "tags": sorted(set(tags)),
        "distances": distances or [],
        "url": url,
        "official_url": official_url or "",
    }
