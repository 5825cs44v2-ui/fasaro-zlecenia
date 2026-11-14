"""Źródło: BIP Urzędu Miasta Kędzierzyn-Koźle - zamówienia nieobjęte PZP."""

from __future__ import annotations

import re

from ..geo import CITY
from .base import clean, get, make_session, pl_datetime

LIST_URL = "https://bip.kedzierzynkozle.pl/przetargi/23/1/25"
SOURCE_LABEL = "BIP Kędzierzyn-Koźle"


def fetch(cfg: dict, first_run: bool = False) -> tuple[list[dict], str]:
    session = make_session()
    response = get(session, LIST_URL, verify=False)
    response.raise_for_status()
    response.encoding = "utf-8"

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(response.text, "lxml")
    leads: list[dict] = []
    seen: set[str] = set()

    for table in soup.select("table"):
        link = table.select_one("a[href*='/przetarg/']")
        if not link:
            continue
        href = link.get("href", "")
        number_match = re.search(r"/przetarg/(\d+)/", href)
        if not number_match:
            continue
        number = number_match.group(1)
        if number in seen:
            continue
        seen.add(number)

        caption = table.find("caption")
        title = clean(link.get_text(" "))
        if caption:
            caption_text = clean(caption.get_text(" "))
            if ":" in caption_text:
                title = clean(caption_text.split(":", 1)[1]) or title

        values: dict[str, str] = {}
        for row in table.select("tr"):
            header = row.find("th")
            cell = row.find("td")
            if header and cell:
                values[clean(header.get_text(" ")).lower()] = clean(cell.get_text(" "))

        deadline = None
        time_node = table.select_one("time[datetime]")
        if time_node and time_node.get("datetime"):
            raw_dt = time_node.get("datetime", "")
            try:
                from datetime import datetime, timezone

                deadline = datetime.fromisoformat(raw_dt).replace(tzinfo=timezone.utc).isoformat()
            except ValueError:
                deadline = pl_datetime(time_node.get_text(" "))
        if deadline is None:
            deadline = pl_datetime(values.get("termin składania ofert", ""))

        status = values.get("status zamówienia", "")
        buyer = values.get("zamawiający", "")
        description = " | ".join(part for part in [status, buyer] if part)

        leads.append(
            {
                "source": "bip_kk",
                "source_label": SOURCE_LABEL,
                "external_id": number,
                "title": title,
                "description": description,
                "url": href,
                "city": CITY,
                "distance_km": 0.0,
                "published_at": None,
                "deadline": deadline,
                "cpv": "",
                "organization": buyer or "Gmina Kędzierzyn-Koźle",
                "budget": None,
            }
        )

    return leads, f"pobrano {len(leads)} ogłoszeń"
