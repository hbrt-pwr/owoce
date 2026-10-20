from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "FruitRankings – panel administratora"
admin.site.site_title = "FruitRankings admin"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("konto/", include("django.contrib.auth.urls")),
    path("", include("fruits.urls")),
]

# Lokalnie Django samo serwuje wgrane zdjęcia (działa tylko przy DEBUG=True).
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
