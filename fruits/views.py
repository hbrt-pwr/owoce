import logging
from smtplib import SMTPException

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, password_validation
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Avg, Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.http import require_POST

from . import accounts
from .forms import CommentForm, RatingForm, ResendConfirmationForm, SignUpForm
from .models import CRITERIA, VERDICTS, Category, Comment, EmailConfirmation, Fruit, Rating, tier_for, verdict_for

log = logging.getLogger(__name__)


def _with_stats(qs):
    return qs.annotate(avg_score=Avg("ratings__score"), num_ratings=Count("ratings", distinct=True))


def home(request):
    fruits = _with_stats(Fruit.objects.prefetch_related("categories", "images"))

    category = None
    if slug := request.GET.get("kategoria"):
        category = get_object_or_404(Category, slug=slug)
        fruits = fruits.filter(categories=category)
    query = request.GET.get("q", "").strip()
    if query:
        fruits = fruits.filter(Q(name__icontains=query) | Q(tagline__icontains=query))

    fruits = list(fruits)
    rated = sorted((f for f in fruits if f.avg_score is not None), key=lambda f: (-f.avg_score, f.name))
    unrated = [f for f in fruits if f.avg_score is None]

    # Grupowanie w "tiery" jak na applerankings.com, z numeracją miejsc.
    tiers = []
    for position, fruit in enumerate(rated, start=1):
        fruit.position = position
        fruit.score_display = round(fruit.avg_score)
        fruit.verdict = verdict_for(fruit.score_display)
        key, label = tier_for(fruit.score_display)
        if not tiers or tiers[-1]["key"] != key:
            tiers.append({"key": key, "label": label, "fruits": []})
        tiers[-1]["fruits"].append(fruit)
    for fruit in unrated:
        fruit.position = None
        fruit.score_display = None
    if unrated:
        tiers.append({"key": "none", "label": "Jeszcze nieocenione", "fruits": unrated})

    return render(request, "fruits/home.html", {
        "tiers": tiers,
        "category": category,
        "query": query,
        "total": len(fruits),
    })


def fruit_detail(request, slug):
    fruit = get_object_or_404(_with_stats(Fruit.objects.prefetch_related("categories", "images")), slug=slug)
    ratings = fruit.ratings.select_related("user")
    criteria_avgs = ratings.aggregate(**{f: Avg(f) for f, _, _ in CRITERIA})
    criteria = [
        {"label": label, "weight": round(weight * 100), "avg": criteria_avgs[field]}
        for field, label, weight in CRITERIA
    ]

    my_rating = None
    rating_form = None
    if request.user.is_authenticated:
        my_rating = ratings.filter(user=request.user).first()
        rating_form = RatingForm(instance=my_rating)

    comments = fruit.comments.filter(parent__isnull=True).select_related("user").prefetch_related("replies__user")
    score = round(fruit.avg_score) if fruit.avg_score is not None else None

    return render(request, "fruits/detail.html", {
        "fruit": fruit,
        "score": score,
        "verdict": verdict_for(score),
        "criteria": criteria,
        "ratings": ratings,
        "my_rating": my_rating,
        "rating_form": rating_form,
        "comments": comments,
        "comment_form": CommentForm(),
    })


@login_required
@require_POST
def rate(request, slug):
    fruit = get_object_or_404(Fruit, slug=slug)
    existing = Rating.objects.filter(user=request.user, fruit=fruit).first()
    form = RatingForm(request.POST, instance=existing)
    if form.is_valid():
        rating = form.save(commit=False)
        rating.user = request.user
        rating.fruit = fruit
        rating.save()
        messages.success(request, f"Zapisano Twoją ocenę: {rating.score}/100 ({rating.verdict}).")
    else:
        messages.error(request, "Ocena niepoprawna – każde kryterium musi mieć wartość 0–10.")
    return redirect(fruit)


@login_required
@require_POST
def delete_rating(request, pk):
    rating = get_object_or_404(Rating, pk=pk)
    if rating.user != request.user and not request.user.is_staff:
        raise PermissionDenied
    fruit = rating.fruit
    rating.delete()
    messages.info(request, "Ocena usunięta.")
    return redirect(fruit)


@login_required
@require_POST
def add_comment(request, slug):
    fruit = get_object_or_404(Fruit, slug=slug)
    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.user = request.user
        comment.fruit = fruit
        if parent_id := form.cleaned_data.get("parent_id"):
            parent = get_object_or_404(Comment, pk=parent_id, fruit=fruit)
            # Tylko jeden poziom odpowiedzi – odpowiedź na odpowiedź trafia do wątku głównego.
            comment.parent = parent.parent or parent
        comment.save()
        messages.success(request, "Dodano komentarz.")
    else:
        messages.error(request, "Komentarz nie może być pusty.")
    return redirect(f"{fruit.get_absolute_url()}#komentarze")


@login_required
@require_POST
def delete_comment(request, pk):
    comment = get_object_or_404(Comment, pk=pk)
    if comment.user != request.user and not request.user.is_staff:
        raise PermissionDenied
    fruit = comment.fruit
    comment.delete()
    messages.info(request, "Komentarz usunięty.")
    return redirect(f"{fruit.get_absolute_url()}#komentarze")


def signup(request):
    """Rejestracja: konto powstaje nieaktywne, aktywuje je dopiero link z e-maila (fruits/accounts.py)."""
    if request.user.is_authenticated:
        return redirect("home")
    if request.method == "POST":
        accounts.purge_expired()  # zwalnia nazwy i adresy z niepotwierdzonych kont, którym wygasł link
    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():  # bez wysłanego maila nie zostawiamy martwego konta
                user = form.save()
                accounts.start_confirmation(user)
                accounts.send_confirmation_email(request, user)
        except (SMTPException, OSError):
            log.exception("Nie udało się wysłać e-maila potwierdzającego rejestrację")
            messages.error(request, "Nie udało się wysłać e-maila z linkiem potwierdzającym. Spróbuj za kilka minut.")
        else:
            request.session["signup_email"] = user.email
            return redirect("signup_done")
    return render(request, "registration/signup.html", {"form": form})


def signup_done(request):
    return render(request, "registration/signup_done.html", {
        "email": request.session.get("signup_email"),
        "hours": settings.ACCOUNT_CONFIRMATION_TIMEOUT // 3600,
    })


def resend_confirmation(request):
    """Ponowne wysłanie linku. Odpowiedź zawsze ta sama – nie zdradza, czy adres jest w bazie."""
    form = ResendConfirmationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        accounts.purge_expired()
        user = accounts.pending_users().filter(email__iexact=form.cleaned_data["email"]).first()
        if user is not None:
            try:
                accounts.send_confirmation_email(request, user)
            except (SMTPException, OSError):
                log.exception("Nie udało się ponownie wysłać e-maila potwierdzającego")
                messages.error(request, "Nie udało się wysłać e-maila. Spróbuj za kilka minut.")
                return render(request, "registration/resend_confirmation.html", {"form": form})
        messages.info(request, "Jeśli na ten adres czeka niepotwierdzone konto, wysłaliśmy na niego nowy link.")
        request.session["signup_email"] = form.cleaned_data["email"]
        return redirect("signup_done")
    return render(request, "registration/resend_confirmation.html", {"form": form})


def confirm_email(request, uidb64, token):
    """Link z e-maila. GET pokazuje tylko przycisk – skanery linków w poczcie (otwierające adresy
    automatycznie) nie aktywują konta. Konto aktywuje dopiero POST po kliknięciu przycisku."""
    try:
        user = accounts.pending_users().get(pk=force_str(urlsafe_base64_decode(uidb64)))
    except (ValueError, OverflowError, User.DoesNotExist):
        user = None
    valid = user is not None and accounts.confirmation_token.check_token(user, token)
    if not valid:
        return render(request, "registration/confirm_email.html", {"valid": False})
    if request.method == "POST":
        user.is_active = True
        user.save(update_fields=["is_active"])
        EmailConfirmation.objects.filter(user=user).delete()
        request.session.pop("signup_email", None)
        login(request, user)
        messages.success(request, f"Witaj, {user.username}! Adres e-mail potwierdzony, konto aktywne.")
        return redirect("home")
    return render(request, "registration/confirm_email.html", {"valid": True, "confirm_user": user})


@require_POST
def password_check(request):
    """Które wymogi hasła są spełnione – dla listy odhaczanej na żywo przy rejestracji i resecie hasła.

    POST (hasło nie trafia do adresu ani logów), chroniony CSRF jak każdy formularz.
    Zwraca {"ok": [true/false, ...]} w kolejności AUTH_PASSWORD_VALIDATORS.
    """
    password = request.POST.get("password", "")
    user = User(username=request.POST.get("username", ""), email=request.POST.get("email", ""))
    ok = []
    for validator in password_validation.get_default_password_validators():
        try:
            validator.validate(password, user)
        except ValidationError:
            ok.append(False)
        else:
            ok.append(True)
    return JsonResponse({"ok": ok})


def profile(request, username):
    profile_user = get_object_or_404(User, username=username)
    ratings = profile_user.ratings.select_related("fruit").prefetch_related("fruit__images").order_by("-score")
    return render(request, "fruits/profile.html", {
        "profile_user": profile_user,
        "ratings": ratings,
        "num_comments": profile_user.comments.count(),
    })


def how_we_rate(request):
    criteria = [{"label": label, "weight": round(weight * 100)} for _, label, weight in CRITERIA]
    return render(request, "fruits/how.html", {"criteria": criteria, "verdicts": VERDICTS})
