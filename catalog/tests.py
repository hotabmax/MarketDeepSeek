from decimal import Decimal

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .models import Category, Product
from .templatetags.shop_tags import money, plural_ru


class ShopTemplateTagsTests(SimpleTestCase):
    def test_money_format(self):
        self.assertEqual(money(Decimal("1290.00")), "1\u00a0290\u00a0₽")
        self.assertEqual(money(Decimal("99.50")), "99,50\u00a0₽")

    def test_money_handles_invalid_values(self):
        self.assertEqual(money("не число"), "не число")

    def test_plural_ru(self):
        forms = "товар,товара,товаров"
        self.assertEqual(plural_ru(1, forms), "товар")
        self.assertEqual(plural_ru(3, forms), "товара")
        self.assertEqual(plural_ru(5, forms), "товаров")
        self.assertEqual(plural_ru(11, forms), "товаров")
        self.assertEqual(plural_ru(21, forms), "товар")


class CatalogModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(
            name="Овощи и фрукты", slug="fruits", color="#eaf5e6"
        )

    def test_available_manager_excludes_unavailable_products(self):
        in_stock = Product.objects.create(
            category=self.category, name="Apples", slug="apples", price=Decimal("150"), stock=10
        )
        Product.objects.create(
            category=self.category, name="Pears", slug="pears", price=Decimal("180"), stock=0
        )
        disabled = Product.objects.create(
            category=self.category,
            name="Plums",
            slug="plums",
            price=Decimal("200"),
            stock=5,
            is_available=False,
        )

        available = list(Product.objects.available())

        self.assertEqual(available, [in_stock])
        self.assertNotIn(disabled, available)

    def test_discount_percent(self):
        product = Product.objects.create(
            category=self.category,
            name="Strawberry",
            slug="strawberry",
            price=Decimal("300"),
            old_price=Decimal("400"),
            stock=5,
        )

        self.assertTrue(product.has_discount)
        self.assertEqual(product.discount_percent, 25)

    def test_product_without_discount(self):
        product = Product.objects.create(
            category=self.category,
            name="Milk",
            slug="milk",
            price=Decimal("100"),
            old_price=Decimal("100"),
            stock=5,
        )

        self.assertFalse(product.has_discount)
        self.assertEqual(product.discount_percent, 0)

    def test_slug_is_generated_from_russian_name_and_unique(self):
        first = Product.objects.create(
            category=self.category, name="Помидоры", price=Decimal("100"), stock=3
        )
        second = Product.objects.create(
            category=self.category, name="Помидоры", price=Decimal("120"), stock=3
        )

        self.assertEqual(first.slug, "pomidory")
        self.assertEqual(second.slug, "pomidory-2")

    def test_in_stock_requires_flag_and_quantity(self):
        product = Product.objects.create(
            category=self.category, name="Bread", slug="bread", price=Decimal("50"), stock=0
        )

        self.assertFalse(product.in_stock)

    def test_search_text_is_rebuilt_on_save(self):
        product = Product.objects.create(
            category=self.category,
            name="Молоко",
            description="Пастеризованное",
            price=Decimal("99"),
            stock=5,
        )
        self.assertEqual(product.search_text, "молоко пастеризованное")

        product.name = "Кефир"
        product.save(update_fields=["name"])
        product.refresh_from_db()

        self.assertEqual(product.search_text, "кефир пастеризованное")


class CatalogViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.vegetables = Category.objects.create(
            name="Овощи", slug="vegetables", icon="🥦", sort_order=1
        )
        cls.dairy = Category.objects.create(
            name="Молочное", slug="dairy", icon="🥛", sort_order=2
        )
        cls.tomato = Product.objects.create(
            category=cls.vegetables,
            name="Томаты",
            slug="tomatoes",
            description="Сладкие черри",
            price=Decimal("150"),
            stock=10,
        )
        cls.milk = Product.objects.create(
            category=cls.dairy,
            name="Молоко",
            slug="milk",
            description="Пастеризованное",
            price=Decimal("99"),
            stock=10,
        )
        cls.sold_out = Product.objects.create(
            category=cls.vegetables,
            name="Огурцы",
            slug="cucumbers",
            price=Decimal("120"),
            stock=0,
        )

    def test_list_shows_only_available_products(self):
        response = self.client.get(reverse("catalog:list"))

        self.assertEqual(response.status_code, 200)
        products = list(response.context["products"])
        self.assertIn(self.tomato, products)
        self.assertIn(self.milk, products)
        self.assertNotIn(self.sold_out, products)

    def test_search_filters_by_name_and_description(self):
        response = self.client.get(reverse("catalog:list"), {"q": "черри"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["products"]), [self.tomato])

    def test_search_is_case_insensitive_for_cyrillic(self):
        for term in ("молоко", "МОЛОКО", "Молоко", "  молоко  "):
            with self.subTest(term=term):
                response = self.client.get(reverse("catalog:list"), {"q": term})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(list(response.context["products"]), [self.milk])

    def test_search_finds_product_by_description_case_insensitively(self):
        response = self.client.get(reverse("catalog:list"), {"q": "ПАСТЕРИЗОВАННОЕ"})

        self.assertEqual(list(response.context["products"]), [self.milk])

    def test_search_without_matches_renders_empty_state(self):
        response = self.client.get(reverse("catalog:list"), {"q": "ананас"})

        self.assertContains(response, "Ничего не нашлось")
        self.assertEqual(list(response.context["products"]), [])

    def test_category_filter_returns_products_of_one_category(self):
        response = self.client.get(
            reverse("catalog:category", kwargs={"category_slug": self.dairy.slug})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["products"]), [self.milk])
        self.assertEqual(response.context["current_category"], self.dairy)

    def test_sorting_by_price(self):
        response = self.client.get(reverse("catalog:list"), {"sort": "price_asc"})
        prices = [product.price for product in response.context["products"]]
        self.assertEqual(prices, sorted(prices))

        response = self.client.get(reverse("catalog:list"), {"sort": "price_desc"})
        prices = [product.price for product in response.context["products"]]
        self.assertEqual(prices, sorted(prices, reverse=True))

    def test_inactive_category_returns_404(self):
        self.dairy.is_active = False
        self.dairy.save(update_fields=["is_active"])

        response = self.client.get(
            reverse("catalog:category", kwargs={"category_slug": self.dairy.slug})
        )

        self.assertEqual(response.status_code, 404)

    def test_product_detail_page(self):
        response = self.client.get(reverse("catalog:detail", kwargs={"slug": self.tomato.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Томаты")
        self.assertContains(response, "Сладкие черри")
        self.assertContains(response, "Добавить в корзину")

    def test_product_detail_404_for_unknown_slug(self):
        response = self.client.get(reverse("catalog:detail", kwargs={"slug": "unknown"}))
        self.assertEqual(response.status_code, 404)

    def test_homepage_renders_hero_and_categories(self):
        response = self.client.get(reverse("catalog:list"))

        self.assertContains(response, "Свежие продукты")
        self.assertContains(response, "Овощи")
        self.assertTrue(response.context["is_home"])

    def test_pagination_splits_catalog(self):
        for number in range(15):
            Product.objects.create(
                category=self.vegetables,
                name=f"Товар {number}",
                slug=f"item-{number}",
                price=Decimal("100"),
                stock=5,
            )

        first_page = self.client.get(reverse("catalog:list"))
        second_page = self.client.get(reverse("catalog:list"), {"page": 2})

        self.assertEqual(len(first_page.context["products"]), 12)
        self.assertTrue(first_page.context["is_paginated"])
        self.assertTrue(second_page.context["products"])
        self.assertFalse(second_page.context["is_home"])

    def test_search_query_is_preserved_in_pagination_links(self):
        for number in range(15):
            Product.objects.create(
                category=self.vegetables,
                name=f"Яблоко {number}",
                slug=f"apple-{number}",
                price=Decimal("100"),
                stock=5,
            )

        response = self.client.get(reverse("catalog:list"), {"q": "Яблоко"})

        self.assertContains(response, "q=%D0%AF")
        self.assertContains(response, "page=2")

    def test_delivery_and_contacts_pages_render(self):
        for name in ("delivery", "contacts"):
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "ФрешМаркет")
