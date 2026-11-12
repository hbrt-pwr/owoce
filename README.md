# Owocownik 🍎

Prosta strona do oceniania owoców (wzorowana na applerankings.com).
Stack: **Python 3.12 + Django 5.2 + Pillow (zdjęcia)**; lokalnie SQLite, w Azure PostgreSQL (Container Apps).

## Funkcje
- Rejestracja, logowanie i wylogowanie (sesje Django zapisywane w bazie, ważne 14 dni). Hasło: min. 10 znaków,
  wielka i mała litera, cyfra i znak specjalny – przy rejestracji lista wymogów odhacza się na żywo.
- „Nie pamiętasz hasła?” – link do ustawienia nowego hasła mailem (ważny 1 godzinę).
- Limit żądań (rate limiting) chroniący przed spamowaniem: ogólny na IP oraz osobne na logowanie, rejestrację
  i reset hasła (`fruits/ratelimit.py`); po przekroczeniu odpowiedź 429.
- Ranking owoców pogrupowany jak na applerankings: *Najlepsze* (70+), *Przeciętne* (40–69), *Owocowe piekło* (<40), *Jeszcze nieocenione*.
- Wyszukiwarka, filtr kategorii, menu „Wybierz owoc”.
- Ocena owocu (tylko dla zalogowanych): 4 kryteria 0–10 (smak 40%, tekstura 25%, soczystość 20%, wygląd i aromat 15%) → wynik 0–100 z werdyktem; jedna ocena na użytkownika, można ją edytować i usuwać.
- Komentarze pod każdym owocem z jednym poziomem odpowiedzi (dyskusja).
- Zdjęcia owoców: galeria (dowolnie wiele zdjęć, z podpisem i autorem/licencją), wgrywana w panelu admina przy edycji owocu. Pierwsze zdjęcie (najniższa wartość pola „kolejność”) jest miniaturą w rankingu; owoce bez zdjęć mają placeholder. Zdjęcia większe niż 1200 px są automatycznie zmniejszane.
- Profil użytkownika z jego osobistym rankingiem.
- Admin (`is_staff`): panel `/admin/` (dodawanie/edycja owoców i kategorii), usuwanie dowolnych ocen i komentarzy (moderacja) bezpośrednio na stronie.
- Na start w bazie są 30 owoców i 6 kategorii, **bez żadnych ocen ani komentarzy**.

## Uruchomienie (Windows / PowerShell)
```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python manage.py migrate
.\.venv\Scripts\python manage.py createcachetable     # tabela cache dla limitów żądań
.\.venv\Scripts\python manage.py load_sample_photos   # przykładowe zdjęcia (jabłko, gruszka, banan)
.\.venv\Scripts\python manage.py createsuperuser   # konto admina
.\.venv\Scripts\python manage.py runserver
```
Strona: http://localhost:8000 · Panel admina: http://localhost:8000/admin/

Testy: `.\.venv\Scripts\python manage.py test fruits`

## Chmura
Projekt architektury (load balancer ze skalowaniem, PostgreSQL, domena, TLS na load balancerze): [docs/L3-architektura.md](docs/L3-architektura.md).
Lokalnie nic się nie zmienia. W chmurze aplikacja działa z obrazu `Dockerfile` (gunicorn), a konfigurację bierze ze zmiennych środowiskowych – wzór w `.env.example`. Sonda dla load balancera: `GET /healthz/`.

Wdrożenie w Azure (Container Apps + PostgreSQL Flexible Server), skrypty w `deploy/azure/`: [docs/wdrozenie-azure.md](docs/wdrozenie-azure.md).

## Struktura
- `config/` – ustawienia (zmienne środowiskowe dla chmury) i główne URL-e
- `fruits/health.py` – sonda `/healthz/` dla load balancera
- `fruits/ratelimit.py` – limit żądań na IP / formularz, `fruits/validators.py` – polityka haseł
- `fruits/management/commands/init_db.py` – migracje + tabela cache + przykładowe zdjęcia przy wdrożeniu
- `deploy/azure/` – skrypty wdrożenia w Azure
- `fruits/models.py` – Category, Fruit, Rating, Comment + logika wyniku i werdyktów
- `fruits/views.py` – ranking, szczegóły owocu, ocenianie, komentarze, rejestracja, profil
- `fruits/migrations/0002_seed_fruits.py` – początkowa lista owoców
- `fruits/sample_photos/` – przykładowe zdjęcia z Wikimedia Commons (licencje w `manifest.json`); wgrane pliki trafiają do `media/`
- `templates/`, `static/style.css` – widoki HTML i prosty CSS
