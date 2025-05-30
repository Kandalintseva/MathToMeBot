import sqlite3


def init_db():
    """
    Создаёт базу данных и таблицы, если они не существуют.
    """
    conn = sqlite3.connect('tutor_bot.db')
    cursor = conn.cursor()

    # Создаём таблицу students
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS students (
        user_id INTEGER PRIMARY KEY,
        name TEXT,
        class TEXT
    )
    ''')

    # Создаём таблицу tasks
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tasks (
        task_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        task_text TEXT,
        photo_path TEXT,
        status TEXT,
        FOREIGN KEY (user_id) REFERENCES students (user_id)
    )
    ''')

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()