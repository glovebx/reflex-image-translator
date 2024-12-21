import sqlite3
from typing import List, Tuple


class Database:
    _instance = None

    @staticmethod
    def get_instance():
        if Database._instance is None:
            Database._instance = Database()
        return Database._instance

    def __init__(self, db_path="image_translated.db"):
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
                CREATE TABLE IF NOT EXISTS odoo_user (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ajs_user_id TEXT,       
                    uid INTGER,
                    login TEXT,
                    session_id TEXT,
                    name TEXT,
                    avatar TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS translated_text (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    src TEXT,
                    dst TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def get_odoo_user(self, ajs_user_id: str) -> List[Tuple[str, int, str, str, str, str]]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT ajs_user_id, uid, login, session_id, name, avatar
                FROM odoo_user
                WHERE ajs_user_id = ?
            """, (ajs_user_id, ))
            return cursor.fetchone()
        
    def add_or_update_user(self, ajs_user_id: str, uid: int, login: str, session_id: str, name: str, avatar: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT count(*)
                FROM odoo_user
                WHERE uid = ?
            """, (uid, ))
            counts = cursor.fetchone()
            if counts[0] == 0:
                cursor.execute(
                    "INSERT INTO odoo_user (ajs_user_id, uid, login, session_id, name, avatar) VALUES (?, ?, ?, ?, ?, ?)",
                    (ajs_user_id, uid, login, session_id, name, avatar),
                )
            else:
                cursor.execute(
                    "UPDATE odoo_user set ajs_user_id = ?, updated_at=datetime('now') WHERE uid = ?",
                    (ajs_user_id, uid, ),
                )

            conn.commit()
            print(
                f"Added or updated odoo user: login={login}, name={name}"
            )  # Debug log

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
