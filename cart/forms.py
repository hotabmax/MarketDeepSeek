from django import forms
from django.core.exceptions import ValidationError


class AddToCartForm(forms.Form):
    """Форма «В корзину» с карточки товара и со страницы товара."""

    product_id = forms.IntegerField(widget=forms.HiddenInput)
    quantity = forms.IntegerField(
        min_value=1,
        initial=1,
        label="Количество",
        widget=forms.NumberInput(
            attrs={"class": "qty-input", "step": 1, "inputmode": "numeric", "aria-label": "Количество"}
        ),
    )
    next = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, product=None, **kwargs):
        self.product = product
        super().__init__(*args, **kwargs)
        if product is not None:
            self.fields["product_id"].initial = product.pk
            self.fields["quantity"].widget.attrs["max"] = product.stock
            self.fields["quantity"].widget.attrs["min"] = 1

    def clean(self):
        cleaned_data = super().clean()
        quantity = cleaned_data.get("quantity")
        if self.product is None or quantity is None:
            return cleaned_data
        if not self.product.in_stock:
            raise ValidationError("Этого товара сейчас нет в наличии.")
        if quantity > self.product.stock:
            raise ValidationError(
                f"В наличии только {self.product.stock} {self.product.stock_unit} — "
                f"уменьшите количество."
            )
        return cleaned_data


class CartItemForm(forms.Form):
    """Изменение количества одной позиции корзины или её удаление."""

    quantity = forms.IntegerField(
        min_value=0,
        label="Количество",
        widget=forms.NumberInput(
            attrs={"class": "qty-input", "step": 1, "inputmode": "numeric", "aria-label": "Количество"}
        ),
    )
    remove = forms.BooleanField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, product, **kwargs):
        self.product = product
        super().__init__(*args, **kwargs)
        self.fields["quantity"].widget.attrs["max"] = product.stock
        self.fields["quantity"].widget.attrs["min"] = 0

    def clean_quantity(self):
        quantity = self.cleaned_data["quantity"]
        if quantity > self.product.stock:
            raise ValidationError(
                f"В наличии только {self.product.stock} {self.product.stock_unit}."
            )
        return quantity
