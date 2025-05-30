from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
import sqlite3
from config import TOKEN, ADMIN_ID


# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('tutor_bot.db')
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS students (
        user_id INTEGER PRIMARY KEY,
        name TEXT,
        class TEXT
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tasks (
        task_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        task_text TEXT,
        photo_path TEXT,
        status TEXT,
        FOREIGN KEY (user_id) REFERENCES students(user_id)
    )
    ''')

    conn.commit()
    conn.close()


# Инициализируем БД
init_db()


# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я бот-репетитор по математике. Отправь мне задачу на проверку.")


# Обработчик задач
async def handle_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    task_text = update.message.text if update.message.text else "Фото задачи"

    if update.message.photo:
        photo = await update.message.photo[-1].get_file()
        photo_path = f"tasks/{user_id}_{photo.file_id}.jpg"
        await photo.download_to_drive(photo_path)
    else:
        photo_path = None

    conn = sqlite3.connect('tutor_bot.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO tasks (user_id, task_text, photo_path, status) VALUES (?, ?, ?, ?)',
                   (user_id, task_text, photo_path, 'pending'))
    conn.commit()
    conn.close()

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"Новая задача от ученика {user_id}!\nТекст: {task_text}"
    )

    await update.message.reply_text("✅ Задача отправлена на проверку!")


# Обработчик кнопок
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split('_')
    action, task_id = data[0], data[1]

    conn = sqlite3.connect('tutor_bot.db')
    cursor = conn.cursor()

    if action == "correct":
        cursor.execute("UPDATE tasks SET status='correct' WHERE task_id=?", (task_id,))
        await query.edit_message_text("✅ Задача верна!")
    else:
        cursor.execute("UPDATE tasks SET status='incorrect' WHERE task_id=?", (task_id,))
        await query.edit_message_text("❌ Задача неверна, отправлена на доработку.")
        user_id = cursor.execute("SELECT user_id FROM tasks WHERE task_id=?", (task_id,)).fetchone()[0]
        await context.bot.send_message(chat_id=user_id, text="Исправь ошибки и отправь задачу снова!")

    conn.commit()
    conn.close()


def main():
    # Создаем Application
    application = Application.builder().token(TOKEN).build()

    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, handle_task))
    application.add_handler(CallbackQueryHandler(button_callback))

    # Запускаем бота
    application.run_polling()


if __name__ == "__main__":
    main()