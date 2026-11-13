from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User

from .models import Comment, Rating

SCORE_CHOICES = [(i, str(i)) for i in range(10, -1, -1)]


class SignUpForm(UserCreationForm):
    # Wymagany i unikalny – na ten adres przychodzi link potwierdzający konto i link do resetu hasła.
    email = forms.EmailField(label="E-mail")

    class Meta:
        model = User
        fields = ("username", "email")

    def clean_email(self):
        email = self.cleaned_data["email"]
        existing = User.objects.filter(email__iexact=email).first()
        if existing is not None:
            if not existing.is_active and hasattr(existing, "email_confirmation"):
                raise forms.ValidationError(
                    "Na ten adres wysłaliśmy już link potwierdzający – sprawdź skrzynkę (także spam) "
                    "albo wyślij link ponownie.", code="pending")
            raise forms.ValidationError("Konto z tym adresem e-mail już istnieje.")
        return email


class LoginForm(AuthenticationForm):
    """Logowanie z czytelnym komunikatem dla konta, które jeszcze nie potwierdziło e-maila.

    Komunikat pojawia się tylko przy poprawnym haśle – nie zdradza, czy dana nazwa istnieje.
    """
    unconfirmed = False

    def clean(self):
        try:
            return super().clean()
        except forms.ValidationError:
            username, password = self.cleaned_data.get("username"), self.cleaned_data.get("password")
            user = User.objects.filter(username=username, is_active=False, email_confirmation__isnull=False).first()
            if user is not None and password and user.check_password(password):
                self.unconfirmed = True
                raise forms.ValidationError("Konto nie jest jeszcze potwierdzone.", code="unconfirmed")
            raise


class ResendConfirmationForm(forms.Form):
    email = forms.EmailField(label="E-mail")


class RatingForm(forms.ModelForm):
    class Meta:
        model = Rating
        fields = ("taste", "texture", "juiciness", "look", "review")
        widgets = {
            "taste": forms.Select(choices=SCORE_CHOICES),
            "texture": forms.Select(choices=SCORE_CHOICES),
            "juiciness": forms.Select(choices=SCORE_CHOICES),
            "look": forms.Select(choices=SCORE_CHOICES),
            "review": forms.Textarea(attrs={"rows": 3, "placeholder": "Krótka recenzja (opcjonalnie)"}),
        }


class CommentForm(forms.ModelForm):
    parent_id = forms.IntegerField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = Comment
        fields = ("text",)
        labels = {"text": ""}
        widgets = {"text": forms.Textarea(attrs={"rows": 3, "placeholder": "Napisz komentarz…"})}
