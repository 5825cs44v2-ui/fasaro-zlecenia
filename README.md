# FASARO Zlecenia

Aplikacja na iPhone, która pokazuje **zlecenia budowlane i przetargi z okolic Kędzierzyna-Koźla** dopasowane do usług FASARO PRO: elewacje, ocieplenia, tynki i gładzie, remonty wnętrz.

Działa jak zwykła aplikacja (ikona na ekranie początkowym), a o nowych zleceniach powiadamia przez darmową aplikację **ntfy**.

---

## Co robi

- Co 30 minut sprawdza publiczne źródła: **BZP**, **e-ProPublico**, **BIP Kędzierzyn-Koźle** i **Oferteo**.
- Odsiewa ogłoszenia spoza okolicy (domyślnie do 40 km) i te niezwiązane z usługami firmy.
- Liczy trafność 0–100 (słowa kluczowe + odległość + świeżość + termin).
- Pokazuje listę w aplikacji i wysyła push, gdy pojawi się coś nowego.
- Podpowiada szybkie wyszukiwanie w OLX, Facebook Marketplace i Google (tych serwisów nie da się sprawdzać automatycznie — blokują boty).

**Czego nie robi:** nie pobiera danych kontaktowych klientów, nie loguje się nigdzie, nie publikuje danych osobowych. W repozytorium są wyłącznie publiczne ogłoszenia i przetargi.

---

## Instalacja na iPhone (dla właściciela)

1. Otwórz adres aplikacji w **Safari** (np. `https://twoj-login.github.io/fasaro-zlecenia/`).
2. Dotknij przycisku **Udostępnij** (kwadrat ze strzałką).
3. Wybierz **„Dodaj do ekranu początkowego”** i potwierdź.
4. Na ekranie pojawi się ikona **F**. Otwieraj zlecenia jednym dotknięciem.

### Powiadomienia

1. Zainstaluj z App Store darmową aplikację **ntfy**.
2. W aplikacji FASARO otwórz zakładkę **Info** → **Otwórz w ntfy**.
3. Zatwierdź subskrypcję tematu. Od tej pory nowe zlecenia przychodzą jako push.

Temat powiadomień jest w pliku `config.json` (pole `ntfy_topic`). Jest trudny do odgadnięcia, ale **nie podawaj go publicznie** — kto zna temat, ten widzi powiadomienia.

---

## Wdrożenie na GitHub (jednorazowo)

Potrzebne: konto GitHub i program **GitHub CLI** (`gh`). Na Windows:

```powershell
winget install --id GitHub.cli
```

Potem w folderze projektu uruchom:

```powershell
powershell -ExecutionPolicy Bypass -File .\wgraj-na-github.ps1
```

Skrypt:

1. poprosi o zalogowanie do GitHama (otworzy przeglądarkę),
2. utworzy **publiczne** repozytorium,
3. wgra pliki,
4. włączy GitHub Pages dla folderu `docs`,
5. uruchomi pierwszy skan i otworzy gotowy adres.

Pierwszy skan tylko zapisuje bazę startową — **nie wysyła powiadomień**, żeby nie zasypać telefonu starymi ogłoszeniami. Kolejne skany powiadamiają już normalnie.

### Ręcznie (jeśli wolisz)

1. Utwórz puste, publiczne repozytorium na GitHubie.
2. W folderze projektu:
   ```powershell
   git init
   git add -A
   git commit -m "FASARO Zlecenia"
   git branch -M main
   git remote add origin https://github.com/TWOJ-LOGIN/fasaro-zlecenia.git
   git push -u origin main
   ```
3. W repozytorium: **Settings → Pages → Source: Deploy from a branch → Branch: main / folder: /docs → Save**.
4. W zakładce **Actions** uruchom workflow **Skan zleceń** (Run workflow).

Adres aplikacji: `https://TWOJ-LOGIN.github.io/fasaro-zlecenia/`

---

## Podgląd na komputerze

```powershell
powershell -ExecutionPolicy Bypass -File .\start-lokalnie.ps1
```

Skrypt uruchomi lokalny serwer i otworzy `http://localhost:8765/`. Zamknięcie okna zatrzymuje serwer.

Ręcznie:

```powershell
cd docs
python -m http.server 8765
```

Potem wejdź na `http://localhost:8765/`.

Skanowanie danych lokalnie:

```powershell
pip install -r requirements.txt
python -m scanner.run --out docs/data
```

---

## Struktura projektu

```
zlecenia-app/
├─ config.json                  ustawienia: temat ntfy, promień, progi, źródła
├─ requirements.txt             biblioteki Pythona
├─ scanner/
│  ├─ run.py                    główny przebieg: pobierz → oceń → zapisz → powiadom
│  ├─ matching.py               słowa kluczowe i punktacja trafności
│  ├─ geo.py                    miejscowości w promieniu i liczenie odległości
│  ├─ notify.py                 wysyłka push przez ntfy
│  └─ sources/
│     ├─ bzp.py                 BZP / e-Zamówienia (API)
│     ├─ epropublico.py         4 zamawiających z Kędzierzyna-Koźla
│     ├─ bip_kk.py              BIP Urzędu Miasta
│     └─ oferteo.py             publiczne zlecenia Oferteo
├─ docs/                        aplikacja (GitHub Pages)
│  ├─ index.html
│  ├─ app.js
│  ├─ style.css
│  ├─ manifest.webmanifest
│  ├─ sw.js                     tryb offline
│  ├─ icons/
│  └─ data/                     generowane dane: leads.json, meta.json, seen.json
├─ tools/make_icons.py          generator ikon
└─ .github/workflows/skan.yml   harmonogram co 30 minut
```

---

## Ustawienia (`config.json`)

| Pole | Znaczenie |
|---|---|
| `radius_km` | promień używany w opisach i punktacji |
| `max_distance_km` | twarde odcięcie ogłoszeń spoza okolicy (domyślnie 40) |
| `min_score` | minimalna trafność, żeby ogłoszenie trafiło na listę (18) |
| `notify_min_score` | minimalna trafność, żeby wysłać push (35) |
| `notify_max_per_run` | maksymalna liczba pushy w jednym przebiegu (4) |
| `ntfy_topic` | temat powiadomień ntfy |
| `sources.*.enabled` | które źródła są włączone |
| `sources.oferteo.categories` | kategorie Oferteo do sprawdzania |

Po zmianie `config.json` nie trzeba nic wgrywać ręcznie — następny skan użyje nowych ustawień.

---

## Źródła — co działa, a co nie

| Źródło | Sposób | Uwagi |
|---|---|---|
| BZP / e-Zamówienia | API JSON | Pewne dane, ale w województwie opolskim niewiele przetargów dotyczy elewacji. |
| e-ProPublico | strony HTML | Gmina K-K, MZBudynki, PCUW, Starostwo Powiatowe. |
| BIP Kędzierzyn-Koźle | strony HTML | Zamówienia nieobjęte PZP — często drobne remonty. |
| Oferteo | strony HTML | Zlecenia prywatne; strona miasta miesza też dalekie miasta, dlatego liczymy odległość sami. |
| OLX | zablokowane | Tylko przycisk szybkiego wyszukiwania. |
| Facebook Marketplace | zablokowane | Tylko przycisk szybkiego wyszukiwania. |

Strony HTML mogą się zmienić. Jeśli źródło przestanie działać, w zakładce **Info → Skąd bierzemy zlecenia** przy jego nazwie pojawi się „chwilowy błąd”. Aplikacja pokaże wtedy ostatnie zapisane dane.

---

## RODO i bezpieczeństwo

- Repozytorium jest **publiczne** (darmowy GitHub Pages), dlatego nie wolno w nim umieszczać danych klientów, umów, wycen ani plików z formularza.
- Aplikacja zbiera wyłącznie publiczne ogłoszenia i przetargi. Nie zawiera numerów telefonów osób prywatnych ani adresów e-mail.
- Temat ntfy działa jak hasło dostępu do powiadomień — nie publikuj go.
- `docs/data/seen.json` zawiera tylko identyfikatory i daty, bez danych osobowych.

---

## Rozwiązywanie problemów

**Lista jest pusta**
- Sprawdź w zakładce **Info**, czy źródła mają zieloną kropkę.
- Uruchom ręcznie workflow **Skan zleceń** w zakładce Actions.
- Poczekaj — GitHub czasem opóźnia zadania o kilka minut.

**Brak powiadomień**
- Sprawdź, czy w aplikacji ntfy subskrybujesz właściwy temat.
- Sprawdź uprawnienia powiadomień dla ntfy w Ustawieniach iPhone’a.
- Pierwszy skan celowo nie wysyła powiadomień.
- Push wysyłamy tylko dla zleceń z trafnością ≥ 35 i maksymalnie 4 na przebieg.

**Aplikacja pokazuje stare dane**
- Dotknij ikony odświeżania w prawym górnym rogu.
- Pociągnij stronę w dół w Safari, aby odświeżyć.

**Błąd „403” lub „chwilowy błąd” przy źródle**
- Serwis mógł zmienić zabezpieczenia. Sprawdź logi workflow w GitHub Actions.
- Aplikacja nadal pokazuje ostatnie poprawne dane.

---

## Rozwój

Nowe źródło dodajesz w `scanner/sources/`, rejestrujesz w `scanner/sources/__init__.py` i dodajesz sekcję w `config.json`.

```python
def fetch(cfg: dict, first_run: bool = False) -> tuple[list[dict], str]:
    ...
    return leads, "pobrano N ogłoszeń"
```

Każde ogłoszenie to słownik z polami: `source`, `source_label`, `external_id`, `title`, `description`, `url`, `city`, `distance_km`, `published_at`, `deadline`, `cpv`, `organization`.

Punktację i słowa kluczowe zmieniasz w `scanner/matching.py` (listy `POSITIVE` i `NEGATIVE`).

---

## Licencja i własność

Projekt wewnętrzny FASARO PRO Dominika Ziomek.
Kontakt: tel. 735 431 999 · [fasaro.pro](https://fasaro.pro)
