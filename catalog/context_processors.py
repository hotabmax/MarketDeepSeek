from django.conf import settings

from .models import Category


def categories(request):
    """Активные разделы каталога для меню в шапке."""
    return {"nav_categories": Category.objects.filter(is_active=True)}


def site_info(request):
    """Общие настройки магазина для шаблонов."""
    return {
        "site": {
            "name": settings.SITE_NAME,
            "phone": settings.SITE_PHONE,
            "phone_link": "".join(ch for ch in settings.SITE_PHONE if ch.isdigit() or ch == "+"),
            "free_delivery_from": settings.FREE_DELIVERY_FROM,
            "delivery_price": settings.DELIVERY_PRICE,
        }
    }
