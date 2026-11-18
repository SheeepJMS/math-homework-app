"""定时任务：发送未交作业家长邮件提醒。

用法：
  python scripts/send_homework_reminders.py
  python scripts/send_homework_reminders.py --force
"""
import argparse
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault('FLASK_APP', 'app.py')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--force', action='store_true', help='忽略周五17点时间窗，立即发送')
    args = parser.parse_args()

    from app import app, send_weekly_homework_reminders
    with app.app_context():
        result = send_weekly_homework_reminders(force=args.force)
        print(result)
        # 非强制且因时间窗跳过时仍视为成功退出
        if result.get('failed', 0) > 0:
            sys.exit(2)


if __name__ == '__main__':
    main()
