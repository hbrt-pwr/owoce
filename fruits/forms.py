from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Comment, Rating

SCORE_CHOICES = [(i, str(i)) for i in range(10, -1, -1)]


class SignUpForm(UserCreationForm):
    email = forms.EmailField(label="E-mail", required=False)

    class Meta:
        model = User
        fields = ("username", "email")


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
