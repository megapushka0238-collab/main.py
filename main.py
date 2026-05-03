import logging
from typing import Dict, Set

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    PreCheckoutQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# ===== CONFIGURATION =====
BOT_TOKEN = "8519594701:AAH-SMlovPFRj_sOw2IhlNvC-56--fDa--g"  # Replace with your bot token
MANAGER_ID = 8348555758        # Replace with manager's Telegram user ID
CARD_NUMBER = "2200701213863662"  # Card number for manual payment
MANAGER_USERNAME = "@ElixirManagerElixirManager"  # Manager's username for contact message

# Tariff data: days, price in RUB, price in Stars
TARIFFS = {
    "7": {"days": 7, "price_rub": 199, "price_stars": 150, "title": "Elixir | 7 дней"},
    "30": {"days": 30, "price_rub": 350, "price_stars": 250, "title": "Elixir | 30 дней"},
    "forever": {"days": "Навсегда", "price_rub": 1100, "price_stars": 750, "title": "Elixir | Навсегда"},
}

# Set to track users who already got the /start welcome notification
started_users: Set[int] = set()

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


# ===== HELPER FUNCTIONS =====
async def notify_manager(context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    """Send a notification to the manager."""
    try:
        await context.bot.send_message(chat_id=MANAGER_ID, text=text)
    except Exception as e:
        logger.error(f"Failed to notify manager: {e}")


def get_tariff_info(tariff_key: str) -> dict:
    """Return tariff data for the given key."""
    return TARIFFS.get(tariff_key)


# ===== HANDLERS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /start command."""
    user = update.effective_user
    user_id = user.id
    username = user.username or "No username"

    # Welcome message
    welcome_text = (
        "Вас приветствует @ElixirStand\n\n"
        "Наши преимущества:\n"
        "- Реальный софт без root-прав. Никаких банов.\n"
        "- Топ функций: Aimbot, ESP, Wallhack, Radar.\n"
        "- Облачный скинченжер, сохраняй и меняй скины в облаке"
    )
    keyboard = [[InlineKeyboardButton("Приобрести товар", callback_data="buy")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

    # Notify manager on first start only
    if user_id not in started_users:
        started_users.add(user_id)
        await notify_manager(
            context,
            f"🆕 Новый пользователь запустил бота:\n"
            f"👤 @{username} (ID: {user_id})"
        )


async def buy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show tariff selection menu."""
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("Elixir | 7 дней", callback_data="tariff_7")],
        [InlineKeyboardButton("Elixir | 30 дней", callback_data="tariff_30")],
        [InlineKeyboardButton("Elixir | Навсегда", callback_data="tariff_forever")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "Выберите тариф ниже 👇", reply_markup=reply_markup
    )


async def tariff_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle tariff selection, save tariff info, show payment method menu."""
    query = update.callback_query
    await query.answer()

    tariff_key = query.data.split("_")[1]  # "7", "30", or "forever"
    tariff = get_tariff_info(tariff_key)
    if not tariff:
        await query.edit_message_text("Ошибка: тариф не найден.")
        return

    # Save tariff info in user_data for later use (payment)
    context.user_data["selected_tariff"] = tariff_key
    context.user_data["tariff_title"] = tariff["title"]
    context.user_data["price_rub"] = tariff["price_rub"]

    # Show payment method menu
    text = (
        f"Товар: {tariff['title']}\n"
        f"Цена: {tariff['price_rub']} ₽\n\n"
        "Выберите способ оплаты ниже 👇"
    )
    keyboard = [
        [InlineKeyboardButton("⭐ Telegram Stars", callback_data="pay_stars")],
        [InlineKeyboardButton("💳 Картой (перевод)", callback_data="pay_card")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)


async def pay_stars_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send Telegram Stars invoice."""
    query = update.callback_query
    await query.answer()

    tariff_key = context.user_data.get("selected_tariff")
    if not tariff_key:
        await query.edit_message_text("Ошибка: выберите тариф заново.")
        return

    tariff = get_tariff_info(tariff_key)
    if not tariff:
        await query.edit_message_text("Ошибка: тариф не найден.")
        return

    title = tariff["title"]
    stars_amount = tariff["price_stars"]
    payload = f"stars_{tariff_key}_{update.effective_user.id}"

    # Create invoice for Telegram Stars
    await context.bot.send_invoice(
        chat_id=update.effective_chat.id,
        title=title,
        description=f"Оплата через Telegram Stars за {title}",
        payload=payload,
        provider_token="",  # Required for Stars, leave empty
        currency="XTR",      # XTR is the currency code for Telegram Stars
        prices=[LabeledPrice(label=title, amount=stars_amount)],
        need_name=False,
        need_phone_number=False,
        need_email=False,
        is_flexible=False,
    )


async def pay_card_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show card payment details and a 'I paid' button."""
    query = update.callback_query
    await query.answer()

    price_rub = context.user_data.get("price_rub")
    if not price_rub:
        await query.edit_message_text("Ошибка: выберите тариф заново.")
        return

    text = (
        f"Способ оплаты: Картой (перевод)\n"
        f"Сумма к оплате: {price_rub} ₽\n\n"
        f"Отправьте на данную карту сумму, равную стоимости товара.\n"
        f"💳 {CARD_NUMBER}\n\n"
        "После перевода нажмите кнопку ниже."
    )
    keyboard = [[InlineKeyboardButton("Я оплатил", callback_data="confirm_paid")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)


async def confirm_paid_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """User clicked 'I paid' for card transfer. Notify manager."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    username = user.username or "No username"
    tariff_title = context.user_data.get("tariff_title", "неизвестный тариф")
    days = TARIFFS.get(context.user_data.get("selected_tariff", {}), {}).get("days", "?")

    # Notify manager
    await notify_manager(
        context,
        f"💰 Пользователь сообщил об оплате картой:\n"
        f"👤 @{username} (ID: {user.id})\n"
        f"📦 Товар: {tariff_title} (дней: {days})\n"
        f"💳 Способ: Картой (перевод)\n"
        f"⚠️ Требуется ручная проверка."
    )

    # Clear tariff data
    context.user_data.pop("selected_tariff", None)
    context.user_data.pop("tariff_title", None)
    context.user_data.pop("price_rub", None)

    # Acknowledge user
    await query.edit_message_text(
        f"✅ Ваше уведомление отправлено менеджеру {MANAGER_USERNAME}.\n"
        f"Ожидайте подтверждения."
    )


async def pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Answer the pre-checkout query (required for Stars payment)."""
    query = update.pre_checkout_query
    await query.answer(ok=True)


async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle successful Stars payment."""
    user = update.effective_user
    username = user.username or "No username"
    payment = update.message.successful_payment

    # Extract tariff from payload (payload format: stars_{tariff_key}_{user_id})
    payload_parts = payment.invoice_payload.split("_")
    if len(payload_parts) >= 2:
        tariff_key = payload_parts[1]
    else:
        tariff_key = "unknown"

    tariff = get_tariff_info(tariff_key)
    if tariff:
        tariff_title = tariff["title"]
        days = tariff["days"]
    else:
        tariff_title = "неизвестный тариф"
        days = "?"

    # Notify user
    await update.message.reply_text(
        f"✅ Успешная покупка, свяжитесь с менеджером {MANAGER_USERNAME}."
    )

    # Notify manager
    await notify_manager(
        context,
        f"⭐ Пользователь оплатил через Telegram Stars:\n"
        f"👤 @{username} (ID: {user.id})\n"
        f"📦 Товар: {tariff_title} (дней: {days})\n"
        f"⭐ Сумма: {payment.total_amount} звёзд"
    )

    # Clear tariff data after successful purchase
    context.user_data.pop("selected_tariff", None)
    context.user_data.pop("tariff_title", None)
    context.user_data.pop("price_rub", None)


# ===== MAIN =====
def main() -> None:
    """Start the bot."""
    application = Application.builder().token(BOT_TOKEN).build()

    # Command handlers
    application.add_handler(CommandHandler("start", start))

    # Callback handlers
    application.add_handler(CallbackQueryHandler(buy_callback, pattern="^buy$"))
    application.add_handler(CallbackQueryHandler(tariff_callback, pattern="^tariff_"))
    application.add_handler(CallbackQueryHandler(pay_stars_callback, pattern="^pay_stars$"))
    application.add_handler(CallbackQueryHandler(pay_card_callback, pattern="^pay_card$"))
    application.add_handler(CallbackQueryHandler(confirm_paid_callback, pattern="^confirm_paid$"))

    # Payment handlers
    application.add_handler(PreCheckoutQueryHandler(pre_checkout))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))

    # Start polling
    application.run_polling()


if __name__ == "__main__":
    main()