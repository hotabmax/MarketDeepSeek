from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

admin.site.site_header = "ФрешМаркет — управление магазином"
admin.site.site_title = "ФрешМаркет"
admin.site.index_title = "Панель магазина"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("cart/", include("cart.urls")),
    path("orders/", include("orders.urls")),
    path(
        "help/delivery/",
        TemplateView.as_view(template_name="pages/delivery.html"),
        name="delivery",
    ),
    path(
        "help/contacts/",
        TemplateView.as_view(template_name="pages/contacts.html"),
        name="contacts",
    ),
    path("", include("catalog.urls")),
]
