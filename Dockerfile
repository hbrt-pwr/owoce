# Obraz aplikacji FruitRankings – ten sam obraz uruchamia każda instancja za load balancerem.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_DEBUG=0 \
    PORT=8000

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Pliki statyczne budowane raz, w obrazie (klucz tylko na czas budowania, prawdziwy przychodzi ze zmiennych).
RUN DJANGO_SECRET_KEY=build-only python manage.py collectstatic --noinput

# Aplikacja nie działa jako root.
RUN useradd --create-home --uid 10001 app && chown -R app /app
USER app

EXPOSE 8000

# HTTP w sieci prywatnej – TLS kończy się na load balancerze.
# Migracje NIE są tu uruchamiane: przy kilku instancjach robi to jednorazowe zadanie przy wdrożeniu
# (docker run ... python manage.py migrate), żeby instancje nie migrowały bazy równocześnie.
CMD gunicorn config.wsgi:application --bind 0.0.0.0:${PORT} --workers ${GUNICORN_WORKERS:-3} --access-logfile -
