"""一次性脚本：为 diag_competitions 表添加 subject、category 列（若不存在）。
运行：在项目根目录执行 python add_diag_competition_columns.py
"""
import sys
from app import app, db

def main():
    with app.app_context():
        conn = db.engine.raw_connection()
        try:
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(diag_competitions)")
            cols = [row[1] for row in cur.fetchall()]
            if 'subject' not in cols:
                cur.execute("ALTER TABLE diag_competitions ADD COLUMN subject VARCHAR(80)")
                print("Added column: subject")
            else:
                print("Column subject exists, skip")
            if 'category' not in cols:
                cur.execute("ALTER TABLE diag_competitions ADD COLUMN category VARCHAR(80)")
                print("Added column: category")
            else:
                print("Column category exists, skip")
            if 'score_scheme' not in cols:
                cur.execute("ALTER TABLE diag_competitions ADD COLUMN score_scheme TEXT")
                print("Added column: score_scheme")
            else:
                print("Column score_scheme exists, skip")
            if 'blank_bonus' not in cols:
                cur.execute("ALTER TABLE diag_competitions ADD COLUMN blank_bonus INTEGER DEFAULT 0")
                print("Added column: blank_bonus")
            else:
                print("Column blank_bonus exists, skip")
            cur.execute("PRAGMA table_info(diag_exams)")
            exam_cols = [row[1] for row in cur.fetchall()]
            if 'year' not in exam_cols:
                cur.execute("ALTER TABLE diag_exams ADD COLUMN year INTEGER")
                print("Added column: diag_exams.year")
            else:
                print("Column diag_exams.year exists, skip")
            cur.execute(
                "CREATE TABLE IF NOT EXISTS diag_practice_attempts "
                "(id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, practice_set_id INTEGER NOT NULL, "
                "user_id INTEGER NOT NULL, answers_json TEXT, submitted_at DATETIME, "
                "FOREIGN KEY (practice_set_id) REFERENCES diag_practice_sets(id), "
                "FOREIGN KEY (user_id) REFERENCES diag_users(id))"
            )
            conn.commit()
        finally:
            conn.close()
    print("Done.")

if __name__ == "__main__":
    main()
    sys.exit(0)
