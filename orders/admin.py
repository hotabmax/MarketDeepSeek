from django.contrib import admin
from django.utils.html import format_html

from .models import Order, OrderItem, OrderStatusEvent


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    fields = ("product", "product_name", "unit", "price", "quantity")
    readonly_fields = ("product", "product_name", "unit", "price", "quantity")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class OrderStatusEventInline(admin.TabularInline):
    model = OrderStatusEvent
    extra = 0
    fields = ("status", "comment", "created_at")
    readonly_fields = ("status", "comment", "created_at")
    can_delete = False
    ordering = ("created_at",)

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "customer_name",
        "phone",
        "status_badge",
        "delivery_method",
        "total",
        "created_at",
    )
    list_filter = ("status", "delivery_method", "payment_method", "created_at")
    search_fields = ("number", "customer_name", "phone", "email")
    date_hierarchy = "created_at"
    readonly_fields = ("number", "subtotal", "delivery_price", "total", "created_at", "updated_at")
    inlines = (OrderItemInline, OrderStatusEventInline)
    fieldsets = (
        ("Заказ", {"fields": ("number", "status", "created_at", "updated_at")}),
        ("Покупатель", {"fields": ("customer_name", "phone", "email")}),
        ("Доставка", {"fields": ("delivery_method", "address", "delivery_slot")}),
        ("Оплата и суммы", {"fields": ("payment_method", "subtotal", "delivery_price", "total")}),
        ("Прочее", {"fields": ("comment",)}),
    )
    actions = ("mark_confirmed", "mark_delivering", "mark_done", "mark_cancelled")

    @admin.display(description="Статус", ordering="status")
    def status_badge(self, obj):
        return format_html(
            '<span style="display:inline-block;padding:2px 10px;border-radius:999px;'
            'color:#fff;background:{};font-size:12px;">{}</span>',
            obj.status_color,
            obj.get_status_display(),
        )

    @admin.action(description="Подтвердить выбранные заказы")
    def mark_confirmed(self, request, queryset):
        self._change_status(
            request,
            queryset,
            Order.Status.CONFIRMED,
            "Подтверждён оператором",
            "Подтверждено заказов",
        )

    @admin.action(description="Передать выбранные заказы в доставку")
    def mark_delivering(self, request, queryset):
        self._change_status(
            request,
            queryset,
            Order.Status.DELIVERING,
            "Передан в доставку",
            "Передано в доставку",
        )

    @admin.action(description="Отметить выбранные заказы выполненными")
    def mark_done(self, request, queryset):
        self._change_status(
            request,
            queryset,
            Order.Status.DONE,
            "Заказ доставлен",
            "Выполнено заказов",
        )

    @admin.action(description="Отменить выбранные заказы")
    def mark_cancelled(self, request, queryset):
        self._change_status(
            request,
            queryset,
            Order.Status.CANCELLED,
            "Отменён оператором",
            "Отменено заказов",
        )

    def _change_status(self, request, queryset, status, comment, message):
        """Меняет статус и пишет событие в историю заказа."""
        orders = list(queryset.exclude(status=status))
        for order in orders:
            order.status = status
            order.save(update_fields=["status", "updated_at"])
            OrderStatusEvent.objects.create(order=order, status=status, comment=comment)
        self.message_user(request, f"{message}: {len(orders)}.")

    def save_model(self, request, obj, form, change):
        previous_status = None
        if change and obj.pk:
            previous_status = (
                Order.objects.filter(pk=obj.pk).values_list("status", flat=True).first()
            )
        super().save_model(request, obj, form, change)
        if previous_status != obj.status:
            OrderStatusEvent.objects.create(
                order=obj,
                status=obj.status,
                comment="Статус изменён в админке" if change else "Заказ создан в админке",
            )


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("order", "product_name", "price", "quantity", "total_price")
    list_filter = ("order__status",)
    search_fields = ("order__number", "product_name")
    list_select_related = ("order",)

    @admin.display(description="Сумма")
    def total_price(self, obj):
        return obj.total_price
