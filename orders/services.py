"""Бизнес-логика оформления заказа."""

from decimal import Decimal

from django.conf import settings
from django.db import transaction

from catalog.models import Product

from .models import Order, OrderItem, OrderStatusEvent


class CartValidationError(Exception):
    """Корзину нельзя оформить: товар кончился или пропал из продажи."""


def get_delivery_price(subtotal, delivery_method):
    """Стоимость доставки: самовывоз бесплатный, курьер — бесплатно от суммы."""
    if delivery_method == Order.DeliveryMethod.PICKUP:
        return Decimal("0.00")
    if subtotal >= settings.FREE_DELIVERY_FROM:
        return Decimal("0.00")
    return settings.DELIVERY_PRICE


@transaction.atomic
def create_order_from_cart(cart, data):
    """Создаёт заказ из корзины, списывает остатки и очищает корзину."""
    items = list(cart)
    if not items:
        raise CartValidationError("Корзина пуста — добавьте товары перед оформлением.")

    products = {
        product.pk: product
        for product in Product.objects.select_for_update().filter(
            pk__in=[item["product"].pk for item in items]
        )
    }

    subtotal = Decimal("0.00")
    checked_items = []
    for item in items:
        product = products.get(item["product"].pk)
        if product is None or not product.is_available:
            raise CartValidationError(
                f"«{item['product'].name}» больше не продаётся. Удалите его из корзины."
            )
        if item["quantity"] > product.stock:
            raise CartValidationError(
                f"«{product.name}»: в наличии только {product.stock} {product.stock_unit}. "
                "Уменьшите количество в корзине."
            )
        subtotal += product.price * item["quantity"]
        checked_items.append((product, item["quantity"]))

    delivery_method = data["delivery_method"]
    delivery_price = get_delivery_price(subtotal, delivery_method)

    order = Order.objects.create(
        customer_name=data["customer_name"],
        phone=data["phone"],
        email=data.get("email", ""),
        delivery_method=delivery_method,
        address=data.get("address", "") if delivery_method == Order.DeliveryMethod.COURIER else "",
        delivery_slot=data.get("delivery_slot", ""),
        payment_method=data["payment_method"],
        comment=data.get("comment", ""),
        subtotal=subtotal,
        delivery_price=delivery_price,
        total=subtotal + delivery_price,
    )

    for product, quantity in checked_items:
        OrderItem.objects.create(
            order=order,
            product=product,
            product_name=product.name,
            unit=product.unit,
            price=product.price,
            quantity=quantity,
        )
        product.stock = max(product.stock - quantity, 0)
        update_fields = ["stock", "updated_at"]
        if product.stock == 0:
            product.is_available = False
            update_fields.append("is_available")
        product.save(update_fields=update_fields)

    OrderStatusEvent.objects.create(
        order=order,
        status=Order.Status.NEW,
        comment="Заказ оформлен на сайте",
    )
    cart.clear()
    return order
