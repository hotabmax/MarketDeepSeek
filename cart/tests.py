from decimal import Decimal

from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory, TestCase
from django.urls import reverse

from catalog.models import Category, Product

from .cart import Cart


def make_request():
    request = RequestFactory().get("/")
    request.session = SessionStore()
    return request


class CartModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(name="Бакалея", slug="grocery")
        cls.rice = Product.objects.create(
            category=cls.category,
            name="Рис",
            slug="rice",
            price=Decimal("100"),
            stock=5,
            unit="кг",
        )
        cls.oil = Product.objects.create(
            category=cls.category,
            name="Масло",
            slug="oil",
            price=Decimal("300"),
            stock=3,
        )

    def setUp(self):
        self.request = make_request()
        self.cart = Cart(self.request)

    def test_empty_cart(self):
        self.assertTrue(self.cart.is_empty)
        self.assertEqual(len(self.cart), 0)
        self.assertEqual(self.cart.get_subtotal(), Decimal("0.00"))
        self.assertEqual(list(self.cart), [])

    def test_add_product(self):
        self.cart.add(self.rice, 2)

        self.assertFalse(self.cart.is_empty)
        self.assertEqual(len(self.cart), 2)
        self.assertEqual(self.cart.positions_count, 1)
        item = next(iter(self.cart))
        self.assertEqual(item["product"], self.rice)
        self.assertEqual(item["quantity"], 2)
        self.assertEqual(item["total_price"], Decimal("200.00"))

    def test_add_clamps_quantity_to_stock(self):
        self.cart.add(self.rice, 99)

        self.assertEqual(self.cart.cart[str(self.rice.pk)]["quantity"], 5)
        self.assertEqual(len(self.cart), 5)

    def test_update_quantity(self):
        self.cart.add(self.rice, 2)
        self.cart.add(self.rice, 4, update_quantity=True)

        self.assertEqual(self.cart.cart[str(self.rice.pk)]["quantity"], 4)

    def test_zero_quantity_removes_item(self):
        self.cart.add(self.rice, 2)
        self.cart.add(self.rice, 0, update_quantity=True)

        self.assertTrue(self.cart.is_empty)

    def test_remove_and_clear(self):
        self.cart.add(self.rice, 1)
        self.cart.add(self.oil, 1)
        self.cart.remove(self.rice)

        self.assertNotIn(self.rice, self.cart)
        self.assertEqual(len(self.cart), 1)

        self.cart.clear()
        self.assertTrue(self.cart.is_empty)
        self.assertEqual(self.request.session.get("cart"), {})

    def test_totals_include_delivery_below_threshold(self):
        self.cart.add(self.rice, 2)
        self.cart.add(self.oil, 1)

        self.assertEqual(self.cart.get_subtotal(), Decimal("500.00"))
        self.assertEqual(self.cart.get_delivery_price(), Decimal("299.00"))
        self.assertEqual(self.cart.get_total(), Decimal("799.00"))
        self.assertEqual(self.cart.amount_to_free_delivery(), Decimal("1500.00"))

    def test_free_delivery_from_threshold(self):
        expensive = Product.objects.create(
            category=self.category,
            name="Икра",
            slug="caviar",
            price=Decimal("2500"),
            stock=2,
        )
        self.cart.add(expensive, 1)

        self.assertGreaterEqual(self.cart.get_subtotal(), Decimal("2000"))
        self.assertEqual(self.cart.get_delivery_price(), Decimal("0.00"))
        self.assertEqual(self.cart.get_total(), self.cart.get_subtotal())
        self.assertEqual(self.cart.amount_to_free_delivery(), Decimal("0.00"))

    def test_prune_removes_products_out_of_stock(self):
        self.cart.add(self.rice, 2)
        self.cart.add(self.oil, 1)

        self.rice.stock = 0
        self.rice.save(update_fields=["stock"])

        self.assertEqual(self.cart.prune(), 1)
        self.assertNotIn(self.rice, self.cart)
        self.assertIn(self.oil, self.cart)
        self.assertEqual(self.cart.prune(), 0)

    def test_prune_removes_deleted_products(self):
        self.cart.add(self.rice, 1)
        product_id = self.rice.pk
        self.rice.delete()

        self.assertEqual(self.cart.prune(), 1)
        self.assertNotIn(str(product_id), self.cart.cart)


class CartViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(name="Молочное", slug="dairy")
        cls.milk = Product.objects.create(
            category=cls.category,
            name="Молоко",
            slug="milk",
            price=Decimal("99"),
            stock=3,
            unit="л",
        )

    def add_to_cart(self, quantity=1, follow=False):
        return self.client.post(
            reverse("cart:add"),
            {"product_id": self.milk.pk, "quantity": quantity, "next": reverse("catalog:list")},
            follow=follow,
        )

    def test_add_to_cart_via_post(self):
        response = self.add_to_cart(quantity=2)

        self.assertRedirects(response, reverse("catalog:list"))
        self.assertEqual(self.client.session["cart"][str(self.milk.pk)]["quantity"], 2)

        page = self.client.get(reverse("cart:detail"))
        self.assertContains(page, "Молоко")
        self.assertContains(page, "Оформить заказ")

    def test_add_more_than_stock_shows_error(self):
        response = self.add_to_cart(quantity=10, follow=True)

        self.assertContains(response, "В наличии только 3")
        self.assertEqual(self.client.session.get("cart", {}), {})

    def test_add_requires_post(self):
        response = self.client.get(reverse("cart:add"))
        self.assertEqual(response.status_code, 405)

    def test_add_out_of_stock_product_shows_error(self):
        self.milk.stock = 0
        self.milk.save(update_fields=["stock"])

        response = self.add_to_cart(quantity=1, follow=True)

        self.assertContains(response, "нет в наличии")
        self.assertEqual(self.client.session.get("cart", {}), {})

    def test_update_quantity_and_remove(self):
        self.add_to_cart(quantity=1)

        response = self.client.post(
            reverse("cart:update", kwargs={"product_id": self.milk.pk}), {"quantity": 3}
        )
        self.assertRedirects(response, reverse("cart:detail"))
        self.assertEqual(self.client.session["cart"][str(self.milk.pk)]["quantity"], 3)

        response = self.client.post(
            reverse("cart:update", kwargs={"product_id": self.milk.pk}),
            {"quantity": 3, "remove": "1"},
        )
        self.assertRedirects(response, reverse("cart:detail"))
        self.assertEqual(self.client.session["cart"], {})

    def test_update_above_stock_is_rejected(self):
        self.add_to_cart(quantity=1)

        response = self.client.post(
            reverse("cart:update", kwargs={"product_id": self.milk.pk}), {"quantity": 10}
        )

        self.assertRedirects(response, reverse("cart:detail"))
        self.assertEqual(self.client.session["cart"][str(self.milk.pk)]["quantity"], 1)

    def test_cart_remove_view(self):
        self.add_to_cart(quantity=2)

        response = self.client.post(reverse("cart:remove", kwargs={"product_id": self.milk.pk}))

        self.assertRedirects(response, reverse("cart:detail"))
        self.assertEqual(self.client.session["cart"], {})

    def test_cart_drops_unavailable_product(self):
        self.add_to_cart(quantity=1)
        self.milk.is_available = False
        self.milk.save(update_fields=["is_available"])

        response = self.client.get(reverse("cart:detail"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Корзина пока пуста")

    def test_empty_cart_page(self):
        response = self.client.get(reverse("cart:detail"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Корзина пока пуста")
