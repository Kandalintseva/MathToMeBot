import telebot
from telebot import types
import sqlite3
from config import TOKEN, ADMIN_ID

# Инициализация бота
bot = telebot.TeleBot(TOKEN)

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
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "Привет! Я бот-репетитор по математике. Отправь мне задачу на проверку.")

# Обработчик текстовых сообщений и фото
@bot.message_handler(content_types=['text', 'photo'])
def handle_task(message):
    user_id = message.from_user.id
    task_text = message.text if message.text else "Фото задачи"

    if message.photo:
        photo = message.photo[-1]
        file_info = bot.get_file(photo.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        photo_path = f"tasks/{user_id}_{photo.file_id}.jpg"
        with open(photo_path, 'wb') as new_file:
            new_file.write(downloaded_file)
    else:
        photo_path = None

    conn = sqlite3.connect('tutor_bot.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO tasks (user_id, task_text, photo_path, status) VALUES (?, ?, ?, ?)',
                   (user_id, task_text, photo_path, 'pending'))
    conn.commit()
    conn.close()

    bot.send_message(
        ADMIN_ID,
        f"Новая задача от ученика {user_id}!\nТекст: {task_text}"
    )

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Проверить задачу", callback_data=f"check_{cursor.lastrowid}"))
    bot.send_message(ADMIN_ID, "Выберите действие:", reply_markup=markup)

    bot.reply_to(message, "✅ Задача отправлена на проверку!")

# Обработчик кнопок
@bot.callback_query_handler(func=lambda call: True)
def button_callback(call):
    data = call.data.split('_')
    action, task_id = data[0], data[1]

    conn = sqlite3.connect('tutor_bot.db')
    cursor = conn.cursor()

    if action == "correct":
        cursor.execute("UPDATE tasks SET status='correct' WHERE task_id=?", (task_id,))
        bot.edit_message_text(chat_id=call.message.chat.id,
                             message_id=call.message.message_id,
                             text="✅ Задача верна!")
    else:
        cursor.execute("UPDATE tasks SET status='incorrect' WHERE task_id=?", (task_id,))
        bot.edit_message_text(chat_id=call.message.chat.id,
                             message_id=call.message.message_id,
                             text="❌ Задача неверна, отправлена на доработку.")
        user_id = cursor.execute("SELECT user_id FROM tasks WHERE task_id=?", (task_id,)).fetchone()[0]
        bot.send_message(chat_id=user_id, text="Исправь ошибки и отправь задачу снова!")

    conn.commit()
    conn.close()

# Запуск бота
if __name__ == "__main__":
    bot.infinity_polling()
