"""Wgrywa przykładowe zdjęcia z fruits/sample_photos/ (opis w manifest.json) do galerii owoców.

Uruchomienie: python manage.py load_sample_photos
Polecenie można odpalać wielokrotnie – zdjęcia już wgrane są pomijane.
"""
import json
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand

from fruits.models import Fruit, FruitImage

SAMPLE_DIR = Path(__file__).resolve().parents[2] / "sample_photos"


class Command(BaseCommand):
    help = "Wgrywa przykładowe zdjęcia owoców z fruits/sample_photos/."

    def handle(self, *args, **options):
        manifest = json.loads((SAMPLE_DIR / "manifest.json").read_text(encoding="utf-8"))
        added = 0
        for entry in manifest:
            fruit = Fruit.objects.filter(slug=entry["fruit"]).first()
            if fruit is None:
                self.stderr.write(f"Pominięto {entry['file']}: brak owocu '{entry['fruit']}'.")
                continue
            if fruit.images.filter(caption=entry["caption"]).exists():
                continue
            with open(SAMPLE_DIR / entry["file"], "rb") as fh:
                img = FruitImage(fruit=fruit, caption=entry["caption"], credit=entry["credit"], order=entry.get("order", 0))
                img.image.save(entry["file"], File(fh), save=True)
            added += 1
            self.stdout.write(f"+ {fruit.name}: {entry['caption']}")
        self.stdout.write(self.style.SUCCESS(f"Dodano zdjęć: {added}"))
