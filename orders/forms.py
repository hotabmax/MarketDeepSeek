from django import forms
from django.core.exceptions import ValidationError

from .models import DeliverySlot, Order
from .utils import normalize_phone, phones_match


class CheckoutForm(forms.Form):
    """Данные покупателя и способ получения заказа."""

    customer_name = forms.CharField(
        label="Имя и фамилия",
        max_length=120,
        widget=forms.TextInput(
            attrs={"placeholder": "Анна Смирнова", "autocomplete": "name", "class": "input"}
        ),
    )
    phone = forms.CharField(
        label="Телефон",
        max_length=32,
        widget=forms.TextInput(
            attrs={
                "placeholder": "+7 (999) 123-45-67",
                "autocomplete": "tel",
                "inputmode": "tel",
                "class": "input",
            }
        ),
    )
    email = forms.EmailField(
        label="E-mail для чека",
        required=False,
        widget=forms.EmailInput(
            attrs={"placeholder": "anna@example.com", "autocomplete": "email", "class": "input"}
        ),
    )
    delivery_method = forms.ChoiceField(
        label="Способ получения",
        choices=Order.DeliveryMethod.choices,
        initial=Order.DeliveryMethod.COURIER,
        widget=forms.RadioSelect,
    )
    address = forms.CharField(
        label="Адрес доставки",
        required=False,
        max_length=255,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Самара, ул. Ленинградская, 1, кв. 5",
                "autocomplete": "street-address",
                "class": "input",
            }
        ),
    )
    delivery_slot = forms.ChoiceField(
        label="Желаемое время",
        choices=DeliverySlot.choices,
        initial=DeliverySlot.ASAP,
        widget=forms.Select(attrs={"class": "input"}),
    )
    payment_method = forms.ChoiceField(
        label="Способ оплаты",
        choices=Order.PaymentMethod.choices,
        initial=Order.PaymentMethod.CASH,
        widget=forms.RadioSelect,
    )
    comment = forms.CharField(
        label="Комментарий к заказу",
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "Код домофона, пожелания по доставке…",
                "class": "input",
            }
        ),
    )
    agree = forms.BooleanField(
        label="Согласен с обработкой персональных данных",
        error_messages={"required": "Без согласия на обработку данных оформить заказ нельзя."},
    )

    def clean_phone(self):
        return normalize_phone(self.cleaned_data["phone"])

    def clean(self):
        cleaned_data = super().clean()
        if (
            cleaned_data.get("delivery_method") == Order.DeliveryMethod.COURIER
            and not (cleaned_data.get("address") or "").strip()
        ):
            self.add_error("address", "Для доставки курьером нужен адрес.")
        return cleaned_data


class TrackOrderForm(forms.Form):
    """Поиск заказа по номеру и телефону покупателя."""

    number = forms.CharField(
        label="Номер заказа",
        max_length=24,
        widget=forms.TextInput(
            attrs={
                "placeholder": "FM-20261020-A7K2Q",
                "autocomplete": "off",
                "autocapitalize": "characters",
                "class": "input",
            }
        ),
    )
    phone = forms.CharField(
        label="Телефон",
        max_length=32,
        widget=forms.TextInput(
            attrs={
                "placeholder": "+7 (999) 123-45-67",
                "autocomplete": "tel",
                "inputmode": "tel",
                "class": "input",
            }
        ),
        help_text="Тот же номер, что указывали при оформлении заказа.",
    )

    def clean_number(self):
        return self.cleaned_data["number"].strip().upper()

    def clean(self):
        cleaned_data = super().clean()
        number = cleaned_data.get("number")
        phone = cleaned_data.get("phone")
        if not number or not phone:
            return cleaned_data

        order = Order.objects.filter(number__iexact=number).first()
        if order is None or not phones_match(order.phone, phone):
            raise ValidationError(
                "Заказ с таким номером и телефоном не найден. Проверьте данные."
            )
        cleaned_data["order"] = order
        return cleaned_data
