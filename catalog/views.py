from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from cart.forms import AddToCartForm

from .models import Category, Product

PAGE_SIZE = 12

SORT_OPTIONS = {
    "popular": ("-is_featured", "name"),
    "price_asc": ("price", "name"),
    "price_desc": ("-price", "name"),
    "new": ("-created_at",),
    "name": ("name",),
}

SORT_LABELS = (
    ("popular", "Популярные"),
    ("price_asc", "Сначала дешёвые"),
    ("price_desc", "Сначала дорогие"),
    ("new", "Новинки"),
    ("name", "По названию"),
)


def product_list(request, category_slug=None):
    """Каталог с фильтром по категории, поиском, сортировкой и пагинацией."""
    categories = Category.objects.filter(is_active=True)
    current_category = None
    if category_slug:
        current_category = get_object_or_404(Category, slug=category_slug, is_active=True)

    products = Product.objects.available().with_category()
    if current_category:
        products = products.filter(category=current_category)

    query = request.GET.get("q", "").strip()
    if query:
        normalized_query = " ".join(query.casefold().split())
        products = products.filter(search_text__contains=normalized_query)

    sort = request.GET.get("sort", "popular")
    if sort not in SORT_OPTIONS:
        sort = "popular"
    products = products.order_by(*SORT_OPTIONS[sort])

    page_obj = Paginator(products, PAGE_SIZE).get_page(request.GET.get("page"))
    is_home = not query and current_category is None and page_obj.number == 1

    context = {
        "categories": categories,
        "current_category": current_category,
        "products": page_obj.object_list,
        "page_obj": page_obj,
        "is_paginated": page_obj.has_other_pages(),
        "query": query,
        "sort": sort,
        "sort_labels": SORT_LABELS,
        "is_home": is_home,
        "featured_products": (
            Product.objects.available().with_category().filter(is_featured=True)[:4] if is_home else None
        ),
        "add_form": AddToCartForm(),
    }
    return render(request, "catalog/product_list.html", context)


def product_detail(request, slug):
    product = get_object_or_404(Product.objects.with_category(), slug=slug)
    related = (
        Product.objects.available()
        .with_category()
        .filter(category=product.category)
        .exclude(pk=product.pk)[:4]
    )
    context = {
        "product": product,
        "related_products": related,
        "add_form": AddToCartForm(product=product, initial={"quantity": 1}),
    }
    return render(request, "catalog/product_detail.html", context)
