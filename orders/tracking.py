"""Этапы и история отслеживания заказа."""

from .models import Order

TRACKING_STEPS = (
    (Order.Status.NEW, "Заказ принят", "Мы получили заказ и уже собираем продукты."),
    (Order.Status.CONFIRMED, "Заказ подтверждён", "Оператор подтвердил состав заказа и время доставки."),
    (Order.Status.DELIVERING, "В доставке", "Курьер везёт заказ по указанному адресу."),
    (Order.Status.DONE, "Выполнен", "Заказ доставлен. Спасибо, что выбираете нас!"),
)

ACTIVE_STATUSES = tuple(status for status, _, _ in TRACKING_STEPS)


def build_tracking(order):
    """Собирает шаги таймлайна и словарь событий истории по статусам."""
    events = {}
    for event in order.status_events.all():
        events[event.status] = event

    if order.status == Order.Status.CANCELLED:
        reached_index = max(
            (index for index, status in enumerate(ACTIVE_STATUSES) if status in events),
            default=-1,
        )
    elif order.status in ACTIVE_STATUSES:
        reached_index = ACTIVE_STATUSES.index(order.status)
    else:
        reached_index = -1

    steps = []
    for index, (status, title, description) in enumerate(TRACKING_STEPS):
        steps.append(
            {
                "status": status,
                "title": title,
                "description": description,
                "is_done": index <= reached_index,
                "is_current": index == reached_index and order.status != Order.Status.CANCELLED,
                "event": events.get(status),
            }
        )
    return steps, events
