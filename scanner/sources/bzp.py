"""Źródło: Biuletyn Zamówień Publicznych (API e-Zamówienia)."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from ..geo import nearest_place
from .base import clean, get, html_to_text, iso, make_session

API = "https://ezamowienia.gov.pl/mo-board/api/v1/notice"
DETAIL = "https://ezamowienia.gov.pl/mo-client-board/bzp/notice-details/{object_id}"
SOURCE_LABEL = "BZP / e-Zamówienia"


def fetch(cfg: dict, first_run: bool = False) -> tuple[list[dict], str]:
    conf = cfg["sources"]["bzp"]
    days = int(conf.get("first_run_days" if first_run else "days", 3))
    now = datetime.now(timezone.utc)
    params = {
        "NoticeType": "ContractNotice",
        "PublicationDateFrom": (now - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S"),
        "PublicationDateTo": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "PageSize": 100,
        "OrderType": "Works",
        "OrganizationProvince": "PL16",
    }

    session = make_session()
    response = get(session, API, params=params)
    response.raise_for_status()
    items = response.json()
    if not isinstance(items, list):
        raise RuntimeError(f"Nieoczekiwana odpowiedź API BZP: {str(items)[:200]}")

    leads: list[dict] = []
    for item in items:
        notice = clean(item.get("noticeNumber"))
        object_id = clean(item.get("objectId"))
        title = clean(item.get("orderObject")) or f"Ogłoszenie BZP {notice}"
        body = html_to_text(item.get("htmlBody") or "")
        if not body:
            body = title

        location_snippet = ""
        match = re.search(
            r"Miejsce realizacji[^:]{0,80}:\s*(.{0,320}?)(?:\s{2,}|Termin|Informacje|Warunki|$)",
            body,
            re.IGNORECASE,
        )
        if match:
            location_snippet = match.group(1)

        place, distance = nearest_place(location_snippet) if location_snippet else (None, None)
        if place is None:
            place, distance = nearest_place(body[:2500])
        if place is None:
            place, distance = nearest_place(clean(item.get("organizationCity")))
        if place is None:
            # Nie znamy lokalizacji - nie wpuszczamy do wyników poza obszar.
            distance = 999.0
        city = place or clean(item.get("organizationCity"))

        description = title
        przedmiot = re.search(
            r"Przedmiot zamówienia[^:]{0,60}:\s*(.{0,700}?)(?:\s{2,}|CPV|Termin|$)",
            body,
            re.IGNORECASE,
        )
        if przedmiot:
            description = clean(przedmiot.group(1))
        elif location_snippet:
            description = f"{title}. Miejsce realizacji: {clean(location_snippet)}"

        deadline = iso(item.get("submittingOffersDate"))
        leads.append(
            {
                "source": "bzp",
                "source_label": SOURCE_LABEL,
                "external_id": notice or object_id,
                "title": title,
                "description": description[:900],
                "url": DETAIL.format(object_id=object_id),
                "city": city,
                "distance_km": distance,
                "published_at": iso(item.get("publicationDate")),
                "deadline": deadline,
                "cpv": clean(item.get("cpvCode")),
                "organization": clean(item.get("organizationName")),
                "budget": None,
            }
        )

    return leads, f"pobrano {len(items)} ogłoszeń (ostatnie {days} dni)"
