from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory
import os
import pandas as pd
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from sqlalchemy.sql import func
from flask_wtf.csrf import CSRFProtect
from functools import wraps
from flask_wtf import FlaskForm
import base64
import io
from PIL import Image
import random
from flask_migrate import Migrate
import json
import time
from collections import namedtuple

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # 用于 flash 消息和 session

# 配置 CSRF 保护
csrf = CSRFProtect(app)
app.config['WTF_CSRF_TIME_LIMIT'] = 3600  # CSRF 令牌有效期设置为1小时
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)  # 会话有效期设置为1小时

# 配置会话为永久性的，这样可以延长会话的有效期
@app.before_request
def make_session_permanent():
    session.permanent = True

# 配置 Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# 配置数据库
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///quiz.db'  # 使用 SQLite 数据库
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 配置文件上传
UPLOAD_FOLDER = 'static/uploads'  # 修改为相对路径
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
ALLOWED_PDF_EXTENSIONS = {'pdf'}
ALLOWED_EXCEL_EXTENSIONS = {'xlsx', 'xls'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 限制文件大小为16MB

# 确保上传目录存在
os.makedirs(os.path.join(UPLOAD_FOLDER, 'exams'), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_FOLDER, 'explanations'), exist_ok=True)

# 初始化数据库
db = SQLAlchemy(app)
migrate = Migrate(app, db)

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
    users = db.relationship('User', backref='class', lazy=True)
    lessons = db.relationship('Lesson', secondary=lesson_class_association, backref='classes', lazy=True)

# 定义课程模型
class Lesson(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)  # 课程标题
    description = db.Column(db.String(200))  # 课程描述
    is_active = db.Column(db.Boolean, default=False)  # 是否当前显示
    video_url = db.Column(db.String(500))  # 视频回放链接
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

# 定义用户模型
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False)
    class_id = db.Column(db.Integer, db.ForeignKey('class.id'))
    achievement_count = db.Column(db.Integer, default=0)  # 达标次数（80%以上正确率）
    badge_level = db.Column(db.Integer, default=0)  # 徽章等级，默认为0（无徽章）
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 一对多关系
    answers = db.relationship('UserAnswer', backref='user', lazy=True)

    def get_id(self):
        return str(self.id)
    
    @property
    def badge_info(self):
        encouragements = {
            1: "Nice start!",
            2: "Keep it up!",
            3: "You're growing stronger!",
            4: "Skills are shining!",
            5: "You've leveled up!",
            6: "On your way to greatness!",
            7: "Powerful progress!",
            8: "Shining bright!",
            9: "Excellence unlocked!",
            10: "Next stop: Mastery!"
        }

        if self.badge_level == 0:
            return {
                "current_level": 0,
                "name": "No Badge",
                "icon": "❓",
                "achievements": self.achievement_count,
                "next_level_at": 1,
                "next_achievements_needed": 1,
                "encouragement": "Ready to start your journey!"
            }

        badges = {
            1: {"name": "Little Worm", "icon": "🐛", "next_level": 2},
            2: {"name": "Butterfly", "icon": "🦋", "next_level": 4},
            3: {"name": "Python", "icon": "🐍", "next_level": 6},
            4: {"name": "Wolf", "icon": "🐺", "next_level": 8},
            5: {"name": "Tiger", "icon": "🐯", "next_level": 10},
            6: {"name": "Dragon", "icon": "🐲", "next_level": 12},
            7: {"name": "Mini Monster", "icon": "👾", "next_level": 14},
            8: {"name": "Big Monster", "icon": "👹", "next_level": 16},
            9: {"name": "Beast", "icon": "🦖", "next_level": 18},
            10: {"name": "Godzilla", "icon": "🐉", "next_level": None}
        }
        current_badge = badges.get(self.badge_level, badges[1])
        next_achievements_needed = current_badge["next_level"] - self.achievement_count if current_badge["next_level"] else 0
        return {
            "current_level": self.badge_level,
            "name": current_badge["name"],
            "icon": current_badge["icon"],
            "achievements": self.achievement_count,
            "next_level_at": current_badge["next_level"],
            "next_achievements_needed": next_achievements_needed,
            "encouragement": encouragements.get(self.badge_level, "Amazing progress!")
        }

# 用户答题记录模型
class UserAnswer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    quiz_history_id = db.Column(db.Integer, db.ForeignKey('quiz_history.id'), nullable=False)
    answer = db.Column(db.String(255), nullable=True)  # 允许为空，表示未作答
    is_correct = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    question = db.relationship('Question', backref='user_answers')
    quiz_history = db.relationship('QuizHistory', backref='answers')

# 定义答题历史记录模型
class QuizHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=False)
    total_questions = db.Column(db.Integer, nullable=False)
    correct_answers = db.Column(db.Integer, nullable=False)
    time_spent = db.Column(db.Integer, nullable=False)  # 答题用时（秒）
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 添加关系
    user = db.relationship('User', backref='quiz_history', lazy=True)
    lesson = db.relationship('Lesson', backref='quiz_history', lazy=True)
    
    @property
    def correct_rate(self):
        return (self.correct_answers / self.total_questions * 100) if self.total_questions > 0 else 0

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('请先登录')
            return redirect(url_for('login'))
        if not current_user.is_admin:
            flash('需要管理员权限')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('student_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        print(f"尝试登录: 用户名 = {username}")  # 添加日志
        
        user = User.query.filter_by(username=username).first()
        if user:
            print(f"找到用户: {user.username}, 激活状态: {user.is_active}")  # 添加日志
            if user.password == password:
                if not user.is_active:
                    flash('账号未激活，请联系管理员')
                    return redirect(url_for('login'))
                login_user(user)
                print(f"用户 {username} 登录成功")  # 添加日志
                flash('登录成功！')
                return redirect(url_for('index'))
            else:
                print(f"密码错误: {username}")  # 添加日志
                flash('密码错误')
        else:
            print(f"用户不存在: {username}")  # 添加日志
            flash('用户名不存在')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        class_id = request.form['class_id']
        
        if password != confirm_password:
            flash('两次输入的密码不一致')
            return redirect(url_for('register'))
        
        if User.query.filter_by(username=username).first():
            flash('用户名已存在')
            return redirect(url_for('register'))
        
        # 为email生成一个默认值
        default_email = f"{username}@example.com"
        
        new_user = User(
            username=username,
            email=default_email,  # 使用默认email
            password=password,
            class_id=class_id,
            is_active=True  # 默认设置为激活状态
        )
        db.session.add(new_user)
        db.session.commit()
        
        flash('注册成功！请登录')
        return redirect(url_for('login'))
    
    classes = Class.query.filter_by(is_active=True).all()
    return render_template('register.html', classes=classes)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('已退出登录')
    return redirect(url_for('login'))

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    # 获取统计数据
    total_students = User.query.filter_by(is_admin=False).count()
    total_lessons = Lesson.query.count()
    total_classes = Class.query.count()
    
    # 获取最近活动（最近的测验记录）
    recent_activities = db.session.query(
        QuizHistory,
        User.username.label('student_name'),
        Lesson.title.label('lesson_title')
    ).join(
        User, QuizHistory.user_id == User.id
    ).join(
        Lesson, QuizHistory.lesson_id == Lesson.id
    ).order_by(
        QuizHistory.completed_at.desc()
    ).limit(10).all()
    
    # 处理活动数据
    activities = []
    for activity in recent_activities:
        activities.append({
            'completed_at': activity.QuizHistory.completed_at,
            'student_name': activity.student_name,
            'lesson_title': activity.lesson_title,
            'correct_rate': round(activity.QuizHistory.correct_answers * 100 / activity.QuizHistory.total_questions, 1)
        })
    
    return render_template('admin/dashboard.html',
                         total_students=total_students,
                         total_lessons=total_lessons,
                         total_classes=total_classes,
                         recent_activities=activities)

@app.route('/admin/users')
@app.route('/admin/users/<int:class_id>')
@admin_required
def admin_users(class_id=None):
    # 获取所有管理员用户
    admin_users = User.query.filter_by(is_admin=True).all()
    
    # 获取所有班级
    classes = Class.query.all()
    
    # 获取非管理员用户，根据班级ID筛选
    if class_id:
        students = User.query.filter_by(
            class_id=class_id, 
            is_admin=False
        ).all()
        class_users = {Class.query.get(class_id): students}
    else:
        # 如果没有指定班级，获取所有班级的用户
        class_users = {}
        for class_ in classes:
            students = User.query.filter_by(
                class_id=class_.id,
                is_admin=False
            ).all()
            class_users[class_] = students
    
    return render_template('admin/users.html', 
                         admin_users=admin_users,
                         class_users=class_users,
                         classes=classes,
                         current_class_id=class_id)

@app.route('/admin/user/<int:user_id>/toggle', methods=['POST'])
@admin_required
def toggle_user_status(user_id):
    user = User.query.get_or_404(user_id)
    
    # 防止管理员被禁用
    if user.is_admin:
        return redirect(url_for('admin_users'))
    
    user.is_active = not user.is_active
    db.session.commit()
    return redirect(url_for('admin_users'))

@app.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    
    # 防止管理员被删除
    if user.is_admin:
        return redirect(url_for('admin_users'))
    
    db.session.delete(user)
    db.session.commit()
    return redirect(url_for('admin_users'))

@app.route('/admin/classes')
@admin_required
def admin_classes():
    classes = Class.query.all()
    return render_template('admin/classes.html', classes=classes)

@app.route('/admin/class/add', methods=['POST'])
@admin_required
def add_class():
    name = request.form.get('name')
    description = request.form.get('description')
    
    if not name:
        flash('班级名称不能为空')
        return redirect(url_for('admin_classes'))
    
    if Class.query.filter_by(name=name).first():
        flash('班级名称已存在')
        return redirect(url_for('admin_classes'))
    
    new_class = Class(name=name, description=description)
    db.session.add(new_class)
    db.session.commit()
    
    flash('班级添加成功')
    return redirect(url_for('admin_classes'))

@app.route('/admin/class/<int:class_id>/toggle', methods=['POST'])
@admin_required
def toggle_class_status(class_id):
    class_ = Class.query.get_or_404(class_id)
    class_.is_active = not class_.is_active
    db.session.commit()
    flash(f'班级 {class_.name} 状态已更新')
    return redirect(url_for('admin_classes'))

@app.route('/admin/class/<int:class_id>/delete', methods=['POST'])
@admin_required
def delete_class(class_id):
    class_ = Class.query.get_or_404(class_id)
    
    try:
        # 删除关联的用户
        User.query.filter_by(class_id=class_id).delete()
        
        # 删除与课程的关联（不删除课程本身）
        class_.lessons = []
        
        # 删除班级
        db.session.delete(class_)
        db.session.commit()
        
        flash(f'班级 {class_.name} 及其所有用户已删除', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'删除失败：{str(e)}', 'error')
    
    return redirect(url_for('admin_classes'))

@app.route('/admin/class/<int:class_id>/edit', methods=['POST'])
@admin_required
def edit_class(class_id):
    class_ = Class.query.get_or_404(class_id)
    
    # 获取表单数据
    name = request.form.get('name')
    description = request.form.get('description')
    
    if not name:
        flash('班级名称不能为空')
        return redirect(url_for('admin_classes'))
    
    # 检查名称是否已存在（排除当前班级）
    existing_class = Class.query.filter(Class.name == name, Class.id != class_id).first()
    if existing_class:
        flash('班级名称已存在')
        return redirect(url_for('admin_classes'))
    
    # 更新班级信息
    class_.name = name
    class_.description = description
    
    try:
        db.session.commit()
        flash('班级更新成功')
    except Exception as e:
        db.session.rollback()
        flash(f'更新失败：{str(e)}')
    
    return redirect(url_for('admin_classes'))

@app.route('/admin/lessons')
@admin_required
def admin_lessons():
    lessons = Lesson.query.all()
    classes = Class.query.all()
    return render_template('admin/lessons.html', lessons=lessons, classes=classes)

@app.route('/admin/lesson/add', methods=['POST'])
@admin_required
def add_lesson():
    title = request.form.get('title')
    description = request.form.get('description')
    class_ids = request.form.getlist('class_ids')  # 修改这里
    
    if not title or not class_ids:
        flash('课程标题和所属班级不能为空')
        return redirect(url_for('admin_lessons'))
    
    # 创建新课程
    new_lesson = Lesson(
        title=title,
        description=description,
        is_active=False
    )
    
    # 添加班级关联
    for class_id in class_ids:
        class_ = Class.query.get(class_id)
        if class_:
            new_lesson.classes.append(class_)
    
    try:
        db.session.add(new_lesson)
        db.session.commit()
        flash('课程添加成功')
    except Exception as e:
        db.session.rollback()
        flash(f'添加失败：{str(e)}')
    
    return redirect(url_for('admin_lessons'))

@app.route('/admin/lesson/<int:lesson_id>/toggle', methods=['POST'])
@admin_required
def toggle_lesson_status(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    
    # 直接切换当前课程的状态
    lesson.is_active = not lesson.is_active
    db.session.commit()
    
    flash(f'课程 {lesson.title} {{ "已激活" if lesson.is_active else "已停用" }}')
    return redirect(url_for('admin_lessons'))

@app.route('/admin/lesson/<int:lesson_id>/delete', methods=['POST'])
@admin_required
def delete_lesson(lesson_id):
    try:
        print(f"开始删除课程 ID: {lesson_id}")  # 调试日志
        lesson = Lesson.query.get_or_404(lesson_id)
        print(f"找到课程: {lesson.title}")  # 调试日志
        
        # 首先删除与课程相关的所有考试记录
        quiz_count = QuizHistory.query.filter_by(lesson_id=lesson_id).delete()
        print(f"删除了 {quiz_count} 条考试记录")  # 调试日志
        
        # 删除与课程相关的所有答题记录
        answer_count = UserAnswer.query.filter_by(lesson_id=lesson_id).delete()
        print(f"删除了 {answer_count} 条答题记录")  # 调试日志
        
        # 删除与课程相关的所有试卷文件
        exam_files = ExamFile.query.filter_by(lesson_id=lesson_id).all()
        print(f"找到 {len(exam_files)} 个试卷文件")  # 调试日志
        for file in exam_files:
            try:
                # 删除物理文件
                file_path = os.path.join('static', file.path)
                print(f"尝试删除文件: {file_path}")  # 调试日志
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"成功删除文件: {file_path}")  # 调试日志
            except Exception as e:
                print(f"删除文件失败: {str(e)}")  # 记录文件删除错误但继续执行
        
        # 删除数据库中的试卷文件记录
        file_count = ExamFile.query.filter_by(lesson_id=lesson_id).delete()
        print(f"删除了 {file_count} 条试卷文件记录")  # 调试日志

        # 删除与课程相关的所有解析文件
        explanation_files = ExplanationFile.query.filter_by(lesson_id=lesson_id).all()
        print(f"找到 {len(explanation_files)} 个解析文件")  # 调试日志
        for file in explanation_files:
            try:
                # 删除物理文件
                file_path = os.path.join('static', file.path)
                print(f"尝试删除解析文件: {file_path}")  # 调试日志
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"成功删除解析文件: {file_path}")  # 调试日志
            except Exception as e:
                print(f"删除解析文件失败: {str(e)}")  # 记录文件删除错误但继续执行
        
        # 删除数据库中的解析文件记录
        explanation_count = ExplanationFile.query.filter_by(lesson_id=lesson_id).delete()
        print(f"删除了 {explanation_count} 条解析文件记录")  # 调试日志
        
        # 删除与课程相关的所有问题
        question_count = Question.query.filter_by(lesson_id=lesson_id).delete()
        print(f"删除了 {question_count} 道题目")  # 调试日志
        
        # 最后删除课程本身
        db.session.delete(lesson)
        db.session.commit()
        print("成功删除课程")  # 调试日志
        
        flash('课程已成功删除', 'success')
        return redirect(url_for('admin_lessons'))
        
    except Exception as e:
        db.session.rollback()
        error_msg = str(e)
        print(f"删除课程时出错: {error_msg}")  # 调试日志
        flash(f'删除课程时出错: {error_msg}', 'error')
        return redirect(url_for('manage_questions', lesson_id=lesson_id))

@app.route('/admin/lesson/<int:lesson_id>/questions')
@admin_required
def manage_questions(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    questions = Question.query.filter_by(lesson_id=lesson_id).all()
    exam_files = ExamFile.query.filter_by(lesson_id=lesson_id).order_by(ExamFile.page_number).all()
    explanation_files = ExplanationFile.query.filter_by(lesson_id=lesson_id).order_by(ExplanationFile.page_number).all()
    return render_template('admin/questions.html', 
                         lesson=lesson, 
                         questions=questions,
                         exam_files=exam_files,
                         explanation_files=explanation_files)

@app.route('/student/dashboard')
@login_required
def student_dashboard():
    # 获取用户的所有测验历史记录
    quiz_history = QuizHistory.query.filter_by(user_id=current_user.id).all()
    
    # 如果用户还没有完成任何测验，将徽章等级设置为0
    if not quiz_history:
        current_user.badge_level = 0
        current_user.achievement_count = 0
    else:
        # 如果用户完成了测验但还是Level 0，升级到Level 1
        if current_user.badge_level == 0:
            current_user.badge_level = 1
            current_user.achievement_count = 1
            flash('恭喜！你获得了第一个徽章：小毛毛虫！🐛', 'success')
            db.session.commit()
    
    # 计算总测验数和平均正确率
    total_quizzes = len(quiz_history)
    if total_quizzes > 0:
        total_correct_rate = round(sum(quiz.correct_rate for quiz in quiz_history) / total_quizzes)
    else:
        total_correct_rate = 0
    
    # 获取历史课程数据
    history_data = db.session.query(Lesson, QuizHistory)\
        .join(QuizHistory, Lesson.id == QuizHistory.lesson_id)\
        .filter(QuizHistory.user_id == current_user.id)\
        .order_by(QuizHistory.completed_at.desc())\
        .all()
    
    # 获取已完成的课程ID列表
    completed_lesson_ids = [quiz.lesson_id for quiz in quiz_history]
    
    # 获取当前可用的课程（激活状态且未完成的课程）
    # 修改这里：使用多对多关联查询
    available_lessons = Lesson.query.join(
        lesson_class_association,
        Lesson.id == lesson_class_association.c.lesson_id
    ).filter(
        lesson_class_association.c.class_id == current_user.class_id,
        Lesson.is_active == True,
        ~Lesson.id.in_(completed_lesson_ids) if completed_lesson_ids else True
    ).all()
    
    # 准备趋势图数据
    trend_data = []
    for quiz in quiz_history:
        lesson = Lesson.query.get(quiz.lesson_id)
        
        # 计算该课程的班级平均正确率
        class_avg = db.session.query(func.avg(QuizHistory.correct_answers * 100.0 / QuizHistory.total_questions))\
            .filter(QuizHistory.lesson_id == quiz.lesson_id,
                   QuizHistory.user_id != current_user.id)\
            .scalar() or 0
        
        trend_data.append({
            'date': quiz.completed_at.strftime('%Y-%m-%d'),
            'correct_rate': round(quiz.correct_rate),  # 取整
            'class_avg': round(class_avg),  # 取整
            'lesson_title': lesson.title if lesson else 'Unknown'
        })
    trend_data.reverse()  # 按时间顺序排列
    
    return render_template('student/dashboard.html',
                         total_quizzes=total_quizzes,
                         average_correct_rate=total_correct_rate,
                         history_data=history_data,
                         trend_data=json.dumps(trend_data),
                         lessons=available_lessons)

@app.route('/admin/lesson/<int:lesson_id>/edit', methods=['POST'])
@admin_required
def edit_lesson(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    
    # 获取表单数据
    title = request.form.get('title')
    description = request.form.get('description')
    class_ids = request.form.getlist('class_ids')  # 注意这里使用class_ids而不是class_id
    
    if not title or not class_ids:
        flash('课程标题和所属班级不能为空')
        return redirect(url_for('admin_lessons'))
    
    # 更新课程信息
    lesson.title = title
    lesson.description = description
    
    # 更新班级关联
    lesson.classes = []  # 清除现有关联
    for class_id in class_ids:
        class_ = Class.query.get(class_id)
        if class_:
            lesson.classes.append(class_)
    
    try:
        db.session.commit()
        flash('课程更新成功')
    except Exception as e:
        db.session.rollback()
        flash(f'更新失败：{str(e)}')
    
    return redirect(url_for('admin_lessons'))

@app.route('/admin/lesson/<int:lesson_id>/upload_exam')
@admin_required
def upload_exam(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    exam_files = ExamFile.query.filter_by(lesson_id=lesson_id).order_by(ExamFile.page_number).all()
    return render_template('admin/upload_exam.html', 
                         lesson=lesson,
                         exam_files=exam_files)

@app.route('/student/quiz/start/<int:lesson_id>')
@login_required
def start_quiz(lesson_id):
    user = current_user
    lesson = Lesson.query.get_or_404(lesson_id)
    
    # 验证课程是否属于用户班级且已激活
    user_class = Class.query.get(user.class_id)
    if user_class not in lesson.classes or not lesson.is_active:
        flash('无法访问该课程')
        return redirect(url_for('student_dashboard'))
    
    # 检查是否已经完成过这个课程的答题
    existing_quiz = QuizHistory.query.filter_by(
        user_id=user.id,
        lesson_id=lesson_id
    ).first()
    
    if existing_quiz:
        flash('你已经完成过这个课程的答题，不能重复答题', 'warning')
        return redirect(url_for('view_history', lesson_id=lesson_id))
    
    # 检查课程是否有题目
    questions = Question.query.filter_by(lesson_id=lesson_id).order_by(Question.question_number).all()
    if not questions:
        flash('该课程还没有题目，请等待教师上传题目')
        return redirect(url_for('student_dashboard'))
    
    # 获取试题文件
    exam_files = ExamFile.query.filter_by(lesson_id=lesson_id).order_by(ExamFile.page_number).all()
    if not exam_files:
        flash('该课程还没有上传试卷，请等待教师上传试卷')
        return redirect(url_for('student_dashboard'))

    # 获取解析文件
    explanation_files = ExplanationFile.query.filter_by(lesson_id=lesson_id).order_by(ExplanationFile.page_number).all()

    # 创建一个空的表单用于CSRF保护
    form = FlaskForm()
    
    return render_template('student/quiz.html',
                         lesson=lesson,
                         questions=questions,
                         exam_files=exam_files,
                         explanation_files=explanation_files,
                         form=form)

@app.route('/student/lesson/<int:lesson_id>/submit_quiz', methods=['POST'])
@login_required
def submit_quiz(lesson_id):
    try:
        # 获取所有题目
        questions = Question.query.filter_by(lesson_id=lesson_id).order_by(Question.question_number).all()
        if not questions:
            flash('未找到题目', 'error')
            return redirect(url_for('student_dashboard'))

        # 获取答题用时
        time_spent = int(request.form.get('time_spent', 0))

        # 创建答题历史记录
        quiz_history = QuizHistory(
            user_id=current_user.id,
            lesson_id=lesson_id,
            total_questions=len(questions),
            correct_answers=0,  # 初始化为0，后面会更新
            time_spent=time_spent,
            completed_at=datetime.now()
        )
        db.session.add(quiz_history)
        db.session.flush()  # 获取quiz_history.id

        correct_count = 0
        # 处理每个题目的答案
        for question in questions:
            # 检查是否选择了"不会做"
            idk_answer = request.form.get(f'answer_{question.id}_idk')
            user_answer = request.form.get(f'answer_{question.id}', '').strip()
            
            # 如果选择了"不会做"或没有提交答案，标记为未作答
            if idk_answer == 'IDK' or not user_answer:
                answer_record = UserAnswer(
                    user_id=current_user.id,
                    lesson_id=lesson_id,
                    question_id=question.id,
                    quiz_history_id=quiz_history.id,
                    answer='IDK' if idk_answer == 'IDK' else '',
                    is_correct=False
                )
                db.session.add(answer_record)
                continue

            # 根据题目类型判断答案正确性
            is_correct = False
            if question.type == 'proof':  # 解答题
                is_correct = True if user_answer else False  # 只要提交了答案就算正确
            elif question.type == 'choice':  # 选择题
                is_correct = user_answer.upper() == question.answer.upper()
            else:  # 填空题
                is_correct = user_answer.strip() == question.answer.strip()

            # 创建用户答案记录
            answer_record = UserAnswer(
                user_id=current_user.id,
                lesson_id=lesson_id,
                question_id=question.id,
                quiz_history_id=quiz_history.id,
                answer=user_answer,
                is_correct=is_correct
            )
            db.session.add(answer_record)
            
            if is_correct:
                correct_count += 1

        # 更新答题历史的正确题目数
        quiz_history.correct_answers = correct_count
        
        # 计算正确率
        correct_rate = (correct_count / len(questions)) * 100

        # 更新成就计数和徽章等级
        # Level 0 到 Level 1：只要提交作业就升级
        if current_user.badge_level == 0:
            current_user.badge_level = 1
            current_user.achievement_count = 1
            flash('恭喜！你获得了第一个徽章：小毛毛虫！🐛', 'success')
        # Level 1 到 Level 3：需要达到60%
        elif current_user.badge_level < 3:
            if correct_rate >= 60:
                current_user.achievement_count += 1
                if current_user.achievement_count >= current_user.badge_level + 1:
                    current_user.badge_level += 1
                    flash(f'恭喜！你已经升级到 {current_user.badge_info["name"]} 级别！', 'success')
        # Level 3 到 Level 8：每级需要两次80%
        elif 3 <= current_user.badge_level < 8:
            if correct_rate >= 80:
                current_user.achievement_count += 1
                if current_user.achievement_count >= (current_user.badge_level - 2) * 2:
                    current_user.badge_level += 1
                    flash(f'恭喜！你已经升级到 {current_user.badge_info["name"]} 级别！', 'success')
        # Level 8以上：每级需要五次80%
        else:
            if correct_rate >= 80:
                current_user.achievement_count += 1
                achievements_needed = (current_user.badge_level - 7) * 5 + 10
                if current_user.achievement_count >= achievements_needed:
                    current_user.badge_level += 1
                    flash(f'太厉害了！你已经升级到 {current_user.badge_info["name"]} 级别！', 'success')
        
        db.session.commit()

        flash('答题完成！', 'success')
        return redirect(url_for('view_history', lesson_id=lesson_id))

    except Exception as e:
        db.session.rollback()
        print(f"Error in submit_quiz: {str(e)}")
        flash('提交答案时出错', 'error')
        return redirect(url_for('student_dashboard'))

@app.route('/admin/question/<int:lesson_id>/add', methods=['POST'])
@admin_required
def add_question(lesson_id):
    content = request.form.get('content')
    answer = request.form.get('answer')
    explanation = request.form.get('explanation')
    
    if not content or not answer:
        flash('题目内容和正确答案不能为空')
        return redirect(url_for('manage_questions', lesson_id=lesson_id))
    
    if answer not in ['A', 'B', 'C', 'D']:
        flash('正确答案必须是A、B、C或D')
        return redirect(url_for('manage_questions', lesson_id=lesson_id))
    
    new_question = Question(
        content=content,
        answer=answer,
        explanation=explanation,
        lesson_id=lesson_id
    )
    db.session.add(new_question)
    db.session.commit()
    
    flash('题目添加成功')
    return redirect(url_for('manage_questions', lesson_id=lesson_id))

@app.route('/admin/question/<int:question_id>/edit', methods=['POST'])
@admin_required
def edit_question(question_id):
    try:
        data = request.get_json()
        question = Question.query.get_or_404(question_id)
        
        # 验证答案格式
        answer = data.get('answer', '').strip().upper()
        if question.type == 'choice' and answer not in ['A', 'B', 'C', 'D']:
            return jsonify({'error': '选择题答案必须是A、B、C或D'}), 400
        
        question.answer = answer
        question.points = int(data.get('points', 1))
        db.session.commit()
        
        return jsonify({'message': '更新成功'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/question/<int:question_id>/delete', methods=['POST'])
@admin_required
def delete_question(question_id):
    question = Question.query.get_or_404(question_id)
    lesson_id = question.lesson_id
    db.session.delete(question)
    db.session.commit()
    
    flash('题目删除成功')
    return redirect(url_for('manage_questions', lesson_id=lesson_id))

@app.route('/admin/question/<int:lesson_id>/import', methods=['POST'])
@admin_required
def import_questions(lesson_id):
    if 'file' not in request.files:
        flash('没有选择文件', 'error')
        return redirect(url_for('manage_questions', lesson_id=lesson_id))
    
    file = request.files['file']
    if file.filename == '':
        flash('没有选择文件', 'error')
        return redirect(url_for('manage_questions', lesson_id=lesson_id))
    
    if not file.filename.endswith(tuple(ALLOWED_EXCEL_EXTENSIONS)):
        flash('只支持Excel文件（.xlsx或.xls）', 'error')
        return redirect(url_for('manage_questions', lesson_id=lesson_id))
    
    try:
        df = pd.read_excel(file)
        success_count = 0
        error_count = 0
        
        for _, row in df.iterrows():
            try:
                if pd.notna(row[0]) and pd.notna(row[1]):  # 确保题号和答案不为空
                    question_number = int(row[0])
                    answer = str(row[1]).strip().upper()
                    content = str(row[2]) if len(row) > 2 and pd.notna(row[2]) else "题目内容待补充"
                    explanation = str(row[3]) if len(row) > 3 and pd.notna(row[3]) else None
                    
                    # 根据答案判断题目类型
                    question_type = 'choice' if answer in ['A', 'B', 'C', 'D'] else 'fill'
                    
                    # 查找是否已存在该题号的题目
                    question = Question.query.filter_by(
                        lesson_id=lesson_id,
                        question_number=question_number
                    ).first()
                    
                    if question:
                        # 更新现有题目
                        question.type = question_type
                        question.answer = answer
                        question.content = content
                        question.explanation = explanation
                    else:
                        # 创建新题目
                        question = Question(
                            lesson_id=lesson_id,
                            question_number=question_number,
                            type=question_type,
                            answer=answer,
                            content=content,
                            explanation=explanation
                        )
                        db.session.add(question)
                    
                    success_count += 1
            except Exception as e:
                error_count += 1
                print(f"导入题目时出错: {str(e)}")
                continue
        
        db.session.commit()
        flash_message = f'成功导入{success_count}道题目'
        if error_count > 0:
            flash_message += f'，{error_count}道题目导入失败'
        flash(flash_message, 'success' if error_count == 0 else 'warning')
    except Exception as e:
        flash(f'导入失败：{str(e)}', 'error')
    
    return redirect(url_for('manage_questions', lesson_id=lesson_id))

@app.route('/student/lesson/<int:lesson_id>/history')
def view_history(lesson_id):
    # 检查课程是否存在
    lesson = Lesson.query.get_or_404(lesson_id)
    
    # 获取当前用户的所有答题记录
    quiz_history = QuizHistory.query.filter_by(
        user_id=current_user.id,
        lesson_id=lesson_id
    ).order_by(QuizHistory.completed_at.desc()).all()
    
    # 如果用户有答题记录，允许查看历史，即使课程当前未激活
    if quiz_history:
        # 获取最近一次答题的详细信息
        latest_quiz = quiz_history[0]
        latest_answers = UserAnswer.query.filter_by(quiz_history_id=latest_quiz.id).all()
        latest_questions = [answer.question for answer in latest_answers]
        
        # 获取试题图片
        exam_files = ExamFile.query.filter_by(lesson_id=lesson_id).order_by(ExamFile.page_number).all()
        explanation_files = ExplanationFile.query.filter_by(lesson_id=lesson_id).order_by(ExplanationFile.page_number).all()
        
        return render_template('student/quiz_history.html',
                             lesson=lesson,
                             quiz_history=quiz_history,
                             latest_questions=latest_questions,
                             latest_answers=latest_answers,
                             exam_files=exam_files,
                             explanation_files=explanation_files)
    else:
        # 如果没有答题记录，且课程未激活，则不允许访问
        if not lesson.is_active:
            flash('该课程当前未激活，且您没有历史答题记录。', 'warning')
            return redirect(url_for('student_dashboard'))
            
        flash('还没有答题记录', 'info')
        return render_template('student/quiz_history.html', lesson=lesson, quiz_history=None)

@app.route('/student/quiz/detail/<int:history_id>')
@login_required
def quiz_detail(history_id):
    user = current_user
    quiz_history = QuizHistory.query.get_or_404(history_id)
    
    # 验证历史记录是否属于当前用户
    if quiz_history.user_id != user.id:
        flash('无权访问该记录')
        return redirect(url_for('student_dashboard'))
    
    # 获取该次答题的所有答案
    user_answers = UserAnswer.query.filter_by(
        user_id=user.id,
        lesson_id=quiz_history.lesson_id,
        created_at=quiz_history.completed_at
    ).order_by(UserAnswer.question_id).all()
    
    # 获取所有问题
    questions = Question.query.filter_by(
        lesson_id=quiz_history.lesson_id
    ).order_by(Question.question_number).all()
    
    # 获取试卷文件
    exam_files = ExamFile.query.filter_by(
        lesson_id=quiz_history.lesson_id
    ).order_by(ExamFile.page_number).all()
    
    # 获取解析文件
    explanation_files = ExplanationFile.query.filter_by(
        lesson_id=quiz_history.lesson_id
    ).order_by(ExplanationFile.page_number).all()
    
    # 创建问题和答案的映射
    question_answers = {}
    for answer in user_answers:
        question = Question.query.get(answer.question_id)
        if question:
            is_correct = True if question.type == 'proof' else (answer.answer == question.answer)
            question_answers[question] = {
                'selected_answer': answer.answer,
                'is_correct': is_correct
            }
    
    return render_template('student/detail.html',
                         quiz_history=quiz_history,
                         question_answers=question_answers,
                         exam_files=exam_files,
                         explanation_files=explanation_files)

def allowed_file(filename, allowed_extensions):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

# 文件处理函数
def save_uploaded_file(file, allowed_extensions):
    if file and file.filename != '' and allowed_file(file.filename, allowed_extensions):
        # 确保上传目录存在
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        # 生成安全的文件名
        filename = secure_filename(file.filename)
        # 添加时间戳避免文件名冲突
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
        # 保存文件
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        return filename
    return None

def init_db():
    print("检查数据库状态...")
    
    with app.app_context():
        # 创建所有表
        db.create_all()
        print("数据库表已创建！")
        
        # 检查是否需要创建默认数据
        if not Class.query.first():
            print("创建默认班级...")
            # 创建默认班级
            default_class = Class(
                name='默认班级',
                description='系统默认班级',
                is_active=True
            )
            db.session.add(default_class)
            db.session.commit()
            print(f"默认班级已创建，ID: {default_class.id}")
            
            print("创建管理员账号...")
            # 创建管理员账号
            admin = User(
                username='admin',
                email='admin@example.com',
                password='admin123',
                is_active=True,
                is_admin=True,
                class_id=default_class.id
            )
            db.session.add(admin)
            
            # 创建测试学生账号
            student = User(
                username='student',
                email='student@example.com',
                password='student123',
                is_active=True,
                is_admin=False,
                class_id=default_class.id
            )
            db.session.add(student)
            
            db.session.commit()
            print("账号已创建！")
            
        print("数据库初始化完成！")

# 试卷管理相关路由
@app.route('/admin/lesson/<int:lesson_id>/manage_exam')
@admin_required
def manage_exam(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    exam_files = ExamFile.query.filter_by(lesson_id=lesson_id).all()
    questions = Question.query.filter_by(lesson_id=lesson_id).all()
    explanation_files = ExplanationFile.query.filter_by(lesson_id=lesson_id).all()
    return render_template('admin/manage_exam.html', 
                         lesson=lesson, 
                         exam_files=exam_files,
                         questions=questions,
                         explanation_files=explanation_files)

@app.route('/admin/lesson/<int:lesson_id>/upload_exam_files', methods=['POST'])
@admin_required
def upload_exam_files(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    if 'files[]' not in request.files:
        flash('没有选择文件', 'error')
        return redirect(url_for('manage_questions', lesson_id=lesson_id))
    
    files = request.files.getlist('files[]')
    print(f"收到{len(files)}个文件上传请求")
    
    # 获取当前最大页码
    max_page = db.session.query(func.max(ExamFile.page_number)).filter_by(lesson_id=lesson_id).scalar() or 0
    
    success_count = 0
    for file in files:
        if file and allowed_file(file.filename, ALLOWED_PDF_EXTENSIONS.union(ALLOWED_IMAGE_EXTENSIONS)):
            try:
                # 生成安全的文件名
                original_filename = secure_filename(file.filename)
                # 添加时间戳和课程ID，避免文件名冲突
                filename = f"{lesson_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{original_filename}"
                
                # 设置相对路径（用于数据库存储和URL访问）
                relative_path = f'uploads/exams/{filename}'
                # 设置绝对路径（用于文件保存）
                absolute_path = os.path.join('static', relative_path)
                
                # 确保目录存在
                os.makedirs(os.path.dirname(absolute_path), exist_ok=True)
                
                # 保存文件
                file.save(absolute_path)
                print(f"文件已保存到: {absolute_path}")
                print(f"数据库存储路径: {relative_path}")
                
                # 创建试卷文件记录
                exam_file = ExamFile(
                    filename=filename,
                    path=relative_path,  # 存储相对路径
                    lesson_id=lesson_id,
                    page_number=max_page + 1 + success_count
                )
                db.session.add(exam_file)
                success_count += 1
                
            except Exception as e:
                print(f"上传失败: {str(e)}")
                flash(f'文件 {file.filename} 上传失败：{str(e)}', 'error')
                continue
    
    if success_count > 0:
        try:
            db.session.commit()
            flash(f'成功上传{success_count}个文件', 'success')
        except Exception as e:
            db.session.rollback()
            print(f"保存到数据库失败: {str(e)}")
            flash('保存文件记录失败，请重试', 'error')
    
    return redirect(url_for('manage_questions', lesson_id=lesson_id))

@app.route('/admin/exam_file/<int:file_id>/delete', methods=['POST'])
@admin_required
def delete_exam_file(file_id):
    exam_file = ExamFile.query.get_or_404(file_id)
    lesson_id = exam_file.lesson_id
    
    try:
        # 构建完整的文件路径
        file_path = os.path.join('static', exam_file.path)
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # 删除数据库记录
        db.session.delete(exam_file)
        db.session.commit()
        flash('文件删除成功', 'success')
    except Exception as e:
        print(f"删除文件失败: {str(e)}")
        flash('文件删除失败', 'error')
        
    return redirect(url_for('manage_questions', lesson_id=lesson_id))

@app.route('/admin/lesson/<int:lesson_id>/import_answers', methods=['POST'])
@admin_required
def import_answers(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    if 'file' not in request.files:
        flash('没有选择文件', 'error')
        return redirect(url_for('manage_exam', lesson_id=lesson_id))
    
    file = request.files['file']
    if file and file.filename.endswith('.xlsx'):
        try:
            df = pd.read_excel(file)
            for _, row in df.iterrows():
                question = Question(
                    lesson_id=lesson_id,
                    question_text=row['题目'],
                    correct_answer=row['答案'],
                    points=row['分值']
                )
                db.session.add(question)
            db.session.commit()
            flash('答案导入成功', 'success')
        except Exception as e:
            flash('答案导入失败', 'error')
    else:
        flash('请上传Excel文件', 'error')
        
    return redirect(url_for('manage_exam', lesson_id=lesson_id))

@app.route('/admin/lesson/<int:lesson_id>/upload_explanation_files', methods=['POST'])
@admin_required
def upload_explanation_files(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    if 'files[]' not in request.files:
        flash('没有选择文件', 'error')
        return redirect(url_for('manage_questions', lesson_id=lesson_id))
    
    files = request.files.getlist('files[]')
    print(f"收到{len(files)}个解析文件上传请求")
    
    # 获取当前最大页码
    max_page = db.session.query(func.max(ExplanationFile.page_number)).filter_by(lesson_id=lesson_id).scalar() or 0
    
    success_count = 0
    for file in files:
        if file and allowed_file(file.filename, ALLOWED_PDF_EXTENSIONS):
            try:
                # 生成安全的文件名
                original_filename = secure_filename(file.filename)
                # 添加时间戳和课程ID，避免文件名冲突
                filename = f"{lesson_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{original_filename}"
                
                # 设置相对路径（用于数据库存储和URL访问）
                relative_path = f'uploads/explanations/{filename}'
                # 设置绝对路径（用于文件保存）
                absolute_path = os.path.join('static', relative_path)
                
                # 确保目录存在
                os.makedirs(os.path.dirname(absolute_path), exist_ok=True)
                
                # 保存文件
                file.save(absolute_path)
                print(f"解析文件已保存到: {absolute_path}")
                print(f"数据库存储路径: {relative_path}")
                
                # 创建解析文件记录
                explanation_file = ExplanationFile(
                    filename=filename,
                    path=relative_path,  # 存储相对路径
                    lesson_id=lesson_id,
                    page_number=max_page + 1 + success_count
                )
                db.session.add(explanation_file)
                success_count += 1
                
            except Exception as e:
                print(f"上传解析文件失败: {str(e)}")
                flash(f'文件 {file.filename} 上传失败：{str(e)}', 'error')
                continue
    
    if success_count > 0:
        try:
            db.session.commit()
            flash(f'成功上传{success_count}个解析文件', 'success')
        except Exception as e:
            db.session.rollback()
            print(f"保存到数据库失败: {str(e)}")
            flash('保存文件记录失败，请重试', 'error')
    
    return redirect(url_for('manage_questions', lesson_id=lesson_id))

@app.route('/admin/explanation_file/<int:file_id>/delete', methods=['POST'])
@admin_required
def delete_explanation_file(file_id):
    explanation_file = ExplanationFile.query.get_or_404(file_id)
    lesson_id = explanation_file.lesson_id
    
    try:
        # 构建完整的文件路径
        file_path = os.path.join('static', explanation_file.path)
        if os.path.exists(file_path):
            os.remove(file_path)
            
        # 删除数据库记录
        db.session.delete(explanation_file)
        db.session.commit()
        flash('解析文件删除成功', 'success')
    except Exception as e:
        print(f"删除文件失败: {str(e)}")
        flash('解析文件删除失败', 'error')
        
    return redirect(url_for('manage_questions', lesson_id=lesson_id))

@app.route('/static/<path:filename>')
def serve_static(filename):
    # 移除路径中的重复 'static'
    if filename.startswith('static/'):
        filename = filename[7:]
    
    # 检查是否是PDF文件
    if filename.lower().endswith('.pdf'):
        # 设置响应头，禁止下载
        response = send_from_directory('static', filename)
        response.headers['Content-Disposition'] = 'inline'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response
    
    return send_from_directory('static', filename)

@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    # 确保路径正确
    if filename.startswith('uploads/'):
        filename = filename[8:]
    
    # 检查是否是PDF文件
    if filename.lower().endswith('.pdf'):
        # 设置响应头，禁止下载
        response = send_from_directory('uploads', filename)
        response.headers['Content-Disposition'] = 'inline'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response
    
    return send_from_directory('uploads', filename)

@app.route('/admin/lesson/<int:lesson_id>/add_questions', methods=['POST'])
@admin_required
def add_questions(lesson_id):
    try:
        print("开始添加题目...")  # 调试日志
        # 获取所有答案
        answers = request.form.getlist('answers[]')
        print(f"收到的答案数量: {len(answers)}")  # 调试日志
        
        # 获取当前最大题号
        max_question_number = db.session.query(func.max(Question.question_number)).filter_by(lesson_id=lesson_id).scalar() or 0
        
        # 添加新题目
        for i, answer in enumerate(answers, max_question_number + 1):
            answer = answer.strip().upper()  # 转换为大写并去除空白
            print(f"处理第{i}题答案: {answer}")  # 调试日志
            
            # 根据答案判断题目类型
            if not answer:  # 空答案表示证明题
                question_type = 'proof'
                answer = '证明题'
            elif answer in ['A', 'B', 'C', 'D', 'E']:  # ABCDE表示选择题
                question_type = 'choice'
            else:  # 其他情况为填空题
                question_type = 'fill'
            
            print(f"题目类型: {question_type}")  # 调试日志
            
            # 查找是否已存在该题号的题目
            existing_question = Question.query.filter_by(
                lesson_id=lesson_id,
                question_number=i
            ).first()
            
            if existing_question:
                # 更新现有题目
                existing_question.type = question_type
                existing_question.answer = answer
            else:
                # 创建新题目
                question = Question(
                    lesson_id=lesson_id,
                    question_number=i,
                    type=question_type,
                    answer=answer,
                    content=f"第{i}题"  # 添加默认内容
                )
                db.session.add(question)
            
            print(f"已处理第{i}题")  # 调试日志
        
        print("准备提交到数据库...")  # 调试日志
        db.session.commit()
        print("成功提交到数据库")  # 调试日志
        flash('题目添加成功', 'success')
        
    except Exception as e:
        db.session.rollback()
        print(f"添加题目时出错: {str(e)}")  # 调试日志
        print(f"错误类型: {type(e)}")  # 添加错误类型信息
        flash(f'添加题目时出错: {str(e)}', 'error')
    
    return redirect(url_for('manage_questions', lesson_id=lesson_id))

@app.route('/admin/lesson/<int:lesson_id>/upload_individual_exam_files', methods=['POST'])
@admin_required
def upload_individual_exam_files(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    
    try:
        # 获取Base64图片数据
        image_data = request.form.get('file')
        if not image_data or not image_data.startswith('data:image'):
            flash('无效的图片数据', 'error')
            return redirect(url_for('manage_questions', lesson_id=lesson_id))
        
        # 解析Base64数据
        image_data = image_data.split(',')[1]
        image_bytes = base64.b64decode(image_data)
        
        # 使用PIL打开图片并转换为PNG格式
        image = Image.open(io.BytesIO(image_bytes))
        
        # 获取当前最大页码
        max_page = db.session.query(func.max(ExamFile.page_number)).filter_by(lesson_id=lesson_id).scalar() or 0
        
        # 生成带毫秒的时间戳
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        
        # 生成文件名（添加随机数以确保唯一性）
        random_suffix = random.randint(1000, 9999)
        filename = f"{lesson_id}_{timestamp}_{random_suffix}.png"
        relative_path = f'uploads/exams/{filename}'
        absolute_path = os.path.join('static', relative_path)
        
        # 确保目录存在
        os.makedirs(os.path.dirname(absolute_path), exist_ok=True)
        
        # 保存图片
        image.save(absolute_path, 'PNG')
        
        # 创建试卷文件记录
        exam_file = ExamFile(
            filename=filename,
            path=relative_path,
            lesson_id=lesson_id,
            page_number=max_page + 1
        )
        db.session.add(exam_file)
        db.session.commit()
        
        flash('试题上传成功', 'success')
        
    except Exception as e:
        db.session.rollback()
        print(f"上传失败: {str(e)}")
        flash(f'图片上传失败：{str(e)}', 'error')
    
    return redirect(url_for('manage_questions', lesson_id=lesson_id))

@app.route('/admin/lesson/<int:lesson_id>/upload_individual_explanation_files', methods=['POST'])
@admin_required
def upload_individual_explanation_files(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    
    try:
        # 获取Base64图片数据
        image_data = request.form.get('file')
        if not image_data or not image_data.startswith('data:image'):
            flash('无效的图片数据', 'error')
            return redirect(url_for('manage_questions', lesson_id=lesson_id))
        
        # 解析Base64数据
        image_data = image_data.split(',')[1]
        image_bytes = base64.b64decode(image_data)
        
        # 使用PIL打开图片并转换为PNG格式
        image = Image.open(io.BytesIO(image_bytes))
        
        # 获取当前最大页码
        max_page = db.session.query(func.max(ExplanationFile.page_number)).filter_by(lesson_id=lesson_id).scalar() or 0
        
        # 生成带毫秒的时间戳
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        
        # 生成文件名（添加随机数以确保唯一性）
        random_suffix = random.randint(1000, 9999)
        filename = f"{lesson_id}_{timestamp}_{random_suffix}.png"
        relative_path = f'uploads/explanations/{filename}'
        absolute_path = os.path.join('static', relative_path)
        
        # 确保目录存在
        os.makedirs(os.path.dirname(absolute_path), exist_ok=True)
        
        # 保存图片
        image.save(absolute_path, 'PNG')
        
        # 创建解析文件记录
        explanation_file = ExplanationFile(
            filename=filename,
            path=relative_path,
            lesson_id=lesson_id,
            page_number=max_page + 1
        )
        db.session.add(explanation_file)
        db.session.commit()
        
        flash('解析上传成功', 'success')
        
    except Exception as e:
        db.session.rollback()
        print(f"上传失败: {str(e)}")
        flash(f'图片上传失败：{str(e)}', 'error')
    
    return redirect(url_for('manage_questions', lesson_id=lesson_id))

@app.route('/admin/badge_rules')
@admin_required
def badge_rules():
    return render_template('admin/badge_rules.html')

@app.route('/admin/student/<int:user_id>/dashboard')
@admin_required
def student_dashboard_admin(user_id):
    # 获取学生用户
    student = User.query.get_or_404(user_id)
    if student.is_admin:
        flash('无法查看管理员的仪表盘')
        return redirect(url_for('admin_users'))
    
    # 获取该学生的所有测验历史记录
    quiz_history = QuizHistory.query.filter_by(user_id=student.id).all()
    
    # 计算总测验数和平均正确率
    total_quizzes = len(quiz_history)
    if total_quizzes > 0:
        total_correct_rate = round(sum(quiz.correct_rate for quiz in quiz_history) / total_quizzes)
    else:
        total_correct_rate = 0
    
    # 获取历史课程数据
    history_data = db.session.query(Lesson, QuizHistory)\
        .join(QuizHistory, Lesson.id == QuizHistory.lesson_id)\
        .filter(QuizHistory.user_id == student.id)\
        .order_by(QuizHistory.completed_at.desc())\
        .all()
    
    # 获取已完成的课程ID列表
    completed_lesson_ids = [quiz.lesson_id for quiz in quiz_history]
    
    # 获取当前可用的课程（激活状态且未完成的课程）
    available_lessons = Lesson.query.join(
        lesson_class_association,
        Lesson.id == lesson_class_association.c.lesson_id
    ).filter(
        lesson_class_association.c.class_id == student.class_id,
        Lesson.is_active == True,
        ~Lesson.id.in_(completed_lesson_ids) if completed_lesson_ids else True
    ).all()
    
    # 准备趋势图数据
    trend_data = []
    for quiz in quiz_history:
        lesson = Lesson.query.get(quiz.lesson_id)
        
        # 计算该课程的班级平均正确率
        class_avg = db.session.query(func.avg(QuizHistory.correct_answers * 100.0 / QuizHistory.total_questions))\
            .filter(QuizHistory.lesson_id == quiz.lesson_id,
                   QuizHistory.user_id != student.id)\
            .scalar() or 0
        
        trend_data.append({
            'date': quiz.completed_at.strftime('%Y-%m-%d'),
            'correct_rate': round(quiz.correct_rate),  # 取整
            'class_avg': round(class_avg),  # 取整
            'lesson_title': lesson.title if lesson else 'Unknown'
        })
    trend_data.reverse()  # 按时间顺序排列
    
    return render_template('student/dashboard.html',
                         current_user=student,  # 使用学生用户信息
                         total_quizzes=total_quizzes,
                         average_correct_rate=total_correct_rate,
                         history_data=history_data,
                         trend_data=json.dumps(trend_data),
                         lessons=available_lessons,
                         is_admin_view=True)  # 标记这是管理员视图

@app.route('/student/wrong_questions')
@login_required
def wrong_questions():
    # 获取用户所有的错题记录
    wrong_answers = (db.session.query(
        UserAnswer, Question, Lesson, QuizHistory
    ).join(
        Question, UserAnswer.question_id == Question.id
    ).join(
        Lesson, Question.lesson_id == Lesson.id
    ).join(
        QuizHistory, UserAnswer.quiz_history_id == QuizHistory.id
    ).filter(
        UserAnswer.user_id == current_user.id,
        UserAnswer.is_correct == False
    ).order_by(
        Lesson.id,
        Question.question_number
    ).all())

    # 获取包含错题的课程列表
    lessons = list(set(wa.Lesson for wa in wrong_answers))
    lessons.sort(key=lambda x: x.id)

    # 获取每个错题对应的试卷和解析图片
    images = {}
    for wa in wrong_answers:
        lesson_id = wa.Lesson.id
        question_number = wa.Question.question_number
        key = (lesson_id, question_number)
        
        if key not in images:
            # 获取对应的试卷图片
            exam_file = ExamFile.query.filter_by(
                lesson_id=lesson_id,
                page_number=question_number
            ).first()
            
            # 获取对应的解析图片
            explanation_file = ExplanationFile.query.filter_by(
                lesson_id=lesson_id,
                page_number=question_number
            ).first()
            
            images[key] = {
                'exam': exam_file.path if exam_file else None,
                'explanation': explanation_file.path if explanation_file else None
            }

    return render_template(
        'student/wrong_questions.html',
        wrong_answers=wrong_answers,
        lessons=lessons,
        images=images
    )

@app.route('/admin/lesson/<int:lesson_id>/upload_video', methods=['POST'])
@admin_required
def upload_video(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    video_url = request.form.get('video_url')
    
    if not video_url:
        flash('视频链接不能为空')
        return redirect(url_for('admin_lessons'))
    
    try:
        lesson.video_url = video_url
        db.session.commit()
        flash('视频链接更新成功')
    except Exception as e:
        db.session.rollback()
        flash(f'更新失败：{str(e)}')
    
    return redirect(url_for('admin_lessons'))

@app.route('/admin/user/add', methods=['POST'])
@admin_required
def add_user():
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    role = request.form.get('role')
    class_ids = request.form.getlist('classes')  # 获取多个班级ID
    
    if not username or not email or not password:
        return redirect(url_for('admin_users'))
    
    if User.query.filter_by(username=username).first():
        return redirect(url_for('admin_users'))
    
    if User.query.filter_by(email=email).first():
        return redirect(url_for('admin_users'))
    
    # 创建新用户
    new_user = User(
        username=username,
        email=email,
        password=password,
        is_active=True
    )
    
    # 设置用户角色
    if role == 'admin':
        new_user.is_admin = True
    elif role == 'student' and class_ids:
        # 如果是学生，添加班级关联
        for class_id in class_ids:
            class_ = Class.query.get(class_id)
            if class_:
                new_user.classes.append(class_)
    
    try:
        db.session.add(new_user)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
    
    return redirect(url_for('admin_users'))

if __name__ == '__main__':
    init_db()  # 初始化数据库
    app.run(debug=True, host='0.0.0.0', port=5000) 