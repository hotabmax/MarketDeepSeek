from django import template
from decimal import Decimal, InvalidOperation

register = template.Library()

NBSP = "\u00a0"


@register.filter
def money(value):
    """Форматирует сумму в рублях: 1234.5 -> '1 234,50 ₽'."""
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return value
    formatted = f"{amount:,.2f}".replace(",", NBSP).replace(".", ",")
    if formatted.endswith(",00"):
        formatted = formatted[:-3]
    return f"{formatted}{NBSP}₽"


@register.filter
def plural_ru(value, forms="товар,товара,товаров"):
    """Склоняет слово по числу: 5|plural_ru:'товар,товара,товаров' -> 'товаров'."""
    try:
        number = abs(int(value))
    except (TypeError, ValueError):
        return forms
    one, few, many = (forms.split(",") + ["", "", ""])[:3]
    if number % 10 == 1 and number % 100 != 11:
        word = one
    elif 2 <= number % 10 <= 4 and not 12 <= number % 100 <= 14:
        word = few
    else:
        word = many
    return word
