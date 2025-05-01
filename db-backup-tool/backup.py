import os
import sqlite3
import shutil
from datetime import datetime

def backup_database():
    """备份SQLite数据库"""
    try:
        # 获取环境变量
        source_db = os.environ.get('SOURCE_DB_PATH', '/data/quiz.db')
        backup_dir = os.environ.get('BACKUP_DIR', '/backups')
        
        # 确保备份目录存在
        os.makedirs(backup_dir, exist_ok=True)
        
        # 生成备份文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = os.path.join(backup_dir, f'quiz_backup_{timestamp}.db')
        
        print(f"开始备份数据库: {source_db}")
        print(f"备份文件: {backup_file}")
        
        # 连接数据库并创建备份
        conn = sqlite3.connect(source_db)
        backup = sqlite3.connect(backup_file)
        conn.backup(backup)
        
        # 关闭连接
        backup.close()
        conn.close()
        
        print("数据库备份完成！")
        
        # 显示备份文件信息
        backup_size = os.path.getsize(backup_file) / (1024 * 1024)  # 转换为MB
        print(f"备份文件大小: {backup_size:.2f} MB")
        
        return backup_file
        
    except Exception as e:
        print(f"备份过程中出错: {str(e)}")
        raise

if __name__ == '__main__':
    backup_database() 