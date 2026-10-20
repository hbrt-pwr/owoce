from django.contrib import admin
from django.templatetags.static import static
from django.utils.html import format_html

from .models import Category, Comment, Fruit, FruitImage, Rating


def _thumb(url, size=60):
    return format_html('<img src="{}" style="width:{}px;height:{}px;object-fit:cover;border-radius:4px">', url, size, size)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


class FruitImageInline(admin.TabularInline):
    model = FruitImage
    extra = 1
    fields = ("preview", "image", "caption", "credit", "order")
    readonly_fields = ("preview",)

    @admin.display(description="podgląd")
    def preview(self, obj):
        return _thumb(obj.image.url) if obj.pk and obj.image else "—"


@admin.register(Fruit)
class FruitAdmin(admin.ModelAdmin):
    list_display = ("thumbnail", "name", "tagline", "num_images", "created_at")
    list_display_links = ("thumbnail", "name")
    list_filter = ("categories",)
    search_fields = ("name", "tagline")
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = ("categories",)
    inlines = [FruitImageInline]

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("images")

    @admin.display(description="zdjęcie")
    def thumbnail(self, obj):
        img = obj.main_image
        return _thumb(img.image.url if img else static("placeholder.svg"), 40)

    @admin.display(description="liczba zdjęć")
    def num_images(self, obj):
        return len(obj.images.all())


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ("fruit", "user", "score", "taste", "texture", "juiciness", "look", "updated_at")
    list_filter = ("fruit",)
    search_fields = ("user__username", "fruit__name", "review")
    readonly_fields = ("score",)


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("fruit", "user", "short_text", "parent", "created_at")
    list_filter = ("fruit",)
    search_fields = ("user__username", "text")

    @admin.display(description="treść")
    def short_text(self, obj):
        return obj.text[:60]
