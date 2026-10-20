"""Заказы покупателей."""

from django.db import models
from django.utils import timezone
from django.utils.crypto import get_random_string


def _generate_order_number():
    date_part = timezone.localdate().strftime("%Y%m%d")
    token = get_random_string(5, allowed_chars="ABCDEFGHJKLMNPQRSTUVWXYZ23456789")
    return f"FM-{date_part}-{token}"


STATUS_COLORS = {
    "new": "#2f6fed",
    "confirmed": "#b26a00",
    "delivering": "#0d7a8f",
    "done": "#1f7a4d",
    "cancelled": "#b3261e",
}


class Order(models.Model):
    """Заказ, оформленный с сайта."""

    class Status(models.TextChoices):
        NEW = "new", "Новый"
        CONFIRMED = "confirmed", "Подтверждён"
        DELIVERING = "delivering", "В доставке"
        DONE = "done", "Выполнен"
        CANCELLED = "cancelled", "Отменён"

    class DeliveryMethod(models.TextChoices):
        COURIER = "courier", "Курьером"
        PICKUP = "pickup", "Самовывоз"

    class PaymentMethod(models.TextChoices):
        CASH = "cash", "При получении"
        CARD_COURIER = "card_courier", "Картой курьеру"
        CARD_ONLINE = "card_online", "Картой онлайн"

    number = models.CharField("Номер заказа", max_length=24, unique=True, editable=False)
    status = models.CharField(
        "Статус", max_length=20, choices=Status.choices, default=Status.NEW, db_index=True
    )

    customer_name = models.CharField("Имя и фамилия", max_length=120)
    phone = models.CharField("Телефон", max_length=32)
    email = models.EmailField("E-mail", blank=True)

    delivery_method = models.CharField(
        "Способ получения",
        max_length=20,
        choices=DeliveryMethod.choices,
        default=DeliveryMethod.COURIER,
    )
    address = models.CharField("Адрес доставки", max_length=255, blank=True)
    delivery_slot = models.CharField("Время доставки", max_length=20, blank=True)

    payment_method = models.CharField(
        "Оплата",
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH,
    )
    comment = models.TextField("Комментарий покупателя", blank=True)

    subtotal = models.DecimalField("Стоимость товаров", max_digits=10, decimal_places=2, default=0)
    delivery_price = models.DecimalField("Доставка", max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField("Итого", max_digits=10, decimal_places=2, default=0)

    created_at = models.DateTimeField("Оформлен", auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        ordering = ("-created_at",)

    def __str__(self):
        return f"Заказ {self.number}"

    def save(self, *args, **kwargs):
        if not self.number:
            number = _generate_order_number()
            while Order.objects.filter(number=number).exists():
                number = _generate_order_number()
            self.number = number
        super().save(*args, **kwargs)

    @property
    def status_color(self):
        return STATUS_COLORS.get(self.status, "#4b5563")

    @property
    def is_cancellable(self):
        return self.status in {self.Status.NEW, self.Status.CONFIRMED}


class OrderItem(models.Model):
    """Позиция заказа: снимок названия и цены на момент покупки."""

    order = models.ForeignKey(Order, verbose_name="Заказ", related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey(
        "catalog.Product",
        verbose_name="Товар",
        related_name="order_items",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    product_name = models.CharField("Название товара", max_length=150)
    unit = models.CharField("Единица", max_length=20, default="шт.")
    price = models.DecimalField("Цена", max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField("Количество", default=1)

    class Meta:
        verbose_name = "Позиция заказа"
        verbose_name_plural = "Позиции заказа"
        ordering = ("pk",)

    def __str__(self):
        return f"{self.product_name} × {self.quantity}"

    @property
    def total_price(self):
        return self.price * self.quantity


class OrderStatusEvent(models.Model):
    """Запись истории: когда и почему у заказа появился статус."""

    order = models.ForeignKey(
        Order,
        verbose_name="Заказ",
        related_name="status_events",
        on_delete=models.CASCADE,
    )
    status = models.CharField("Статус", max_length=20, choices=Order.Status.choices)
    comment = models.CharField("Комментарий", max_length=255, blank=True)
    created_at = models.DateTimeField("Когда", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Событие статуса"
        verbose_name_plural = "История статусов"
        ordering = ("created_at", "pk")

    def __str__(self):
        return f"{self.order.number}: {self.get_status_display()}"

    @property
    def status_color(self):
        return STATUS_COLORS.get(self.status, "#4b5563")


class DeliverySlot(models.TextChoices):
    ASAP = "asap", "Как можно скорее"
    MORNING = "10-14", "Сегодня, 10:00–14:00"
    DAY = "14-18", "Сегодня, 14:00–18:00"
    EVENING = "18-22", "Сегодня, 18:00–22:00"
    TOMORROW = "tomorrow", "Завтра, 10:00–22:00"
