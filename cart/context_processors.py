from .cart import Cart


def cart(request):
    """Делает корзину и её количество доступными во всех шаблонах."""
    current_cart = Cart(request)
    return {
        "cart": current_cart,
        "cart_total_quantity": len(current_cart),
    }
