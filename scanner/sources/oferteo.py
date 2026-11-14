"""Źródło: Oferteo - publiczne zlecenia od osób prywatnych i firm."""

from __future__ import annotations

import re
import time

from .base import clean, get, make_session

BASE = "https://www.oferteo.pl"
CITY_SLUG = "kedzierzyn-kozle"
SOURCE_LABEL = "Oferteo"


def _area(text: str) -> str:
    match = re.search(r"\b\d+\s*[-–]\s*\d+\s*m²|\bdo\s+\d+\s*m²|\b\d+\s*m²", text)
    return clean(match.group(0)) if match else ""


def _deadline_text(tags: str, city: str, area: str) -> str:
    text = tags
    for value in (city, area, "osoba prywatna", "firma"):
        if value:
            text = text.replace(value, " ")
    text = clean(text)
    match = re.search(r"w ciągu\s+\d+\s+\S+|najbliższy wolny termin|termin do ustalenia", text)
    return clean(match.group(0)) if match else ""


def fetch(cfg: dict, first_run: bool = False) -> tuple[list[dict], str]:
    conf = cfg["sources"]["oferteo"]
    categories = conf.get("categories", [])
    session = make_session()
    leads: list[dict] = []
    errors: list[str] = []

    for category in categories:
        url = f"{BASE}/{category}/{CITY_SLUG}"
        try:
            response = get(session, url, verify=False)
            if response.status_code == 404:
                errors.append(f"{category}: brak strony")
                continue
            response.raise_for_status()
            response.encoding = "utf-8"

            from bs4 import BeautifulSoup

            soup = BeautifulSoup(response.text, "lxml")
            for card in soup.select("div.rfp-list-item[data-rfp-id]"):
                rfp_id = clean(card.get("data-rfp-id"))
                if not rfp_id:
                    continue

                title_node = card.select_one("[data-test='rfp_list__item__title']")
                title = clean(title_node.get_text(" ")) if title_node else ""
                if not title:
                    continue

                city_node = card.select_one("[data-test='rfp_list__item__location_city']")
                city_raw = clean(city_node.get_text(" ")) if city_node else ""
                distance = None
                dist_match = re.search(r"(\d+(?:[.,]\d+)?)\s*km\s+od\b", city_raw, re.IGNORECASE)
                shown_distance = (
                    float(dist_match.group(1).replace(",", ".")) if dist_match else None
                )
                city = clean(re.sub(r"\(.*?\)", "", city_raw))

                # Oferteo czasem podaje błędny dystans (np. Bielsko-Biała "38 km").
                # Najpierw liczymy po swojemu, dopiero dla nieznanych miejscowości
                # ufamy dystansowi ze strony.
                from ..geo import nearest_place

                _, distance = nearest_place(city) if city else (None, None)
                if distance is None:
                    distance = shown_distance

                # Strona miasta Oferteo miesza też ogłoszenia z całej Polski.
                # Zostawiamy tylko Kędzierzyn-Koźle i miejscowości w promieniu.
                max_distance = float(cfg.get("max_distance_km", 40))
                if distance is None and not city.lower().startswith("kędzierzyn"):
                    continue
                if distance is not None and distance > max_distance:
                    continue

                date_node = card.select_one("[data-test='rfp_list__item__date']")
                date_value = clean(date_node.get("title")) if date_node else ""
                published = f"{date_value}T06:00:00+00:00" if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_value) else None

                tags_node = card.select_one(".rfp-tile_tags")
                tags = clean(tags_node.get_text(" ")) if tags_node else ""
                area = _area(tags)
                deadline_text = _deadline_text(tags, city, area)
                client = "firma" if "firma" in tags.lower() else "osoba prywatna"

                description = " • ".join(
                    part for part in [client, area, deadline_text] if part
                )

                leads.append(
                    {
                        "source": "oferteo",
                        "source_label": SOURCE_LABEL,
                        "external_id": rfp_id,
                        "title": title,
                        "description": description,
                        "url": url,
                        "city": city,
                        "distance_km": distance,
                        "published_at": published,
                        "deadline": None,
                        "deadline_text": deadline_text,
                        "cpv": "",
                        "organization": "",
                        "budget": None,
                        "area": area,
                    }
                )
        except Exception as exc:  # pojedyncza kategoria nie może zabić całego skanu
            errors.append(f"{category}: {type(exc).__name__}")
        time.sleep(0.8)

    note = f"pobrano {len(leads)} zleceń z {len(categories)} kategorii"
    if errors:
        note += " (problemy: " + "; ".join(errors[:3]) + ")"
    return leads, note
