"""Нормализация и сверка телефонных номеров покупателей."""

import re

from django.core.exceptions import ValidationError

PHONE_FORMAT_ERROR = "Укажите телефон в формате +7 (999) 123-45-67."


def phone_digits(value):
    """Оставляет только цифры номера."""
    return re.sub(r"\D", "", value or "")


def normalize_phone(raw):
    """Приводит номер к виду +7 (999) 123-45-67, не теряя международные номера."""
    digits = phone_digits(raw)
    if digits.startswith("8") and len(digits) == 11:
        digits = "7" + digits[1:]
    if not 10 <= len(digits) <= 15:
        raise ValidationError(PHONE_FORMAT_ERROR)
    if len(digits) == 11 and digits.startswith("7"):
        return f"+7 ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"
    return f"+{digits}"


def phones_match(stored, entered):
    """Сравнивает номера по последним 10 цифрам — с учётом разных форматов ввода."""
    stored_digits = phone_digits(stored)
    entered_digits = phone_digits(entered)
    if len(entered_digits) < 10 or not stored_digits:
        return False
    return stored_digits[-10:] == entered_digits[-10:]
