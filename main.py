import logging
import json
import os

from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CallbackContext, CommandHandler

TOKEN = "Input here your token"

# Отримання абсолютного шляху до файлу data.json
data_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")


# Захаркоджені категорії
categories = ['Їжа та продукти', 'Навчання та саморозвиток', 'Одяг', 'Розваги']
# Баланс гаманця
balance = 0
# Словники для збереження витрат за місяць, тиждень та всі витрати
expenses_month = {}
all_expenses = []
# Для збереження витрат з датами
all_expenses_with_dates = []
# Для збереження доходів
incomes_month = {}
all_incomes = []
all_incomes_with_dates = []


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logging.getLogger("httpx").setLevel(logging.WARNING)


async def start(update: Update, context: CallbackContext) -> None:
    logging.info('Command "start" was triggered!')
    await update.message.reply_text(
        "Вітаю у моєму Finance-tracker Bot! \n"
        "Команди: \n"
        "Список команд: /help\n"
        "Баланс гаманця: /balance\n"
        "Дохід: /add_income [сума]\n"
        "Витрати: /add_expense [категорія] [сума]\n"
        "Список доступних категорій: /list \n"
        "Переглянути всі доходи: /view_all_incomes\n"
        "Переглянути всі витрати: /view_all_expenses\n"
        "Переглянути витрати за місяць: /view_monthly_expenses\n"
        "Видалити дохід: /delete_income [%Y-%m-%d %H:%M:%S]\n"
        "Видалити витрату: /delete_expense [%Y-%m-%d %H:%M:%S]\n"
    )


async def show_help(update: Update, context: CallbackContext) -> None:
    logging.info('Command "help" was triggered!')
    await update.message.reply_text(
        "Команди: \n"
        "Баланс гаманця: /balance\n"
        "Дохід: /add_income [сума]\n"
        "Витрати: /add_expense [категорія] [сума]\n"
        "Список доступних категорій: /list \n"
        "Переглянути всі доходи: /view_all_incomes\n"
        "Переглянути всі витрати: /view_all_expenses\n"
        "Переглянути витрати за місяць: /view_monthly_expenses\n"
        "Видалити дохід: /delete_income [%Y-%m-%d %H:%M:%S]\n"
        "Видалити витрату: /delete_expense [%Y-%m-%d %H:%M:%S]\n"
    )


async def add_income(update: Update, context: CallbackContext) -> None:
    global balance
    logging.info('Command "add_income" was triggered')
    amount = float(context.args[0])
    balance += amount
    await update.message.reply_text(f"Дохід на суму {amount} був успішно доданий")
    await add_all_incomes(update, context, amount)
    save_data()


async def add_expense(update: Update, context: CallbackContext) -> None:
    global balance
    logging.info('Command "add_expense" was triggered')

    if len(context.args) < 2:
        await update.message.reply_text("Ви не ввели категорію або суму витрати.")
        return

    expense_category = " ".join(context.args[:-1])
    amount = float(context.args[-1])

    if expense_category not in categories:
        await update.message.reply_text("Невірна назва категорії!\n\n Список категорій:\n - " + ", \n\t- ".join(categories))
        return

    if balance >= amount:
        balance -= amount
        await update.message.reply_text(
            f"Витрата у категорії  ' {expense_category} ' на суму {amount} була успішно додана.")
        update_expenses(expense_category, amount, datetime.now())
        add_monthly_expenses(update, context, expense_category, amount)
        save_data()
    else:
        await update.message.reply_text("Недостатньо коштів на балансі для виконання цієї операції.")


async def my_balance(update: Update, context: CallbackContext):
    load_data()
    await update.message.reply_text(f"Баланс вашого гаманця становить {balance}")


async def delete_income(update: Update, context: CallbackContext) -> None:
    logging.info('Command "delete_income" was triggered')
    delete_time_str = ' '.join(context.args)
    try:
        delete_time = datetime.strptime(delete_time_str, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        await update.message.reply_text("Невірний формат часу. Використовуйте формат 'YYYY-MM-DD HH:MM:SS'.")
        return

    deleted_income = None
    for income in all_incomes:
        if income['date'].replace(microsecond=0) == delete_time.replace(microsecond=0):
            deleted_income = income
            all_incomes.remove(income)
            break

    if deleted_income:
        amount = deleted_income['amount']
        date = deleted_income['date'].strftime('%Y-%m-%d %H:%M:%S')
        key = (deleted_income['date'].year, deleted_income['date'].month)
        incomes_month[key].remove(deleted_income)
        await update.message.reply_text(f"Дохід {amount} на дату {date} був успішно видалений.")
        save_data()
    else:
        await update.message.reply_text("В цей час не було додано доходу.")


async def delete_expense(update: Update, context: CallbackContext) -> None:
    logging.info('Command "delete_expense" was triggered')
    delete_time_str = ' '.join(context.args)
    try:
        delete_time = datetime.strptime(delete_time_str, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        await update.message.reply_text("Невірний формат часу. Використовуйте формат 'YYYY-MM-DD HH:MM:SS'.")
        return

    deleted_expense = None
    for expense in all_expenses:
        if 'date' in expense and expense['date'].replace(microsecond=0) == delete_time.replace(microsecond=0):
            deleted_expense = expense
            all_expenses.remove(expense)
            break
    if deleted_expense:
        amount = deleted_expense['amount']
        date = deleted_expense['date'].strftime('%Y-%m-%d %H:%M:%S')
        key = (deleted_expense['date'].year, deleted_expense['date'].month)
        if deleted_expense in expenses_month[key]:
            expenses_month[key].remove(deleted_expense)
        await update.message.reply_text(f"Витрата {amount} на дату {date} була успішно видалений.")
        save_data()
    else:
        await update.message.reply_text("В цей час не було витрати .")


async def list_categories(update: Update, context: CallbackContext) -> None:
    logging.info('Command "list_categories" was triggered!')
    categories_text = "\n• ".join(categories)
    await update.message.reply_text(f"Список доступних категорій:\n• {categories_text}")


async def add_all_incomes(update: Update, context: CallbackContext, amount: float) -> None:
    today = datetime.now()
    key = (today.year, today.month)
    incomes_month[key] = incomes_month.get(key, [])
    incomes_month[key].append({'amount': amount, 'date': today})
    all_incomes.append({'amount': amount, 'date': today})


async def view_all_incomes(update: Update, context: CallbackContext) -> None:
    global incomes_month
    logging.info('Command "view_all_incomes" was triggered')
    if not incomes_month:
        await update.message.reply_text("Список доходів порожній")
    else:
        incomes_text = ""
        for date, incomes in incomes_month.items():
            incomes_text += f"{date[0]}-{date[1]}:\n"
            for income in incomes:
                incomes_text += f"    Сума: {income['amount']}\n"
                incomes_text += f"    Дата: {income['date']}\n"
            incomes_text += "\n"
        await update.message.reply_text(f"Доходи:\n{incomes_text}")


def update_incomes(amount: float) -> None:
    global all_incomes
    all_incomes.append({'amount': amount})
    save_data()


def update_expenses(expense_category: str, amount: float, date: datetime) -> None:
    global all_expenses
    all_expenses.append({'category': expense_category, 'amount': amount, 'date': date})


async def view_all_expenses(update: Update, context: CallbackContext) -> None:
    global all_expenses
    logging.info('Command "view_all_expenses" was triggered')
    if not all_expenses:
        await update.message.reply_text("Список витрат порожній")
    else:
        all_expenses_text = "\n".join(f"{expense['category']} - {expense['amount']}" for expense in all_expenses)
        await update.message.reply_text(f"Список всіх витрат:\n{all_expenses_text}")


def add_monthly_expenses(update: Update, context: CallbackContext, category: str, amount: float) -> None:
    today = datetime.now()
    key = (today.year, today.month)
    expenses_month[key] = expenses_month.get(key, [])
    expenses_month[key].append({'category': category, 'amount': amount, 'date': today})
    all_expenses_with_dates.append({'category': category, 'amount': amount, 'date': today})
    save_data()


async def view_monthly_expenses(update: Update, context: CallbackContext) -> None:
    global expenses_month
    logging.info('Command "view_monthly_expenses" was triggered')
    if not expenses_month:
        await update.message.reply_text("Список витрат за місяць порожній")
    else:
        expenses_text = ""
        for date, expenses in expenses_month.items():
            expenses_text += f"{date[0]}-{date[1]}:\n"
            for expense in expenses:
                expenses_text += f"    •Категорія: {expense['category']}\n"
                expenses_text += f"    Сума: {expense['amount']}\n"
                expenses_text += f"    Дата: {expense['date']}\n"
            expenses_text += "\n"
        await update.message.reply_text(f"Витрати за місяць:\n{expenses_text}")


def load_data():
    global balance, expenses_month, all_expenses_with_dates, all_incomes
    try:
        with open(data_file_path, "r") as file:
            data = json.load(file)
            balance = data.get("balance", 0)
            expenses_month = data.get("expenses_month", {})
            all_expenses_with_dates = data.get("all_expenses_with_dates", [])
            all_incomes = data.get("all_incomes", [])
    except FileNotFoundError:
        # Якщо файл data.json не знайдено, початкові значення даних
        balance = 0
        expenses_month = {}
        all_expenses_with_dates = []
        all_incomes = []


def save_data():
    def datetime_serializer(obj):
        if isinstance(obj, datetime):
            return obj.strftime('%Y-%m-%d %H:%M:%S')
        raise TypeError(f"Object of type '{obj.__class__.__name__}' is not JSON serializable")

    data = {
        "balance": balance,
        "expenses_month": {str(key): value for key, value in expenses_month.items()},
        "all_expenses_with_dates": all_expenses_with_dates,
        "all_incomes": all_incomes
    }

    with open(data_file_path, "w") as file:
        json.dump(data, file, default=datetime_serializer)


def run():
    app = ApplicationBuilder().token(TOKEN).build()
    logging.info("Application built succesfully")

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", show_help))
    app.add_handler(CommandHandler("balance", my_balance))
    app.add_handler(CommandHandler("add_income", add_income))
    app.add_handler(CommandHandler("add_expense", add_expense))
    app.add_handler(CommandHandler("list", list_categories))
    app.add_handler(CommandHandler("view_all_expenses", view_all_expenses))
    app.add_handler(CommandHandler("view_monthly_expenses", view_monthly_expenses))
    app.add_handler(CommandHandler("view_all_incomes", view_all_incomes))
    app.add_handler(CommandHandler("delete_income", delete_income))
    app.add_handler(CommandHandler("delete_expense", delete_expense))

    save_data()
    load_data()

    app.run_polling()

    load_data()


if __name__ == "__main__":
    run()
