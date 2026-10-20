from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from catalog.models import Product

from .cart import Cart
from .forms import AddToCartForm, CartItemForm


def _safe_redirect_target(request, fallback):
    """Возвращает безопасный адрес возврата после действия с корзиной."""
    candidate = request.POST.get("next") or request.GET.get("next")
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return fallback


def _first_error(form):
    for errors in form.errors.values():
        if errors:
            return errors[0]
    return "Не удалось выполнить действие."


def cart_detail(request):
    cart = Cart(request)
    if cart.prune():
        messages.warning(request, "Из корзины убраны товары, которых больше нет в продаже.")

    rows = []
    subtotal = Decimal("0.00")
    for item in cart:
        rows.append(
            {
                **item,
                "form": CartItemForm(product=item["product"], initial={"quantity": item["quantity"]}),
                "stock_changed": item["quantity"] > item["product"].stock,
            }
        )
        subtotal += item["total_price"]

    context = {
        "cart": cart,
        "rows": rows,
        "subtotal": subtotal,
        "delivery_price": cart.get_delivery_price(),
        "total": cart.get_total(),
        "free_delivery_from": settings.FREE_DELIVERY_FROM,
        "delivery_tariff": settings.DELIVERY_PRICE,
        "amount_to_free_delivery": cart.amount_to_free_delivery(),
        "free_delivery_reached": cart.amount_to_free_delivery() == 0,
    }
    return render(request, "cart/cart_detail.html", context)


@require_POST
def cart_update(request, product_id):
    """Меняет количество товара в корзине или удаляет позицию."""
    product = get_object_or_404(Product, pk=product_id)
    cart = Cart(request)
    form = CartItemForm(request.POST, product=product)
    if not form.is_valid():
        messages.error(request, _first_error(form))
        return redirect("cart:detail")

    if form.cleaned_data.get("remove") or form.cleaned_data["quantity"] == 0:
        cart.remove(product)
        messages.info(request, f"«{product.name}» удалён из корзины.")
    else:
        cart.add(product, quantity=form.cleaned_data["quantity"], update_quantity=True)
        messages.success(request, f"«{product.name}» — количество обновлено.")
    return redirect("cart:detail")


@require_POST
def cart_add(request):
    product = get_object_or_404(
        Product.objects.with_category(),
        pk=request.POST.get("product_id"),
    )
    form = AddToCartForm(request.POST, product=product)
    fallback = product.get_absolute_url()
    if not form.is_valid():
        messages.error(request, _first_error(form))
        return redirect(_safe_redirect_target(request, fallback))

    cart = Cart(request)
    cart.add(product, quantity=form.cleaned_data["quantity"])
    messages.success(
        request,
        f"«{product.name}» добавлен в корзину. Товаров в корзине: {len(cart)}.",
    )
    return redirect(_safe_redirect_target(request, fallback))


@require_POST
def cart_remove(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    Cart(request).remove(product)
    messages.info(request, f"«{product.name}» удалён из корзины.")
    return redirect("cart:detail")
