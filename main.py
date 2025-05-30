import telebot
from telebot import types
import sqlite3
from config import TOKEN, ADMIN_ID

bot = telebot.TeleBot(TOKEN)



@bot.message_handler(commands=['getdb'], func=lambda m: m.from_user.id == ADMIN_ID)
def send_db_file(message):
    with open('tutor_bot.db', 'rb') as f:
        bot.send_document(message.chat.id, f)
 
# Инициализация базы данных
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
        status TEXT DEFAULT 'pending',
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

# Команда старта для учителя
@bot.message_handler(commands=['start'])
def start(message):
    if message.from_user.id == ADMIN_ID:
        bot.send_message(message.chat.id, "Добро пожаловать, учитель! Используйте /panel для управления")
    else:
        bot.send_message(message.chat.id, "Привет! Я бот-репетитор. Зарегистрируйтесь командой /register")

# Панель управления для учителя
@bot.message_handler(commands=['panel'])
def teacher_panel(message):
    if message.from_user.id == ADMIN_ID:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton('Список учеников'))
        markup.add(types.KeyboardButton('Проверить задания'))
        markup.add(types.KeyboardButton('Статистика'))
        bot.send_message(message.chat.id, "Панель управления:", reply_markup=markup)

# Регистрация ученика
@bot.message_handler(commands=['register'])
def register_student(message):
    if message.from_user.id == ADMIN_ID:
        bot.send_message(message.chat.id, "Эта команда только для учеников")
        return

    msg = bot.send_message(message.chat.id, "Введите ваше имя:")
    bot.register_next_step_handler(msg, process_name_step)

def process_name_step(message):
    try:
        name = message.text
        msg = bot.send_message(message.chat.id, "Введите ваш класс (например, 10А):")
        bot.register_next_step_handler(msg, lambda m: process_class_step(m, name))
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}")

def process_class_step(message, name):
    try:
        class_name = message.text
        user_id = message.from_user.id
        username = message.from_user.username
        
        conn = sqlite3.connect('tutor_bot.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO students (user_id, username, name, class, register_date) VALUES (?, ?, ?, ?, datetime("now"))',
                      (user_id, username, name, class_name))
        conn.commit()
        conn.close()
        
        bot.send_message(message.chat.id, f"Регистрация завершена, {name}!\nТеперь вы можете отправлять задания.")
        bot.send_message(ADMIN_ID, f"Новый ученик:\nИмя: {name}\nКласс: {class_name}\nUsername: @{username}")
    except Exception as e:
        bot.reply_to(message, f"Ошибка регистрации: {e}")

# Прием заданий от учеников
@bot.message_handler(content_types=['text', 'photo'])
def handle_task(message):
    if message.from_user.id == ADMIN_ID:
        return

    # Проверка регистрации
    conn = sqlite3.connect('tutor_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM students WHERE user_id = ?', (message.from_user.id,))
    student = cursor.fetchone()
    
    if not student:
        bot.send_message(message.chat.id, "Сначала зарегистрируйтесь командой /register")
        return

    task_text = message.text if message.text else "Фото задачи"
    
    if message.photo:
        photo = message.photo[-1]
        file_info = bot.get_file(photo.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        photo_path = f"tasks/{message.from_user.id}_{photo.file_id}.jpg"
        with open(photo_path, 'wb') as new_file:
            new_file.write(downloaded_file)
    else:
        photo_path = None

    cursor.execute('INSERT INTO tasks (user_id, task_text, photo_path, status, send_date) VALUES (?, ?, ?, "pending", datetime("now"))',
                  (message.from_user.id, task_text, photo_path))
    task_id = cursor.lastrowid
    
    conn.commit()
    conn.close()

    # Уведомление учителю
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Проверить", callback_data=f"check_{task_id}"))
    
    student_info = f"{student[2]} ({student[3]}) @{student[1]}" if student[1] else f"{student[2]} ({student[3]})"
    
    bot.send_message(
        ADMIN_ID,
        f"📚 Новое задание от {student_info}\nID задания: {task_id}\n\n{task_text}",
        reply_markup=markup
    )

    bot.reply_to(message, "✅ Задание отправлено на проверку!")

# Проверка заданий учителем
@bot.callback_query_handler(func=lambda call: call.data.startswith('check_'))
def check_task(call):
    task_id = call.data.split('_')[1]
    
    conn = sqlite3.connect('tutor_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tasks WHERE task_id = ?', (task_id,))
    task = cursor.fetchone()
    
    if not task:
        bot.answer_callback_query(call.id, "Задание не найдено!")
        return
    
    cursor.execute('SELECT * FROM students WHERE user_id = ?', (task[1],))
    student = cursor.fetchone()
    
    msg = bot.send_message(
        call.message.chat.id,
        f"Задание от: {student[2]} ({student[3]})\n\nТекст: {task[2]}\n\nВведите ваш комментарий и оценку (1-5):"
    )
    bot.register_next_step_handler(msg, lambda m: process_feedback(m, task_id))

def process_feedback(message, task_id):
    feedback = message.text
    
    conn = sqlite3.connect('tutor_bot.db')
    cursor = conn.cursor()
    
    # Обновляем статус задания
    cursor.execute('UPDATE tasks SET status = "checked" WHERE task_id = ?', (task_id,))
    
    # Добавляем обратную связь
    cursor.execute('''
    INSERT INTO feedback (task_id, teacher_comment, grade, check_date)
    VALUES (?, ?, ?, datetime("now"))
    ''', (task_id, feedback, 5))  # Здесь можно добавить парсинг оценки из текста
    
    # Получаем данные ученика
    cursor.execute('SELECT user_id FROM tasks WHERE task_id = ?', (task_id,))
    user_id = cursor.fetchone()[0]
    
    conn.commit()
    conn.close()
    
    # Отправляем результат ученику
    bot.send_message(
        user_id,
        f"📝 Ваше задание проверено!\n\nКомментарий учителя:\n{feedback}"
    )
    
    bot.send_message(
        message.chat.id,
        "✅ Отзыв отправлен ученику!"
    )

# Просмотр списка учеников
@bot.message_handler(func=lambda message: message.text == 'Список учеников' and message.from_user.id == ADMIN_ID)
def show_students(message):
    conn = sqlite3.connect('tutor_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM students')
    students = cursor.fetchall()
    conn.close()
    
    if not students:
        bot.send_message(message.chat.id, "Нет зарегистрированных учеников")
        return
    
    response = "👥 Список учеников:\n\n"
    for student in students:
        response += f"{student[2]} ({student[3]}) - @{student[1]}\n"
    
    bot.send_message(message.chat.id, response)

# Запуск бота
if __name__ == "__main__":
    print("Бот запущен...")
    bot.infinity_polling()
