"""Źródło: e-ProPublico - platforma zamówień publicznych w Kędzierzynie-Koźlu."""

from __future__ import annotations

import re

from ..geo import CITY
from .base import absolute, clean, get, make_session, pl_datetime

BASE = "https://e-propublico.pl"
SOURCE_LABEL = "e-ProPublico"

# Czterej główni zamawiający z Kędzierzyna-Koźla i powiatu.
BUYERS = {
    "Gmina Kędzierzyn-Koźle": "f15dda4c-01df-4c59-b90f-a767d9826443",
    "Miejski Zarząd Budynków Komunalnych": "ff998091-c311-49c0-bb75-a02bb4730050",
    "Powiatowe Centrum Usług Wspólnych": "77dc63a8-5c92-4a75-9319-a101d0990564",
    "Starostwo Powiatowe": "3611a80c-960b-4d62-a833-f0fb5e3d6679",
}


def _buyer_url(buyer_id: str) -> str:
    return f"{BASE}/Zamawiajacy/AktualneOgloszenia?zamawiajacyId={buyer_id}"


def fetch(cfg: dict, first_run: bool = False) -> tuple[list[dict], str]:
    session = make_session()
    leads: list[dict] = []
    seen: set[str] = set()
    errors: list[str] = []

    from bs4 import BeautifulSoup

    for buyer_name, buyer_id in BUYERS.items():
        try:
            response = get(session, _buyer_url(buyer_id), verify=False)
            response.raise_for_status()
            response.encoding = "utf-8"
            soup = BeautifulSoup(response.text, "lxml")
        except Exception as exc:
            errors.append(f"{buyer_name}: {type(exc).__name__}")
            continue

        for table in soup.select("table"):
            rows = table.select("tbody tr")
            if not rows:
                continue
            heading = ""
            previous = table.find_previous(["h2", "h3", "h4", "h5", "strong"])
            if previous:
                heading = clean(previous.get_text(" "))
            if not heading:
                caption = table.find("caption")
                heading = clean(caption.get_text(" ")) if caption else ""

            for row in rows:
                link = row.select_one("a[href*='/Ogloszenia/Details/']")
                if not link:
                    continue
                href = link.get("href", "")
                guid_match = re.search(r"/Ogloszenia/Details/([0-9a-fA-F-]{8,})", href)
                if not guid_match:
                    continue
                guid = guid_match.group(1)
                if guid in seen:
                    continue
                seen.add(guid)

                cells = row.find_all("td")
                signature = clean(cells[0].get_text(" ")) if cells else ""
                title = clean(link.get_text(" "))
                deadline = None
                if len(cells) >= 3:
                    deadline = pl_datetime(cells[-1].get_text(" "))

                leads.append(
                    {
                        "source": "epropublico",
                        "source_label": SOURCE_LABEL,
                        "external_id": guid,
                        "title": title,
                        "description": clean(
                            f"{heading}. {buyer_name}."
                            + (f" Sygnatura: {signature}" if signature else "")
                        ),
                        "url": absolute(BASE, href),
                        "city": CITY,
                        "distance_km": 0.0,
                        "published_at": None,
                        "deadline": deadline,
                        "cpv": "",
                        "organization": buyer_name,
                        "budget": None,
                    }
                )

    note = f"pobrano {len(leads)} aktualnych ogłoszeń od {len(BUYERS)} zamawiających"
    if errors:
        note += " (problemy: " + "; ".join(errors) + ")"
    return leads, note
