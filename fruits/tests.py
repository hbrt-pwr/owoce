import io
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
        r = self.client.post(reverse("signup"), {"username": "nowy", "password1": PW, "password2": PW})
        self.assertRedirects(r, reverse("home"))
        self.assertContains(self.client.get(reverse("home")), "Wyloguj")

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
