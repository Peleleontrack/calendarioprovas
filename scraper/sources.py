"""Um recolhedor por site. Cada função devolve uma lista de provas normalizadas."""
from __future__ import annotations

import datetime as dt
import html
import json
import os
import re
import time
from pathlib import Path

from common import clean, get, race, session

TODAY = dt.date.today()


def _iso(d: dt.date) -> str:
    return d.isoformat()


# ---------------------------------------------------------------------------
# Athleko  — API JSON pública usada pela própria página "Explorar"
# ---------------------------------------------------------------------------
# O Athleko limita muito os pedidos seguidos. Por isso cada execução busca só
# algumas páginas (as mais antigas primeiro) e guarda o progresso; com várias
# execuções por dia a lista completa-se e mantém-se atualizada.
ATHLEKO_STATE = Path(__file__).resolve().parent.parent / "site" / "data" / "sources" / "athleko_state.json"
ATHLEKO_PAGES_PER_RUN = int(os.environ.get("ATHLEKO_PAGES", "4"))
ATHLEKO_PAUSE = float(os.environ.get("ATHLEKO_PAUSE", "8"))


def athleko() -> list[dict]:
    try:
        st = json.loads(ATHLEKO_STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        st = {}
    pages: dict = st.get("pages", {})
    events: dict = st.get("events", {})
    total_pages = int(st.get("total_pages", 1))

    s = session()
    s.headers["Referer"] = "https://www.athleko.pt/explore.php?lang=pt"
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes")
    fetched, blocked, done_now = 0, False, set()
    while fetched < ATHLEKO_PAGES_PER_RUN:
        # próxima página: a que foi lida há mais tempo (ou nunca)
        left = [p for p in range(1, total_pages + 1) if p not in done_now]
        if not left:
            break
        page = min(left, key=lambda p: pages.get(str(p), ""))
        done_now.add(page)
        if fetched:
            time.sleep(ATHLEKO_PAUSE)
        r = s.get("https://www.athleko.pt/api/events.php", params={"lang": "pt", "page": page}, timeout=45)
        if r.status_code == 429:
            blocked = True
            break
        r.raise_for_status()
        data = r.json()
        evs = data.get("events", [])
        for e in evs:
            e["_seen"] = now
            events[str(e["id"])] = e
        pages[str(page)] = now
        fetched += 1
        if page == 1 and evs and data.get("total"):
            total_pages = -(-int(data["total"]) // len(evs))
    print(f"  athleko: {fetched} página(s) lidas{' (limite de pedidos atingido)' if blocked else ''}; "
          f"{sum(1 for p in range(1, total_pages + 1) if str(p) in pages)}/{total_pages} páginas em cache", flush=True)

    # esquece provas que já passaram ou que não aparecem há 4 dias
    cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=4)).isoformat(timespec="minutes")
    yesterday = _iso(TODAY - dt.timedelta(days=1))
    events = {k: e for k, e in events.items() if e.get("_seen", "") >= cutoff and e.get("event_date", "") >= yesterday}
    ATHLEKO_STATE.write_text(
        json.dumps({"total_pages": total_pages, "pages": pages, "events": events}, ensure_ascii=False),
        encoding="utf-8",
    )
    if not events:
        raise RuntimeError("HTTP 429 (limite de pedidos)" if blocked else "sem provas")

    out = []
    for e in events.values():
        cats = [c.strip() for c in (e.get("categories") or "").split(",") if c.strip()]
        loc = ", ".join(x for x in [e.get("city"), e.get("district")] if x)
        out.append(
            race(
                source="athleko",
                source_id=str(e["id"]),
                name=e["title"],
                date=e["event_date"],
                url=f"https://www.athleko.pt/event.php?id={e['id']}&lang=pt",
                location=loc,
                country=e.get("country") or "",
                tags=cats,
                distances=[c for c in cats if re.search(r"\d", c)],
                official_url=e.get("official_url") or "",
            )
        )
    return out


# ---------------------------------------------------------------------------
# Portugal Running — calendário EventOn; pedimos todos os meses de uma vez
# pelo mesmo pedido AJAX que a página usa quando mudas de mês.
# ---------------------------------------------------------------------------
PR_PAGE = "https://www.portugalrunning.com/calendario-de-corridas/"


def portugalrunning() -> list[dict]:
    s = session()
    page = get(s, PR_PAGE).text
    nonce_x = re.search(r'__litespeed_var_0__="([0-9a-f]+)"', page)
    sc_raw = re.search(r"class='evo_cal_data' data-sc=\"([^\"]+)\"", page)
    nonce = re.search(r'"n":"([0-9a-f]+)"', page)
    if not nonce:
        for js in re.findall(r'data-src="(https://www\.portugalrunning\.com/wp-content/litespeed/js/[^"]+)"', page):
            nonce = re.search(r'"n":"([0-9a-f]+)"', get(s, js).text)
            if nonce:
                break
    if not (nonce and sc_raw):
        raise RuntimeError("Portugal Running: estrutura da página mudou (nonce/shortcode)")

    sc = json.loads(html.unescape(sc_raw.group(1)))
    start = dt.datetime(TODAY.year, TODAY.month, 1, tzinfo=dt.timezone.utc)
    end = dt.datetime(TODAY.year + 2, 1, 1, tzinfo=dt.timezone.utc)
    sc.update(
        {
            "event_count": "0",
            "show_limit": "no",
            "number_of_months": "24",
            "focus_start_date_range": str(int(start.timestamp())),
            "focus_end_date_range": str(int(end.timestamp())),
        }
    )
    data = {
        "action": "eventon_get_events",
        "direction": "none",
        "ajaxtype": "switchmonth",
        "nonce": nonce.group(1),
        "nonceX": nonce_x.group(1) if nonce_x else "",
    }
    for k, v in sc.items():
        data[f"shortcode[{k}]"] = v
    headers = {"X-Requested-With": "XMLHttpRequest", "Referer": PR_PAGE}
    if nonce_x:
        headers["X-WP-Nonce"] = nonce_x.group(1)
    r = s.post("https://www.portugalrunning.com/wp-admin/admin-ajax.php", data=data, headers=headers, timeout=120)
    r.raise_for_status()
    payload = r.json()
    if payload.get("status") != "GOOD":
        raise RuntimeError(f"Portugal Running: resposta inesperada {str(payload)[:200]}")

    out, seen = [], set()
    blocks = re.split(r'(?=<div id="event_\d+_\d+" class="eventon_list_event)', payload["html"])
    for b in blocks:
        m = re.match(r'<div id="event_(\d+)_(\d+)"[^>]*data-time="(\d+)-(\d+)"', b)
        if not m:
            continue
        eid, ri, t0, t1 = m.groups()
        key = f"{eid}_{ri}"
        if key in seen:
            continue
        seen.add(key)
        title = re.search(r"evcal_event_title[^>]*>([^<]+)<", b)
        link = re.search(r'class="evo_event_schema"[^>]*>\s*<a href="([^"]+)"', b) or re.search(
            r'href="(https://www\.portugalrunning\.com/eventos/[^"]+)"', b
        )
        loc = re.search(r'data-location_name="([^"]*)"', b)
        types = re.findall(r'data-filter="event_type" data-v="([^"]+)"', b)
        region = re.findall(r'data-filter="event_type_2" data-v="([^"]+)"', b)
        d0 = dt.datetime.fromtimestamp(int(t0), dt.timezone.utc).date()
        d1 = dt.datetime.fromtimestamp(int(t1), dt.timezone.utc).date()
        intl = any(x in ("Europa", "Internacional", "Mundo") for x in region) or (
            region and "Portugal" not in region and not any(r in PT_REGIONS for r in region)
        )
        country = ""
        if intl:
            country = next((x for x in region if x not in ("Europa", "Internacional", "Mundo")), "Internacional")
        else:
            country = "Portugal"
        out.append(
            race(
                source="portugalrunning",
                source_id=key,
                name=title.group(1) if title else "",
                date=_iso(d0),
                end_date=_iso(d1),
                url=link.group(1) if link else PR_PAGE,
                location=_pr_location(clean(loc.group(1)) if loc else "", region, country),
                country=country,
                tags=types,
                distances=[PR_DIST[t] for t in types if t in PR_DIST],
            )
        )
    return out


PR_DIST = {"Corrida 10 km": "10 km", "Meia Maratona": "21 km", "Maratona": "42 km", "Milha": "1 milha"}


def _pr_location(name: str, region: list[str], country: str) -> str:
    """'Mafra' + ['Lisboa e Centro', 'Lisboa'] -> 'Mafra, Lisboa' (sem macro-regiões nem repetidos)."""
    region = [clean(r) for r in region]
    parts = [x.strip() for x in clean(name).split(",")] + [r for r in region if " e " not in r and r not in ("Europa", "Portugal", "Internacional", "Mundo", country)]
    seen, out = set(), []
    for p in parts:
        k = re.sub(r"\W+", "", p.lower())
        if p and k not in seen:
            seen.add(k)
            out.append(p)
    return ", ".join(out)


PT_REGIONS = {
    "Portugal", "Norte", "Centro", "Lisboa", "Alentejo", "Algarve", "Madeira", "Açores",
    "Porto", "Braga", "Coimbra", "Setúbal", "Aveiro", "Leiria", "Viseu", "Faro", "Évora",
    "Santarém", "Viana do Castelo", "Vila Real", "Bragança", "Guarda", "Castelo Branco",
    "Portalegre", "Beja",
}


# ---------------------------------------------------------------------------
# Racefinder — loja WooCommerce; cada prova é um "produto" com atributos
# ---------------------------------------------------------------------------
def racefinder() -> list[dict]:
    s = session()
    out, page = [], 1
    while page <= 30:
        r = get(s, "https://racefinder.pt/wp-json/wc/store/v1/products", params={"per_page": 100, "page": page})
        items = r.json()
        if not items:
            break
        for p in items:
            attrs = {a["taxonomy"]: [t["name"] for t in a["terms"]] for a in p.get("attributes", [])}
            dates = []
            for d in attrs.get("pa_race-start-date", []):
                try:
                    dates.append(dt.datetime.strptime(d.strip(), "%d/%m/%Y").date())
                except ValueError:
                    pass
            # o site acumula datas de várias edições: fica só com a próxima
            dates = sorted(d for d in dates if d >= TODAY - dt.timedelta(days=1))
            if not dates:
                continue
            dates = [d for d in dates if (d - dates[0]).days <= 7]
            cats = [c["name"] for c in p.get("categories", [])]
            out.append(
                race(
                    source="racefinder",
                    source_id=str(p["id"]),
                    name=p["name"],
                    date=_iso(dates[0]),
                    end_date=_iso(dates[-1]),
                    url=p["permalink"],
                    country="Portugal",
                    tags=cats,
                    distances=[d for d in attrs.get("pa_distance", []) if re.search(r"\d", d)],
                )
            )
        total_pages = int(r.headers.get("X-WP-TotalPages", page))
        if page >= total_pages:
            break
        page += 1
        time.sleep(0.5)
    return out


# ---------------------------------------------------------------------------
# ITRA — calendário de provas qualificadas (por defeito só Portugal)
# ---------------------------------------------------------------------------
ITRA_COUNTRIES = ["PT"]
_MONTHS_EN = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August",
     "September", "October", "November", "December"], 1)}


def itra() -> list[dict]:
    s = session()
    base = "https://itra.run/Races/RaceCalendar"
    out = []
    for country in ITRA_COUNTRIES:
        page = get(s, base).text
        tok = re.search(r'name="__RequestVerificationToken"[^>]*value="([^"]+)"', page)
        if not tok:
            raise RuntimeError("ITRA: token do formulário não encontrado")
        r = s.post(
            base,
            data={
                "__RequestVerificationToken": tok.group(1),
                "Input.Country": country,
                "Input.isDateFilterApplied": "false",
                "name": "",
            },
            headers={"Referer": base},
            timeout=90,
        )
        r.raise_for_status()
        h = r.text
        i = h.find("var raceSearchJsonSidePopupNew = [")
        if i < 0:
            raise RuntimeError("ITRA: lista de provas não encontrada")
        arr = h[i : h.find("];", i)]
        for item in re.findall(r'\["(.*?)"\]\s*,?', arr, re.S):
            name = re.search(r"<h4>([^<]+)</h4", item)
            link = re.search(r"class='event_name'><a href='([^']+)'", item)
            date = re.search(r"class='date'><span>(\d+)</span>\s*([A-Za-z]+)<d></d>\s*(\d{4})", item)
            if not (name and link and date):
                continue
            try:
                d = dt.date(int(date.group(3)), _MONTHS_EN[date.group(2)], int(date.group(1)))
            except (KeyError, ValueError):
                continue
            if d < TODAY - dt.timedelta(days=1):
                continue
            loc = re.search(r"class='location'>([^<]*)<", item)
            race_id = re.search(r"/(\d+)$", link.group(1))
            courses = _itra_courses(item)
            # link de inscrição que o ITRA mostra junto ao logótipo da prova
            reg = re.search(r"class='logo_image[^']*'>.*?<a href='(https?://[^']+)'", item, re.S)
            r_ = race(
                source="itra",
                source_id=race_id.group(1) if race_id else link.group(1),
                name=name.group(1),
                date=_iso(d),
                url="https://itra.run" + link.group(1),
                location=re.sub(r",\s*[A-Z]{3}$", "", clean(loc.group(1))) if loc else "",
                country="Portugal" if country == "PT" else country,
                tags=["Trail", "ITRA"],
                types=["Trail"],
                distances=[c["km"] for c in courses],
                official_url=reg.group(1) if reg and "itra.run" not in reg.group(1) else "",
            )
            r_["itra"] = courses
            out.append(r_)
    return out


_POINT_IMG = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}


def _itra_courses(item: str) -> list[dict]:
    """Cada distância da prova: km, desnível positivo, pontos ITRA (None = ainda não atribuídos) e link."""
    courses = []
    for box in re.findall(r"<div class='boxes'>(.*?)</a></div>", item, re.S):
        href = re.search(r"<a href='([^']+)'", box)
        km = re.search(r"class='count'>\s*([\d.,]+)\s*k", box)
        dplus = re.search(r"class='distance'>\s*\+?\s*(\d+)\s*m", box)
        pts = re.search(r"/images/(zero|one|two|three|four|five|six)\.svg", box)
        if not km:
            continue
        courses.append(
            {
                "km": f"{km.group(1).replace(',', '.')} km",
                "dplus": int(dplus.group(1)) if dplus else None,
                "points": _POINT_IMG[pts.group(1)] if pts else None,
                "url": "https://itra.run" + href.group(1) if href else "",
            }
        )
    return courses


ALL = {
    "athleko": athleko,
    "portugalrunning": portugalrunning,
    "racefinder": racefinder,
    "itra": itra,
}
