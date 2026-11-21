"""Onde a recolha guarda as coisas.

- Com SUPABASE_URL e SUPABASE_SERVICE_KEY definidos (GitHub Actions): tudo no Supabase.
- Sem eles (no PC): ficheiros em site/data/, como antes.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "site" / "data" / "sources"
OUT = ROOT / "site" / "data" / "races.json"

URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")


def remote() -> bool:
    return bool(URL and KEY)


def _h(extra: dict | None = None) -> dict:
    h = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
    h.update(extra or {})
    return h


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes")


# ---------------------------------------------------------------------------
# Cache por site: {"items": [...], "state": {...} | None, "updated_at": iso}
# ---------------------------------------------------------------------------
def load_cache(source: str) -> dict | None:
    if remote():
        r = requests.get(
            f"{URL}/rest/v1/source_cache",
            params={"source": f"eq.{source}", "select": "items,state,updated_at"},
            headers=_h(),
            timeout=60,
        )
        r.raise_for_status()
        rows = r.json()
        return rows[0] if rows else None
    f = CACHE_DIR / f"{source}.json"
    st = CACHE_DIR / f"{source}_state.json"
    if not f.exists() and not st.exists():
        return None
    return {
        "items": json.loads(f.read_text(encoding="utf-8")) if f.exists() else [],
        "state": json.loads(st.read_text(encoding="utf-8")) if st.exists() else None,
        "updated_at": dt.datetime.fromtimestamp(
            (f if f.exists() else st).stat().st_mtime, dt.timezone.utc
        ).isoformat(timespec="minutes"),
    }


def save_cache(source: str, items: list | None = None, state: dict | None = None) -> None:
    """Grava itens e/ou estado; o que vier a None fica como estava."""
    if remote():
        row: dict = {"source": source, "updated_at": _now()}
        if items is not None:
            row["items"] = items
        if state is not None:
            row["state"] = state
        if items is None:  # só estado: não pode apagar os itens existentes
            prev = load_cache(source)
            row["items"] = prev["items"] if prev else []
            row["updated_at"] = prev["updated_at"] if prev else row["updated_at"]
        r = requests.post(
            f"{URL}/rest/v1/source_cache",
            json=row,
            headers=_h({"Prefer": "resolution=merge-duplicates,return=minimal"}),
            timeout=120,
        )
        r.raise_for_status()
        return
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if items is not None:
        (CACHE_DIR / f"{source}.json").write_text(json.dumps(items, ensure_ascii=False, indent=0), encoding="utf-8")
    if state is not None:
        (CACHE_DIR / f"{source}_state.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Resultado final
# ---------------------------------------------------------------------------
def publish(races: list[dict], meta: dict) -> None:
    # o ficheiro local é sempre escrito (serve o PC e a pré-visualização)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({**meta, "races": races}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    if remote():
        r = requests.post(
            f"{URL}/rest/v1/rpc/replace_races",
            json={"payload": races, "meta_value": meta},
            headers=_h(),
            timeout=180,
        )
        r.raise_for_status()
        print(f"Supabase: {r.json()} provas gravadas")
