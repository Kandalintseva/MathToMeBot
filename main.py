import telebot
from telebot import types
import sqlite3
from datetime import datetime
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import TOKEN, ADMIN_ID

# Конфигурация


bot = telebot.TeleBot(TOKEN)

# Создаем папку для заданий, если её нет
if not os.path.exists('tasks'):
    os.makedirs('tasks')


def init_db():
    conn = sqlite3.connect('tutor_bot.db')
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS students (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        name TEXT,
        class TEXT,
        register_date TEXT
    )''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tasks (
        task_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        task_text TEXT,
        photo_path TEXT,
        status TEXT DEFAULT 'pending',  -- статус задания
        send_date TEXT,
        FOREIGN KEY (user_id) REFERENCES students(user_id)
    )''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS feedback (
        feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER,
        teacher_comment TEXT,
        grade INTEGER,
        check_date TEXT,
        FOREIGN KEY (task_id) REFERENCES tasks(task_id)
    )''')

    conn.commit()
    conn.close()


init_db()


@bot.message_handler(commands=['start'])
def start(message):
    if message.from_user.id == ADMIN_ID:
        bot.send_message(message.chat.id, "👨🏫 Вы вошли как учитель. Доступные команды:\n"
                                          "/add_task - добавить задание\n"
                                          "/check_solutions - проверить решения")
    else:
        bot.send_message(message.chat.id, "👋 Привет! Я бот-репетитор.\n"
                                          "/register - зарегистрироваться\n"
                                          "/my_tasks - мои задания")


# Регистрация ученика
@bot.message_handler(commands=['register'])
def register_student(message):
    if message.from_user.id == ADMIN_ID:
        bot.send_message(message.chat.id, "Эта команда только для учеников")
        return

    conn = sqlite3.connect('tutor_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM students WHERE user_id = ?', (message.from_user.id,))
    if cursor.fetchone():
        bot.send_message(message.chat.id, "Вы уже зарегистрированы!")
        conn.close()
        return

    msg = bot.send_message(message.chat.id, "Введите ваше ФИО:")
    bot.register_next_step_handler(msg, process_full_name_step)


def process_full_name_step(message):
    try:
        full_name = message.text
        msg = bot.send_message(message.chat.id, "Введите ваш класс (например, 10А):")
        bot.register_next_step_handler(msg, lambda m: process_class_step(m, full_name))
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}")


def process_class_step(message, full_name):
    try:
        class_name = message.text
        user_id = message.from_user.id
        username = message.from_user.username

        conn = sqlite3.connect('tutor_bot.db')
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO students (user_id, username, full_name, class, register_date) VALUES (?, ?, ?, ?, ?)',
            (user_id, username, full_name, class_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()

        bot.send_message(message.chat.id, f"✅ Регистрация завершена, {full_name}!")
        bot.send_message(ADMIN_ID, f"📝 Новый ученик:\nФИО: {full_name}\nКласс: {class_name}\nUsername: @{username}")
    except Exception as e:
        bot.reply_to(message, f"Ошибка регистрации: {e}")


# Учитель добавляет задание
@bot.message_handler(commands=['add_task'], func=lambda m: m.from_user.id == ADMIN_ID)
def add_task(message):
    msg = bot.send_message(message.chat.id, "Введите предмет задания (например, Алгебра):")
    bot.register_next_step_handler(msg, process_subject_step)


def process_subject_step(message):
    subject = message.text
    msg = bot.send_message(message.chat.id, "Введите текст задания или отправьте фото:")
    bot.register_next_step_handler(msg, lambda m: process_task_content_step(m, subject))


def process_task_content_step(message, subject):
    try:
        task_text = message.text if message.text else "Фото задания"
        photo_path = None

        if message.photo:
            photo = message.photo[-1]
            file_info = bot.get_file(photo.file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            photo_path = f"tasks/teacher_task_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
            with open(photo_path, 'wb') as new_file:
                new_file.write(downloaded_file)

        conn = sqlite3.connect('tutor_bot.db')
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO teacher_tasks (teacher_id, task_text, photo_path, create_date, subject) VALUES (?, ?, ?, ?, ?)',
            (ADMIN_ID, task_text, photo_path, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), subject))
        task_id = cursor.lastrowid

        # Отправляем задание всем ученикам
        cursor.execute('SELECT user_id FROM students')
        students = cursor.fetchall()

        for student in students:
            try:
                if photo_path:
                    with open(photo_path, 'rb') as photo:
                        bot.send_photo(
                            student[0],
                            photo,
                            caption=f"📚 Новое задание по {subject} (ID: {task_id})\n\n{task_text}"
                        )
                else:
                    bot.send_message(
                        student[0],
                        f"📚 Новое задание по {subject} (ID: {task_id})\n\n{task_text}"
                    )
            except Exception as e:
                print(f"Не удалось отправить задание ученику {student[0]}: {e}")

        conn.commit()
        conn.close()

        bot.send_message(message.chat.id, f"✅ Задание #{task_id} отправлено всем ученикам!")

    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}")


# Ученик просматривает свои задания
@bot.message_handler(commands=['my_tasks'])
def show_my_tasks(message):
    if message.from_user.id == ADMIN_ID:
        bot.send_message(message.chat.id, "Эта команда только для учеников")
        return

    conn = sqlite3.connect('tutor_bot.db')
    cursor = conn.cursor()

    # Проверяем регистрацию
    cursor.execute('SELECT * FROM students WHERE user_id = ?', (message.from_user.id,))
    if not cursor.fetchone():
        bot.send_message(message.chat.id, "Сначала зарегистрируйтесь командой /register")
        conn.close()
        return

    # Получаем все задания
    cursor.execute('SELECT task_id, subject, task_text FROM teacher_tasks ORDER BY create_date DESC')
    tasks = cursor.fetchall()

    if not tasks:
        bot.send_message(message.chat.id, "У вас пока нет заданий.")
        conn.close()
        return

    markup = types.InlineKeyboardMarkup()
    for task in tasks:
        markup.add(types.InlineKeyboardButton(
            f"{task[1]} (ID: {task[0]})",
            callback_data=f"view_task_{task[0]}"
        ))

    bot.send_message(message.chat.id, "📋 Ваши задания:", reply_markup=markup)
    conn.close()


# Ученик отправляет решение
@bot.callback_query_handler(func=lambda call: call.data.startswith('view_task_'))
def view_task(call):
    task_id = call.data.split('_')[2]

    conn = sqlite3.connect('tutor_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT task_text, photo_path FROM teacher_tasks WHERE task_id = ?', (task_id,))
    task = cursor.fetchone()

    if task:
        if task[1]:  # Если есть фото
            with open(task[1], 'rb') as photo:
                bot.send_photo(
                    call.message.chat.id,
                    photo,
                    caption=f"Задание ID: {task_id}\n\n{task[0]}",
                    reply_markup=types.InlineKeyboardMarkup().add(
                        types.InlineKeyboardButton(
                            "📤 Отправить решение",
                            callback_data=f"send_solution_{task_id}"
                        )
                    )
                )
        else:
            bot.send_message(
                call.message.chat.id,
                f"Задание ID: {task_id}\n\n{task[0]}",
                reply_markup=types.InlineKeyboardMarkup().add(
                    types.InlineKeyboardButton(
                        "📤 Отправить решение",
                        callback_data=f"send_solution_{task_id}"
                    )
                )
            )
    else:
        bot.answer_callback_query(call.id, "Задание не найдено")

    conn.close()


@bot.callback_query_handler(func=lambda call: call.data.startswith('send_solution_'))
def ask_for_solution(call):
    task_id = call.data.split('_')[2]
    msg = bot.send_message(call.message.chat.id, "Отправьте ваше решение (текст или фото):")
    bot.register_next_step_handler(msg, lambda m: save_solution(m, task_id))


def save_solution(message, task_id):
    solution_text = message.text if message.text else "Фото решения"
    photo_path = None

    if message.photo:
        photo = message.photo[-1]
        file_info = bot.get_file(photo.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        photo_path = f"tasks/solution_{message.from_user.id}_{task_id}.jpg"
        with open(photo_path, 'wb') as new_file:
            new_file.write(downloaded_file)

    conn = sqlite3.connect('tutor_bot.db')
    cursor = conn.cursor()

    # Проверяем, не отправлял ли уже решение
    cursor.execute('''
        SELECT * FROM student_solutions 
        WHERE student_id = ? AND task_id = ? AND status = 'pending'
    ''', (message.from_user.id, task_id))

    if cursor.fetchone():
        bot.send_message(message.chat.id, "У вас уже есть решение этого задания на проверке.")
        conn.close()
        return

    cursor.execute(
        'INSERT INTO student_solutions (task_id, student_id, solution_text, photo_path, submit_date) VALUES (?, ?, ?, ?, ?)',
        (task_id, message.from_user.id, solution_text, photo_path, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

    # Получаем информацию об ученике
    cursor.execute('SELECT full_name, class FROM students WHERE user_id = ?', (message.from_user.id,))
    student = cursor.fetchone()

    conn.commit()
    conn.close()

    # Уведомляем учителя
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("✅ Принять", callback_data=f"accept_{task_id}_{message.from_user.id}"),
        types.InlineKeyboardButton("❌ Вернуть", callback_data=f"reject_{task_id}_{message.from_user.id}")
    )

    student_info = f"{student[0]} ({student[1]})"
    if message.from_user.username:
        student_info += f" @{message.from_user.username}"

    message_text = f"📝 Новое решение от {student_info}\n\nЗадание ID: {task_id}\n\nРешение: {solution_text}"

    if photo_path:
        with open(photo_path, 'rb') as photo:
            bot.send_photo(
                ADMIN_ID,
                photo,
                caption=message_text,
                reply_markup=markup
            )
    else:
        bot.send_message(
            ADMIN_ID,
            message_text,
            reply_markup=markup
        )

    bot.send_message(message.chat.id, "✅ Ваше решение отправлено на проверку!")


# Учитель проверяет решения
@bot.callback_query_handler(func=lambda call: call.data.startswith(('accept_', 'reject_')))
def handle_solution_review(call):
    action, task_id, student_id = call.data.split('_')
    student_id = int(student_id)

    if action == 'accept':
        conn = sqlite3.connect('tutor_bot.db')
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE student_solutions SET status = "accepted" WHERE task_id = ? AND student_id = ?',
            (task_id, student_id))
        conn.commit()
        conn.close()

        bot.send_message(
            student_id,
            f"✅ Ваше решение по заданию #{task_id} принято!"
        )
        bot.answer_callback_query(call.id, "Решение принято")
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None
        )

    elif action == 'reject':
        msg = bot.send_message(
            call.message.chat.id,
            f"Введите комментарий для ученика (ID задания {task_id}):"
        )
        bot.register_next_step_handler(msg, lambda m: send_rejection(m, task_id, student_id))


def send_rejection(message, task_id, student_id):
    comment = message.text

    conn = sqlite3.connect('tutor_bot.db')
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE student_solutions SET status = "rejected", teacher_comment = ? WHERE task_id = ? AND student_id = ?',
        (comment, task_id, student_id))
    conn.commit()
    conn.close()

    bot.send_message(
        student_id,
        f"📝 Ваше решение по заданию #{task_id} требует доработки.\n\nКомментарий учителя:\n{comment}"
    )
    bot.send_message(
        message.chat.id,
        f"✅ Комментарий отправлен ученику"
    )


# Запуск бота
if __name__ == "__main__":
    print("Бот запущен...")
    bot.infinity_polling()
