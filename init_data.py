from app import app, db, User, Class, Lesson, Question
from datetime import datetime

def init_data():
    with app.app_context():
        # 创建班级
        classes = [
            Class(name='高一1班', description='高一年级1班', is_active=True),
            Class(name='高一2班', description='高一年级2班', is_active=True),
            Class(name='高一3班', description='高一年级3班', is_active=True),
            Class(name='高一4班', description='高一年级4班', is_active=True),
            Class(name='高一5班', description='高一年级5班', is_active=True),
            Class(name='高一6班', description='高一年级6班', is_active=True),
            Class(name='高一7班', description='高一年级7班', is_active=True),
            Class(name='高一8班', description='高一年级8班', is_active=True),
            Class(name='高一9班', description='高一年级9班', is_active=True),
            Class(name='高一10班', description='高一年级10班', is_active=True),
            Class(name='高一11班', description='高一年级11班', is_active=True),
            Class(name='高一12班', description='高一年级12班', is_active=True),
        ]
        
        # 添加班级
        for class_ in classes:
            existing = Class.query.filter_by(name=class_.name).first()
            if not existing:
                db.session.add(class_)
        
        # 创建管理员账号
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                username='admin',
                email='admin@example.com',
                password='admin123',
                is_active=True,
                is_admin=True
            )
            db.session.add(admin)
        
        # 创建学生账号
        student = User.query.filter_by(username='student1').first()
        if not student:
            student = User(
                username='student1',
                email='student1@example.com',
                password='student123',
                is_active=True,
                is_admin=False,
                class_id=1  # 默认分配到高一1班
            )
            db.session.add(student)
        
        # 创建课程
        lesson1 = Lesson.query.filter_by(title='第一课').first()
        if not lesson1:
            lesson1 = Lesson(
                title='第一课',
                description='第一课的内容',
                is_active=True
            )
            db.session.add(lesson1)
        
        lesson2 = Lesson.query.filter_by(title='第二课').first()
        if not lesson2:
            lesson2 = Lesson(
                title='第二课',
                description='第二课的内容',
                is_active=True
            )
            db.session.add(lesson2)
        
        # 提交所有更改
        db.session.commit()
        print("数据初始化完成！")

if __name__ == '__main__':
    # 在初始化数据之前备份现有数据库
    from app import backup_database
    backup_database()
    
    # 初始化数据
    init_data() 