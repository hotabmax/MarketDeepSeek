from django.contrib import admin
from django.db.models import Count

from .models import Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "icon", "products_count", "sort_order", "is_active")
    list_editable = ("sort_order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(products_total=Count("products"))

    @admin.display(description="Товаров", ordering="products_total")
    def products_count(self, obj):
        return obj.products_total


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "price",
        "old_price",
        "unit",
        "stock",
        "is_available",
        "is_featured",
    )
    list_editable = ("price", "stock", "is_available", "is_featured")
    list_filter = ("category", "is_available", "is_featured")
    list_select_related = ("category",)
    search_fields = ("name", "description", "category__name")
    prepopulated_fields = {"slug": ("name",)}
    fieldsets = (
        ("Основное", {"fields": ("category", "name", "slug", "description", "emoji", "image_url")}),
        ("Цена и склад", {"fields": ("price", "old_price", "unit", "stock")}),
        ("Публикация", {"fields": ("is_available", "is_featured")}),
    )
