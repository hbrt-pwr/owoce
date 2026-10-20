from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import CommentForm, RatingForm, SignUpForm
from .models import CRITERIA, VERDICTS, Category, Comment, Fruit, Rating, tier_for, verdict_for


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
    if request.user.is_authenticated:
        return redirect("home")
    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, f"Witaj, {user.username}! Konto utworzone.")
        return redirect("home")
    return render(request, "registration/signup.html", {"form": form})


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
