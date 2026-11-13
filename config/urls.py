from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.views import LoginView
from django.urls import include, path

from fruits.forms import LoginForm

admin.site.site_header = "Owocownik – panel administratora"
admin.site.site_title = "Owocownik – admin"

urlpatterns = [
    path("admin/", admin.site.urls),
    # logowanie z komunikatem „konto niepotwierdzone” – przed resztą widoków konta z Django
    path("konto/login/", LoginView.as_view(authentication_form=LoginForm), name="login"),
    path("konto/", include("django.contrib.auth.urls")),
    path("", include("fruits.urls")),
]

# Lokalnie Django samo serwuje wgrane zdjęcia (działa tylko przy DEBUG=True).
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
