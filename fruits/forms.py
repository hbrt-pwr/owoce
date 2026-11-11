from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Comment, Rating

SCORE_CHOICES = [(i, str(i)) for i in range(10, -1, -1)]


class SignUpForm(UserCreationForm):
    # Wymagany i unikalny – na ten adres przychodzi link do resetu hasła („Nie pamiętasz hasła?”).
    email = forms.EmailField(label="E-mail")

    class Meta:
        model = User
        fields = ("username", "email")

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Konto z tym adresem e-mail już istnieje.")
        return email


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
