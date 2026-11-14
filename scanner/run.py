"""Główny przebieg skanu: pobierz, dopasuj, zapisz, powiadom."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import __version__, notify
from .geo import fold, nearest_place
from .matching import score_lead
from .sources import SOURCES

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "docs" / "data"
MAX_LEADS = 500
MAX_AGE_DAYS = 60

# Portale z darmowym dostępem do danych kontaktowych zleceniodawcy.
# Oferteo pobiera opłatę (punkty) za odblokowanie kontaktu.
CONTACT_FREE = {
    "bzp": True,
    "epropublico": True,
    "bip_kk": True,
    "oferteo": False,
}


def log(message: str) -> None:
    stamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{stamp}] {message}", flush=True)


def load_json(path: Path, default):
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return default


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    temp.replace(path)


def make_id(source: str, external_id: str) -> str:
    raw = f"{source}|{external_id}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:12]


def title_key(lead: dict) -> tuple[str, str, str]:
    title = fold(lead.get("title", ""))
    title = re.sub(r"[^a-z0-9 ]", " ", title)
    title = " ".join(title.split())[:90]
    deadline = (lead.get("deadline") or "")[:10]
    return title, fold(lead.get("city", "")), deadline


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def is_expired(lead: dict, now: datetime) -> bool:
    deadline = parse_dt(lead.get("deadline"))
    if deadline:
        return deadline < now
    first_seen = parse_dt(lead.get("first_seen"))
    if first_seen and (now - first_seen).days > MAX_AGE_DAYS:
        return True
    return False


def build_lead(raw: dict) -> dict:
    external_id = str(raw.get("external_id") or raw.get("url") or raw.get("title"))
    lead = dict(raw)
    lead["external_id"] = external_id
    lead["id"] = make_id(lead.get("source", "?"), external_id)
    lead.setdefault("description", "")
    lead.setdefault("city", "")
    lead.setdefault("distance_km", None)
    lead.setdefault("published_at", None)
    lead.setdefault("deadline", None)
    lead.setdefault("budget", None)
    lead.setdefault("contact_free", CONTACT_FREE.get(lead.get("source", ""), True))
    lead.setdefault("contact_label", "Kontakt darmowy" if lead.get("contact_free") else "Kontakt płatny")
    return lead


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Skan zleceń budowlanych dla FASARO")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="katalog danych wyjściowych")
    parser.add_argument("--config", default=str(ROOT / "config.json"), help="plik konfiguracji")
    parser.add_argument("--notify", action="store_true", help="wysyłaj powiadomienia ntfy")
    parser.add_argument("--force-notify", action="store_true", help="powiadamiaj nawet przy pierwszym uruchomieniu")
    parser.add_argument("--only", default="", help="tylko wybrane źródła, np. bzp,oferteo")
    parser.add_argument("--app-url", default="", help="adres aplikacji do linków w powiadomieniach")
    args = parser.parse_args(argv)

    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    cfg = load_json(Path(args.config), {})
    if not cfg:
        log("BŁĄD: brak config.json")
        return 2

    now = datetime.now(timezone.utc)
    seen_path = out / "seen.json"
    seen = load_json(seen_path, {"ids": {}})
    seen.setdefault("ids", {})
    first_run = not seen["ids"]

    only = {part.strip() for part in args.only.split(",") if part.strip()}
    raw_leads: list[dict] = []
    statuses: list[dict] = []

    for source_id, label, module in SOURCES:
        conf = cfg.get("sources", {}).get(source_id, {})
        if not conf.get("enabled", False) or (only and source_id not in only):
            statuses.append({"id": source_id, "label": label, "status": "off", "count": 0, "note": "wyłączone"})
            continue
        started = time.time()
        try:
            leads, note = module.fetch(cfg, first_run=first_run)
            raw_leads.extend(leads)
            statuses.append(
                {
                    "id": source_id,
                    "label": label,
                    "status": "ok",
                    "count": len(leads),
                    "note": note,
                    "ms": round((time.time() - started) * 1000),
                }
            )
            log(f"{label}: {note}")
        except Exception as exc:
            statuses.append(
                {
                    "id": source_id,
                    "label": label,
                    "status": "error",
                    "count": 0,
                    "note": f"{type(exc).__name__}: {exc}"[:300],
                    "ms": round((time.time() - started) * 1000),
                }
            )
            log(f"{label}: BŁĄD {type(exc).__name__}: {exc}")

    # Poprzednie wyniki zostają, jeśli źródło chwilowo nie odpowiada.
    previous = load_json(out / "leads.json", {"leads": []}).get("leads", [])
    previous_by_id = {lead.get("id"): lead for lead in previous if lead.get("id")}

    candidates: list[dict] = []
    dedup_ids: set[str] = set()
    for raw in raw_leads:
        lead = build_lead(raw)
        if lead["id"] in dedup_ids:
            continue
        dedup_ids.add(lead["id"])
        candidates.append(lead)

    for lead in previous:
        if not lead.get("id") or any(c["id"] == lead["id"] for c in candidates):
            continue
        carried = dict(lead)
        carried["is_new"] = False
        candidates.append(carried)

    scored: list[dict] = []
    max_distance = float(cfg.get("max_distance_km", 40))
    for lead in candidates:
        if lead.get("contact_free") is None:
            lead["contact_free"] = CONTACT_FREE.get(lead.get("source", ""), True)
        lead.setdefault("contact_label", "Kontakt darmowy" if lead.get("contact_free") else "Kontakt płatny")
        known_first_seen = seen["ids"].get(lead["id"])
        lead["is_new"] = known_first_seen is None
        lead["first_seen"] = known_first_seen or now.isoformat()
        if is_expired(lead, now):
            continue

        if lead.get("city"):
            # Miasto znane naszemu geo ma zawsze pierwszeństwo nad dystansem
            # zapisanym wcześniej (Oferteo potrafi podać błędny).
            _, geo_distance = nearest_place(lead["city"])
            if geo_distance is not None:
                lead["distance_km"] = geo_distance

        if lead.get("distance_km") is None:
            _, fallback = nearest_place(lead.get("city", ""))
            lead["distance_km"] = fallback
        if lead.get("distance_km") is None:
            # Nie znamy lokalizacji - nie zgadujemy, że to okolice K-K.
            if "kedzierzyn" not in fold(lead.get("city", "")):
                continue
        elif lead["distance_km"] > max_distance:
            continue

        result = score_lead(lead, now)
        if not result:
            continue
        if result["score"] < int(cfg.get("min_score", 18)):
            continue
        scored.append(result)

    # Deduplikacja: ta sama inwestycja z BZP i e-ProPublico.
    unique: dict[tuple[str, str, str], dict] = {}
    for lead in sorted(scored, key=lambda item: (item.get("contact_free", False), item.get("score", 0)), reverse=True):
        key = title_key(lead)
        if key in unique:
            existing = unique[key]
            existing.setdefault("also", [])
            label = lead.get("source_label")
            if label and label != existing.get("source_label") and label not in existing["also"]:
                existing["also"].append(label)
            existing["score"] = max(existing.get("score", 0), lead.get("score", 0))
            continue
        unique[key] = lead

    leads = list(unique.values())
    leads.sort(
        key=lambda item: (
            item.get("contact_free", False),
            item.get("score", 0),
            parse_dt(item.get("first_seen")) or now,
        ),
        reverse=True,
    )
    leads = leads[:MAX_LEADS]

    # Zapis seen tylko dla leadów, które przeszły filtr.
    for lead in leads:
        seen["ids"].setdefault(lead["id"], lead["first_seen"])
    cutoff = now - timedelta(days=120)
    seen["ids"] = {
        key: value
        for key, value in seen["ids"].items()
        if (parse_dt(value) or cutoff) >= cutoff
    }
    seen["updated"] = now.isoformat()

    new_count = sum(1 for lead in leads if lead.get("is_new"))
    payload = {
        "updated": now.isoformat(),
        "count": len(leads),
        "new_count": new_count,
        "leads": leads,
    }
    save_json(out / "leads.json", payload)
    save_json(seen_path, seen)

    app_url = args.app_url or os.environ.get("APP_URL") or cfg.get("app_url") or ""
    meta = {
        "updated": now.isoformat(),
        "count": len(leads),
        "new_count": new_count,
        "ntfy_topic": cfg.get("ntfy_topic", ""),
        "app_url": app_url,
        "radius_km": cfg.get("radius_km", 35),
        "version": __version__,
        "sources": statuses,
    }
    save_json(out / "meta.json", meta)
    log(f"Zapisano {len(leads)} zleceń ({new_count} nowych) do {out}")

    if args.notify and not (first_run and not args.force_notify):
        fresh = [
            lead
            for lead in leads
            if lead.get("is_new") and lead.get("score", 0) >= int(cfg.get("notify_min_score", 35))
        ]
        fresh.sort(key=lambda item: (item.get("contact_free", False), item.get("score", 0)), reverse=True)
        limit = int(cfg.get("notify_max_per_run", 4))
        for lead in fresh[:limit]:
            ok, info = notify.notify_lead(cfg.get("ntfy_topic", ""), lead, app_url)
            log(f"ntfy: {'OK' if ok else 'BŁĄD'} — {lead.get('title', '')[:60]} ({info})")
        if len(fresh) > limit:
            ok, info = notify.notify_digest(cfg.get("ntfy_topic", ""), fresh[limit:], app_url)
            log(f"ntfy podsumowanie: {'OK' if ok else 'BŁĄD'} ({info})")
        if not fresh:
            log("ntfy: brak nowych zleceń do powiadomienia")
    elif first_run:
        log("Pierwsze uruchomienie — powiadomienia wstrzymane (baza startowa).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
