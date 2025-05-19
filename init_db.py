from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

app = Flask(__name__)
# 配置数据库
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

if not database_url:
    # 如果没有设置环境变量，使用默认的SQLite配置（用于本地开发）
    base_dir = os.path.abspath(os.path.dirname(__file__))
    database_url = f'sqlite:///{os.path.join(base_dir, "instance", "quiz.db")}'
    print(f"警告：未设置DATABASE_URL环境变量，使用SQLite作为默认数据库: {database_url}")

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 初始化数据库
db = SQLAlchemy(app)

# 课程和班级的多对多关联表
lesson_class_association = db.Table('lesson_class_association',
    db.Column('lesson_id', db.Integer, db.ForeignKey('lesson.id'), primary_key=True),
    db.Column('class_id', db.Integer, db.ForeignKey('class.id'), primary_key=True)
)

# 定义班级模型
class Class(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=True)  # 班级名称
    description = db.Column(db.String(200))  # 班级描述
    is_active = db.Column(db.Boolean, default=True)  # 是否激活
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    lessons = db.relationship('Lesson', secondary=lesson_class_association, backref='classes', lazy=True)

# 定义课程模型
class Lesson(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)  # 课程标题
    description = db.Column(db.String(200))  # 课程描述
    is_active = db.Column(db.Boolean, default=False)  # 是否当前显示
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    questions = db.relationship('Question', backref='lesson', lazy=True)

# 试卷文件模型
class ExamFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    path = db.Column(db.String(255), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=False)
    page_number = db.Column(db.Integer, nullable=False)  # 页码
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    lesson = db.relationship('Lesson', backref=db.backref('exam_files', lazy=True))

# 解析文件模型
class ExplanationFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    path = db.Column(db.String(255), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=False)
    page_number = db.Column(db.Integer, nullable=False)  # 页码
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    lesson = db.relationship('Lesson', backref=db.backref('explanation_files', lazy=True))

# 定义题目模型
class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=False)
    question_number = db.Column(db.Integer, nullable=False)  # 题号
    type = db.Column(db.String(10), nullable=False)  # 题目类型：choice（选择题）、fill（填空题）或proof（证明题）
    answer = db.Column(db.String(100), nullable=False)  # 正确答案
    content = db.Column(db.String(500))  # 移除nullable=False约束
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (
        db.UniqueConstraint('lesson_id', 'question_number', name='unique_question_number'),
    )

# 用户答题记录模型
class UserAnswer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    quiz_history_id = db.Column(db.Integer, db.ForeignKey('quiz_history.id'), nullable=False)
    answer = db.Column(db.Text, nullable=True)  # 使用Text类型支持更长的答案
    is_correct = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# 定义答题历史记录模型
class QuizHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=False)
    total_questions = db.Column(db.Integer, nullable=False)
    correct_answers = db.Column(db.Integer, nullable=False)
    time_spent = db.Column(db.Integer, nullable=False)  # 答题用时（秒）
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)

def init_db():
    print("开始初始化数据库...")
    # 确保数据库目录存在
    os.makedirs('instance', exist_ok=True)
    
    # 创建所有表
    with app.app_context():
        # 使用 SQLAlchemy 的方法创建表
        db.create_all()
        
        # 检查是否已存在默认班级
        default_class = Class.query.filter_by(name='默认班级').first()
        if not default_class:
            default_class = Class(
                name='默认班级',
                description='系统默认班级',
                is_active=True
            )
            db.session.add(default_class)
            db.session.commit()
            print("默认班级已创建")
        
        # 检查是否已存在管理员账号
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                name='管理员',
                username='admin',
                password='admin123',
                is_active=True,
                is_admin=True,
                class_id=default_class.id,
                achievement_count=0,
                badge_level=0
            )
            db.session.add(admin)
        
        # 检查是否已存在测试学生账号
        student = User.query.filter_by(username='student').first()
        if not student:
            student = User(
                name='测试学生',
                username='student',
                password='student123',
                is_active=True,
                is_admin=False,
                class_id=default_class.id,
                achievement_count=0,
                badge_level=0
            )
            db.session.add(student)
        
        db.session.commit()
        print("默认用户已创建")
        print("数据库初始化完成！")

if __name__ == '__main__':
    init_db() 