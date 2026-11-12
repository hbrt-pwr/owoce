"""Walidatory haseł – polityka Owocownika (AUTH_PASSWORD_VALIDATORS w config/settings.py).

Hasło: co najmniej 10 znaków (wbudowany MinimumLengthValidator) oraz po co najmniej jednej wielkiej literze,
małej literze, cyfrze i znaku specjalnym (ten walidator, osobno dla każdej klasy znaków – dzięki temu lista
wymogów przy rejestracji odhacza każdy punkt osobno).
"""
from django.core.exceptions import ValidationError


def _is_symbol(ch):
    return not ch.isalnum() and not ch.isspace()


class CharacterClassValidator:
    KINDS = {
        "upper": (str.isupper, "co najmniej jedną wielką literę"),
        "lower": (str.islower, "co najmniej jedną małą literę"),
        "digit": (str.isdigit, "co najmniej jedną cyfrę"),
        "symbol": (_is_symbol, "co najmniej jeden znak specjalny (np. ! ? @ # - _)"),
    }

    def __init__(self, kind):
        if kind not in self.KINDS:
            raise ValueError(f"Nieznany rodzaj znaków: {kind}")
        self.kind = kind
        self.test, self.text = self.KINDS[kind]

    def validate(self, password, user=None):
        if not any(self.test(ch) for ch in password):
            raise ValidationError(f"Hasło musi zawierać {self.text}.", code=f"password_no_{self.kind}")

    def get_help_text(self):
        return f"Twoje hasło musi zawierać {self.text}."
