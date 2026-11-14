"""Wysyłka powiadomień push przez ntfy.sh (aplikacja ntfy na iPhone)."""

from __future__ import annotations

from datetime import datetime

import requests

NTFY_URL = "https://ntfy.sh/"


def send(
    topic: str,
    title: str,
    message: str,
    priority: int = 3,
    click: str | None = None,
    tags: list[str] | None = None,
) -> tuple[bool, str]:
    if not topic:
        return False, "brak tematu ntfy"
    payload = {
        "topic": topic,
        "title": title[:110],
        "message": message[:3500],
        "priority": priority,
        "tags": tags or ["construction"],
    }
    if click:
        payload["click"] = click
    try:
        response = requests.post(NTFY_URL, json=payload, timeout=20)
        if response.ok:
            return True, f"wysłano ({response.status_code})"
        return False, f"ntfy {response.status_code}: {response.text[:160]}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def format_deadline(value: str | None) -> str:
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return ""


def notify_lead(topic: str, lead: dict, app_url: str = "") -> tuple[bool, str]:
    title = f"Nowe zlecenie: {lead.get('service_label', 'Budowlane')}"
    place = lead.get("city") or "Opolskie"
    distance = lead.get("distance_km")
    place_line = place + (f" ({distance:g} km)" if distance is not None else "")
    lines = [
        lead.get("title", ""),
        "",
        f"Lokalizacja: {place_line}",
        f"Trafność: {lead.get('score', 0)}/100 ({lead.get('score_label', '')})",
        f"Źródło: {lead.get('source_label', '')}",
    ]
    deadline = format_deadline(lead.get("deadline"))
    if deadline:
        lines.append(f"Termin ofert: {deadline}")
    if lead.get("deadline_text"):
        lines.append(f"Termin: {lead['deadline_text']}")
    click = (app_url.rstrip("/") + "/?lead=" + lead["id"]) if app_url else lead.get("url")
    return send(
        topic=topic,
        title=title,
        message="\n".join(line for line in lines if line is not None),
        priority=4 if lead.get("score", 0) >= 65 else 3,
        click=click,
    )


def notify_digest(topic: str, leads: list[dict], app_url: str = "") -> tuple[bool, str]:
    lines = [f"Nowych zleceń: {len(leads)}", ""]
    for lead in leads[:8]:
        place = lead.get("city") or "Opolskie"
        lines.append(f"• {lead.get('score', 0)}/100 — {lead.get('title', '')[:90]} ({place})")
    click = app_url.rstrip("/") + "/" if app_url else None
    return send(
        topic=topic,
        title=f"FASARO: {len(leads)} nowych zleceń",
        message="\n".join(lines),
        priority=3,
        click=click,
    )
