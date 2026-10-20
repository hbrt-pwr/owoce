from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse

# Kryteria oceny i ich wagi (suma = 1.0). Wynik końcowy jest w skali 0–100.
CRITERIA = [
    ("taste", "Smak", 0.40),
    ("texture", "Tekstura", 0.25),
    ("juiciness", "Soczystość", 0.20),
    ("look", "Wygląd i aromat", 0.15),
]

# Werdykty zależne od wyniku (próg minimalny, etykieta) – od najwyższego.
VERDICTS = [
    (90, "Niemal idealny"),
    (80, "Wyborny"),
    (70, "Znakomity"),
    (60, "Dobry"),
    (50, "Przeciętny"),
    (40, "Ledwo warty uwagi"),
    (30, "Niegodny"),
    (20, "Paskudny"),
    (0, "Karma dla koni"),
]

# Grupy w rankingu, tak jak na applerankings.com.
TIERS = [
    (70, "top", "Najlepsze owoce"),
    (40, "avg", "Przeciętne owoce"),
    (0, "hell", "Owocowe piekło"),
]


def verdict_for(score):
    if score is None:
        return "Brak ocen"
    for threshold, label in VERDICTS:
        if score >= threshold:
            return label
    return VERDICTS[-1][1]


def tier_for(score):
    if score is None:
        return ("none", "Jeszcze nieocenione")
    for threshold, key, label in TIERS:
        if score >= threshold:
            return (key, label)
    return TIERS[-1][1:]


class Category(models.Model):
    name = models.CharField("nazwa", max_length=60, unique=True)
    slug = models.SlugField(unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "kategoria"
        verbose_name_plural = "kategorie"

    def __str__(self):
        return self.name


class Fruit(models.Model):
    name = models.CharField("nazwa", max_length=80, unique=True)
    slug = models.SlugField(unique=True)
    tagline = models.CharField("podtytuł", max_length=120, blank=True)
    description = models.TextField("opis", blank=True)
    categories = models.ManyToManyField(Category, blank=True, related_name="fruits", verbose_name="kategorie")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "owoc"
        verbose_name_plural = "owoce"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("fruit_detail", args=[self.slug])

    @property
    def main_image(self):
        """Pierwsze zdjęcie z galerii (korzysta z prefetch_related, jeśli jest)."""
        images = self.images.all()
        return images[0] if images else None


class FruitImage(models.Model):
    MAX_SIZE = 1200  # dłuższy bok w px – większe zdjęcia są zmniejszane przy zapisie

    fruit = models.ForeignKey(Fruit, on_delete=models.CASCADE, related_name="images", verbose_name="owoc")
    image = models.ImageField("zdjęcie", upload_to="owoce/")
    caption = models.CharField("podpis", max_length=200, blank=True)
    credit = models.CharField("autor / źródło", max_length=300, blank=True)
    order = models.PositiveSmallIntegerField("kolejność", default=0, help_text="Najniższa wartość = zdjęcie główne.")

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "zdjęcie"
        verbose_name_plural = "zdjęcia"

    def __str__(self):
        return f"{self.fruit}: {self.caption or self.image.name}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self._shrink()

    def _shrink(self):
        from PIL import Image, ImageOps

        path = self.image.path
        with Image.open(path) as img:
            if max(img.size) <= self.MAX_SIZE:
                return
            img = ImageOps.exif_transpose(img)
            img.thumbnail((self.MAX_SIZE, self.MAX_SIZE))
            img.save(path, quality=85)


class Rating(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ratings")
    fruit = models.ForeignKey(Fruit, on_delete=models.CASCADE, related_name="ratings")
    taste = models.PositiveSmallIntegerField("smak", validators=[MinValueValidator(0), MaxValueValidator(10)])
    texture = models.PositiveSmallIntegerField("tekstura", validators=[MinValueValidator(0), MaxValueValidator(10)])
    juiciness = models.PositiveSmallIntegerField("soczystość", validators=[MinValueValidator(0), MaxValueValidator(10)])
    look = models.PositiveSmallIntegerField("wygląd i aromat", validators=[MinValueValidator(0), MaxValueValidator(10)])
    score = models.PositiveSmallIntegerField("wynik (0–100)", editable=False)
    review = models.TextField("recenzja", blank=True, max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [models.UniqueConstraint(fields=["user", "fruit"], name="one_rating_per_user_per_fruit")]
        verbose_name = "ocena"
        verbose_name_plural = "oceny"

    def __str__(self):
        return f"{self.user} → {self.fruit}: {self.score}"

    def compute_score(self):
        total = sum(getattr(self, field) * weight for field, _, weight in CRITERIA)
        return round(total * 10)

    def save(self, *args, **kwargs):
        self.score = self.compute_score()
        super().save(*args, **kwargs)

    @property
    def verdict(self):
        return verdict_for(self.score)


class Comment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments")
    fruit = models.ForeignKey(Fruit, on_delete=models.CASCADE, related_name="comments")
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="replies", verbose_name="odpowiedź na"
    )
    text = models.TextField("treść", max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "komentarz"
        verbose_name_plural = "komentarze"

    def __str__(self):
        return f"{self.user} o {self.fruit}: {self.text[:40]}"
