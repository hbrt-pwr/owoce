"""Potwierdzanie adresu e-mail przy rejestracji.

Nowe konto powstaje nieaktywne (is_active=False) z wpisem EmailConfirmation. Na podany adres idzie link
(nadawca DEFAULT_FROM_EMAIL, czyli kontakt@owocownik.pl). Dopiero kliknięcie linku i potwierdzenie
przyciskiem aktywuje konto – kto wpisze cudzy adres, nie dostanie działającego konta.
"""
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.utils.encoding import force_bytes
from django.utils.http import base36_to_int, urlsafe_base64_encode

from .models import EmailConfirmation


class EmailConfirmationTokenGenerator(PasswordResetTokenGenerator):
    """Token jak przy resecie hasła, ale z własną solą i czasem ważności (ACCOUNT_CONFIRMATION_TIMEOUT).

    W skrócie jest is_active – po aktywacji konta link przestaje działać (jednorazowy).
    """
    key_salt = "fruits.accounts.EmailConfirmationTokenGenerator"

    def _make_hash_value(self, user, timestamp):
        return f"{user.pk}{user.password}{user.is_active}{timestamp}{user.email}"

    def check_token(self, user, token):
        if not (user and token):
            return False
        try:
            ts_b36, _ = token.split("-")
            ts = base36_to_int(ts_b36)
        except ValueError:
            return False
        if not any(constant_time_compare(self._make_token_with_timestamp(user, ts, secret), token)
                   for secret in [self.secret, *self.secret_fallbacks]):
            return False
        return (self._num_seconds(self._now()) - ts) <= settings.ACCOUNT_CONFIRMATION_TIMEOUT


confirmation_token = EmailConfirmationTokenGenerator()


def pending_users():
    """Konta czekające na potwierdzenie, którym link jeszcze nie wygasł."""
    cutoff = timezone.now() - timedelta(seconds=settings.ACCOUNT_CONFIRMATION_TIMEOUT)
    return User.objects.filter(is_active=False, email_confirmation__created_at__gte=cutoff)


def purge_expired():
    """Usuwa niepotwierdzone konta z wygasłym linkiem – zwalnia ich nazwę i adres e-mail."""
    cutoff = timezone.now() - timedelta(seconds=settings.ACCOUNT_CONFIRMATION_TIMEOUT)
    User.objects.filter(is_active=False, email_confirmation__created_at__lt=cutoff).delete()


def start_confirmation(user):
    """Oznacza nowe (jeszcze niezapisane jako aktywne) konto jako czekające na potwierdzenie."""
    user.is_active = False
    user.save(update_fields=["is_active"])
    EmailConfirmation.objects.update_or_create(user=user, defaults={"created_at": timezone.now()})


def send_confirmation_email(request, user):
    """Wysyła link potwierdzający. Wyjątek SMTP przechodzi wyżej – wywołujący decyduje, co z nim zrobić."""
    url = request.build_absolute_uri(reverse("confirm_email", kwargs={
        "uidb64": urlsafe_base64_encode(force_bytes(user.pk)),
        "token": confirmation_token.make_token(user),
    }))
    context = {"user": user, "url": url, "hours": settings.ACCOUNT_CONFIRMATION_TIMEOUT // 3600}
    subject = "".join(render_to_string("registration/confirm_email_subject.txt", context).splitlines())
    body = render_to_string("registration/confirm_email_email.txt", context)
    EmailMessage(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email]).send()
