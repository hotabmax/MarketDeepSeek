from decimal import Decimal

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from catalog.models import Category, Product

from .admin import OrderAdmin
from .forms import CheckoutForm, TrackOrderForm
from .models import Order, OrderItem, OrderStatusEvent
from .tracking import build_tracking
from .utils import normalize_phone, phones_match


class CheckoutFormTests(TestCase):
    def valid_data(self, **overrides):
        data = {
            "customer_name": "Анна Смирнова",
            "phone": "8 (999) 123-45-67",
            "email": "anna@example.com",
            "delivery_method": Order.DeliveryMethod.COURIER,
            "address": "Самара, ул. Ленинградская, 1",
            "delivery_slot": "asap",
            "payment_method": Order.PaymentMethod.CASH,
            "comment": "",
            "agree": "on",
        }
        data.update(overrides)
        return data

    def test_phone_is_normalized(self):
        form = CheckoutForm(data=self.valid_data())

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["phone"], "+7 (999) 123-45-67")

    def test_invalid_phone(self):
        form = CheckoutForm(data=self.valid_data(phone="123"))

        self.assertFalse(form.is_valid())
        self.assertIn("phone", form.errors)

    def test_courier_requires_address(self):
        form = CheckoutForm(data=self.valid_data(address=""))

        self.assertFalse(form.is_valid())
        self.assertIn("address", form.errors)

    def test_pickup_does_not_require_address(self):
        form = CheckoutForm(
            data=self.valid_data(delivery_method=Order.DeliveryMethod.PICKUP, address="")
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_agreement_is_required(self):
        form = CheckoutForm(data=self.valid_data(agree=""))

        self.assertFalse(form.is_valid())
        self.assertIn("agree", form.errors)


class CheckoutFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(name="Молочное", slug="dairy")
        cls.milk = Product.objects.create(
            category=cls.category,
            name="Молоко",
            slug="milk",
            price=Decimal("100"),
            stock=10,
            unit="л",
        )

    def add_milk(self, quantity=2):
        return self.client.post(
            reverse("cart:add"),
            {"product_id": self.milk.pk, "quantity": quantity},
        )

    def checkout_data(self, **overrides):
        data = {
            "customer_name": "Анна Смирнова",
            "phone": "+7 999 123-45-67",
            "email": "anna@example.com",
            "delivery_method": Order.DeliveryMethod.COURIER,
            "address": "Самара, ул. Ленинградская, 1, кв. 5",
            "delivery_slot": "asap",
            "payment_method": Order.PaymentMethod.CASH,
            "comment": "Код домофона 1234",
            "agree": "on",
        }
        data.update(overrides)
        return data

    def test_checkout_redirects_when_cart_is_empty(self):
        response = self.client.get(reverse("orders:checkout"))

        self.assertRedirects(response, reverse("catalog:list"))

    def test_checkout_page_renders_cart_summary(self):
        self.add_milk(quantity=2)

        response = self.client.get(reverse("orders:checkout"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Оформление заказа")
        self.assertContains(response, "Молоко")
        self.assertContains(response, "Подтвердить заказ")

    def test_successful_courier_checkout(self):
        self.add_milk(quantity=2)

        response = self.client.post(reverse("orders:checkout"), self.checkout_data())

        order = Order.objects.get()
        self.assertRedirects(response, reverse("orders:success"))
        self.assertEqual(order.status, Order.Status.NEW)
        self.assertEqual(order.customer_name, "Анна Смирнова")
        self.assertEqual(order.phone, "+7 (999) 123-45-67")
        self.assertEqual(order.subtotal, Decimal("200.00"))
        self.assertEqual(order.delivery_price, Decimal("299.00"))
        self.assertEqual(order.total, Decimal("499.00"))
        self.assertEqual(order.delivery_method, Order.DeliveryMethod.COURIER)
        self.assertEqual(order.address, "Самара, ул. Ленинградская, 1, кв. 5")
        self.assertEqual(order.items.count(), 1)

        item = order.items.get()
        self.assertEqual(item.product, self.milk)
        self.assertEqual(item.product_name, "Молоко")
        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.total_price, Decimal("200.00"))

        self.milk.refresh_from_db()
        self.assertEqual(self.milk.stock, 8)
        self.assertEqual(self.client.session["cart"], {})
        self.assertEqual(self.client.session["last_order_id"], order.pk)

        self.assertEqual(order.status_events.count(), 1)
        event = order.status_events.get()
        self.assertEqual(event.status, Order.Status.NEW)
        self.assertEqual(event.comment, "Заказ оформлен на сайте")

        tracking_page = self.client.get(
            reverse("orders:track_detail", kwargs={"number": order.number})
        )
        self.assertEqual(tracking_page.status_code, 200)

    def test_free_delivery_above_threshold(self):
        self.add_milk(quantity=10)
        self.milk.price = Decimal("250")
        self.milk.save(update_fields=["price"])

        self.client.post(reverse("orders:checkout"), self.checkout_data())

        order = Order.objects.get()
        self.assertEqual(order.subtotal, Decimal("2500.00"))
        self.assertEqual(order.delivery_price, Decimal("0.00"))
        self.assertEqual(order.total, Decimal("2500.00"))

    def test_pickup_is_free_and_has_no_address(self):
        self.add_milk(quantity=1)

        self.client.post(
            reverse("orders:checkout"),
            self.checkout_data(delivery_method=Order.DeliveryMethod.PICKUP),
        )

        order = Order.objects.get()
        self.assertEqual(order.delivery_method, Order.DeliveryMethod.PICKUP)
        self.assertEqual(order.delivery_price, Decimal("0.00"))
        self.assertEqual(order.total, Decimal("100.00"))
        self.assertEqual(order.address, "")

    def test_invalid_checkout_does_not_create_order(self):
        self.add_milk(quantity=1)

        response = self.client.post(reverse("orders:checkout"), self.checkout_data(address=""))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Для доставки курьером нужен адрес")
        self.assertFalse(Order.objects.exists())
        self.assertEqual(self.client.session["cart"][str(self.milk.pk)]["quantity"], 1)

    def test_checkout_fails_when_stock_is_gone(self):
        self.add_milk(quantity=2)
        self.milk.stock = 1
        self.milk.save(update_fields=["stock"])

        response = self.client.post(reverse("orders:checkout"), self.checkout_data())

        self.assertRedirects(response, reverse("cart:detail"))
        self.assertFalse(Order.objects.exists())
        self.milk.refresh_from_db()
        self.assertEqual(self.milk.stock, 1)
        self.assertEqual(self.client.session["cart"][str(self.milk.pk)]["quantity"], 2)

    def test_last_item_stock_is_decremented_to_zero_and_hidden(self):
        self.add_milk(quantity=10)

        self.client.post(reverse("orders:checkout"), self.checkout_data())

        self.milk.refresh_from_db()
        self.assertEqual(self.milk.stock, 0)
        self.assertFalse(self.milk.is_available)

    def test_order_success_page_shows_number(self):
        self.add_milk(quantity=1)
        self.client.post(reverse("orders:checkout"), self.checkout_data())
        order = Order.objects.get()

        response = self.client.get(reverse("orders:success"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, order.number)
        self.assertContains(response, "Заказ оформлен")

    def test_success_page_without_order_redirects(self):
        response = self.client.get(reverse("orders:success"))

        self.assertRedirects(response, reverse("catalog:list"))

    def test_order_number_format(self):
        self.add_milk(quantity=1)
        self.client.post(reverse("orders:checkout"), self.checkout_data())

        order = Order.objects.get()
        self.assertTrue(order.number.startswith("FM-"))
        date_part, random_part = order.number.split("-")[1:]
        self.assertEqual(len(date_part), 8)
        self.assertEqual(len(random_part), 5)


class OrderModelTests(TestCase):
    def test_order_generates_unique_number(self):
        first = Order.objects.create(customer_name="Иван", phone="+70000000000")
        second = Order.objects.create(customer_name="Пётр", phone="+70000000001")

        self.assertTrue(first.number)
        self.assertNotEqual(first.number, second.number)

    def test_order_item_total_price(self):
        order = Order.objects.create(customer_name="Иван", phone="+70000000000")
        item = OrderItem.objects.create(
            order=order,
            product_name="Хлеб",
            price=Decimal("69.00"),
            quantity=3,
            unit="шт.",
        )

        self.assertEqual(item.total_price, Decimal("207.00"))
        self.assertEqual(str(item), "Хлеб × 3")


class PhoneUtilsTests(SimpleTestCase):
    def test_normalize_phone_variants(self):
        self.assertEqual(normalize_phone("8 (999) 123-45-67"), "+7 (999) 123-45-67")
        self.assertEqual(normalize_phone("+7 999 123 45 67"), "+7 (999) 123-45-67")
        self.assertEqual(normalize_phone("9991234567"), "+9991234567")

    def test_normalize_phone_rejects_short_number(self):
        with self.assertRaises(ValidationError):
            normalize_phone("123")

    def test_phones_match_ignores_formatting(self):
        self.assertTrue(phones_match("+7 (999) 123-45-67", "89991234567"))
        self.assertTrue(phones_match("+7 (999) 123-45-67", "+7 999 123-45-67"))
        self.assertFalse(phones_match("+7 (999) 123-45-67", "+7 (999) 000-00-00"))
        self.assertFalse(phones_match("+7 (999) 123-45-67", "123"))


class TrackOrderFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.order = Order.objects.create(
            customer_name="Анна Смирнова",
            phone="+7 (999) 123-45-67",
        )

    def test_number_is_uppercased_and_order_found(self):
        form = TrackOrderForm(
            data={"number": f"  {self.order.number.lower()}  ", "phone": "+7 999 123-45-67"}
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["number"], self.order.number)
        self.assertEqual(form.cleaned_data["order"], self.order)

    def test_wrong_phone_is_rejected(self):
        form = TrackOrderForm(
            data={"number": self.order.number, "phone": "+7 999 000-00-00"}
        )

        self.assertFalse(form.is_valid())
        self.assertIn("Заказ с таким номером и телефоном не найден", str(form.errors))

    def test_unknown_order_is_rejected(self):
        form = TrackOrderForm(
            data={"number": "FM-20260101-AAAAA", "phone": "+7 999 123-45-67"}
        )

        self.assertFalse(form.is_valid())
        self.assertIn("не найден", str(form.errors))


class TrackingViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.order = Order.objects.create(
            customer_name="Анна Смирнова",
            phone="+7 (999) 123-45-67",
            address="Самара, ул. Ленинградская, 1",
            delivery_method=Order.DeliveryMethod.COURIER,
            subtotal=Decimal("200.00"),
            delivery_price=Decimal("299.00"),
            total=Decimal("499.00"),
        )
        OrderItem.objects.create(
            order=cls.order,
            product_name="Молоко",
            price=Decimal("100.00"),
            quantity=2,
        )
        OrderStatusEvent.objects.create(
            order=cls.order,
            status=Order.Status.NEW,
            comment="Заказ оформлен на сайте",
        )

    def track(self, **overrides):
        data = {"number": self.order.number, "phone": "+7 (999) 123-45-67"}
        data.update(overrides)
        return self.client.post(reverse("orders:track"), data)

    def test_track_form_page(self):
        response = self.client.get(reverse("orders:track"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Отслеживание заказа")
        self.assertContains(response, "Показать статус")

    def test_header_shows_tracking_link_next_to_cart(self):
        html = self.client.get(reverse("catalog:list")).content.decode()

        track_position = html.find('class="track-link"')
        cart_position = html.find('class="cart-link"')
        self.assertGreaterEqual(track_position, 0)
        self.assertGreater(cart_position, track_position)
        self.assertIn('href="/orders/track/"', html)

    def test_lookup_with_alternative_phone_format_grants_access(self):
        response = self.track(
            number=self.order.number.lower(),
            phone="8 999 123 45 67",
        )

        self.assertRedirects(
            response,
            reverse("orders:track_detail", kwargs={"number": self.order.number}),
        )
        self.assertIn(self.order.pk, self.client.session["tracked_orders"])

        page = self.client.get(
            reverse("orders:track_detail", kwargs={"number": self.order.number})
        )
        self.assertContains(page, "Молоко")
        self.assertContains(page, "Заказ принят")
        self.assertContains(page, "История заказа")
        self.assertContains(page, "Заказ оформлен на сайте")

    def test_wrong_phone_does_not_grant_access(self):
        response = self.track(phone="+7 999 000-00-00")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Заказ с таким номером и телефоном не найден")
        self.assertNotIn("tracked_orders", self.client.session)
        self.assertNotContains(response, "Молоко")

    def test_unknown_order_is_not_found(self):
        response = self.track(number="FM-20260101-AAAAA")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Заказ с таким номером и телефоном не найден")

    def test_detail_requires_lookup(self):
        response = self.client.get(
            reverse("orders:track_detail", kwargs={"number": self.order.number})
        )

        self.assertRedirects(response, reverse("orders:track"))

    def test_detail_shows_cancelled_order(self):
        self.order.status = Order.Status.CANCELLED
        self.order.save(update_fields=["status", "updated_at"])
        OrderStatusEvent.objects.create(
            order=self.order,
            status=Order.Status.CANCELLED,
            comment="Отменён оператором",
        )
        self.track()

        page = self.client.get(
            reverse("orders:track_detail", kwargs={"number": self.order.number})
        )

        self.assertContains(page, "Заказ отменён")
        self.assertContains(page, "Отменён оператором")
        self.assertEqual(page.context["cancellation"].status, Order.Status.CANCELLED)

    def test_detail_shows_positions_and_totals(self):
        self.track()

        page = self.client.get(
            reverse("orders:track_detail", kwargs={"number": self.order.number})
        )

        self.assertContains(page, "2 шт. ×")
        self.assertContains(page, "499")
        self.assertContains(page, "Самара, ул. Ленинградская, 1")

    def test_detail_404_for_unknown_number(self):
        response = self.client.get(
            reverse("orders:track_detail", kwargs={"number": "FM-20260101-AAAAA"})
        )

        self.assertEqual(response.status_code, 404)


class TrackingStepsTests(TestCase):
    def make_order(self, status):
        return Order.objects.create(
            customer_name="Иван",
            phone="+70000000000",
            status=status,
        )

    def test_new_order_marks_first_step_current(self):
        order = self.make_order(Order.Status.NEW)
        OrderStatusEvent.objects.create(order=order, status=Order.Status.NEW)

        steps, _ = build_tracking(order)

        self.assertTrue(steps[0]["is_done"])
        self.assertTrue(steps[0]["is_current"])
        self.assertFalse(steps[1]["is_done"])

    def test_delivering_order_marks_first_three_steps(self):
        order = self.make_order(Order.Status.DELIVERING)
        for status in (Order.Status.NEW, Order.Status.CONFIRMED, Order.Status.DELIVERING):
            OrderStatusEvent.objects.create(order=order, status=status)

        steps, _ = build_tracking(order)

        self.assertEqual([step["is_done"] for step in steps], [True, True, True, False])
        self.assertTrue(steps[2]["is_current"])

    def test_cancelled_order_keeps_reached_steps(self):
        order = self.make_order(Order.Status.CANCELLED)
        OrderStatusEvent.objects.create(order=order, status=Order.Status.NEW)
        OrderStatusEvent.objects.create(order=order, status=Order.Status.CANCELLED)

        steps, events = build_tracking(order)

        self.assertTrue(steps[0]["is_done"])
        self.assertFalse(steps[0]["is_current"])
        self.assertFalse(steps[1]["is_done"])
        self.assertIn(Order.Status.CANCELLED, events)


class OrderAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser(
            username="root",
            email="root@example.com",
            password="secret-pass-123",
        )
        cls.order = Order.objects.create(
            customer_name="Иван",
            phone="+70000000000",
            status=Order.Status.NEW,
        )
        OrderStatusEvent.objects.create(order=cls.order, status=Order.Status.NEW)

    def setUp(self):
        self.client.force_login(self.user)

    def test_action_changes_status_and_writes_history(self):
        response = self.client.post(
            reverse("admin:orders_order_changelist"),
            {
                "action": "mark_confirmed",
                "_selected_action": [str(self.order.pk)],
                "select_across": "0",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.CONFIRMED)
        self.assertTrue(
            self.order.status_events.filter(
                status=Order.Status.CONFIRMED,
                comment="Подтверждён оператором",
            ).exists()
        )

    def test_save_model_logs_manual_status_change(self):
        admin_instance = OrderAdmin(Order, AdminSite())
        request = RequestFactory().post("/admin/orders/order/", {})
        request.user = self.user
        self.order.status = Order.Status.DELIVERING

        admin_instance.save_model(request, self.order, form=None, change=True)

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.DELIVERING)
        self.assertTrue(
            self.order.status_events.filter(
                status=Order.Status.DELIVERING,
                comment="Статус изменён в админке",
            ).exists()
        )
