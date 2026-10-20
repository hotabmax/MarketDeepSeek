from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from cart.cart import Cart

from .forms import CheckoutForm, TrackOrderForm
from .models import Order
from .services import CartValidationError, create_order_from_cart, get_delivery_price
from .tracking import build_tracking

TRACKED_ORDERS_SESSION_KEY = "tracked_orders"


def _remember_order(request, order):
    """Запоминает заказ в сессии, чтобы покупатель мог вернуться к отслеживанию."""
    tracked = [
        pk
        for pk in request.session.get(TRACKED_ORDERS_SESSION_KEY, [])
        if pk != order.pk
    ]
    tracked.append(order.pk)
    request.session[TRACKED_ORDERS_SESSION_KEY] = tracked[-20:]


def checkout(request):
    cart = Cart(request)
    if cart.is_empty:
        messages.warning(request, "Корзина пуста. Добавьте товары, чтобы оформить заказ.")
        return redirect("catalog:list")

    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            try:
                order = create_order_from_cart(cart, form.cleaned_data)
            except CartValidationError as error:
                messages.error(request, str(error))
                return redirect("cart:detail")
            request.session["last_order_id"] = order.pk
            _remember_order(request, order)
            messages.success(request, f"Заказ {order.number} оформлен. Спасибо!")
            return redirect("orders:success")
        messages.error(request, "Проверьте выделенные поля — в них есть ошибки.")
    else:
        form = CheckoutForm()

    rows = list(cart)
    subtotal = sum((row["total_price"] for row in rows), Decimal("0.00"))
    delivery_method = form["delivery_method"].value() or Order.DeliveryMethod.COURIER
    delivery_price = get_delivery_price(subtotal, delivery_method)

    context = {
        "form": form,
        "rows": rows,
        "subtotal": subtotal,
        "delivery_price": delivery_price,
        "total": subtotal + delivery_price,
        "free_delivery_from": settings.FREE_DELIVERY_FROM,
        "delivery_tariff": settings.DELIVERY_PRICE,
        "pickup_address": "Самара, ул. Ново-Садовая, 106 (ежедневно 9:00–21:00)",
    }
    return render(request, "orders/checkout.html", context)


def order_success(request):
    order_id = request.session.get("last_order_id")
    order = (
        Order.objects.prefetch_related("items", "status_events").filter(pk=order_id).first()
        if order_id
        else None
    )
    if order is None:
        messages.info(request, "Здесь появится информация о заказе сразу после оформления.")
        return redirect("catalog:list")
    _remember_order(request, order)
    return render(request, "orders/order_success.html", {"order": order})


def order_track(request):
    """Форма поиска заказа по номеру и телефону."""
    form = TrackOrderForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        order = form.cleaned_data["order"]
        _remember_order(request, order)
        return redirect("orders:track_detail", number=order.number)
    return render(request, "orders/track_form.html", {"form": form})


def order_track_detail(request, number):
    """Статус и история заказа; доступ — после проверки номера и телефона."""
    order = get_object_or_404(
        Order.objects.prefetch_related("items", "status_events"),
        number__iexact=number,
    )
    if order.pk not in request.session.get(TRACKED_ORDERS_SESSION_KEY, []):
        messages.info(
            request,
            "Введите номер заказа и телефон, чтобы посмотреть статус доставки.",
        )
        return redirect("orders:track")

    steps, events = build_tracking(order)
    return render(
        request,
        "orders/track_detail.html",
        {
            "order": order,
            "steps": steps,
            "cancellation": events.get(Order.Status.CANCELLED),
        },
    )
