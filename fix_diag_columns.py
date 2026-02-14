# -*- coding: utf-8 -*-
"""One-off script: add missing columns to diag_questions (stem_image_url, solution_image_url).
Run: python fix_diag_columns.py
Use this if flask db upgrade fails or was never run."""
import os
import sqlite3

def main():
    base_dir = os.path.abspath(os.path.dirname(__file__))
    db_path = os.path.join(base_dir, 'instance', 'quiz.db')
    if not os.path.exists(db_path):
        print('DB not found:', db_path)
        return
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(diag_questions)")
    cols = [row[1] for row in cur.fetchall()]
    added = []
    if 'stem_image_url' not in cols:
        cur.execute("ALTER TABLE diag_questions ADD COLUMN stem_image_url VARCHAR(512)")
        added.append('stem_image_url')
    if 'solution_image_url' not in cols:
        cur.execute("ALTER TABLE diag_questions ADD COLUMN solution_image_url VARCHAR(512)")
        added.append('solution_image_url')
    conn.commit()
    conn.close()
    if added:
        print('Added columns:', ', '.join(added))
    else:
        print('Columns already exist, nothing to do.')

if __name__ == '__main__':
    main()
