import sqlite3
import shutil
from datetime import datetime
import os

def get_database_stats(db_path):
    """获取数据库中的统计信息"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        stats = {}
        # 获取各个表的记录数
        tables = [
            ('class', '班级'),
            ('lesson', '课程'),
            ('user', '用户'),
            ('question', '题目'),
            ('quiz_history', '答题记录'),
            ('user_answer', '用户答案'),
            ('exam_file', '试卷文件'),
            ('explanation_file', '解析文件')
        ]
        
        for table, name in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                stats[name] = count
            except sqlite3.OperationalError:
                stats[name] = '表不存在'
        
        # 获取具体的班级和课程信息
        try:
            cursor.execute("SELECT name FROM class")
            stats['班级列表'] = [row[0] for row in cursor.fetchall()]
        except sqlite3.OperationalError:
            stats['班级列表'] = []
            
        try:
            cursor.execute("SELECT title FROM lesson")
            stats['课程列表'] = [row[0] for row in cursor.fetchall()]
        except sqlite3.OperationalError:
            stats['课程列表'] = []
            
        conn.close()
        return stats
    except Exception as e:
        print(f"获取数据库统计信息失败: {str(e)}")
        return None

def print_database_stats(stats, db_name="数据库"):
    """打印数据库统计信息"""
    if not stats:
        print(f"{db_name}统计信息获取失败")
        return
        
    print(f"\n{db_name}统计信息:")
    print("-" * 40)
    for key, value in stats.items():
        if key not in ['班级列表', '课程列表']:
            print(f"{key}: {value}")
    
    if stats['班级列表']:
        print("\n班级列表:")
        for class_name in stats['班级列表']:
            print(f"- {class_name}")
            
    if stats['课程列表']:
        print("\n课程列表:")
        for lesson_name in stats['课程列表']:
            print(f"- {lesson_name}")
    print("-" * 40)

def backup_database():
    """备份数据库"""
    # 确保备份目录存在
    if not os.path.exists('backups'):
        os.makedirs('backups')
    
    # 生成备份文件名（包含时间戳）
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = f'backups/quiz_backup_{timestamp}.db'
    
    try:
        # 如果数据库文件存在，创建备份
        if os.path.exists('quiz.db'):
            # 获取原数据库统计信息
            print("\n开始备份数据库...")
            original_stats = get_database_stats('quiz.db')
            print_database_stats(original_stats, "原始数据库")
            
            # 复制数据库文件
            shutil.copy2('quiz.db', backup_file)
            print(f'\n数据库已备份到: {backup_file}')
            
            # 验证备份
            backup_stats = get_database_stats(backup_file)
            print_database_stats(backup_stats, "备份数据库")
            
            if original_stats == backup_stats:
                print("\n✅ 备份验证成功：数据完全一致")
            else:
                print("\n⚠️ 警告：备份数据可能不完整，请检查")
        else:
            print('数据库文件不存在')
    except Exception as e:
        print(f'备份失败: {str(e)}')

def restore_database(backup_file):
    """恢复数据库"""
    try:
        if os.path.exists(backup_file):
            # 获取备份文件的统计信息
            print("\n准备恢复数据库...")
            backup_stats = get_database_stats(backup_file)
            print_database_stats(backup_stats, "备份数据库")
            
            # 如果当前有数据库文件，先获取其统计信息
            if os.path.exists('quiz.db'):
                current_stats = get_database_stats('quiz.db')
                print_database_stats(current_stats, "当前数据库")
                
                # 创建当前数据库的备份
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                auto_backup = f'backups/quiz_auto_backup_{timestamp}.db'
                shutil.copy2('quiz.db', auto_backup)
                print(f'\n已自动创建当前数据库的备份: {auto_backup}')
            
            # 如果当前有数据库连接，先关闭
            try:
                conn = sqlite3.connect('quiz.db')
                conn.close()
            except:
                pass
            
            # 恢复备份
            shutil.copy2(backup_file, 'quiz.db')
            print(f'\n数据库已从 {backup_file} 恢复')
            
            # 验证恢复
            restored_stats = get_database_stats('quiz.db')
            print_database_stats(restored_stats, "恢复后的数据库")
            
            if backup_stats == restored_stats:
                print("\n✅ 恢复验证成功：数据完全一致")
            else:
                print("\n⚠️ 警告：恢复的数据可能不完整，请检查")
        else:
            print('备份文件不存在')
    except Exception as e:
        print(f'恢复失败: {str(e)}')

def list_backups():
    """列出所有备份文件"""
    if not os.path.exists('backups'):
        print('没有找到备份目录')
        return
        
    backups = [f for f in os.listdir('backups') if f.endswith('.db')]
    if not backups:
        print('没有找到备份文件')
        return
        
    print('\n可用的备份文件:')
    print('-' * 40)
    for i, backup in enumerate(sorted(backups, reverse=True)):
        file_path = os.path.join('backups', backup)
        size = os.path.getsize(file_path) / (1024 * 1024)  # 转换为MB
        stats = get_database_stats(file_path)
        print(f'{i+1}. {backup}')
        print(f'   大小: {size:.2f}MB')
        if stats:
            print(f'   班级数: {stats["班级"]}')
            print(f'   课程数: {stats["课程"]}')
            print(f'   用户数: {stats["用户"]}')
        print()

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print('使用方法:')
        print('备份数据库: python backup_db.py backup')
        print('恢复数据库: python backup_db.py restore <backup_file>')
        print('列出备份: python backup_db.py list')
    elif sys.argv[1] == 'backup':
        backup_database()
    elif sys.argv[1] == 'restore' and len(sys.argv) == 3:
        restore_database(sys.argv[2])
    elif sys.argv[1] == 'list':
        list_backups()
    else:
        print('无效的命令') 