import sqlite3
from typing import List, Tuple


class Database:
    _instance = None

    @staticmethod
    def get_instance():
        if Database._instance is None:
            Database._instance = Database()
        return Database._instance

    def __init__(self, db_path="translated_history.db"):
        if Database._instance is not None:
            raise Exception("This class is a singleton!")
        else:
            Database._instance = self
            self.db_path = db_path
            self.init_db()

    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS translated_text (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    src TEXT,
                    dst TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def add_translated_text(self, src: str, dst: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO translated_text (src, dst) VALUES (?, ?)",
                (src, dst),
            )
            conn.commit()
            print(
                f"Added message: src={src}, dst={dst}"
            )  # Debug log

    def get_translated_text(self, src: str) -> List[Tuple[str]]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT dst
                FROM translated_text
                WHERE src = ?
                ORDER BY created_at DESC
            """, (src, ))
            return cursor.fetchall()
