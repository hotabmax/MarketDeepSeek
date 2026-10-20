"""Каталог магазина: категории и товары."""

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from uuid import uuid4

from .utils import transliterate


class Category(models.Model):
    """Раздел каталога (овощи, молочное, бакалея...)."""

    name = models.CharField("Название", max_length=100)
    slug = models.SlugField("Слаг (URL)", max_length=120, unique=True)
    description = models.TextField("Описание", blank=True)
    icon = models.CharField("Иконка (эмодзи)", max_length=8, default="🛒")
    color = models.CharField(
        "Цвет подложки",
        max_length=7,
        default="#eaf5ec",
        help_text="HEX-цвет фона для карточек товаров раздела, например #eaf5ec",
    )
    sort_order = models.PositiveSmallIntegerField("Порядок вывода", default=0)
    is_active = models.BooleanField("Активна", default=True)

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"
        ordering = ("sort_order", "name")

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("catalog:category", kwargs={"category_slug": self.slug})


class ProductQuerySet(models.QuerySet):
    def available(self):
        """Товары, которые можно купить прямо сейчас."""
        return self.filter(is_available=True, stock__gt=0, category__is_active=True)

    def with_category(self):
        return self.select_related("category")


class Product(models.Model):
    """Товар магазина."""

    category = models.ForeignKey(
        Category,
        verbose_name="Категория",
        related_name="products",
        on_delete=models.PROTECT,
    )
    name = models.CharField("Название", max_length=150)
    slug = models.SlugField("Слаг (URL)", max_length=170, unique=True, blank=True)
    description = models.TextField("Описание", blank=True)
    search_text = models.TextField(
        "Строка поиска",
        blank=True,
        default="",
        editable=False,
        help_text="Нормализованные название и описание для поиска без учёта регистра.",
    )
    emoji = models.CharField("Эмодзи", max_length=8, default="🥕")
    image_url = models.URLField(
        "Ссылка на фото",
        blank=True,
        help_text="Необязательно. Если указана — показывается вместо эмодзи.",
    )
    price = models.DecimalField(
        "Цена",
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    old_price = models.DecimalField(
        "Старая цена",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Для отображения скидки. Должна быть выше текущей цены.",
    )
    unit = models.CharField("Единица", max_length=20, default="шт.")
    stock = models.PositiveIntegerField("Остаток на складе", default=0)
    is_available = models.BooleanField("Доступен к продаже", default=True)
    is_featured = models.BooleanField("Хит продаж", default=False)
    created_at = models.DateTimeField("Добавлен", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    objects = ProductQuerySet.as_manager()

    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товары"
        ordering = ("name",)
        indexes = [
            models.Index(fields=["category", "is_available"]),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._build_slug()
        self.search_text = self._build_search_text()
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            update_fields = set(update_fields)
            if {"name", "description"} & update_fields:
                update_fields.add("search_text")
            kwargs["update_fields"] = update_fields
        super().save(*args, **kwargs)

    def _build_search_text(self):
        """Нормализованная строка для поиска: SQLite не умеет регистронезависимый LIKE для кириллицы."""
        return " ".join(filter(None, (self.name, self.description))).casefold()

    def _build_slug(self):
        base = slugify(transliterate(self.name))[:160] or f"product-{uuid4().hex[:6]}"
        candidate = base
        counter = 2
        while Product.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
            candidate = f"{base}-{counter}"
            counter += 1
        return candidate

    def get_absolute_url(self):
        return reverse("catalog:detail", kwargs={"slug": self.slug})

    @property
    def in_stock(self):
        return self.is_available and self.stock > 0

    @property
    def stock_unit(self):
        """Единица остатка: для фасованных товаров считаем упаковки."""
        return "упак." if any(char.isdigit() for char in self.unit) else self.unit

    @property
    def has_discount(self):
        return self.old_price is not None and self.old_price > self.price

    @property
    def discount_percent(self):
        if not self.has_discount:
            return 0
        return round((self.old_price - self.price) / self.old_price * 100)
