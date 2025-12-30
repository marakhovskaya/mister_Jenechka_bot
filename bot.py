import os
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from menu import MENU, SURPRISES

# Токен берём из переменной окружения
TOKEN = os.getenv("TELEGRAM_TOKEN")

# Админ username (можно изменить)
ADMIN_USERNAME = "твое_имя_админа"

# Файлы для хранения состояния
ORDER_FILE = "current_order.json"
USERS_FILE = "active_users.json"
REQUEST_FILE = "last_request.json"

# ======== Вспомогательные функции ========
def load_json(filename):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("🍽 Что приготовить", callback_data="menu_main")],
        [InlineKeyboardButton("🛒 Список покупок", callback_data="shopping")],
        [InlineKeyboardButton("🎁 Сюрприз", callback_data="surprise")],
        [InlineKeyboardButton("🧺 Моя корзина", callback_data="cart")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_category_buttons():
    keyboard = []
    for key, cat in MENU.items():
        keyboard.append([InlineKeyboardButton(cat["title"], callback_data=f"category_{key}")])
    keyboard.append([InlineKeyboardButton("⬅ Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(keyboard)

def get_item_buttons(category):
    keyboard = []
    for item in MENU[category]["items"]:
        keyboard.append([InlineKeyboardButton(item, callback_data=f"item_{category}_{item}")])
    keyboard.append([InlineKeyboardButton("🧺 В корзину", callback_data="cart")])
    keyboard.append([InlineKeyboardButton("⬅ Назад", callback_data="menu_main")])
    return InlineKeyboardMarkup(keyboard)

def get_cart_buttons():
    keyboard = [
        [InlineKeyboardButton("Отправить заказ", callback_data="send_order")],
        [InlineKeyboardButton("Очистить корзину", callback_data="clear_cart")],
        [InlineKeyboardButton("⬅ Назад", callback_data="menu_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ======== Хэндлеры ========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    users = load_json(USERS_FILE)
    users[user.username] = user.id
    save_json(USERS_FILE, users)
    await update.message.reply_text(f"Привет, {user.first_name}! Чем я могу тебе помочь?", reply_markup=get_main_menu())

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user = query.from_user
    orders = load_json(ORDER_FILE)
    last_req = load_json(REQUEST_FILE)

    # === Главные кнопки ===
    if data == "menu_main":
        await query.edit_message_text("Выберите категорию:", reply_markup=get_category_buttons())
    elif data.startswith("category_"):
        cat = data.split("_")[1]
        await query.edit_message_text(f"Выберите блюдо из {MENU[cat]['title']}:", reply_markup=get_item_buttons(cat))
    elif data.startswith("item_"):
        _, cat, item = data.split("_", 2)
        user_cart = orders.get(user.username, [])
        user_cart.append(item)
        orders[user.username] = user_cart
        save_json(ORDER_FILE, orders)
        await query.edit_message_text(f"✅ {item} добавлено в корзину", reply_markup=get_item_buttons(cat))
    elif data == "cart":
        user_cart = orders.get(user.username, [])
        text = "🧺 Ваша корзина:\n" + "\n".join(user_cart) if user_cart else "Ваша корзина пуста."
        await query.edit_message_text(text, reply_markup=get_cart_buttons())
    elif data == "clear_cart":
        orders[user.username] = []
        save_json(ORDER_FILE, orders)
        await query.edit_message_text("Корзина очищена.", reply_markup=get_cart_buttons())
    elif data == "send_order":
        user_cart = orders.get(user.username, [])
        if not user_cart:
            await query.edit_message_text("Корзина пуста.", reply_markup=get_cart_buttons())
        else:
            orders[user.username] = []
            save_json(ORDER_FILE, orders)
            # Отправляем админу сообщение
            await context.bot.send_message(chat_id=user.id, text="✅ Ваш заказ отправлен администратору.")
            await context.bot.send_message(chat_id=user.id, text=f"Ваш заказ: {user_cart}")
            if ADMIN_USERNAME in load_json(USERS_FILE):
                admin_id = load_json(USERS_FILE)[ADMIN_USERNAME]
                await context.bot.send_message(chat_id=admin_id, text=f"📩 Новый заказ от @{user.username}: {user_cart}")
    elif data == "shopping":
        last_req["shopping"] = user.username
        save_json(REQUEST_FILE, last_req)
        if ADMIN_USERNAME in load_json(USERS_FILE):
            admin_id = load_json(USERS_FILE)[ADMIN_USERNAME]
            await context.bot.send_message(chat_id=admin_id, text=f"📩 @{user.username} запросил список покупок")
        await query.edit_message_text("✅ Запрос отправлен администратору. Ожидайте ответа.")
    elif data == "surprise":
        last_req["surprise"] = user.username
        save_json(REQUEST_FILE, last_req)
        await query.edit_message_text("🎁 Ждите сюрприз в течение 24 часов")

    elif data == "back_main":
        await query.edit_message_text("Главное меню:", reply_markup=get_main_menu())

async def admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.username != ADMIN_USERNAME:
        await update.message.reply_text("❌ Только админ может использовать эту команду.")
        return
    last_req = load_json(REQUEST_FILE)
    msg = update.message.text
    # Отправляем ответ пользователю
    for req_type, username in last_req.items():
        users = load_json(USERS_FILE)
        if username in users:
            await context.bot.send_message(chat_id=users[username], text=f"📩 Ответ администратора: {msg}")
    save_json(REQUEST_FILE, {})

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("/start - запустить бот\n/help - помощь")

# ======== Основная функция ========
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_message))
    app.add_handler(CallbackQueryHandler(button))

    print("🤖 Бот запущен")
    app.run_polling()

if __name__ == "__main__":
    main()
