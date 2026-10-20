/* ФрешМаркет — небольшие улучшения интерфейса без зависимостей. */
(function () {
    "use strict";

    /* Уведомления: закрыть вручную или автоматически через 7 секунд. */
    document.querySelectorAll("[data-toast]").forEach(function (toast) {
        var closeButton = toast.querySelector("[data-toast-close]");
        function remove() {
            toast.style.transition = "opacity 0.2s ease, transform 0.2s ease";
            toast.style.opacity = "0";
            toast.style.transform = "translateX(16px)";
            window.setTimeout(function () {
                toast.remove();
            }, 200);
        }
        if (closeButton) {
            closeButton.addEventListener("click", remove);
        }
        window.setTimeout(remove, 7000);
    });

    /* Счётчики количества: кнопки «−» и «+» рядом с полем. */
    document.querySelectorAll("[data-step]").forEach(function (button) {
        button.addEventListener("click", function () {
            var wrapper = button.closest(".stepper");
            var input = wrapper ? wrapper.querySelector("input[type='number']") : null;
            if (!input) {
                return;
            }
            var step = parseInt(button.getAttribute("data-step"), 10) || 0;
            var current = parseInt(input.value, 10);
            if (isNaN(current)) {
                current = parseInt(input.min, 10) || 1;
            }
            var min = input.min === "" ? 0 : parseInt(input.min, 10);
            var max = input.max === "" ? Infinity : parseInt(input.max, 10);
            var next = Math.min(Math.max(current + step, min), max);
            input.value = next;
            input.dispatchEvent(new Event("change", { bubbles: true }));
        });
    });

    /* Сортировка в каталоге применяется сразу после выбора. */
    document.querySelectorAll("[data-autosubmit]").forEach(function (control) {
        control.addEventListener("change", function () {
            if (control.form) {
                control.form.submit();
            }
        });
    });

    /* Оформление заказа: адрес нужен только для курьера. */
    var checkoutForm = document.querySelector(".checkout-form");
    var deliveryRadios = document.querySelectorAll("input[name='delivery_method']");
    var addressBlock = document.querySelector("[data-address-block]");
    var pickupBlock = document.querySelector("[data-pickup-block]");
    var addressInput = document.querySelector("input[name='address']");
    var summary = document.querySelector("[data-checkout-summary]");

    function formatMoney(amount) {
        try {
            return new Intl.NumberFormat("ru-RU", {
                style: "currency",
                currency: "RUB",
                minimumFractionDigits: 0,
                maximumFractionDigits: 2
            }).format(amount);
        } catch (error) {
            return amount + " ₽";
        }
    }

    function updateDelivery() {
        var checked = document.querySelector("input[name='delivery_method']:checked");
        if (!checked) {
            return;
        }
        var isPickup = checked.value === "pickup";

        if (addressBlock) {
            addressBlock.hidden = isPickup;
        }
        if (pickupBlock) {
            pickupBlock.hidden = !isPickup;
        }
        if (addressInput) {
            addressInput.required = !isPickup;
        }

        if (!summary) {
            return;
        }
        var subtotal = parseFloat(summary.getAttribute("data-subtotal")) || 0;
        var tariff = parseFloat(summary.getAttribute("data-delivery-price")) || 0;
        var freeFrom = parseFloat(summary.getAttribute("data-free-from")) || 0;
        var delivery = isPickup || subtotal >= freeFrom ? 0 : tariff;

        var deliveryValue = summary.querySelector("[data-delivery-value]");
        var totalValue = summary.querySelector("[data-total-value]");
        var deliveryLabel = summary.querySelector("[data-delivery-label]");
        var submitTotal = document.querySelector("[data-checkout-total]");

        if (deliveryValue) {
            deliveryValue.textContent = delivery === 0 ? "Бесплатно" : formatMoney(delivery);
        }
        if (deliveryLabel) {
            deliveryLabel.textContent = isPickup ? "(самовывоз)" : "(курьером)";
        }
        if (totalValue) {
            totalValue.textContent = formatMoney(subtotal + delivery);
        }
        if (submitTotal) {
            submitTotal.textContent = formatMoney(subtotal + delivery);
        }
        if (checkoutForm) {
            /* Не даём браузеру блокировать отправку из-за скрытого поля адреса. */
            checkoutForm.noValidate = true;
        }
    }

    if (deliveryRadios.length) {
        deliveryRadios.forEach(function (radio) {
            radio.addEventListener("change", updateDelivery);
        });
        updateDelivery();
    }
})();
