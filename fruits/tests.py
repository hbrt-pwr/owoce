import io
import os
import subprocess
import sys
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import Comment, Fruit, FruitImage, Rating

PW = "Owocowe-Haslo-123"
SCORES = {"taste": 9, "texture": 8, "juiciness": 7, "look": 6, "review": "Pyszne"}


class FruitSiteTests(TestCase):
    def setUp(self):
        self.fruit = Fruit.objects.get(slug="jablko")  # z migracji 0002
        self.alice = User.objects.create_user("alice", password=PW)
        self.bob = User.objects.create_user("bob", password=PW)
        self.admin = User.objects.create_user("szef", password=PW, is_staff=True)

    def test_seed_has_fruits_but_no_ratings(self):
        self.assertGreater(Fruit.objects.count(), 20)
        self.assertEqual(Rating.objects.count(), 0)
        self.assertEqual(Comment.objects.count(), 0)

    def test_pages_render(self):
        for url in [reverse("home"), reverse("how_we_rate"), self.fruit.get_absolute_url(),
                    reverse("login"), reverse("signup"), reverse("profile", args=["alice"])]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.assertContains(self.client.get(reverse("home") + "?kategoria=cytrusowe"), "Cytryna")

    def test_signup_logs_in(self):
        r = self.client.post(reverse("signup"), {"username": "nowy", "email": "nowy@example.com",
                                                 "password1": PW, "password2": PW})
        self.assertRedirects(r, reverse("home"))
        self.assertContains(self.client.get(reverse("home")), "Wyloguj")

    def test_site_name_is_owocownik(self):
        html = self.client.get(reverse("home")).content.decode()
        self.assertIn("<title>Ranking – Owocownik</title>", html)
        self.assertNotIn("FruitRankings", html)
        self.assertNotIn("wersja lokalna", html)


    def test_anonymous_cannot_rate_or_comment(self):
        r = self.client.post(reverse("rate", args=["jablko"]), SCORES)
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse("login"), r["Location"])
        self.client.post(reverse("add_comment", args=["jablko"]), {"text": "hej"})
        self.assertEqual(Rating.objects.count() + Comment.objects.count(), 0)

    def test_rating_score_and_single_rating_per_user(self):
        self.client.login(username="alice", password=PW)
        self.client.post(reverse("rate", args=["jablko"]), SCORES)
        rating = Rating.objects.get()
        # 9*0.4 + 8*0.25 + 7*0.2 + 6*0.15 = 7.9 -> 79
        self.assertEqual(rating.score, 79)
        self.client.post(reverse("rate", args=["jablko"]), {**SCORES, "taste": 10})
        self.assertEqual(Rating.objects.count(), 1)
        self.assertEqual(Rating.objects.get().score, 83)

    def test_invalid_rating_rejected(self):
        self.client.login(username="alice", password=PW)
        self.client.post(reverse("rate", args=["jablko"]), {**SCORES, "taste": 11})
        self.assertEqual(Rating.objects.count(), 0)

    def test_ranking_orders_by_average(self):
        banan = Fruit.objects.get(slug="banan")
        Rating.objects.create(user=self.alice, fruit=self.fruit, taste=2, texture=2, juiciness=2, look=2)
        Rating.objects.create(user=self.alice, fruit=banan, taste=10, texture=9, juiciness=9, look=9)
        Rating.objects.create(user=self.bob, fruit=banan, taste=8, texture=8, juiciness=8, look=8)
        html = self.client.get(reverse("home")).content.decode()
        self.assertLess(html.index("Banan"), html.index("Jabłko"))
        self.assertIn("Najlepsze owoce", html)
        self.assertIn("Owocowe piekło", html)
        self.assertIn("2 oceny", html)

    def test_comments_replies_and_permissions(self):
        self.client.login(username="alice", password=PW)
        self.client.post(reverse("add_comment", args=["jablko"]), {"text": "Moje ulubione"})
        parent = Comment.objects.get()
        self.client.login(username="bob", password=PW)
        self.client.post(reverse("add_comment", args=["jablko"]), {"text": "Zgadzam się", "parent_id": parent.pk})
        reply = Comment.objects.get(parent=parent)
        self.assertContains(self.client.get(self.fruit.get_absolute_url()), "Zgadzam się")

        # bob nie może usunąć komentarza alice
        r = self.client.post(reverse("delete_comment", args=[parent.pk]))
        self.assertEqual(r.status_code, 403)
        # ale może usunąć swój
        self.client.post(reverse("delete_comment", args=[reply.pk]))
        self.assertFalse(Comment.objects.filter(pk=reply.pk).exists())
        # admin może usunąć cudzy
        self.client.login(username="szef", password=PW)
        self.client.post(reverse("delete_comment", args=[parent.pk]))
        self.assertEqual(Comment.objects.count(), 0)

    def test_admin_can_moderate_ratings(self):
        rating = Rating.objects.create(user=self.alice, fruit=self.fruit, taste=5, texture=5, juiciness=5, look=5)
        self.client.login(username="bob", password=PW)
        self.assertEqual(self.client.post(reverse("delete_rating", args=[rating.pk])).status_code, 403)
        self.client.login(username="szef", password=PW)
        self.client.post(reverse("delete_rating", args=[rating.pk]))
        self.assertEqual(Rating.objects.count(), 0)

    def test_placeholder_without_photos_and_gallery_with_photos(self):
        self.assertContains(self.client.get(self.fruit.get_absolute_url()), "placeholder.svg")
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            buf = io.BytesIO()
            Image.new("RGB", (3000, 1500), "red").save(buf, "JPEG")
            img = FruitImage.objects.create(
                fruit=self.fruit, caption="Testowe", image=SimpleUploadedFile("t.jpg", buf.getvalue(), "image/jpeg")
            )
            # duże zdjęcie zmniejszone do 1200 px dłuższego boku
            with Image.open(img.image.path) as saved:
                self.assertEqual(saved.size, (1200, 600))
            html = self.client.get(self.fruit.get_absolute_url()).content.decode()
            self.assertIn(img.image.url, html)
            self.assertIn("Testowe", html)
            self.assertIn(img.image.url, self.client.get(reverse("home")).content.decode())

    def test_logout_requires_post_and_ends_session(self):
        self.client.login(username="alice", password=PW)
        self.client.post(reverse("logout"))
        self.assertNotContains(self.client.get(reverse("home")), "Wyloguj")


class AccountTests(TestCase):
    """Rejestracja z wymogami hasła na żywo i „Nie pamiętasz hasła?”."""

    def test_signup_requires_unique_email(self):
        User.objects.create_user("ala", email="Ala@example.com", password=PW)
        data = {"username": "nowy", "password1": PW, "password2": PW}
        self.assertFormError(self.client.post(reverse("signup"), data).context["form"], "email", "To pole jest wymagane.")
        r = self.client.post(reverse("signup"), {**data, "email": "ala@EXAMPLE.com"})
        self.assertFormError(r.context["form"], "email", "Konto z tym adresem e-mail już istnieje.")
        self.assertFalse(User.objects.filter(username="nowy").exists())

    def test_signup_page_lists_password_rules(self):
        html = self.client.get(reverse("signup")).content.decode()
        self.assertIn('class="pw-rules"', html)
        self.assertIn("co najmniej 10 znaków", html)
        self.assertIn("co najmniej jedną wielką literę", html)
        self.assertIn("co najmniej jeden znak specjalny", html)
        self.assertIn("password-rules.js", html)

    def test_password_check_reports_unmet_rules(self):
        url = reverse("password_check")

        def check(pw):
            return self.client.post(url, {"password": pw}).json()["ok"]

        # kolejność jak w AUTH_PASSWORD_VALIDATORS: długość ≥ 10, wielka, mała, cyfra, znak specjalny
        self.assertEqual(check("abc"), [False, False, True, False, False])
        self.assertEqual(check("abcdefghij"), [True, False, True, False, False])
        self.assertEqual(check("ABCDEFGHIJ1"), [True, True, False, True, False])
        self.assertEqual(check("Abcdefghi1"), [True, True, True, True, False])
        self.assertEqual(check("Żółć-gęśla1"), [True, True, True, True, True])  # polskie litery też się liczą
        self.assertEqual(check("Abc defgh1"), [True, True, True, True, False])  # spacja to nie znak specjalny
        self.assertEqual(check(PW), [True, True, True, True, True])
        self.assertEqual(self.client.get(url).status_code, 405)  # hasło tylko w treści POST

    def test_signup_enforces_password_policy(self):
        data = {"username": "nowy", "email": "nowy@example.com"}
        for weak in ["Krotkie1!", "bezwielkich1!", "BEZMALYCH1!", "BezCyfr!!!!", "BezSymbolu12"]:
            r = self.client.post(reverse("signup"), {**data, "password1": weak, "password2": weak})
            self.assertEqual(r.status_code, 200, weak)
            self.assertTrue(r.context["form"].errors["password2"], weak)
        self.assertFalse(User.objects.filter(username="nowy").exists())
        # podobieństwo do nazwy użytkownika i „popularne hasła” nie są już sprawdzane
        ok = "Nowy-nowy-1"
        r = self.client.post(reverse("signup"), {**data, "password1": ok, "password2": ok})
        self.assertRedirects(r, reverse("home"))

    def test_password_check_requires_csrf(self):
        client = self.client_class(enforce_csrf_checks=True)
        self.assertEqual(client.post(reverse("password_check"), {"password": "x"}).status_code, 403)

    def test_login_page_links_to_password_reset(self):
        self.assertContains(self.client.get(reverse("login")), reverse("password_reset"))

    def test_password_reset_flow(self):
        from django.core import mail

        User.objects.create_user("ala", email="ala@example.com", password=PW)
        r = self.client.post(reverse("password_reset"), {"email": "ala@example.com"})
        self.assertRedirects(r, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.subject, "Owocownik – ustawienie nowego hasła")
        self.assertEqual(msg.to, ["ala@example.com"])
        link = next(line for line in msg.body.splitlines() if "/konto/reset/" in line).strip()
        self.assertTrue(link.startswith("http://testserver/konto/reset/"))

        r = self.client.get(link, follow=True)  # Django przekierowuje na adres z „set-password” zamiast tokenu
        self.assertContains(r, "Ustaw nowe hasło")
        self.assertContains(r, 'class="pw-rules"')
        new_pw = "Nowe-Owocowe-Haslo-456"
        r = self.client.post(r.redirect_chain[-1][0], {"new_password1": new_pw, "new_password2": new_pw})
        self.assertRedirects(r, reverse("password_reset_complete"))
        self.assertTrue(self.client.login(username="ala", password=new_pw))

    def test_password_reset_unknown_email_sends_nothing_but_looks_the_same(self):
        from django.core import mail

        r = self.client.post(reverse("password_reset"), {"email": "nikt@example.com"})
        self.assertRedirects(r, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)

    def test_password_reset_link_expires_after_one_hour(self):
        from datetime import datetime, timedelta
        from unittest import mock

        from django.contrib.auth.tokens import PasswordResetTokenGenerator, default_token_generator

        user = User.objects.create_user("ala", email="ala@example.com", password=PW)
        start = datetime(2026, 11, 11, 12, 0, 0)
        with mock.patch.object(PasswordResetTokenGenerator, "_now", return_value=start):
            token = default_token_generator.make_token(user)
        for minutes, valid in [(59, True), (61, False)]:
            with mock.patch.object(PasswordResetTokenGenerator, "_now", return_value=start + timedelta(minutes=minutes)):
                self.assertEqual(default_token_generator.check_token(user, token), valid, minutes)


class RateLimitTests(TestCase):
    """Ochrona przed celowym spamowaniem żądaniami (fruits/ratelimit.py)."""

    def setUp(self):
        from django.core.cache import caches

        caches["default"].clear()
        caches["ratelimit"].clear()

    def test_global_limit_per_ip(self):
        from unittest import mock

        from . import ratelimit

        with mock.patch.object(ratelimit, "GLOBAL_LIMIT", (5, 60)):
            for _ in range(5):
                self.assertEqual(self.client.get(reverse("how_we_rate")).status_code, 200)
            r = self.client.get(reverse("how_we_rate"))
            self.assertEqual(r.status_code, 429)
            self.assertIn("Za dużo żądań", r.content.decode())
            self.assertTrue(1 <= int(r["Retry-After"]) <= 60)
            # inny adres IP ma własny licznik
            self.assertEqual(self.client.get(reverse("how_we_rate"), REMOTE_ADDR="10.9.8.7").status_code, 200)
            # sonda load balancera nigdy nie jest blokowana
            self.assertEqual(self.client.get("/healthz/").status_code, 200)

    def test_login_attempts_limited_per_username(self):
        User.objects.create_user("ala", email="ala@example.com", password=PW)
        for _ in range(10):
            r = self.client.post(reverse("login"), {"username": "ala", "password": "zle-haslo"})
            self.assertEqual(r.status_code, 200)
        r = self.client.post(reverse("login"), {"username": "ala", "password": PW})
        self.assertEqual(r.status_code, 429)  # nawet dobre hasło – trzeba odczekać
        self.assertNotIn("_auth_user_id", self.client.session)
        # inny login z tego samego IP nadal działa (limit na IP jest wyższy)
        User.objects.create_user("ola", password=PW)
        self.assertEqual(self.client.post(reverse("login"), {"username": "ola", "password": PW}).status_code, 302)

    def test_password_reset_mails_limited_per_address(self):
        from django.core import mail

        User.objects.create_user("ala", email="ala@example.com", password=PW)
        for _ in range(3):
            self.client.post(reverse("password_reset"), {"email": "ala@example.com"})
        r = self.client.post(reverse("password_reset"), {"email": "ALA@example.com"})
        self.assertEqual(r.status_code, 429)
        self.assertEqual(len(mail.outbox), 3)

    def test_password_check_returns_json_429(self):
        from unittest import mock

        from . import ratelimit

        with mock.patch.dict(ratelimit.POST_LIMITS, {"password_check": [(2, 60, "ip")]}):
            for _ in range(2):
                self.assertEqual(self.client.post(reverse("password_check"), {"password": "x"}).status_code, 200)
            r = self.client.post(reverse("password_check"), {"password": "x"})
            self.assertEqual(r.status_code, 429)
            self.assertEqual(r.json(), {"error": "too_many_requests"})

    def test_client_ip_uses_last_forwarded_for_entry(self):
        from django.test import RequestFactory

        from .ratelimit import client_ip

        req = RequestFactory().get("/", HTTP_X_FORWARDED_FOR="1.2.3.4, 203.0.113.9", REMOTE_ADDR="10.0.0.5")
        with override_settings(RATELIMIT_USE_X_FORWARDED_FOR=True):
            self.assertEqual(client_ip(req), "203.0.113.9")  # pierwszy wpis mógł podrobić klient
        with override_settings(RATELIMIT_USE_X_FORWARDED_FOR=False):
            self.assertEqual(client_ip(req), "10.0.0.5")

    def test_broken_cache_does_not_block_site(self):
        from unittest import mock

        from django.core.cache.backends.db import DatabaseCache
        from django.core.cache.backends.locmem import LocMemCache

        with mock.patch.object(LocMemCache, "add", side_effect=RuntimeError("cache padł")), \
                mock.patch.object(DatabaseCache, "add", side_effect=RuntimeError("cache padł")), \
                self.assertLogs("fruits.ratelimit", "ERROR"):
            self.assertEqual(self.client.get(reverse("home")).status_code, 200)
            self.assertEqual(self.client.post(reverse("password_check"), {"password": "x"}).status_code, 200)


class CloudReadinessTests(TestCase):
    """Elementy potrzebne do działania za load balancerem (L3)."""

    def test_health_check_ok_even_for_unknown_host(self):
        # sonda load balancera przychodzi na prywatny IP instancji, spoza ALLOWED_HOSTS
        r = self.client.get("/healthz/", HTTP_HOST="10.0.1.4")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"status": "ok", "db": True})

    def test_other_pages_still_check_host(self):
        self.assertEqual(self.client.get("/", HTTP_HOST="zly-host.example").status_code, 400)

    def test_https_from_load_balancer_header(self):
        # TLS kończy się na load balancerze; aplikacja wie o HTTPS z nagłówka X-Forwarded-Proto
        with override_settings(SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https")):
            r = self.client.get(reverse("home"), HTTP_X_FORWARDED_PROTO="https")
            self.assertTrue(r.wsgi_request.is_secure())

    def test_blob_storage_uses_managed_identity_without_key(self):
        # w Azure Container Apps zdjęcia zapisujemy tożsamością zarządzaną, bez klucza Storage
        env = {**os.environ, "AZURE_ACCOUNT_NAME": "owocetest", "DJANGO_SETTINGS_MODULE": "config.settings"}
        env.pop("AZURE_ACCOUNT_KEY", None)
        code = (
            "from django.conf import settings as s; o = s.STORAGES['default']['OPTIONS']; "
            "print(s.STORAGES['default']['BACKEND'], 'account_key' in o, type(o['token_credential']).__name__)"
        )
        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        out = subprocess.run([sys.executable, "-c", code], env=env, cwd=project_dir, capture_output=True, text=True, check=True)
        self.assertEqual(out.stdout.split(), ["storages.backends.azure_storage.AzureStorage", "False", "DefaultAzureCredential"])

    def test_small_photo_is_not_reencoded(self):
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            buf = io.BytesIO()
            Image.new("RGB", (400, 300), "green").save(buf, "PNG")
            img = FruitImage.objects.create(
                fruit=Fruit.objects.get(slug="jablko"), image=SimpleUploadedFile("m.png", buf.getvalue(), "image/png")
            )
            with open(img.image.path, "rb") as fh:
                self.assertEqual(fh.read(), buf.getvalue())
