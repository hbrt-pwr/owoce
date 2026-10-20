"""Początkowa lista kategorii i owoców. Celowo BEZ żadnych ocen i komentarzy."""
from django.db import migrations

CATEGORIES = {
    "ziarnkowe": "Ziarnkowe",
    "pestkowe": "Pestkowe",
    "jagodowe": "Jagodowe",
    "cytrusowe": "Cytrusowe",
    "tropikalne": "Tropikalne",
    "melony": "Melony i arbuzy",
}

# (slug, nazwa, emoji, podtytuł, opis, kategorie)
FRUITS = [
    ("jablko", "Jabłko", "🍎", "tu wstaw podtytuł", "tu wstaw opis", ["ziarnkowe"]),
    ("gruszka", "Gruszka", "🍐", "tu wstaw podtytuł", "tu wstaw opis", ["ziarnkowe"]),
    ("pigwa", "Pigwa", "🟡", "tu wstaw podtytuł", "tu wstaw opis", ["ziarnkowe"]),
    ("sliwka", "Śliwka", "🟣", "tu wstaw podtytuł", "tu wstaw opis", ["pestkowe"]),
    ("wisnia", "Wiśnia", "🍒", "tu wstaw podtytuł", "tu wstaw opis", ["pestkowe"]),
    ("czeresnia", "Czereśnia", "🍒", "tu wstaw podtytuł", "tu wstaw opis", ["pestkowe"]),
    ("brzoskwinia", "Brzoskwinia", "🍑", "tu wstaw podtytuł", "tu wstaw opis", ["pestkowe"]),
    ("morela", "Morela", "🟠", "tu wstaw podtytuł", "tu wstaw opis", ["pestkowe"]),
    ("truskawka", "Truskawka", "🍓", "tu wstaw podtytuł", "tu wstaw opis", ["jagodowe"]),
    ("malina", "Malina", "🔴", "tu wstaw podtytuł", "tu wstaw opis", ["jagodowe"]),
    ("borowka", "Borówka amerykańska", "🫐", "tu wstaw podtytuł", "tu wstaw opis", ["jagodowe"]),
    ("winogrono", "Winogrono", "🍇", "tu wstaw podtytuł", "tu wstaw opis", ["jagodowe"]),
    ("agrest", "Agrest", "🟢", "tu wstaw podtytuł", "tu wstaw opis", ["jagodowe"]),
    ("porzeczka", "Czarna porzeczka", "⚫", "tu wstaw podtytuł", "tu wstaw opis", ["jagodowe"]),
    ("pomarancza", "Pomarańcza", "🍊", "tu wstaw podtytuł", "tu wstaw opis", ["cytrusowe"]),
    ("mandarynka", "Mandarynka", "🍊", "tu wstaw podtytuł", "tu wstaw opis", ["cytrusowe"]),
    ("cytryna", "Cytryna", "🍋", "tu wstaw podtytuł", "tu wstaw opis", ["cytrusowe"]),
    ("limonka", "Limonka", "🟢", "tu wstaw podtytuł", "tu wstaw opis", ["cytrusowe"]),
    ("grejpfrut", "Grejpfrut", "🔶", "tu wstaw podtytuł", "tu wstaw opis", ["cytrusowe"]),
    ("banan", "Banan", "🍌", "tu wstaw podtytuł", "tu wstaw opis", ["tropikalne"]),
    ("ananas", "Ananas", "🍍", "tu wstaw podtytuł", "tu wstaw opis", ["tropikalne"]),
    ("mango", "Mango", "🥭", "tu wstaw podtytuł", "tu wstaw opis", ["tropikalne", "pestkowe"]),
    ("kiwi", "Kiwi", "🥝", "tu wstaw podtytuł", "tu wstaw opis", ["tropikalne"]),
    ("kokos", "Kokos", "🥥", "tu wstaw podtytuł", "tu wstaw opis", ["tropikalne"]),
    ("granat", "Granat", "🔴", "tu wstaw podtytuł", "tu wstaw opis", ["tropikalne"]),
    ("awokado", "Awokado", "🥑", "tu wstaw podtytuł", "tu wstaw opis", ["tropikalne"]),
    ("marakuja", "Marakuja", "🟤", "tu wstaw podtytuł", "tu wstaw opis", ["tropikalne"]),
    ("liczi", "Liczi", "⚪", "tu wstaw podtytuł", "tu wstaw opis", ["tropikalne"]),
    ("arbuz", "Arbuz", "🍉", "tu wstaw podtytuł", "tu wstaw opis", ["melony"]),
    ("melon", "Melon", "🍈", "tu wstaw podtytuł", "tu wstaw opis", ["melony"]),
]


def seed(apps, schema_editor):
    Category = apps.get_model("fruits", "Category")
    Fruit = apps.get_model("fruits", "Fruit")
    cats = {}
    for slug, name in CATEGORIES.items():
        cats[slug], _ = Category.objects.get_or_create(slug=slug, defaults={"name": name})
    for slug, name, emoji, tagline, description, cat_slugs in FRUITS:
        fruit, _ = Fruit.objects.get_or_create(
            slug=slug, defaults={"name": name, "emoji": emoji, "tagline": tagline, "description": description}
        )
        fruit.categories.set([cats[c] for c in cat_slugs])


def unseed(apps, schema_editor):
    apps.get_model("fruits", "Fruit").objects.filter(slug__in=[f[0] for f in FRUITS]).delete()
    apps.get_model("fruits", "Category").objects.filter(slug__in=CATEGORIES).delete()


class Migration(migrations.Migration):
    dependencies = [("fruits", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
