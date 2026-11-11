from django import template
from django.contrib.auth.password_validation import password_validators_help_texts

register = template.Library()


@register.inclusion_tag("registration/_password_rules.html")
def password_rules(password_field, confirm_field, username="", email=""):
    """Lista wymogów hasła odhaczana na żywo (static/password-rules.js) – przy rejestracji i resecie hasła.

    Teksty i kolejność biorą się z AUTH_PASSWORD_VALIDATORS, tak samo jak w widoku password_check.
    """
    return {
        "rules": password_validators_help_texts(),
        "password_id": password_field.auto_id,
        "confirm_id": confirm_field.auto_id,
        "username": username,  # przy resecie hasła nie ma pól username/email – bierzemy je z konta
        "email": email,
    }


@register.filter
def pl_plural(n, forms):
    """{{ 5|pl_plural:"ocena,oceny,ocen" }} -> "5 ocen" (polska odmiana liczebników)."""
    one, few, many = forms.split(",")
    n = int(n or 0)
    if n == 1:
        word = one
    elif n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        word = few
    else:
        word = many
    return f"{n} {word}"
