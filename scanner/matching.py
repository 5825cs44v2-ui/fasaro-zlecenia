"""Dopasowanie ogłoszenia do usług FASARO i punktacja trafności."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from .geo import distance_points, fold

SERVICE_LABELS = {
    "elewacje": "Elewacje",
    "ocieplenia": "Ocieplenia",
    "tynki": "Tynki i gładzie",
    "remonty": "Remonty wnętrz",
    "inne": "Budowlane",
}

# (rdzeń, punkty, usługa, waga)
POSITIVE: list[tuple[str, int, str, str]] = [
    ("termomoderniz", 48, "elewacje", "strong"),
    ("elewac", 40, "elewacje", "strong"),
    ("ociepl", 38, "ocieplenia", "strong"),
    ("dociepl", 38, "ocieplenia", "strong"),
    ("termoizolac", 26, "ocieplenia", "strong"),
    ("fasad", 30, "elewacje", "strong"),
    ("etics", 35, "ocieplenia", "strong"),
    ("styropian", 24, "ocieplenia", "strong"),
    ("welna mineraln", 20, "ocieplenia", "strong"),
    ("parapet", 14, "elewacje", "strong"),
    ("tynk", 26, "tynki", "strong"),
    ("gladz", 20, "tynki", "strong"),
    ("szpachlow", 18, "tynki", "strong"),
    ("gipsow", 12, "tynki", "medium"),
    ("remont", 18, "remonty", "strong"),
    ("modernizac", 12, "remonty", "medium"),
    ("wykonczen", 16, "remonty", "strong"),
    ("malowan", 15, "remonty", "medium"),
    ("robot budowlan", 8, "inne", "medium"),
    ("budynek", 4, "inne", "medium"),
    ("mieszkan", 7, "remonty", "medium"),
    ("lokal", 5, "remonty", "medium"),
    ("pomieszczen", 7, "remonty", "medium"),
    ("scian", 4, "remonty", "medium"),
    ("sufit", 5, "remonty", "medium"),
    ("izolac", 10, "ocieplenia", "medium"),
    ("uszczeln", 5, "inne", "medium"),
    ("murar", 5, "inne", "medium"),
    ("beton", 3, "inne", "medium"),
    ("okladzin", 12, "elewacje", "medium"),
]

NEGATIVE: list[tuple[str, int]] = [
    ("dach", 28),
    ("fotowoltaik", 35),
    ("pompa ciepla", 30),
    ("pomp ciepla", 30),
    ("instalacj", 20),
    ("elektryczn", 22),
    ("hydraulicz", 22),
    ("kanalizac", 25),
    ("wodociag", 25),
    ("budowa drogi", 30),
    ("rozbudowa drogi", 30),
    ("przebudowa drogi", 30),
    ("remont drogi", 30),
    ("drogi gminn", 25),
    ("drogi powiatow", 25),
    ("chodnik", 20),
    ("kostka brukow", 18),
    ("ogrodzen", 15),
    ("stolar", 15),
    ("meble", 20),
    ("okna", 12),
    ("drzwi", 10),
    ("kotlown", 20),
    ("wentylac", 15),
    ("klimatyzac", 20),
    ("sprzat", 25),
    ("dostaw", 22),
    ("zakup", 20),
    ("projekt", 15),
    ("dokumentacj", 15),
    ("nadzor", 20),
    ("inwentaryzac", 15),
    ("audyt", 20),
    ("szkolen", 25),
    ("ubezpieczen", 25),
    ("transport", 20),
    ("wywoz", 20),
    ("urzadzen", 15),
    ("monitoring", 20),
    ("oswietlen", 18),
    ("zielen", 20),
    ("trawnik", 18),
    ("nawierzchn", 15),
    ("place zabaw", 25),
    ("sprzet", 20),
    ("serwis", 12),
    ("konserwacj", 10),
]


def _hit(folded: str, term: str) -> bool:
    t = fold(term)
    if len(t) <= 5:
        return re.search(r"(?<![a-z])" + re.escape(t), folded) is not None
    return t in folded


def analyse(text: str) -> dict | None:
    folded = fold(text)
    strong = medium = negative = 0
    matched: list[str] = []
    negatives: list[str] = []
    per_service: dict[str, int] = {}

    for term, points, service, tier in POSITIVE:
        if _hit(folded, term):
            matched.append(term)
            if tier == "strong":
                strong += points
            else:
                medium += points
            per_service[service] = per_service.get(service, 0) + points

    for term, points in NEGATIVE:
        if _hit(folded, term):
            negatives.append(term)
            negative += points

    if strong == 0 and medium == 0:
        return None

    relevance = strong + medium * 0.55 - negative * 0.9
    if relevance < 6:
        return None

    service = max(per_service, key=per_service.get) if per_service else "inne"
    return {
        "service": service,
        "service_label": SERVICE_LABELS.get(service, "Budowlane"),
        "relevance": relevance,
        "strong": strong,
        "medium": medium,
        "negative": negative,
        "matched": matched,
        "negatives": negatives,
    }


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def score_lead(lead: dict, now: datetime | None = None) -> dict | None:
    now = now or datetime.now(timezone.utc)
    text = " ".join(
        part
        for part in [
            lead.get("title", ""),
            lead.get("description", ""),
            lead.get("cpv", ""),
            lead.get("city", ""),
        ]
        if part
    )
    result = analyse(text)
    if not result:
        return None

    deadline = _parse_dt(lead.get("deadline"))
    if deadline and deadline < now:
        return None

    distance = lead.get("distance_km")
    city = lead.get("city") or ""
    loc = distance_points(distance, city)

    published = _parse_dt(lead.get("published_at")) or _parse_dt(lead.get("first_seen"))
    fresh = 3
    if published:
        age_days = max(0.0, (now - published).total_seconds() / 86400)
        if age_days <= 2:
            fresh = 10
        elif age_days <= 5:
            fresh = 7
        elif age_days <= 10:
            fresh = 4
        else:
            fresh = 1

    deadline_bonus = 0
    if deadline:
        days_left = (deadline - now).total_seconds() / 86400
        if days_left >= 3:
            deadline_bonus = 5
        elif days_left >= 1:
            deadline_bonus = 2

    score = result["relevance"] + loc + fresh + deadline_bonus
    score = int(max(0, min(100, round(score))))

    if score >= 70:
        label = "Bardzo trafne"
    elif score >= 50:
        label = "Trafne"
    elif score >= 32:
        label = "Możliwe"
    else:
        label = "Do sprawdzenia"

    reasons = []
    if result["matched"]:
        reasons.append("Słowa: " + ", ".join(result["matched"][:4]))
    if distance is not None:
        reasons.append(f"{distance:g} km od Kędzierzyna-Koźla")
    elif city:
        reasons.append(city)
    if deadline:
        reasons.append("termin " + deadline.strftime("%d.%m.%Y"))

    lead.update(
        {
            "score": score,
            "score_label": label,
            "service": result["service"],
            "service_label": result["service_label"],
            "matched": result["matched"][:8],
            "negatives": result["negatives"][:6],
            "reasons": reasons,
        }
    )
    return lead
