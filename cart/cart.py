"""Корзина покупателя, хранящаяся в сессии."""

from decimal import Decimal

from django.conf import settings

from catalog.models import Product

CART_SESSION_KEY = "cart"


class Cart:
    """Простая корзина: {product_id: {"quantity": int}} в сессии."""

    def __init__(self, request):
        self.session = request.session
        cart = self.session.get(CART_SESSION_KEY)
        if not isinstance(cart, dict):
            cart = {}
        self.cart = cart

    # --- содержание -----------------------------------------------------
    def __len__(self):
        """Общее количество единиц товара в корзине."""
        return sum(item["quantity"] for item in self.cart.values())

    def __iter__(self):
        """Итерирует позиции корзины с текущими ценами из каталога."""
        products = Product.objects.filter(pk__in=self.cart.keys()).with_category()
        for product in products:
            item = self.cart[str(product.pk)]
            yield {
                "product": product,
                "quantity": item["quantity"],
                "price": product.price,
                "total_price": product.price * item["quantity"],
            }

    def __contains__(self, product):
        return str(product.pk) in self.cart

    @property
    def is_empty(self):
        return not self.cart

    @property
    def positions_count(self):
        """Количество разных товаров в корзине."""
        return len(self.cart)

    # --- изменение ------------------------------------------------------
    def add(self, product, quantity=1, update_quantity=False):
        """Добавляет товар или меняет количество, не превышая остаток."""
        if quantity <= 0:
            if update_quantity:
                self.remove(product)
            return
        key = str(product.pk)
        item = self.cart.setdefault(key, {"quantity": 0})
        item["quantity"] = quantity if update_quantity else item["quantity"] + quantity
        item["quantity"] = min(item["quantity"], product.stock)
        if item["quantity"] <= 0:
            self.cart.pop(key, None)
        self.save()

    def remove(self, product):
        self.remove_id(product.pk)

    def remove_id(self, product_id):
        if str(product_id) in self.cart:
            del self.cart[str(product_id)]
            self.save()

    def clear(self):
        self.session[CART_SESSION_KEY] = {}
        self.session.modified = True
        self.cart = {}

    def prune(self):
        """Убирает товары, которых больше нет в продаже. Возвращает число удалённых."""
        if not self.cart:
            return 0
        available = {
            str(pk)
            for pk in Product.objects.available()
            .filter(pk__in=self.cart.keys())
            .values_list("pk", flat=True)
        }
        removed = [key for key in self.cart if key not in available]
        for key in removed:
            del self.cart[key]
        if removed:
            self.save()
        return len(removed)

    def save(self):
        self.session[CART_SESSION_KEY] = self.cart
        self.session.modified = True

    # --- суммы ----------------------------------------------------------
    def get_subtotal(self):
        return sum((item["total_price"] for item in self), Decimal("0.00"))

    def get_delivery_price(self):
        if self.get_subtotal() >= settings.FREE_DELIVERY_FROM:
            return Decimal("0.00")
        return settings.DELIVERY_PRICE

    def get_total(self):
        return self.get_subtotal() + self.get_delivery_price()

    def amount_to_free_delivery(self):
        remaining = settings.FREE_DELIVERY_FROM - self.get_subtotal()
        return max(remaining, Decimal("0.00"))
