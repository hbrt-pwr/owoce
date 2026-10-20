from .models import Category, Fruit


def nav(request):
    """Lista owoców i kategorii do menu "Wybierz owoc" w nagłówku."""
    return {
        "nav_fruits": Fruit.objects.only("name", "slug"),
        "nav_categories": Category.objects.all(),
    }
