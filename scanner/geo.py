"""Miejscowości w promieniu ~40 km od Kędzierzyna-Koźla i liczenie odległości."""

from __future__ import annotations

import math
import re
import unicodedata

CITY = "Kędzierzyn-Koźle"
CITY_LAT = 50.3490
CITY_LON = 18.2260

# (nazwa, szerokość, długość, rdzenie nazw do wyszukania w tekście)
PLACES: list[tuple[str, float, float, tuple[str, ...]]] = [
    ("Kędzierzyn-Koźle", 50.3490, 18.2260, ("kedzierzyn", "kozle", "kladnick", "slawiecic")),
    ("Krapkowice", 50.4750, 17.9650, ("krapkowic", "otmet")),
    ("Strzelce Opolskie", 50.5100, 18.3020, ("strzelc",)),
    ("Zdzieszowice", 50.4240, 18.1230, ("zdzieszowic",)),
    ("Gogolin", 50.4920, 18.0200, ("gogolin",)),
    ("Leśnica", 50.4310, 18.1870, ("lesnic",)),
    ("Ujazd", 50.3970, 18.3490, ("ujazd",)),
    ("Reńska Wieś", 50.3160, 18.1170, ("rensk",)),
    ("Cisek", 50.2820, 18.2000, ("cisek",)),
    ("Bierawa", 50.2860, 18.2440, ("bieraw",)),
    ("Polska Cerekiew", 50.2280, 18.1260, ("cerekiew",)),
    ("Pawłowiczki", 50.2830, 18.0560, ("pawlowicz",)),
    ("Walce", 50.3720, 17.9860, ("walce",)),
    ("Zawadzkie", 50.6070, 18.4850, ("zawadzki",)),
    ("Jemielnica", 50.5520, 18.3830, ("jemielnic",)),
    ("Izbicko", 50.5730, 18.1580, ("izbick",)),
    ("Strzeleczki", 50.4600, 17.8570, ("strzeleczk",)),
    ("Głogówek", 50.3540, 17.8640, ("glogowk",)),
    ("Kietrz", 50.0800, 18.0000, ("kietrz",)),
    ("Baborów", 50.1600, 17.9800, ("baborow",)),
    ("Racibórz", 50.0900, 18.2200, ("raciborz",)),
    ("Kuźnia Raciborska", 50.2000, 18.3100, ("kuzni",)),
    ("Nędza", 50.1600, 18.3000, ("nedz",)),
    ("Rudnik", 50.1300, 18.1900, ("rudnik",)),
    ("Sośnicowice", 50.2700, 18.5300, ("sosnicowic",)),
    ("Rudziniec", 50.3500, 18.4800, ("rudziniec",)),
    ("Wielowieś", 50.5100, 18.4200, ("wielowies",)),
    ("Krupski Młyn", 50.5700, 18.4200, ("krupski",)),
    ("Tworóg", 50.5300, 18.4800, ("tworog",)),
    ("Toszek", 50.4500, 18.5200, ("toszek",)),
    ("Pyskowice", 50.4000, 18.6300, ("pyskowic",)),
    ("Gliwice", 50.2945, 18.6714, ("gliwice", "gliwicz")),
    ("Opole", 50.6751, 17.9213, ("opole",)),
    ("Korfantów", 50.4900, 17.6000, ("korfantow",)),
    # Miejscowości poza promieniem 35 km - po to, by odrzucić dalekie ogłoszenia.
    ("Nysa", 50.4740, 17.3320, ("nysa", "nysie", "nysy")),
    ("Brzeg", 50.8610, 17.4670, ("brzeg", "brzegu")),
    ("Głuchołazy", 50.3150, 17.3830, ("glucholaz",)),
    ("Prudnik", 50.3210, 17.5740, ("prudnik",)),
    ("Grodków", 50.6980, 17.3840, ("grodkow",)),
    ("Namysłów", 51.0760, 17.7230, ("namyslow",)),
    ("Kluczbork", 50.9730, 18.2180, ("kluczbork",)),
    ("Olesno", 50.8770, 18.4210, ("olesno",)),
    ("Dobrodzień", 50.7300, 18.4470, ("dobrodzien",)),
    ("Kolonowskie", 50.6570, 18.3860, ("kolonowsk",)),
    ("Ozimek", 50.6790, 18.2130, ("ozimek",)),
    ("Tarnów Opolski", 50.5770, 18.0830, ("tarnow opolsk",)),
    ("Chrząstowice", 50.6650, 18.0730, ("chrzastowic",)),
    ("Tułowice", 50.5960, 17.6570, ("tulowic",)),
    ("Niemodlin", 50.6420, 17.6200, ("niemodlin",)),
    ("Biała", 50.5030, 17.7350, ("biala",)),
    ("Głubczyce", 50.2000, 17.8290, ("glubczyc",)),
    ("Branice", 50.0000, 17.7500, ("branic",)),
    ("Pokój", 50.9000, 17.8300, ("pokoj",)),
    ("Murów", 50.8600, 17.9500, ("murow",)),
    ("Łubniany", 50.7800, 18.0000, ("lubnian",)),
    ("Komprachcice", 50.6300, 17.8200, ("komprachcic",)),
    ("Dąbrowa", 50.6800, 17.9500, ("dabrowa",)),
    # Dalekie miasta - tylko po to, by nie mylić ich z miejscowościami o podobnej nazwie
    # (np. Bielsko-Biała nie jest Białą pod Krapkowicami).
    ("Bielsko-Biała", 49.8224, 19.0584, ("bielsko",)),
    ("Dąbrowa Górnicza", 50.3216, 19.1873, ("gornicza",)),
    ("Ruda Śląska", 50.2558, 18.8555, ("ruda śląska",)),
    ("Sosnowiec", 50.2863, 19.1040, ("sosnowiec",)),
    ("Jaworzno", 50.2050, 19.2746, ("jaworzno",)),
    ("Katowice", 50.2649, 19.0238, ("katowice",)),
    ("Chorzów", 50.2975, 18.9545, ("chorzow",)),
    ("Zabrze", 50.3249, 18.7857, ("zabrze",)),
    ("Bytom", 50.3480, 18.9157, ("bytom",)),
    ("Tychy", 50.1372, 18.9662, ("tychy",)),
    ("Rybnik", 50.0921, 18.5417, ("rybnik",)),
    ("Żory", 50.0450, 18.7000, ("zory",)),
    ("Tarnowskie Góry", 50.4450, 18.8610, ("tarnowskie",)),
    ("Pszczyna", 49.9800, 18.9500, ("pszczyna",)),
    ("Oświęcim", 50.0340, 19.2100, ("oswiecim",)),
    ("Chrzanów", 50.1400, 19.4000, ("chrzanow",)),
    ("Będzin", 50.3300, 19.1300, ("bedzin",)),
    ("Kraków", 50.0647, 19.9450, ("krakow",)),
    ("Wrocław", 51.1079, 17.0385, ("wroclaw",)),
    ("Warszawa", 52.2297, 21.0122, ("warszawa",)),
    ("Poznań", 52.4064, 16.9252, ("poznan",)),
    ("Łódź", 51.7592, 19.4560, ("lodz",)),
    ("Częstochowa", 50.8118, 19.1203, ("czestochowa",)),
]

_DIACRITICS = str.maketrans(
    {
        "ą": "a",
        "ć": "c",
        "ę": "e",
        "ł": "l",
        "ń": "n",
        "ó": "o",
        "ś": "s",
        "ź": "z",
        "ż": "z",
        "Ą": "a",
        "Ć": "c",
        "Ę": "e",
        "Ł": "l",
        "Ń": "n",
        "Ó": "o",
        "Ś": "s",
        "Ź": "z",
        "Ż": "z",
    }
)


def fold(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "").translate(_DIACRITICS).lower()


def haversine_km(lat: float, lon: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(CITY_LAT), math.radians(lat)
    dp = p2 - p1
    dl = math.radians(lon - CITY_LON)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(a)), 1)


_WORD = re.compile(r"[a-z0-9]+")


def _words(value: str) -> list[str]:
    return _WORD.findall(fold(value))


def nearest_place(text: str) -> tuple[str | None, float | None]:
    """Zwraca najbliższą rozpoznaną miejscowość i dystans w km.

    Najpierw dopasowuje pełne nazwy (np. "bielsko biala"), a dopiero potem
    pojedyncze rdzenie - dzięki temu "Bielsko-Biała" nie jest "Białą".
    """
    tokens = _words(text)
    if not tokens:
        return None, None

    used = [False] * len(tokens)
    hits: list[tuple[str, float]] = []

    for name, lat, lon, _aliases in PLACES:
        parts = _words(name)
        if len(parts) < 2 or len(parts) > len(tokens):
            continue
        span = len(parts)
        for start in range(len(tokens) - span + 1):
            window = tokens[start : start + span]
            if window == parts and not any(used[start : start + span]):
                for index in range(start, start + span):
                    used[index] = True
                hits.append((name, haversine_km(lat, lon)))
                break

    for name, lat, lon, aliases in PLACES:
        for alias in aliases:
            parts = _words(alias)
            if len(parts) != 1:
                continue
            stem = parts[0]
            for index, token in enumerate(tokens):
                if used[index]:
                    continue
                if token == stem or (len(stem) >= 5 and token.startswith(stem)):
                    used[index] = True
                    hits.append((name, haversine_km(lat, lon)))
                    break
            else:
                continue
            break

    if not hits:
        return None, None
    return min(hits, key=lambda item: item[1])


def parse_city_distance(text: str) -> tuple[str, float | None]:
    """Parsuje 'Steblów ( 17 km od Kędzierzyn-Koźle )'."""
    raw = re.sub(r"\s+", " ", (text or "")).strip()
    m = re.search(r"^(.*?)\s*\(\s*(\d+(?:[.,]\d+)?)\s*km\s+od\b", raw, re.IGNORECASE)
    if m:
        city = m.group(1).strip(" ,-")
        return city, float(m.group(2).replace(",", "."))
    city = re.sub(r"\s*\(.*?\)\s*$", "", raw).strip(" ,-")
    _, dist = nearest_place(raw)
    return city, dist


def distance_points(distance_km: float | None, city: str = "") -> int:
    if city and fold(city) in {"kedzierzyn-kozle", "kedzierzyn kozle"}:
        return 30
    if distance_km is None:
        return 3
    if distance_km <= 5:
        return 30
    if distance_km <= 10:
        return 27
    if distance_km <= 15:
        return 23
    if distance_km <= 20:
        return 19
    if distance_km <= 25:
        return 15
    if distance_km <= 30:
        return 11
    if distance_km <= 35:
        return 7
    return 0
