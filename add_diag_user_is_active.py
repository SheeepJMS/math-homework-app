"""一次性脚本：为 diag_users 表添加 is_active 列（若不存在）。
运行：在项目根目录执行 python add_diag_user_is_active.py
"""
import sys
from app import app, db


def main():
    with app.app_context():
        conn = db.engine.raw_connection()
        try:
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(diag_users)")
            cols = [row[1] for row in cur.fetchall()]
            if 'is_active' not in cols:
                cur.execute("ALTER TABLE diag_users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")
                conn.commit()
                print("Added column: diag_users.is_active")
            else:
                print("Column is_active exists, skip")
        finally:
            conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
    sys.exit(0)
