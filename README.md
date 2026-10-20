# FruitRankings 🍎

Prosta strona do oceniania owoców (wzorowana na applerankings.com).
Stack: **Python 3.12 + Django 5.2 + SQLite + Pillow (zdjęcia)** — tylko localhost.

## Funkcje
- Rejestracja, logowanie i wylogowanie (sesje Django zapisywane w bazie, ważne 14 dni).
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
.\.venv\Scripts\python manage.py load_sample_photos   # przykładowe zdjęcia (jabłko, gruszka, banan)
.\.venv\Scripts\python manage.py createsuperuser   # konto admina
.\.venv\Scripts\python manage.py runserver
```
Strona: http://localhost:8000 · Panel admina: http://localhost:8000/admin/

Testy: `.\.venv\Scripts\python manage.py test fruits`

## Struktura
- `config/` – ustawienia i główne URL-e
- `fruits/models.py` – Category, Fruit, Rating, Comment + logika wyniku i werdyktów
- `fruits/views.py` – ranking, szczegóły owocu, ocenianie, komentarze, rejestracja, profil
- `fruits/migrations/0002_seed_fruits.py` – początkowa lista owoców
- `fruits/sample_photos/` – przykładowe zdjęcia z Wikimedia Commons (licencje w `manifest.json`); wgrane pliki trafiają do `media/`
- `templates/`, `static/style.css` – widoki HTML i prosty CSS
