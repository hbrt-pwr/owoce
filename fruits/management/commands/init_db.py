"""Przygotowanie bazy przy wdrożeniu: migracje + przykładowe zdjęcia.

Uruchomienie: python manage.py init_db
W Azure uruchamia to jednorazowe zadanie (Container Apps Job) przy każdym wdrożeniu – nie robią tego
instancje aplikacji przy starcie, żeby kilka instancji nie migrowało bazy jednocześnie.
Polecenie można odpalać wielokrotnie: migracje już wykonane i zdjęcia już wgrane są pomijane.
"""
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Wykonuje migracje i wgrywa przykładowe zdjęcia (do uruchamiania przy wdrożeniu)."

    def handle(self, *args, **options):
        call_command("migrate", interactive=False)
        call_command("load_sample_photos")
        self.stdout.write(self.style.SUCCESS("Baza gotowa."))
