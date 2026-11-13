from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("jak-oceniamy/", views.how_we_rate, name="how_we_rate"),
    path("rejestracja/", views.signup, name="signup"),
    path("rejestracja/sprawdz-haslo/", views.password_check, name="password_check"),
    path("rejestracja/sprawdz-skrzynke/", views.signup_done, name="signup_done"),
    path("rejestracja/wyslij-ponownie/", views.resend_confirmation, name="resend_confirmation"),
    path("rejestracja/potwierdz/<uidb64>/<token>/", views.confirm_email, name="confirm_email"),
    path("uzytkownik/<str:username>/", views.profile, name="profile"),
    path("owoc/<slug:slug>/", views.fruit_detail, name="fruit_detail"),
    path("owoc/<slug:slug>/ocen/", views.rate, name="rate"),
    path("owoc/<slug:slug>/komentarz/", views.add_comment, name="add_comment"),
    path("ocena/<int:pk>/usun/", views.delete_rating, name="delete_rating"),
    path("komentarz/<int:pk>/usun/", views.delete_comment, name="delete_comment"),
]
