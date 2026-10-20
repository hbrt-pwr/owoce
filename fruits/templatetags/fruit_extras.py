from django import template

register = template.Library()


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
