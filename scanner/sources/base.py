"""Wspólne narzędzia dla źródeł."""

from __future__ import annotations

import re
import warnings
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

warnings.filterwarnings("ignore", message="Unverified HTTPS request")

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": UA,
            "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.7",
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        }
    )
    retry = Retry(
        total=2,
        backoff_factor=1.2,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "POST"),
    )
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


def get(session: requests.Session, url: str, **kwargs) -> requests.Response:
    kwargs.setdefault("timeout", 45)
    return session.get(url, **kwargs)


def clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html or "", "lxml")
    for tag in soup(["style", "script", "noscript"]):
        tag.decompose()
    return clean(soup.get_text(" "))


def iso(value: str | None) -> str | None:
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
    return dt.astimezone(timezone.utc).isoformat()


def pl_datetime(date_text: str, time_text: str = "") -> str | None:
    raw = clean(f"{date_text} {time_text}")
    m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})(?:\s+(\d{1,2}):(\d{2}))?", raw)
    if not m:
        return None
    day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    hour = int(m.group(4) or 0)
    minute = int(m.group(5) or 0)
    try:
        return datetime(year, month, day, hour, minute, tzinfo=timezone.utc).isoformat()
    except ValueError:
        return None


def absolute(base: str, href: str) -> str:
    return urljoin(base, href)


def first_text(node, selector: str, default: str = "") -> str:
    found = node.select_one(selector)
    return clean(found.get_text(" ")) if found else default
