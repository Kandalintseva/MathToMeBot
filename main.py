import telebot
from telebot import types
import sqlite3
import os
from datetime import datetime

# Безопасное получение переменных окружения
TOKEN = os.getenv('TELEGRAM_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))  # 0 как значение по умолчанию

if not TOKEN:
    print("ОШИБКА: Токен бота не найден!")
    print("Укажите TELEGRAM_TOKEN в переменных окружения")
    exit(1)

bot = telebot.TeleBot(TOKEN)

# Создаем папку для заданий
os.makedirs('tasks', exist_ok=True)

def init_db():
    """Инициализация базы данных с безопасными SQL-запросами"""
    try:
        conn = sqlite3.connect('tutor_bot.db')
        cursor = conn.cursor()

        # Создаем таблицы с правильными комментариями (используя -- вместо #)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            class TEXT,
            register_date TEXT
        )''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS teacher_tasks (
            task_id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER,
            task_text TEXT,
            photo_path TEXT,
            create_date TEXT,
            subject TEXT
        )''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_solutions (
            solution_id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            student_id INTEGER,
            solution_text TEXT,
            photo_path TEXT,
            status TEXT DEFAULT 'pending',
            submit_date TEXT,
            teacher_comment TEXT,
            FOREIGN KEY (task_id) REFERENCES teacher_tasks(task_id),
            FOREIGN KEY (student_id) REFERENCES students(user_id)
        )''')

        conn.commit()
    except sqlite3.Error as e:
        print(f"Ошибка базы данных: {e}")
    finally:
        if conn:
            conn.close()

init_db()

@bot.message_handler(commands=['start'])
def start(message):
    """Обработчик команды /start"""
    if message.from_user.id == ADMIN_ID:
        bot.send_message(message.chat.id, 
                        "👨🏫 Вы вошли как учитель. Доступные команды:\n"
                        "/add_task - добавить задание\n"
                        "/check_solutions - проверить решения")
    else:
        bot.send_message(message.chat.id,
                        "👋 Привет! Я бот-репетитор.\n"
                        "/register - зарегистрироваться\n"
                        "/my_tasks - мои задания")

# ... (остальные функции остаются такими же, но с добавлением обработки ошибок)

def save_photo(file_info, file_path):
    """Безопасное сохранение фото"""
    try:
        downloaded_file = bot.download_file(file_info.file_path)
        with open(file_path, 'wb') as new_file:
            new_file.write(downloaded_file)
        return True
    except Exception as e:
        print(f"Ошибка сохранения фото: {e}")
        return False

if __name__ == "__main__":
    print("Запуск бота...")
    try:
        bot.infinity_polling()
    except Exception as e:
        print(f"Ошибка в работе бота: {e}")
