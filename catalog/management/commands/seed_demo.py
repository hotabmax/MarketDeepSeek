"""Демонстрационные данные магазина: категории и товары.

Запуск: python manage.py seed_demo
Повторный запуск обновляет существующие записи по slug, не создавая дублей.
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from catalog.models import Category, Product

CATEGORIES = [
    {
        "slug": "fruits-vegetables",
        "name": "Овощи и фрукты",
        "icon": "🥦",
        "color": "#eaf5e6",
        "description": "Свежий урожай каждый день",
        "sort_order": 1,
    },
    {
        "slug": "dairy",
        "name": "Молочное и яйца",
        "icon": "🥛",
        "color": "#eef4fb",
        "description": "Фермерское и проверенное",
        "sort_order": 2,
    },
    {
        "slug": "meat-fish",
        "name": "Мясо и рыба",
        "icon": "🍗",
        "color": "#fdf0ed",
        "description": "Охлаждённое, без заморозки",
        "sort_order": 3,
    },
    {
        "slug": "bakery",
        "name": "Хлеб и выпечка",
        "icon": "🥖",
        "color": "#fbf3e3",
        "description": "Печём каждое утро",
        "sort_order": 4,
    },
    {
        "slug": "grocery",
        "name": "Бакалея",
        "icon": "🌾",
        "color": "#f6f1e4",
        "description": "Крупы, масло, мука",
        "sort_order": 5,
    },
    {
        "slug": "drinks",
        "name": "Напитки",
        "icon": "🧃",
        "color": "#eaf3f7",
        "description": "Соки, вода, чай и кофе",
        "sort_order": 6,
    },
    {
        "slug": "sweets",
        "name": "Сладости",
        "icon": "🍫",
        "color": "#f7eef4",
        "description": "К чаю и для детей",
        "sort_order": 7,
    },
    {
        "slug": "frozen",
        "name": "Заморозка",
        "icon": "🧊",
        "color": "#edf3f6",
        "description": "Быстрые ужины и ягоды",
        "sort_order": 8,
    },
]

# slug, категория, название, эмодзи, цена, старая цена, единица, остаток, хит, описание
PRODUCTS = [
    # Овощи и фрукты
    ("tomaty-cherri", "fruits-vegetables", "Томаты черри", "🍅", "249.00", None, "500 г", 24, True,
     "Сладкие томаты черри с ветки. Идеальны для салата и перекуса."),
    ("ogurcy-gladkie", "fruits-vegetables", "Огурцы гладкие", "🥒", "139.00", "169.00", "кг", 30, False,
     "Хрустящие огурцы из теплиц Самарской области."),
    ("kartofel-molodoy", "fruits-vegetables", "Картофель молодой", "🥔", "69.00", None, "кг", 46, False,
     "Молодой картофель с тонкой кожурой — для варки и запекания."),
    ("yabloki-golden", "fruits-vegetables", "Яблоки Голден", "🍎", "159.00", None, "кг", 38, True,
     "Сочные яблоки с лёгкой кислинкой. Урожай этого сезона."),
    ("banany", "fruits-vegetables", "Бананы", "🍌", "119.00", None, "кг", 52, False,
     "Спелые бананы, сладкие и ароматные."),
    ("apelsiny", "fruits-vegetables", "Апельсины", "🍊", "179.00", "199.00", "кг", 28, False,
     "Сочные апельсины, богаты витамином C."),
    ("avokado", "fruits-vegetables", "Авокадо Хасс", "🥑", "129.00", None, "шт.", 18, True,
     "Спелое авокадо с маслянистой текстурой — для тостов и салатов."),
    ("salat-roman", "fruits-vegetables", "Салат Романо", "🥬", "89.00", None, "пучок", 12, False,
     "Свежий хрустящий салат в упаковке."),
    ("vinograd", "fruits-vegetables", "Виноград Кишмиш", "🍇", "249.00", None, "500 г", 20, False,
     "Без косточек, очень сладкий."),
    ("klubnika", "fruits-vegetables", "Клубника", "🍓", "349.00", "399.00", "500 г", 10, True,
     "Ароматная клубника из Краснодарского края."),

    # Молочное
    ("moloko-3-2", "dairy", "Молоко 3,2%", "🥛", "99.00", None, "1 л", 40, True,
     "Пастеризованное молоко от фермерского хозяйства."),
    ("kefir-1", "dairy", "Кефир 1%", "🥛", "89.00", None, "1 л", 26, False,
     "Классический кефир с мягким вкусом."),
    ("smetana-15", "dairy", "Сметана 15%", "🥣", "129.00", None, "300 г", 22, False,
     "Густая сметана из натуральных сливок."),
    ("tvorog-5", "dairy", "Творог 5%", "🧀", "149.00", "179.00", "350 г", 18, False,
     "Расссыпчатый творог, подходит для завтрака и выпечки."),
    ("maslo-slivochnoe", "dairy", "Масло сливочное 82,5%", "🧈", "189.00", None, "180 г", 24, False,
     "Натуральное сливочное масло без растительных жиров."),
    ("yayca-s1", "dairy", "Яйца куриные С1", "🥚", "129.00", None, "10 шт.", 34, True,
     "Свежие яйца первой категории."),
    ("syr-gauda", "dairy", "Сыр Гауда", "🧀", "459.00", "499.00", "300 г", 14, False,
     "Полутвёрдый сыр с ореховым вкусом, нарезка."),
    ("yogurt-naturalny", "dairy", "Йогурт натуральный", "🥛", "79.00", None, "290 г", 16, False,
     "Густой йогурт без сахара — добавьте ягоды и мёд."),

    # Мясо и рыба
    ("kurinaya-grudka", "meat-fish", "Куриная грудка", "🍗", "389.00", None, "кг", 20, True,
     "Охлаждённая грудка без кожи. Отличный источник белка."),
    ("farsh-govyazhiy", "meat-fish", "Фарш говяжий", "🥩", "429.00", None, "500 г", 15, False,
     "Свежий фарш из говядины, помол средний."),
    ("govyadina-lopatka", "meat-fish", "Говядина, лопатка", "🥩", "699.00", "749.00", "кг", 9, False,
     "Мясо для тушения и супов. Охлаждённое."),
    ("svinina-sheya", "meat-fish", "Свинина, шея", "🥓", "519.00", None, "кг", 12, False,
     "Сочная шея для шашлыка и запекания."),
    ("losos", "meat-fish", "Лосось, стейк", "🐟", "1290.00", None, "кг", 7, True,
     "Свежий лосось, нарезаем по вашему запросу."),
    ("treska", "meat-fish", "Треска, филе", "🐟", "549.00", "599.00", "кг", 11, False,
     "Филе трески без костей в вакуумной упаковке."),
    ("kolbasa-kurina", "meat-fish", "Колбаса куриная", "🌭", "289.00", None, "400 г", 13, False,
     "Варёная колбаса из куриного филе."),

    # Хлеб
    ("hleb-borodinskiy", "bakery", "Хлеб Бородинский", "🍞", "69.00", None, "400 г", 30, True,
     "Ржаной хлеб с кориандром и тмином."),
    ("baget-francuzskiy", "bakery", "Багет французский", "🥖", "89.00", None, "шт.", 24, False,
     "Хрустящий багет с нежной мякотью."),
    ("kruassan-slivochnyy", "bakery", "Круассан сливочный", "🥐", "79.00", "99.00", "шт.", 18, True,
     "Слоёный круассан на натуральном масле."),
    ("lavash-tonskiy", "bakery", "Лаваш тонкий", "🫓", "59.00", None, "шт.", 22, False,
     "Тонкий лаваш для дома и на гриль."),
    ("ciabatta", "bakery", "Чиабатта с оливами", "🥖", "119.00", None, "шт.", 12, False,
     "Итальянский хлеб с оливками и розмарином."),
    ("pirozhki-s-yablokom", "bakery", "Пирожки с яблоком", "🥟", "49.00", None, "шт.", 20, False,
     "Домашние пирожки из дрожжевого теста."),

    # Бакалея
    ("ris-basmati", "grocery", "Рис Басмати", "🍚", "129.00", None, "900 г", 26, False,
     "Длиннозёрный ароматный рис."),
    ("grechka-yadro", "grocery", "Гречка ядрица", "🌾", "99.00", "119.00", "900 г", 33, True,
     "Цельная гречневая крупа первого сорта."),
    ("makarony-spaghetti", "grocery", "Спагетти", "🍝", "89.00", None, "450 г", 30, False,
     "Макароны из твёрдых сортов пшеницы."),
    ("maslo-podsolnechnoe", "grocery", "Масло подсолнечное", "🌻", "149.00", None, "1 л", 25, False,
     "Нерафинированное масло первого отжима."),
    ("muka-vs", "grocery", "Мука пшеничная в/с", "🌾", "79.00", None, "2 кг", 28, False,
     "Мука высшего сорта для выпечки и домашнего хлеба."),
    ("sahar", "grocery", "Сахар-песок", "🧂", "89.00", None, "1 кг", 35, False,
     "Сахар белый кристаллический."),
    ("sol", "grocery", "Соль поваренная", "🧂", "39.00", None, "1 кг", 40, False,
     "Соль помола №1, йодированная."),
    ("med-cvetochny", "grocery", "Мёд цветочный", "🍯", "349.00", "399.00", "500 г", 15, True,
     "Натуральный мёд с разнотравья."),

    # Напитки
    ("sok-yablochny", "drinks", "Сок яблочный", "🧃", "119.00", None, "1 л", 27, False,
     "Сок прямого отжима без добавленного сахара."),
    ("voda-mineralnaya", "drinks", "Вода минеральная", "💧", "49.00", None, "1,5 л", 48, False,
     "Негазированная минеральная вода."),
    ("chay-cherny", "drinks", "Чай чёрный, 25 пакетиков", "🍵", "249.00", None, "упак.", 20, False,
     "Крепкий чёрный чай в пакетиках."),
    ("kofe-molotyy", "drinks", "Кофе молотый", "☕", "599.00", "649.00", "250 г", 13, True,
     "Кофе средней обжарки, арабика."),
    ("limonad-domashniy", "drinks", "Лимонад домашний", "🍋", "99.00", None, "0,5 л", 18, False,
     "Освежающий лимонад с мятой."),

    # Сладости
    ("shokolad-gorkiy", "sweets", "Шоколад горький 70%", "🍫", "129.00", None, "90 г", 30, False,
     "Плитка тёмного шоколада с какао 70%."),
    ("pechenye-ovsyanoe", "sweets", "Печенье овсяное", "🍪", "149.00", "169.00", "300 г", 22, True,
     "Овсяное печенье с изюмом, без пальмового масла."),
    ("zefir-vanilnyy", "sweets", "Зефир ванильный", "🍬", "119.00", None, "250 г", 19, False,
     "Мягкий зефир на яблочном пектине."),
    ("pranik-tulskiy", "sweets", "Пряник тульский", "🥮", "89.00", None, "140 г", 24, False,
     "Пряник с клюквенной начинкой."),

    # Заморозка
    ("pelmeni-domashnie", "frozen", "Пельмени домашние", "🥟", "349.00", None, "700 г", 17, False,
     "Пельмени ручной лепки из говядины и свинины."),
    ("yagody-zamorozhennye", "frozen", "Смородина замороженная", "🫐", "249.00", "299.00", "300 г", 20, True,
     "Быстрая заморозка сохраняет витамины."),
    ("morozhenoe-plombir", "frozen", "Мороженое пломбир", "🍦", "219.00", None, "450 г", 16, False,
     "Классический пломбир в ванночке."),
    ("pizza-margarita", "frozen", "Пицца Маргарита", "🍕", "299.00", None, "1 шт.", 14, False,
     "Замороженная пицца, готова за 12 минут."),
]


class Command(BaseCommand):
    help = "Создаёт демонстрационные категории и товары (можно запускать повторно)."

    @transaction.atomic
    def handle(self, *args, **options):
        categories = {}
        for data in CATEGORIES:
            category, _ = Category.objects.update_or_create(
                slug=data["slug"],
                defaults={key: value for key, value in data.items() if key != "slug"},
            )
            categories[category.slug] = category

        created = 0
        for (
            slug,
            category_slug,
            name,
            emoji,
            price,
            old_price,
            unit,
            stock,
            featured,
            description,
        ) in PRODUCTS:
            _, was_created = Product.objects.update_or_create(
                slug=slug,
                defaults={
                    "category": categories[category_slug],
                    "name": name,
                    "emoji": emoji,
                    "description": description,
                    "price": Decimal(price),
                    "old_price": Decimal(old_price) if old_price else None,
                    "unit": unit,
                    "stock": stock,
                    "is_featured": featured,
                    "is_available": True,
                },
            )
            created += int(was_created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Готово: категорий — {len(categories)}, товаров — {len(PRODUCTS)} "
                f"(новых: {created})."
            )
        )
