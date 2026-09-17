from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory, send_file, abort
import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass
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
from sqlalchemy.exc import IntegrityError
import cloudinary
import cloudinary.uploader
from cloudinary_config import *  # σ»╝σàÑ Cloudinary Θàìτ╜«
from collections import defaultdict
import requests
from io import BytesIO

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # τö¿Σ║Ä flash µ╢êµü»σÆî session

# Θàìτ╜« CSRF Σ┐¥µèñ
csrf = CSRFProtect(app)
app.config['WTF_CSRF_TIME_LIMIT'] = 10800  # CSRF Σ╗ñτëîµ£ëµòêµ£ƒΦ«╛τ╜«Σ╕║3σ░Åµù╢
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=3)  # Σ╝ÜΦ»¥µ£ëµòêµ£ƒΦ«╛τ╜«Σ╕║3σ░Åµù╢

# Θàìτ╜«Σ╝ÜΦ»¥Σ╕║µ░╕Σ╣àµÇºτÜä∩╝îΦ┐Öµá╖σÅ»Σ╗Ñσ╗╢Θò┐Σ╝ÜΦ»¥τÜäµ£ëµòêµ£ƒ
@app.before_request
def make_session_permanent():
    session.permanent = True

# Θàìτ╜« Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Θàìτ╜«µò░µì«σ║ô
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

if not database_url:
    # σªéµ₧£µ▓íµ£ëΦ«╛τ╜«τÄ»σóâσÅÿΘçÅ∩╝îΣ╜┐τö¿Θ╗ÿΦ«ñτÜäSQLiteΘàìτ╜«∩╝êτö¿Σ║Äµ£¼σ£░σ╝ÇσÅæ∩╝ë
    base_dir = os.path.abspath(os.path.dirname(__file__))
    database_url = f'sqlite:///{os.path.join(base_dir, "instance", "quiz.db")}'

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# σ╗╢Φ┐ƒσê¥σºïσîû SQLAlchemy∩╝îΘü┐σàì debug reloader Σ╕ï _app_engines KeyError∩╝êΦ»èµû¡τ½»µ│¿σåî/τÖ╗σ╜òτ¡ë∩╝ë
db = SQLAlchemy()
db.init_app(app)

# Θàìτ╜«µûçΣ╗╢Σ╕èΣ╝á
UPLOAD_FOLDER = 'uploads'  # Σ┐«µö╣Σ╕║Σ╕ìσ╕ª static σëìτ╝ÇτÜäΦ╖»σ╛ä
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
ALLOWED_PDF_EXTENSIONS = {'pdf'}
ALLOWED_EXCEL_EXTENSIONS = {'xlsx', 'xls'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # ΘÖÉσê╢µûçΣ╗╢σñºσ░ÅΣ╕║16MB

# Φ»èµû¡µ¿íσ¥ùΘóäτòÖΘàìτ╜«∩╝êsubscription scaffolding∩╝îσ╜ôσëìΣ╕ìσÉ»τö¿∩╝ë
app.config['BILLING_ENABLED'] = os.environ.get('BILLING_ENABLED', 'false').lower() == 'true'
app.config['STRIPE_WEBHOOK_SECRET'] = os.environ.get('STRIPE_WEBHOOK_SECRET', '')
app.config['DIAG_SHOW_HELP_BUTTON'] = False  # µ£¬µ¥Ñσ╝ÇσÉ»σ╕«σè⌐σàÑσÅú
app.config['DIAG_OFFICIAL_WEBSITE_URL'] = os.environ.get('DIAG_OFFICIAL_WEBSITE_URL', '')  # Φ»èµû¡τ│╗τ╗ƒΘí╢µáÅπÇîσ«ÿτ╜æπÇìσàÑσÅúΘô╛µÄÑ∩╝îτ⌐║σêÖµ¿íµ¥┐σåàτö¿ #

# τí«Σ┐¥Σ╕èΣ╝áτ¢«σ╜òσ¡ÿσ£¿
os.makedirs(os.path.join('static', UPLOAD_FOLDER, 'exams'), exist_ok=True)
os.makedirs(os.path.join('static', UPLOAD_FOLDER, 'explanations'), exist_ok=True)

migrate = Migrate(app, db)

def create_default_admin():
    """σê¢σ╗║Θ╗ÿΦ«ñτ«íτÉåσæÿΦ┤ªµê╖∩╝êσªéµ₧£Σ╕ìσ¡ÿσ£¿∩╝ë"""
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(
            username='admin',
            email='admin@example.com',
            password='admin123',  # Φ»╖σ£¿Θªûµ¼íτÖ╗σ╜òσÉÄτ½ïσì│Σ┐«µö╣µ¡ñσ»åτáü
            is_admin=True,
            is_active=True
        )
        db.session.add(admin)
        try:
            db.session.commit()
            print("Θ╗ÿΦ«ñτ«íτÉåσæÿΦ┤ªµê╖σ╖▓σê¢σ╗║")
        except Exception as e:
            db.session.rollback()
            print(f"σê¢σ╗║Θ╗ÿΦ«ñτ«íτÉåσæÿΦ┤ªµê╖σñ▒Φ┤Ñ: {str(e)}")

@app.before_first_request
def initialize_app():
    """σ£¿τ¼¼Σ╕Çµ¼íΦ»╖µ▒éΣ╣ïσëìσê¥σºïσîûσ║öτö¿"""
    create_default_admin()

# τí«Σ┐¥µëÇµ£ëΦí¿σ¡ÿσ£¿σ╣╢σê¢σ╗║Θ╗ÿΦ«ñµò░µì«
def init_db():
    with app.app_context():
        try:
            print("σ╝Çσºïµò░µì«σ║ôσê¥σºïσîû...")
            
            # σàêσ░¥Φ»òσêáΘÖñµëÇµ£ëΦí¿∩╝îτä╢σÉÄΘçìµû░σê¢σ╗║
            db.drop_all()
            db.create_all()
            print("µò░µì«σ║ôΦí¿σê¢σ╗║µêÉσèƒ")
            
            # µúÇµƒÑµÿ»σÉªΘ£ÇΦªüσê¢σ╗║Θ╗ÿΦ«ñµò░µì«
            admin = User.query.filter_by(is_admin=True).first()
            if not admin:
                print("σê¢σ╗║Θ╗ÿΦ«ñτ«íτÉåσæÿΦ┤ªσÅ╖...")
                # σê¢σ╗║Θ╗ÿΦ«ñτÅ¡τ║º
                default_class = Class(
                    name='Θ╗ÿΦ«ñτÅ¡τ║º',
                    description='τ│╗τ╗ƒΘ╗ÿΦ«ñτÅ¡τ║º',
                    is_active=True
                )
                db.session.add(default_class)
                db.session.flush()  # ΦÄ╖σÅûdefault_classτÜäID
                
                # σê¢σ╗║τ«íτÉåσæÿΦ┤ªσÅ╖
                admin = User(
                    username='admin',
                    email='admin@example.com',
                    password='admin123',
                    is_active=True,
                    is_admin=True,
                    class_id=default_class.id
                )
                db.session.add(admin)
                db.session.commit()
                print("Θ╗ÿΦ«ñµò░µì«σê¢σ╗║µêÉσèƒ∩╝ü")
            else:
                print("τ«íτÉåσæÿΦ┤ªσÅ╖σ╖▓σ¡ÿσ£¿∩╝îΦ╖│Φ┐çσê¢σ╗║Θ╗ÿΦ«ñµò░µì«πÇé")
        except Exception as e:
            print(f"µò░µì«σ║ôσê¥σºïσîûσç║ΘöÖ: {str(e)}")
            # σªéµ₧£σç║ΘöÖ∩╝îσ╝║σê╢Θçìµû░σê¢σ╗║µò░µì«σ║ô
            print("σ╝║σê╢Θçìµû░σê¢σ╗║µò░µì«σ║ô...")
            db.drop_all()
            db.create_all()
            print("µò░µì«σ║ôΘçìµû░σê¢σ╗║µêÉσèƒ")
            
            # Θçìµû░σê¢σ╗║Θ╗ÿΦ«ñµò░µì«
            try:
                default_class = Class(
                    name='Θ╗ÿΦ«ñτÅ¡τ║º',
                    description='τ│╗τ╗ƒΘ╗ÿΦ«ñτÅ¡τ║º',
                    is_active=True
                )
                db.session.add(default_class)
                db.session.flush()
                
                admin = User(
                    username='admin',
                    email='admin@example.com',
                    password='admin123',
                    is_active=True,
                    is_admin=True,
                    class_id=default_class.id
                )
                db.session.add(admin)
                db.session.commit()
                print("Θ╗ÿΦ«ñµò░µì«Θçìµû░σê¢σ╗║µêÉσèƒ∩╝ü")
            except Exception as e2:
                print(f"Θçìµû░σê¢σ╗║Θ╗ÿΦ«ñµò░µì«σñ▒Φ┤Ñ: {str(e2)}")
                db.session.rollback()

# Φ»╛τ¿ïσÆîτÅ¡τ║ºτÜäσñÜσ»╣σñÜσà│ΦüöΦí¿
lesson_class_association = db.Table('lesson_class_association',
    db.Column('lesson_id', db.Integer, db.ForeignKey('lesson.id'), primary_key=True),
    db.Column('class_id', db.Integer, db.ForeignKey('class.id'), primary_key=True)
)

# σ«ÜΣ╣ëτÅ¡τ║ºµ¿íσ₧ï
class Class(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=True)  # τÅ¡τ║ºσÉìτº░
    description = db.Column(db.String(200))  # τÅ¡τ║ºµÅÅΦ┐░
    is_active = db.Column(db.Boolean, default=True)  # µÿ»σÉªµ┐Çµ┤╗
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    users = db.relationship('User', backref='class', lazy=True)
    lessons = db.relationship('Lesson', secondary=lesson_class_association, backref='classes', lazy=True)

# σ«ÜΣ╣ëΦ»╛τ¿ïµ¿íσ₧ï
class Lesson(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)  # Φ»╛τ¿ïµáçΘóÿ
    description = db.Column(db.String(200))  # Φ»╛τ¿ïµÅÅΦ┐░
    is_active = db.Column(db.Boolean, default=False)  # µÿ»σÉªσ╜ôσëìµÿ╛τñ║
    video_url = db.Column(db.String(500))  # ΦºåΘóæσ¢₧µö╛Θô╛µÄÑ
    # τ«íτÉåσæÿΣ╕èΣ╝áτÜäτƒÑΦ»åτé╣τ¼öΦ«░∩╝êσìòσ¢╛ URL∩╝ë∩╝¢τ⌐║σêÖσ¡ªτöƒτ½»Σ╕ìµÿ╛τñ║πÇîτƒÑΦ»åτé╣πÇìµîëΘÆ«
    kp_notes_image_url = db.Column(db.String(512), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    questions = db.relationship('Question', backref='lesson', lazy=True)

# Φ»òσì╖µûçΣ╗╢µ¿íσ₧ï
class ExamFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    path = db.Column(db.String(255), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=False)
    page_number = db.Column(db.Integer, nullable=False)  # Θí╡τáü
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    lesson = db.relationship('Lesson', backref=db.backref('exam_files', lazy=True))

# Φºúµ₧ÉµûçΣ╗╢µ¿íσ₧ï
class ExplanationFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    path = db.Column(db.String(255), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=False)
    page_number = db.Column(db.Integer, nullable=False)  # Θí╡τáü
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    lesson = db.relationship('Lesson', backref=db.backref('explanation_files', lazy=True))

# σ«ÜΣ╣ëΘóÿτ¢«µ¿íσ₧ï
class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=False)
    question_number = db.Column(db.Integer, nullable=False)  # ΘóÿσÅ╖
    type = db.Column(db.String(10), nullable=False)  # Θóÿτ¢«τ▒╗σ₧ï∩╝Üchoice∩╝êΘÇëµï⌐Θóÿ∩╝ëπÇüfill∩╝êσí½τ⌐║Θóÿ∩╝ëµêûproof∩╝êΦ»üµÿÄΘóÿ∩╝ë
    answer = db.Column(db.String(100), nullable=False)  # µ¡úτí«τ¡öµíê
    content = db.Column(db.String(500))  # τº╗ΘÖñnullable=Falseτ║ªµ¥ƒ
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('lesson_id', 'question_number', name='unique_question_number'),
    )

# σ«ÜΣ╣ëτö¿µê╖µ¿íσ₧ï
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False)
    class_id = db.Column(db.Integer, db.ForeignKey('class.id'))
    achievement_count = db.Column(db.Integer, default=0)  # Φ╛╛µáçµ¼íµò░∩╝ê80%Σ╗ÑΣ╕èµ¡úτí«τÄç∩╝ë
    badge_level = db.Column(db.Integer, default=0)  # σ╛╜τ½áτ¡ëτ║º∩╝îΘ╗ÿΦ«ñΣ╕║0∩╝êµùáσ╛╜τ½á∩╝ë
    report_link = db.Column(db.String(500), nullable=True)  # Φ»╛σáéµÖ║Φâ╜µèÑσæèΘô╛µÄÑ

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Σ╕Çσ»╣σñÜσà│τ│╗
    answers = db.relationship('UserAnswer', backref='user', lazy=True, cascade="all, delete-orphan")
    quiz_history = db.relationship('QuizHistory', backref='user', lazy=True, cascade="all, delete-orphan")

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
                "icon": "Γ¥ô",
                "achievements": self.achievement_count,
                "next_level_at": 1,
                "next_achievements_needed": 1,
                "encouragement": "Ready to start your journey!"
            }

        badges = {
            1: {"name": "Little Worm", "icon": "≡ƒÉ¢", "next_level": 2},
            2: {"name": "Butterfly", "icon": "≡ƒªï", "next_level": 4},
            3: {"name": "Python", "icon": "≡ƒÉì", "next_level": 6},
            4: {"name": "Wolf", "icon": "≡ƒÉ║", "next_level": 8},
            5: {"name": "Tiger", "icon": "≡ƒÉ»", "next_level": 10},
            6: {"name": "Dragon", "icon": "≡ƒÉ▓", "next_level": 12},
            7: {"name": "Mini Monster", "icon": "≡ƒæ╛", "next_level": 14},
            8: {"name": "Big Monster", "icon": "≡ƒæ╣", "next_level": 16},
            9: {"name": "Beast", "icon": "≡ƒªû", "next_level": 18},
            10: {"name": "Dragon", "icon": "≡ƒÉë", "next_level": None}
        }
        current_badge = badges.get(self.badge_level, badges[1])
        
        # τ«ÇσîûτÜäσ╛╜τ½áσìçτ║ºΦ«íτ«ùΘÇ╗Φ╛æ
        if current_badge["next_level"]:
            if self.badge_level < 3:
                # Level 1-2: Θ£ÇΦªü60%Σ╗ÑΣ╕èµ¡úτí«τÄç
                if self.badge_level == 1:
                    next_achievements_needed = 2 - (self.achievement_count % 2)
                else:  # Level 2
                    next_achievements_needed = 3 - (self.achievement_count % 3)
            elif self.badge_level < 8:
                # Level 3-7: Θ£ÇΦªü80%Σ╗ÑΣ╕èµ¡úτí«τÄç∩╝îµ»Åµ¼í2µ¼íΦ╛╛µáç
                next_achievements_needed = 2 - (self.achievement_count % 2)
            else:
                # Level 8+: Θ£ÇΦªü80%Σ╗ÑΣ╕èµ¡úτí«τÄç∩╝îµ»Åµ¼í5µ¼íΦ╛╛µáç
                next_achievements_needed = 5 - (self.achievement_count % 5)
        else:
            next_achievements_needed = 0
            
        return {
            "current_level": self.badge_level,
            "name": current_badge["name"],
            "icon": current_badge["icon"],
            "achievements": self.achievement_count,
            "next_level_at": current_badge["next_level"],
            "next_achievements_needed": max(0, next_achievements_needed),
            "encouragement": encouragements.get(self.badge_level, "Amazing progress!")
        }

# τö¿µê╖τ¡öΘóÿΦ«░σ╜òµ¿íσ₧ï
class UserAnswer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    quiz_history_id = db.Column(db.Integer, db.ForeignKey('quiz_history.id'), nullable=False)
    answer = db.Column(db.Text, nullable=True)  # Σ╜┐τö¿Textτ▒╗σ₧ïµö»µîüµ¢┤Θò┐τÜäτ¡öµíê
    is_correct = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    question = db.relationship('Question', backref='user_answers')
    quiz_history = db.relationship('QuizHistory', backref='answers')

# σ«ÜΣ╣ëτ¡öΘóÿσÄåσÅ▓Φ«░σ╜òµ¿íσ₧ï
class QuizHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=False)
    total_questions = db.Column(db.Integer, nullable=False)
    correct_answers = db.Column(db.Integer, nullable=False)
    time_spent = db.Column(db.Integer, nullable=False)  # τ¡öΘóÿτö¿µù╢∩╝êτºÆ∩╝ë
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # τº╗ΘÖñ user = db.relationship('User', backref='quiz_history', lazy=True)
    lesson = db.relationship('Lesson', backref='quiz_history', lazy=True)
    
    @property
    def correct_rate(self):
        return (self.correct_answers / self.total_questions * 100) if self.total_questions > 0 else 0


# ========== Φ»èµû¡µ¿íσ¥ùτï¼τ½ïΦí¿∩╝êdiag_ σëìτ╝Ç∩╝îΣ╕ìσ╜▒σôìτÄ░µ£ëΣ╕Üσèí∩╝ë==========
class DiagUser(db.Model):
    __tablename__ = 'diag_users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # ΘóäτòÖ∩╝Üµ£¬µ¥ÑΘé«τ«▒µë╛σ¢₧
    email = db.Column(db.String(255), nullable=True)
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    # µ│¿σåîσ¡ªσæÿΦíÑσààΣ┐íµü»∩╝êσÅ»ΘÇë∩╝îΘ╗ÿΦ«ñΣ╕ìσ╜▒σôìµùºΦ┤ªσÅ╖∩╝ë
    birth_year = db.Column(db.Integer, nullable=True)  # σç║τöƒσ╣┤Σ╗╜
    school = db.Column(db.String(255), nullable=True)  # σ¡ªµáí
    province = db.Column(db.String(32), nullable=True, default='BC')  # σ£░σî║∩╝êτ£ü/σ╖₧∩╝ë∩╝îΘ╗ÿΦ«ñ BC


class DiagPasswordResetToken(db.Model):
    """ΘóäτòÖ∩╝Üσ»åτáüΘçìτ╜« token∩╝îσ╜ôσëìΣ╕ìσÉ»τö¿ UI"""
    __tablename__ = 'diag_password_reset_tokens'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('diag_users.id', ondelete='CASCADE'), nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('DiagUser', backref=db.backref('reset_tokens', lazy=True))


class DiagSubscription(db.Model):
    """ΘóäτòÖ∩╝ÜΦ«óΘÿàτè╢µÇü∩╝îΘ╗ÿΦ«ñ allow_all∩╝îµ£¬µ¥Ñµö╢Φ┤╣µù╢σÉ»τö¿"""
    __tablename__ = 'diag_subscriptions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('diag_users.id', ondelete='CASCADE'), nullable=False)
    plan = db.Column(db.String(32), nullable=False, default='legacy_active')  # free/trial/pro/legacy_active
    status = db.Column(db.String(32), nullable=False, default='active')  # active/trialing/past_due/canceled/none
    current_period_end = db.Column(db.DateTime, nullable=True)
    provider = db.Column(db.String(32), nullable=True)  # stripe
    provider_customer_id = db.Column(db.String(255), nullable=True)
    provider_subscription_id = db.Column(db.String(255), nullable=True)
    entitlements_json = db.Column(db.Text, nullable=True)  # σèƒΦâ╜σ╝Çσà│ JSON
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user = db.relationship('DiagUser', backref=db.backref('subscriptions', lazy=True))


class DiagSupportTicket(db.Model):
    """ΘóäτòÖ∩╝Üσ«óµ£ìσ╖Ñσìò∩╝îσ╜ôσëìµùá UI"""
    __tablename__ = 'diag_support_tickets'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('diag_users.id', ondelete='CASCADE'), nullable=False)
    category = db.Column(db.String(64), nullable=True)
    message = db.Column(db.Text, nullable=False)
    attachment_url = db.Column(db.String(512), nullable=True)
    status = db.Column(db.String(32), nullable=False, default='open')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('DiagUser', backref=db.backref('support_tickets', lazy=True))


class DiagAuthAudit(db.Model):
    """ΘóäτòÖ∩╝ÜτÖ╗σ╜òσ«íΦ«í∩╝îσ╜ôσëìΣ╕ìσÉ»τö¿σÉîµù╢σ£¿τ║┐ΘÖÉσê╢"""
    __tablename__ = 'diag_auth_audit'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('diag_users.id', ondelete='CASCADE'), nullable=False)
    event = db.Column(db.String(32), nullable=False)  # login/logout
    ip = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(512), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('DiagUser', backref=db.backref('auth_audits', lazy=True))


class DiagSession(db.Model):
    __tablename__ = 'diag_sessions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('diag_users.id'), nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('DiagUser', backref=db.backref('sessions', lazy=True))


class DiagGuestStudent(db.Model):
    """σà¼σ╝Çµ╡ïΦ»äσàÑσÅú∩╝Üµùáµ│¿σåîΦ┤ªσÅ╖τÜäµ╡ïΦ»äσ¡ªσæÿ∩╝êΣ╗à diagnostic Φí¿∩╝ëπÇé"""
    __tablename__ = 'diag_guest_students'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    grade = db.Column(db.String(8), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class DiagGuestSession(db.Model):
    """Φ«┐σ«óΣ╝ÜΦ»¥∩╝Ücookie token τ╗æσ«Ü diag_guest_studentsπÇé"""
    __tablename__ = 'diag_guest_sessions'
    id = db.Column(db.Integer, primary_key=True)
    guest_student_id = db.Column(db.Integer, db.ForeignKey('diag_guest_students.id', ondelete='CASCADE'), nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    guest_student = db.relationship('DiagGuestStudent', backref=db.backref('sessions', lazy=True))


class DiagCompetition(db.Model):
    __tablename__ = 'diag_competitions'
    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(80), nullable=True, default='')   # σ¡ªτºæ∩╝îσªé∩╝Üµò░σ¡ªτ½₧Φ╡¢
    category = db.Column(db.String(80), nullable=True, default='')  # τ½₧Φ╡¢σñºτ▒╗∩╝îσªé∩╝ÜWaterloo
    name = db.Column(db.String(120), nullable=False)                # σà╖Σ╜ôτ½₧Φ╡¢∩╝îσªé∩╝ÜGauss7 2025
    # σêåµ«╡σêåσÇ╝ JSON∩╝Ü[{"start":1,"end":10,"points":5},{"start":11,"end":20,"points":6}]∩╝îΘóÿσÅ╖ 1-based∩╝îµ£¬Φ«╛σêÖµ»ÅΘóÿ 1 σêå
    score_scheme = db.Column(db.Text, nullable=True)
    blank_bonus = db.Column(db.Integer, nullable=True, default=0)  # τ⌐║ΘóÿσèáσêåσÇ╝∩╝îµ£¬Σ╜£τ¡öµ»ÅΘóÿσèáσçáσêå∩╝îΘ╗ÿΦ«ñ 0


class DiagExam(db.Model):
    __tablename__ = 'diag_exams'
    id = db.Column(db.Integer, primary_key=True)
    competition_id = db.Column(db.Integer, db.ForeignKey('diag_competitions.id'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    year = db.Column(db.Integer, nullable=True)  # σ╣┤Σ╗╜∩╝îσªé 2025
    time_limit_sec = db.Column(db.Integer, nullable=True)
    is_published = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # 1=G1ΓÇôG6, 2=G7ΓÇôG9, 3=G10ΓÇôG12 σêåτ║ºΦ»èµû¡σì╖∩╝¢τ⌐║Φí¿τñ║µÖ«ΘÇÜτ½₧Φ╡¢σì╖
    diag_placement_level = db.Column(db.Integer, nullable=True)
    competition = db.relationship('DiagCompetition', backref=db.backref('exams', lazy=True))


class DiagQuestion(db.Model):
    __tablename__ = 'diag_questions'
    id = db.Column(db.Integer, primary_key=True)
    competition_id = db.Column(db.Integer, db.ForeignKey('diag_competitions.id'), nullable=False)
    stem_text = db.Column(db.Text, nullable=False)
    stem_image_url = db.Column(db.String(512), nullable=True)  # Θóÿσ╣▓σ¢╛τëç∩╝êτ▓ÿΦ┤┤Σ╕èΣ╝á∩╝ë
    choices_json = db.Column(db.Text, nullable=True)
    answer_key = db.Column(db.String(20), nullable=True)
    solution_text = db.Column(db.Text, nullable=True)
    solution_image_url = db.Column(db.String(512), nullable=True)  # Φºúµ₧Éσ¢╛τëç∩╝êτ▓ÿΦ┤┤Σ╕èΣ╝á∩╝ë
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    competition = db.relationship('DiagCompetition', backref=db.backref('questions', lazy=True))


class DiagExamQuestion(db.Model):
    __tablename__ = 'diag_exam_questions'
    exam_id = db.Column(db.Integer, db.ForeignKey('diag_exams.id'), primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('diag_questions.id'), primary_key=True)
    q_index = db.Column(db.Integer, nullable=False)
    exam = db.relationship('DiagExam', backref=db.backref('exam_questions', lazy=True))
    question = db.relationship('DiagQuestion', backref=db.backref('exam_links', lazy=True))


class DiagAttempt(db.Model):
    __tablename__ = 'diag_attempts'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('diag_users.id'), nullable=True)
    guest_student_id = db.Column(db.Integer, db.ForeignKey('diag_guest_students.id', ondelete='SET NULL'), nullable=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('diag_exams.id'), nullable=False)
    status = db.Column(db.String(20), default='in_progress')
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    finished_at = db.Column(db.DateTime, nullable=True)
    total_time_ms = db.Column(db.BigInteger, default=0)
    placement_level = db.Column(db.Integer, nullable=True)
    guest_grade = db.Column(db.String(16), nullable=True)
    share_token = db.Column(db.String(64), unique=True, nullable=True)
    user = db.relationship('DiagUser', backref=db.backref('attempts', lazy=True))
    guest_student = db.relationship('DiagGuestStudent', backref=db.backref('attempts', lazy=True))
    exam = db.relationship('DiagExam', backref=db.backref('attempts', lazy=True))


class DiagnosticBenchmarkSample(db.Model):
    """Φ»èµû¡τ│╗τ╗ƒσÅéΦÇâµá╖µ£¼σêåσ╕â∩╝êσå╖σÉ»σè¿/τ£ƒσ«₧µá╖µ£¼∩╝ëπÇéΣ╗à diagnostic Σ╜┐τö¿∩╝îΣ╕ìσ╜▒σôìΣ╜£Σ╕Üτ╜æτ½ÖπÇé"""
    __tablename__ = 'diagnostic_benchmark_samples'
    id = db.Column(db.Integer, primary_key=True)
    contest_key = db.Column(db.String(64), nullable=False, index=True)
    score = db.Column(db.Float, nullable=False)
    max_score = db.Column(db.Float, nullable=False)
    source_type = db.Column(db.String(20), nullable=False, default='seed')  # 'seed' | 'real'
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class DiagAttemptAnswer(db.Model):
    __tablename__ = 'diag_attempt_answers'
    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey('diag_attempts.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('diag_questions.id'), nullable=False)
    answer = db.Column(db.String(50), nullable=True)
    is_correct = db.Column(db.Boolean, nullable=True)
    time_spent_ms = db.Column(db.BigInteger, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    attempt = db.relationship('DiagAttempt', backref=db.backref('answers', lazy=True))
    question = db.relationship('DiagQuestion', backref=db.backref('attempt_answers', lazy=True))


class DiagKnowledgePoint(db.Model):
    __tablename__ = 'diag_knowledge_points'
    kp_id = db.Column(db.String(64), primary_key=True)
    competition_id = db.Column(db.Integer, db.ForeignKey('diag_competitions.id'), nullable=False)
    name_en = db.Column(db.String(120), nullable=True)
    name_cn = db.Column(db.String(120), nullable=True)
    parent_kp_id = db.Column(db.String(64), nullable=True)
    competition = db.relationship('DiagCompetition', backref=db.backref('knowledge_points', lazy=True))


class DiagQuestionTag(db.Model):
    __tablename__ = 'diag_question_tags'
    question_id = db.Column(db.Integer, db.ForeignKey('diag_questions.id'), primary_key=True)
    kp_id = db.Column(db.String(64), primary_key=True)
    weight = db.Column(db.Float, default=1.0)
    manual_override = db.Column(db.Boolean, default=False)
    question = db.relationship('DiagQuestion', backref=db.backref('tags', lazy=True))


class DiagBankQuestion(db.Model):
    __tablename__ = 'diag_bank_questions'
    id = db.Column(db.Integer, primary_key=True)
    competition_id = db.Column(db.Integer, db.ForeignKey('diag_competitions.id'), nullable=False)
    stem_text = db.Column(db.Text, nullable=False)
    choices_json = db.Column(db.Text, nullable=True)
    answer_key = db.Column(db.String(20), nullable=True)
    solution_text = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    competition = db.relationship('DiagCompetition', backref=db.backref('bank_questions', lazy=True))


class DiagBankQuestionTag(db.Model):
    __tablename__ = 'diag_bank_question_tags'
    bank_question_id = db.Column(db.Integer, db.ForeignKey('diag_bank_questions.id'), primary_key=True)
    kp_id = db.Column(db.String(64), primary_key=True)
    weight = db.Column(db.Float, default=1.0)
    bank_question = db.relationship('DiagBankQuestion', backref=db.backref('tags', lazy=True))


class DiagQuestionBankLink(db.Model):
    __tablename__ = 'diag_question_bank_links'
    question_id = db.Column(db.Integer, db.ForeignKey('diag_questions.id'), primary_key=True)
    bank_question_id = db.Column(db.Integer, db.ForeignKey('diag_bank_questions.id'), primary_key=True)
    link_order = db.Column(db.Integer, nullable=False)
    question = db.relationship('DiagQuestion', backref=db.backref('bank_links', lazy=True))
    bank_question = db.relationship('DiagBankQuestion', backref=db.backref('diagnostic_links', lazy=True))


class DiagQuestionAnswer(db.Model):
    """CSV σ»╝σàÑτÜäµ»ÅΘóÿτ¡öµíêΣ╕ÄΦºúµ₧É∩╝êµîë exam+q_index σî╣Θàì∩╝ë"""
    __tablename__ = 'diag_question_answers'
    exam_id = db.Column(db.Integer, db.ForeignKey('diag_exams.id', ondelete='CASCADE'), primary_key=True)
    q_index = db.Column(db.Integer, primary_key=True)
    correct_answer = db.Column(db.String(50), nullable=True)
    solution_explain = db.Column(db.Text, nullable=True)
    answer_format = db.Column(db.String(20), nullable=True)
    reserved_1 = db.Column(db.String(255), nullable=True)  # needs_image µù╢σ¡ÿ "1"
    reserved_2 = db.Column(db.String(255), nullable=True)
    reserved_3 = db.Column(db.String(255), nullable=True)
    extra_json = db.Column(db.Text, nullable=True)
    exam = db.relationship('DiagExam', backref=db.backref('imported_answers', lazy=True))


class DiagQuestionKp(db.Model):
    """CSV σ»╝σàÑτÜäµ»ÅΘóÿτƒÑΦ»åτé╣∩╝êΦç¬τö▒µûçµ£¼∩╝ë"""
    __tablename__ = 'diag_question_kp'
    exam_id = db.Column(db.Integer, db.ForeignKey('diag_exams.id', ondelete='CASCADE'), primary_key=True)
    q_index = db.Column(db.Integer, primary_key=True)
    kp_primary = db.Column(db.String(120), nullable=True)
    kp_secondary = db.Column(db.Text, nullable=True)
    reserved_1 = db.Column(db.String(255), nullable=True)
    reserved_2 = db.Column(db.String(255), nullable=True)
    reserved_3 = db.Column(db.String(255), nullable=True)
    extra_json = db.Column(db.Text, nullable=True)
    exam = db.relationship('DiagExam', backref=db.backref('imported_kp', lazy=True))


class DiagQuestionPracticeItem(db.Model):
    """CSV σ»╝σàÑτÜäΘöÖΘóÿτ╗âΣ╣áΘ¢å∩╝êµ»ÅΘóÿ 5-8 Θüô∩╝ë"""
    __tablename__ = 'diag_question_practice_items'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('diag_exams.id', ondelete='CASCADE'), nullable=False)
    q_index = db.Column(db.Integer, nullable=False)
    item_index = db.Column(db.Integer, nullable=False)
    stem = db.Column(db.Text, nullable=False)
    choices = db.Column(db.Text, nullable=True)
    answer = db.Column(db.String(50), nullable=True)
    explain = db.Column(db.Text, nullable=True)
    source = db.Column(db.String(32), nullable=True)
    reserved_1 = db.Column(db.String(255), nullable=True)
    reserved_2 = db.Column(db.String(255), nullable=True)
    reserved_3 = db.Column(db.String(255), nullable=True)
    extra_json = db.Column(db.Text, nullable=True)
    exam = db.relationship('DiagExam', backref=db.backref('practice_items_imported', lazy=True))


class DiagExamQuestionPracticeConfig(db.Model):
    """CSV σ»╝σàÑτÜäµ»ÅΘóÿΘ╗ÿΦ«ñτ╗âΣ╣áµò░ΘçÅ"""
    __tablename__ = 'diag_exam_question_practice_config'
    exam_id = db.Column(db.Integer, db.ForeignKey('diag_exams.id', ondelete='CASCADE'), primary_key=True)
    q_index = db.Column(db.Integer, primary_key=True)
    practice_count_default = db.Column(db.Integer, nullable=False, default=3)
    reserved_1 = db.Column(db.String(255), nullable=True)
    reserved_2 = db.Column(db.String(255), nullable=True)
    reserved_3 = db.Column(db.String(255), nullable=True)
    extra_json = db.Column(db.Text, nullable=True)
    exam = db.relationship('DiagExam', backref=db.backref('practice_config_imported', lazy=True))


class DiagQuestionPracticeConfig(db.Model):
    __tablename__ = 'diag_question_practice_config'
    question_id = db.Column(db.Integer, db.ForeignKey('diag_questions.id'), primary_key=True)
    is_capstone = db.Column(db.Boolean, default=False)
    practice_mode = db.Column(db.String(64), default='bank_by_kp')
    random_count = db.Column(db.Integer, default=3)
    homework_assignment_id = db.Column(db.Integer, nullable=True)
    curated_homework_question_ids = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    question = db.relationship('DiagQuestion', backref=db.backref('practice_config', uselist=False), lazy=True)


class DiagPracticeSet(db.Model):
    __tablename__ = 'diag_practice_sets'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('diag_users.id'), nullable=True)
    guest_student_id = db.Column(db.Integer, db.ForeignKey('diag_guest_students.id', ondelete='SET NULL'), nullable=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey('diag_attempts.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('DiagUser', backref=db.backref('practice_sets', lazy=True))
    guest_student = db.relationship('DiagGuestStudent', backref=db.backref('practice_sets', lazy=True))
    attempt = db.relationship('DiagAttempt', backref=db.backref('practice_sets', lazy=True))


class DiagPracticeSetItem(db.Model):
    __tablename__ = 'diag_practice_set_items'
    id = db.Column(db.Integer, primary_key=True)
    practice_set_id = db.Column(db.Integer, db.ForeignKey('diag_practice_sets.id'), nullable=False)
    source_type = db.Column(db.String(16), nullable=False)
    source_question_id = db.Column(db.Integer, nullable=False)
    q_index = db.Column(db.Integer, nullable=False)
    practice_set = db.relationship('DiagPracticeSet', backref=db.backref('items', lazy=True))


class DiagPracticeAttempt(db.Model):
    """τ╗âΣ╣áσîàµÅÉΣ║ñΦ«░σ╜ò∩╝Üµ»ÅΣ╕¬τ╗âΣ╣áσîàµ»ÅΣ║║σÅ¬Φâ╜µÅÉΣ║ñΣ╕Çµ¼í∩╝îσåìΦ┐¢σàÑµÿ╛τñ║σ╖▓σ«îµêÉΣ╕Äσ╛ùσêå"""
    __tablename__ = 'diag_practice_attempts'
    id = db.Column(db.Integer, primary_key=True)
    practice_set_id = db.Column(db.Integer, db.ForeignKey('diag_practice_sets.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('diag_users.id'), nullable=True)
    guest_student_id = db.Column(db.Integer, db.ForeignKey('diag_guest_students.id', ondelete='SET NULL'), nullable=True)
    answers_json = db.Column(db.Text, nullable=True)  # {"item_id": "A", ...}
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    practice_set = db.relationship('DiagPracticeSet', backref=db.backref('attempts', lazy=True))
    user = db.relationship('DiagUser', backref=db.backref('practice_attempts', lazy=True))
    guest_student = db.relationship('DiagGuestStudent', backref=db.backref('practice_attempts', lazy=True))


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Φ»╖σàêτÖ╗σ╜ò')
            return redirect(url_for('login'))
        if not current_user.is_admin:
            flash('Θ£ÇΦªüτ«íτÉåσæÿµ¥âΘÖÉ')
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
        
        print(f"σ░¥Φ»òτÖ╗σ╜ò: τö¿µê╖σÉì = {username}")  # µ╖╗σèáµùÑσ┐ù
        
        user = User.query.filter_by(username=username).first()
        if user:
            print(f"µë╛σê░τö¿µê╖: {user.username}, µ┐Çµ┤╗τè╢µÇü: {user.is_active}")  # µ╖╗σèáµùÑσ┐ù
            if user.password == password:
                if not user.is_active:
                    flash('Φ┤ªσÅ╖µ£¬µ┐Çµ┤╗∩╝îΦ»╖Φüöτ│╗τ«íτÉåσæÿ')
                    return redirect(url_for('login'))
                login_user(user)
                print(f"τö¿µê╖ {username} τÖ╗σ╜òµêÉσèƒ")  # µ╖╗σèáµùÑσ┐ù
                flash('τÖ╗σ╜òµêÉσèƒ∩╝ü')
                return redirect(url_for('index'))
            else:
                print(f"σ»åτáüΘöÖΦ»»: {username}")  # µ╖╗σèáµùÑσ┐ù
                flash('σ»åτáüΘöÖΦ»»')
        else:
            print(f"τö¿µê╖Σ╕ìσ¡ÿσ£¿: {username}")  # µ╖╗σèáµùÑσ┐ù
            flash('τö¿µê╖σÉìΣ╕ìσ¡ÿσ£¿')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        class_id = request.form['class_id']
        
        if password != confirm_password:
            flash('Σ╕ñµ¼íΦ╛ôσàÑτÜäσ»åτáüΣ╕ìΣ╕ÇΦç┤')
            return redirect(url_for('register'))
        
        if User.query.filter_by(username=username).first():
            flash('τö¿µê╖σÉìσ╖▓σ¡ÿσ£¿')
            return redirect(url_for('register'))
        
        # Σ╕║emailτöƒµêÉΣ╕ÇΣ╕¬Θ╗ÿΦ«ñσÇ╝
        default_email = f"{username}@example.com"
        
        new_user = User(
            username=username,
            email=default_email,  # Σ╜┐τö¿Θ╗ÿΦ«ñemail
            password=password,
            class_id=class_id,
            is_active=True  # Θ╗ÿΦ«ñΦ«╛τ╜«Σ╕║µ┐Çµ┤╗τè╢µÇü
        )
        db.session.add(new_user)
        db.session.commit()
        
        flash('µ│¿σåîµêÉσèƒ∩╝üΦ»╖τÖ╗σ╜ò')
        return redirect(url_for('login'))
    
    classes = Class.query.filter_by(is_active=True).all()
    return render_template('register.html', classes=classes)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('σ╖▓ΘÇÇσç║τÖ╗σ╜ò')
    return redirect(url_for('login'))

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    # ΦÄ╖σÅûτ╗ƒΦ«íµò░µì«
    total_students = User.query.filter_by(is_admin=False).count()
    total_lessons = Lesson.query.count()
    total_classes = Class.query.count()

    # σêåΘí╡σÅéµò░
    page = request.args.get('page', 1, type=int)
    per_page = 50

    # µƒÑΦ»óµÇ╗µò░
    total_activities = db.session.query(QuizHistory).count()
    total_pages = (total_activities + per_page - 1) // per_page

    # ΦÄ╖σÅûµ£ÇΦ┐æµ┤╗σè¿∩╝êσêåΘí╡∩╝ë
    recent_activities = db.session.query(
        QuizHistory,
        User.id.label('student_id'),
        User.username.label('student_name'),
        Lesson.title.label('lesson_title')
    ).join(
        User, QuizHistory.user_id == User.id
    ).join(
        Lesson, QuizHistory.lesson_id == Lesson.id
    ).order_by(
        QuizHistory.completed_at.desc()
    ).offset((page - 1) * per_page).limit(per_page).all()

    # σñäτÉåµ┤╗σè¿µò░µì«
    activities = []
    for activity in recent_activities:
        activities.append({
            'completed_at': activity.QuizHistory.completed_at,
            'student_id': activity.student_id,
            'student_name': activity.student_name,
            'lesson_title': activity.lesson_title,
            'correct_rate': round(activity.QuizHistory.correct_answers * 100 / activity.QuizHistory.total_questions, 1)
        })

    return render_template('admin/dashboard.html',
                         total_students=total_students,
                         total_lessons=total_lessons,
                         total_classes=total_classes,
                         recent_activities=activities,
                         page=page,
                         total_pages=total_pages)

@app.route('/admin/users')
@app.route('/admin/users/<int:class_id>')
@admin_required
def admin_users(class_id=None):
    # ΦÄ╖σÅûµëÇµ£ëτ«íτÉåσæÿτö¿µê╖
    admin_users = User.query.filter_by(is_admin=True).all()
    
    # ΦÄ╖σÅûµëÇµ£ëτÅ¡τ║º
    classes = Class.query.all()
    
    # ΦÄ╖σÅûΘ¥₧τ«íτÉåσæÿτö¿µê╖∩╝îµá╣µì«τÅ¡τ║ºIDτ¡¢ΘÇë
    if class_id:
        students = User.query.filter_by(
            class_id=class_id, 
            is_admin=False
        ).all()
        class_users = {Class.query.get(class_id): students}
    else:
        # σªéµ₧£µ▓íµ£ëµîçσ«ÜτÅ¡τ║º∩╝îΦÄ╖σÅûµëÇµ£ëτÅ¡τ║ºτÜäτö¿µê╖
        class_users = {}
        for class_ in classes:
            students = User.query.filter_by(
                class_id=class_.id,
                is_admin=False
            ).all()
            class_users[class_] = students
    
    # τ╗ƒΦ«íµ»ÅΣ╕¬σ¡ªτöƒµ£¬σ«îµêÉΣ╜£Σ╕Üµò░
    unfinished_count = defaultdict(int)
    lessons = Lesson.query.filter_by(is_active=True).all()
    for class_, students in class_users.items():
        for user in students:
            # Φ»Ñσ¡ªτöƒµëÇσ£¿τÅ¡τ║ºτÜäµëÇµ£ëΦ»╛τ¿ï
            user_lessons = [lesson for lesson in lessons if class_ in lesson.classes]
            # Φ»Ñσ¡ªτöƒσ╖▓σ«îµêÉτÜäΦ»╛τ¿ïid
            finished_ids = set(qh.lesson_id for qh in user.quiz_history)
            # µ£¬σ«îµêÉΦ»╛τ¿ïµò░
            unfinished_count[user.id] = len([l for l in user_lessons if l.id not in finished_ids])
    
    return render_template('admin/users.html', 
                         admin_users=admin_users,
                         class_users=class_users,
                         classes=classes,
                         current_class_id=class_id,
                         unfinished_count=unfinished_count)

@app.route('/admin/user/<int:user_id>/toggle', methods=['POST'])
@admin_required
def toggle_user_status(user_id):
    user = User.query.get_or_404(user_id)
    # Θÿ▓µ¡óτ«íτÉåσæÿΦó½τªüτö¿
    if user.is_admin:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'msg': 'Σ╕ìΦâ╜τªüτö¿τ«íτÉåσæÿ'})
        return redirect(url_for('admin_users'))
    user.is_active = not user.is_active
    db.session.commit()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'is_active': user.is_active})
    return redirect(url_for('admin_users'))

@app.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    
    # Θÿ▓µ¡óτ«íτÉåσæÿΦó½σêáΘÖñ
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
        flash('τÅ¡τ║ºσÉìτº░Σ╕ìΦâ╜Σ╕║τ⌐║')
        return redirect(url_for('admin_classes'))
    
    if Class.query.filter_by(name=name).first():
        flash('τÅ¡τ║ºσÉìτº░σ╖▓σ¡ÿσ£¿')
        return redirect(url_for('admin_classes'))
    
    new_class = Class(name=name, description=description)
    db.session.add(new_class)
    db.session.commit()
    
    flash('τÅ¡τ║ºµ╖╗σèáµêÉσèƒ')
    return redirect(url_for('admin_classes'))

@app.route('/admin/class/<int:class_id>/toggle', methods=['POST'])
@admin_required
def toggle_class_status(class_id):
    class_ = Class.query.get_or_404(class_id)
    class_.is_active = not class_.is_active
    db.session.commit()
    flash(f'τÅ¡τ║º {class_.name} τè╢µÇüσ╖▓µ¢┤µû░')
    return redirect(url_for('admin_classes'))

@app.route('/admin/class/<int:class_id>/delete', methods=['POST'])
@admin_required
def delete_class(class_id):
    try:
        class_ = Class.query.get_or_404(class_id)
        
        # σÅ¬σêáΘÖñΘ¥₧τ«íτÉåσæÿτö¿µê╖
        User.query.filter_by(class_id=class_id, is_admin=False).delete()
        
        # σêáΘÖñτÅ¡τ║ºσÆîΦ»╛τ¿ïτÜäσà│Φüö∩╝êΘÇÜΦ┐çσà│ΦüöΦí¿∩╝ë
        db.session.execute(lesson_class_association.delete().where(
            lesson_class_association.c.class_id == class_id
        ))
        
        # σêáΘÖñτÅ¡τ║º
        db.session.delete(class_)
        db.session.commit()
        
        flash(f'τÅ¡τ║º {class_.name} σÅèσà╢µëÇµ£ëΘ¥₧τ«íτÉåσæÿτö¿µê╖σ╖▓σêáΘÖñ', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'σêáΘÖñσñ▒Φ┤Ñ∩╝Ü{str(e)}', 'error')
        print(f"σêáΘÖñτÅ¡τ║ºµù╢σç║ΘöÖ: {str(e)}")  # µ╖╗σèáµùÑσ┐ù
    
    return redirect(url_for('admin_classes'))

@app.route('/admin/class/<int:class_id>/edit', methods=['POST'])
@admin_required
def edit_class(class_id):
    class_ = Class.query.get_or_404(class_id)
    
    # ΦÄ╖σÅûΦí¿σìòµò░µì«
    name = request.form.get('name')
    description = request.form.get('description')
    
    if not name:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'msg': 'τÅ¡τ║ºσÉìτº░Σ╕ìΦâ╜Σ╕║τ⌐║'})
        flash('τÅ¡τ║ºσÉìτº░Σ╕ìΦâ╜Σ╕║τ⌐║')
        return redirect(url_for('admin_classes'))
    
    # µúÇµƒÑσÉìτº░µÿ»σÉªσ╖▓σ¡ÿσ£¿∩╝êµÄÆΘÖñσ╜ôσëìτÅ¡τ║º∩╝ë
    existing_class = Class.query.filter(Class.name == name, Class.id != class_id).first()
    if existing_class:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'msg': 'τÅ¡τ║ºσÉìτº░σ╖▓σ¡ÿσ£¿'})
        flash('τÅ¡τ║ºσÉìτº░σ╖▓σ¡ÿσ£¿')
        return redirect(url_for('admin_classes'))
    
    # µ¢┤µû░τÅ¡τ║ºΣ┐íµü»
    class_.name = name
    class_.description = description
    
    try:
        db.session.commit()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'msg': 'τÅ¡τ║ºµ¢┤µû░µêÉσèƒ'})
        flash('τÅ¡τ║ºµ¢┤µû░µêÉσèƒ')
    except Exception as e:
        db.session.rollback()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'msg': f'µ¢┤µû░σñ▒Φ┤Ñ∩╝Ü{str(e)}'})
        flash(f'µ¢┤µû░σñ▒Φ┤Ñ∩╝Ü{str(e)}')
    
    return redirect(url_for('admin_classes'))

@app.route('/admin/lessons')
@admin_required
def admin_lessons():
    lessons = Lesson.query.order_by(Lesson.created_at.desc()).all()
    classes = Class.query.all()
    return render_template('admin/lessons.html', lessons=lessons, classes=classes)

@app.route('/admin/lesson/add', methods=['POST'])
@admin_required
def add_lesson():
    title = request.form.get('title')
    description = request.form.get('description')
    class_ids = request.form.getlist('class_ids')  # Σ┐«µö╣Φ┐ÖΘçî
    
    if not title or not class_ids:
        return redirect(url_for('admin_lessons'))
    
    # σê¢σ╗║µû░Φ»╛τ¿ï
    new_lesson = Lesson(
        title=title,
        description=description,
        is_active=False
    )
    
    # µ╖╗σèáτÅ¡τ║ºσà│Φüö
    for class_id in class_ids:
        class_ = Class.query.get(class_id)
        if class_:
            new_lesson.classes.append(class_)
    
    try:
        db.session.add(new_lesson)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
    
    return redirect(url_for('admin_lessons'))

@app.route('/admin/lesson/<int:lesson_id>/toggle', methods=['POST'])
@admin_required
def toggle_lesson_status(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    
    # τ¢┤µÄÑσêçµìóσ╜ôσëìΦ»╛τ¿ïτÜäτè╢µÇü
    lesson.is_active = not lesson.is_active
    db.session.commit()
    
    # µúÇµƒÑµÿ»σÉªµÿ»AJAXΦ»╖µ▒é
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True,
            'is_active': lesson.is_active,
            'message': f'Φ»╛τ¿ï {lesson.title} {{ "σ╖▓µ┐Çµ┤╗" if lesson.is_active else "σ╖▓σü£τö¿" }}'
        })
    
    return redirect(url_for('admin_lessons'))

@app.route('/admin/lesson/<int:lesson_id>/delete', methods=['POST'])
@admin_required
def delete_lesson(lesson_id):
    try:
        print(f"σ╝ÇσºïσêáΘÖñΦ»╛τ¿ï ID: {lesson_id}")  # Φ░âΦ»òµùÑσ┐ù
        lesson = Lesson.query.get_or_404(lesson_id)
        print(f"µë╛σê░Φ»╛τ¿ï: {lesson.title}")  # Φ░âΦ»òµùÑσ┐ù
        
        # ΘªûσàêσêáΘÖñΣ╕ÄΦ»╛τ¿ïτ¢╕σà│τÜäµëÇµ£ëτ¡öΘóÿΦ«░σ╜ò
        UserAnswer.query.filter_by(lesson_id=lesson_id).delete()
        print("σêáΘÖñΣ║åτ¡öΘóÿΦ«░σ╜ò")  # Φ░âΦ»òµùÑσ┐ù
        
        # τä╢σÉÄσêáΘÖñΦÇâΦ»òΦ«░σ╜ò
        QuizHistory.query.filter_by(lesson_id=lesson_id).delete()
        print("σêáΘÖñΣ║åΦÇâΦ»òΦ«░σ╜ò")  # Φ░âΦ»òµùÑσ┐ù
        
        # σêáΘÖñΣ╕ÄΦ»╛τ¿ïτ¢╕σà│τÜäµëÇµ£ëΦ»òσì╖µûçΣ╗╢
        exam_files = ExamFile.query.filter_by(lesson_id=lesson_id).all()
        print(f"µë╛σê░ {len(exam_files)} Σ╕¬Φ»òσì╖µûçΣ╗╢")  # Φ░âΦ»òµùÑσ┐ù
        for file in exam_files:
            try:
                # σêáΘÖñτë⌐τÉåµûçΣ╗╢∩╝êσªéµ₧£µÿ»µ£¼σ£░σ¡ÿσé¿τÜäΦ»¥∩╝ë
                file_path = os.path.join('static', file.path)
                print(f"σ░¥Φ»òσêáΘÖñµûçΣ╗╢: {file_path}")  # Φ░âΦ»òµùÑσ┐ù
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"µêÉσèƒσêáΘÖñµûçΣ╗╢: {file_path}")  # Φ░âΦ»òµùÑσ┐ù
            except Exception as e:
                print(f"σêáΘÖñµûçΣ╗╢σñ▒Φ┤Ñ: {str(e)}")  # Φ«░σ╜òµûçΣ╗╢σêáΘÖñΘöÖΦ»»Σ╜åτ╗ºτ╗¡µëºΦíî
        
        # σêáΘÖñµò░µì«σ║ôΣ╕¡τÜäΦ»òσì╖µûçΣ╗╢Φ«░σ╜ò
        ExamFile.query.filter_by(lesson_id=lesson_id).delete()
        print("σêáΘÖñΣ║åΦ»òσì╖µûçΣ╗╢Φ«░σ╜ò")  # Φ░âΦ»òµùÑσ┐ù

        # σêáΘÖñΣ╕ÄΦ»╛τ¿ïτ¢╕σà│τÜäµëÇµ£ëΦºúµ₧ÉµûçΣ╗╢
        explanation_files = ExplanationFile.query.filter_by(lesson_id=lesson_id).all()
        print(f"µë╛σê░ {len(explanation_files)} Σ╕¬Φºúµ₧ÉµûçΣ╗╢")  # Φ░âΦ»òµùÑσ┐ù
        for file in explanation_files:
            try:
                # σêáΘÖñτë⌐τÉåµûçΣ╗╢∩╝êσªéµ₧£µÿ»µ£¼σ£░σ¡ÿσé¿τÜäΦ»¥∩╝ë
                file_path = os.path.join('static', file.path)
                print(f"σ░¥Φ»òσêáΘÖñΦºúµ₧ÉµûçΣ╗╢: {file_path}")  # Φ░âΦ»òµùÑσ┐ù
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"µêÉσèƒσêáΘÖñΦºúµ₧ÉµûçΣ╗╢: {file_path}")  # Φ░âΦ»òµùÑσ┐ù
            except Exception as e:
                print(f"σêáΘÖñΦºúµ₧ÉµûçΣ╗╢σñ▒Φ┤Ñ: {str(e)}")  # Φ«░σ╜òµûçΣ╗╢σêáΘÖñΘöÖΦ»»Σ╜åτ╗ºτ╗¡µëºΦíî
        
        # σêáΘÖñµò░µì«σ║ôΣ╕¡τÜäΦºúµ₧ÉµûçΣ╗╢Φ«░σ╜ò
        ExplanationFile.query.filter_by(lesson_id=lesson_id).delete()
        print("σêáΘÖñΣ║åΦºúµ₧ÉµûçΣ╗╢Φ«░σ╜ò")  # Φ░âΦ»òµùÑσ┐ù
        
        # σêáΘÖñΣ╕ÄΦ»╛τ¿ïτ¢╕σà│τÜäµëÇµ£ëΘù«Θóÿ
        Question.query.filter_by(lesson_id=lesson_id).delete()
        print("σêáΘÖñΣ║åΘóÿτ¢«Φ«░σ╜ò")  # Φ░âΦ»òµùÑσ┐ù
        
        # σêáΘÖñΦ»╛τ¿ïσÆîτÅ¡τ║ºτÜäσà│Φüö
        lesson.classes = []
        print("σêáΘÖñΣ║åΦ»╛τ¿ïσÆîτÅ¡τ║ºτÜäσà│Φüö")  # Φ░âΦ»òµùÑσ┐ù
        
        # µ£ÇσÉÄσêáΘÖñΦ»╛τ¿ïµ£¼Φ║½
        db.session.delete(lesson)
        db.session.commit()
        print("µêÉσèƒσêáΘÖñΦ»╛τ¿ï")  # Φ░âΦ»òµùÑσ┐ù
        
        return redirect(url_for('admin_lessons'))
        
    except Exception as e:
        db.session.rollback()
        error_msg = str(e)
        print(f"σêáΘÖñΦ»╛τ¿ïµù╢σç║ΘöÖ: {error_msg}")  # Φ░âΦ»òµùÑσ┐ù
        return redirect(url_for('admin_lessons'))

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
    # ΦÄ╖σÅûτö¿µê╖τÜäµëÇµ£ëµ╡ïΘ¬îσÄåσÅ▓Φ«░σ╜ò
    quiz_history = QuizHistory.query.filter_by(user_id=current_user.id).all()
    
    # µû░σó₧∩╝Üσ«ÜΣ╣ë correct_rate∩╝îΘÿ▓µ¡óµ£¬σ«ÜΣ╣ëµèÑΘöÖ
    if quiz_history:
        correct_rate = quiz_history[-1].correct_rate  # µ£ÇΦ┐æΣ╕Çµ¼íµ╡ïΘ¬îτÜäµ¡úτí«τÄç
    else:
        correct_rate = 0
    
    # σªéµ₧£τö¿µê╖Φ┐ÿµ▓íµ£ëσ«îµêÉΣ╗╗Σ╜òµ╡ïΘ¬î∩╝îσ░åσ╛╜τ½áτ¡ëτ║ºΦ«╛τ╜«Σ╕║0
    if not quiz_history:
        current_user.badge_level = 0
        current_user.achievement_count = 0
    else:
        # σªéµ₧£τö¿µê╖σ«îµêÉΣ║åµ╡ïΘ¬îΣ╜åΦ┐ÿµÿ»Level 0∩╝îσìçτ║ºσê░Level 1
        if current_user.badge_level == 0:
            current_user.badge_level = 1
            current_user.achievement_count = 1

            flash('µü¡σû£∩╝üΣ╜áΦÄ╖σ╛ùΣ║åτ¼¼Σ╕ÇΣ╕¬σ╛╜τ½á∩╝Üσ░Åµ»¢µ»¢ΦÖ½∩╝ü≡ƒÉ¢', 'success')
        # Level 1 σê░ Level 3∩╝ÜΘ£ÇΦªüΦ╛╛σê░60%
        elif current_user.badge_level < 3:
            if correct_rate >= 60:
                # Level 1 σìç Level 2 Θ£ÇΦªü2µ¼íΦ╛╛µáç
                if current_user.badge_level == 1 and current_user.achievement_count % 2 == 0:
                    current_user.badge_level = 2
                    flash(f'µü¡σû£∩╝üΣ╜áσ╖▓τ╗Åσìçτ║ºσê░ {current_user.badge_info["name"]} τ║ºσê½∩╝ü', 'success')
                # Level 2 σìç Level 3 Θ£ÇΦªü3µ¼íΦ╛╛µáç
                elif current_user.badge_level == 2 and current_user.achievement_count % 3 == 0:
                    current_user.badge_level = 3
                    flash(f'µü¡σû£∩╝üΣ╜áσ╖▓τ╗Åσìçτ║ºσê░ {current_user.badge_info["name"]} τ║ºσê½∩╝ü', 'success')
        # Level 3 σê░ Level 8∩╝Üµ»Åτ║ºΘ£ÇΦªüΣ╕ñµ¼í80%
        elif 3 <= current_user.badge_level < 8:
            if correct_rate >= 80 and current_user.achievement_count % 2 == 0:
                current_user.badge_level += 1
                flash(f'µü¡σû£∩╝üΣ╜áσ╖▓τ╗Åσìçτ║ºσê░ {current_user.badge_info["name"]} τ║ºσê½∩╝ü', 'success')
        # Level 8Σ╗ÑΣ╕è∩╝Üµ»Åτ║ºΘ£ÇΦªüΣ║öµ¼í80%
        else:
            if correct_rate >= 80:
                if current_user.achievement_count % 5 == 0:
                    current_user.badge_level += 1
                    flash(f'σñ¬σÄëσ«│Σ║å∩╝üΣ╜áσ╖▓τ╗Åσìçτ║ºσê░ {current_user.badge_info["name"]} τ║ºσê½∩╝ü', 'success')
        # µÇ╗µêÉσ░▒µò░Σ╛¥τä╢τ┤»Φ«í
        current_user.achievement_count += 1
    
    # Φ«íτ«ùµÇ╗µ╡ïΘ¬îµò░σÆîσ╣│σ¥çµ¡úτí«τÄç
    total_quizzes = len(quiz_history)
    if total_quizzes > 0:
        total_correct_rate = round(sum(quiz.correct_rate for quiz in quiz_history) / total_quizzes)
    else:
        total_correct_rate = 0
    
    # ΦÄ╖σÅûσÄåσÅ▓Φ»╛τ¿ïµò░µì«
    history_data = db.session.query(Lesson, QuizHistory)\
        .join(QuizHistory, Lesson.id == QuizHistory.lesson_id)\
        .filter(QuizHistory.user_id == current_user.id)\
        .order_by(QuizHistory.completed_at.desc())\
        .all()
    
    # ΦÄ╖σÅûσ╖▓σ«îµêÉτÜäΦ»╛τ¿ïIDσêùΦí¿
    completed_lesson_ids = [quiz.lesson_id for quiz in quiz_history]
    
    # ΦÄ╖σÅûσ╜ôσëìσÅ»τö¿τÜäΦ»╛τ¿ï∩╝êµ┐Çµ┤╗τè╢µÇüΣ╕öµ£¬σ«îµêÉτÜäΦ»╛τ¿ï∩╝ë
    # Σ┐«µö╣Φ┐ÖΘçî∩╝ÜΣ╜┐τö¿σñÜσ»╣σñÜσà│ΦüöµƒÑΦ»ó
    available_lessons = Lesson.query.join(
        lesson_class_association,
        Lesson.id == lesson_class_association.c.lesson_id
    ).filter(
        lesson_class_association.c.class_id == current_user.class_id,
        Lesson.is_active == True,
        ~Lesson.id.in_(completed_lesson_ids) if completed_lesson_ids else True
    ).all()
    
    # σçåσñçΦ╢ïσè┐σ¢╛µò░µì«
    trend_data = []
    for quiz in quiz_history:
        lesson = Lesson.query.get(quiz.lesson_id)
        
        # Φ«íτ«ùΦ»ÑΦ»╛τ¿ïτÜäτÅ¡τ║ºσ╣│σ¥çµ¡úτí«τÄç
        class_avg = db.session.query(func.avg(QuizHistory.correct_answers * 100.0 / QuizHistory.total_questions))\
            .filter(QuizHistory.lesson_id == quiz.lesson_id,
                   QuizHistory.user_id != current_user.id)\
            .scalar() or 0
        
        trend_data.append({
            'date': quiz.completed_at.strftime('%Y-%m-%d'),
            'correct_rate': round(quiz.correct_rate),  # σÅûµò┤
            'class_avg': round(class_avg),  # σÅûµò┤
            'lesson_title': lesson.title if lesson else 'Unknown'
        })
    
    return render_template('student/dashboard.html',
                         total_quizzes=total_quizzes,
                         average_correct_rate=total_correct_rate,
                         history_data=history_data,
                         trend_data=json.dumps(trend_data),
                         lessons=available_lessons)

@app.route('/admin/lesson/<int:lesson_id>/kp_notes', methods=['POST'])
@admin_required
def upload_lesson_kp_notes(lesson_id):
    """Σ╕èΣ╝áσìòΣ╕¬Φ»╛τ¿ïτÜäτƒÑΦ»åτé╣τ¼öΦ«░σ¢╛τëç∩╝êσåÖσàÑ Cloudinary URL∩╝ëπÇé"""
    lesson = Lesson.query.get_or_404(lesson_id)
    file = request.files.get('kp_notes_image')
    if not file or not file.filename:
        flash('Φ»╖ΘÇëµï⌐σ¢╛τëçµûçΣ╗╢', 'error')
        return redirect(url_for('admin_lessons'))
    ext_ok = allowed_file(file.filename, ALLOWED_IMAGE_EXTENSIONS)
    if not ext_ok:
        flash('Σ╗àµö»µîü png / jpg / jpeg / gif σ¢╛τëç', 'error')
        return redirect(url_for('admin_lessons'))
    url = upload_to_cloudinary(file, resource_type='image')
    if not url:
        flash('Σ╕èΣ╝áσñ▒Φ┤Ñ∩╝îΦ»╖τ¿ìσÉÄΘçìΦ»ò', 'error')
        return redirect(url_for('admin_lessons'))
    lesson.kp_notes_image_url = url
    db.session.commit()
    flash('τƒÑΦ»åτé╣τ¼öΦ«░σ╖▓Σ┐¥σ¡ÿ', 'success')
    return redirect(url_for('admin_lessons'))

@app.route('/admin/lesson/<int:lesson_id>/kp_notes/clear', methods=['POST'])
@admin_required
def clear_lesson_kp_notes(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    lesson.kp_notes_image_url = None
    db.session.commit()
    flash('σ╖▓µ╕àΘÖñτƒÑΦ»åτé╣τ¼öΦ«░', 'info')
    return redirect(url_for('admin_lessons'))

@app.route('/student/lesson/<int:lesson_id>/kp_notes')
@login_required
def student_lesson_kp_notes(lesson_id):
    """σ¡ªτöƒµƒÑτ£ïτƒÑΦ»åτé╣τ¼öΦ«░σ¢╛∩╝êΘí╗σ▒₧Σ║ÄΦ»ÑτöƒτÅ¡τ║ºσà│ΦüöΦ»╛τ¿ï∩╝ë∩╝¢τ«íτÉåσæÿσÅ»ΘÜÅµù╢ΘóäΦºêπÇé"""
    lesson = Lesson.query.get_or_404(lesson_id)
    if not (lesson.kp_notes_image_url or '').strip():
        flash('µÜéµùáτƒÑΦ»åτé╣τ¼öΦ«░', 'warning')
        return redirect(url_for('student_dashboard'))
    if getattr(current_user, 'is_admin', False):
        return render_template('student/kp_notes_image.html',
                               lesson_title=lesson.title,
                               image_url=lesson.kp_notes_image_url.strip())
    user_class = Class.query.get(current_user.class_id)
    if not user_class or user_class not in lesson.classes:
        flash('µùáµ¥âµƒÑτ£ïΦ»Ñσåàσ«╣', 'error')
        return redirect(url_for('student_dashboard'))
    return render_template('student/kp_notes_image.html',
                           lesson_title=lesson.title,
                           image_url=lesson.kp_notes_image_url.strip())

@app.route('/admin/lesson/<int:lesson_id>/edit', methods=['POST'])
@admin_required
def edit_lesson(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    
    # ΦÄ╖σÅûΦí¿σìòµò░µì«
    title = request.form.get('title')
    description = request.form.get('description')
    class_ids = request.form.getlist('class_ids')  # µ│¿µäÅΦ┐ÖΘçîΣ╜┐τö¿class_idsΦÇîΣ╕ìµÿ»class_id
    
    if not title or not class_ids:
        return redirect(url_for('admin_lessons'))
    
    # µ¢┤µû░Φ»╛τ¿ïΣ┐íµü»
    lesson.title = title
    lesson.description = description
    
    # µ¢┤µû░τÅ¡τ║ºσà│Φüö
    lesson.classes = []  # µ╕àΘÖñτÄ░µ£ëσà│Φüö
    for class_id in class_ids:
        class_ = Class.query.get(class_id)
        if class_:
            lesson.classes.append(class_)
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
    
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
    print(f"σ╝Çσºïτ¡öΘóÿ - Φ»╛τ¿ïID: {lesson_id}, Φ»╛τ¿ïσÉìτº░: {lesson.title}")

    # Θ¬îΦ»üΦ»╛τ¿ïµÿ»σÉªσ▒₧Σ║Äτö¿µê╖τÅ¡τ║ºΣ╕öσ╖▓µ┐Çµ┤╗
    user_class = Class.query.get(user.class_id)
    if user_class not in lesson.classes or not lesson.is_active:
        flash('µùáµ│òΦ«┐Θù«Φ»ÑΦ»╛τ¿ï')
        return redirect(url_for('student_dashboard'))

    # µúÇµƒÑµÿ»σÉªσ╖▓τ╗Åσ«îµêÉΦ┐çΦ┐ÖΣ╕¬Φ»╛τ¿ïτÜäτ¡öΘóÿ∩╝êσÅ¬σàüΦ«╕Σ╕Çµ¼í∩╝ë
    existing_quiz = QuizHistory.query.filter_by(
        user_id=user.id,
        lesson_id=lesson_id
    ).order_by(QuizHistory.completed_at.asc()).first()

    if existing_quiz:
        flash('Σ╜áσ╖▓τ╗Åσ«îµêÉΦ┐çΦ┐ÖΣ╕¬Φ»╛τ¿ïτÜäτ¡öΘóÿ∩╝îΣ╕ìΦâ╜Θçìσñìτ¡öΘóÿ', 'warning')
        return redirect(url_for('view_history', lesson_id=lesson_id))

    # µúÇµƒÑΦ»╛τ¿ïµÿ»σÉªµ£ëΘóÿτ¢«
    questions = Question.query.filter_by(lesson_id=lesson_id).order_by(Question.question_number).all()
    print(f"Θóÿτ¢«µò░ΘçÅ: {len(questions)}")
    for q in questions:
        print(f"ΘóÿσÅ╖: {q.question_number}, τ▒╗σ₧ï: {q.type}, τ¡öµíê: {q.answer}")

    # τ╗Öµ»ÅΣ╕¬Θóÿτ¢«σèáΘ╗ÿΦ«ñσ¡ùµò░ΘÖÉσê╢∩╝êσªé200σ¡ù∩╝ë
    for q in questions:
        if not hasattr(q, 'word_limit') or q.word_limit is None:
            q.word_limit = 200

    if not questions:
        flash('Φ»ÑΦ»╛τ¿ïΦ┐ÿµ▓íµ£ëΘóÿτ¢«∩╝îΦ»╖τ¡ëσ╛àµòÖσ╕êΣ╕èΣ╝áΘóÿτ¢«')
        return redirect(url_for('student_dashboard'))

    # ΦÄ╖σÅûΦ»òΘóÿµûçΣ╗╢
    exam_files = ExamFile.query.filter_by(lesson_id=lesson_id).order_by(ExamFile.page_number).all()
    print(f"Φ»òΘóÿµûçΣ╗╢µò░ΘçÅ: {len(exam_files)}")
    for f in exam_files:
        print(f"µûçΣ╗╢ID: {f.id}, Θí╡τáü: {f.page_number}, Φ╖»σ╛ä: {f.path}")

    if not exam_files:
        flash('Φ»ÑΦ»╛τ¿ïΦ┐ÿµ▓íµ£ëΣ╕èΣ╝áΦ»òσì╖∩╝îΦ»╖τ¡ëσ╛àµòÖσ╕êΣ╕èΣ╝áΦ»òσì╖')
        return redirect(url_for('student_dashboard'))

    # ΦÄ╖σÅûΦºúµ₧ÉµûçΣ╗╢
    explanation_files = ExplanationFile.query.filter_by(lesson_id=lesson_id).order_by(ExplanationFile.page_number).all()
    print(f"Φºúµ₧ÉµûçΣ╗╢µò░ΘçÅ: {len(explanation_files)}")

    # σê¢σ╗║Σ╕ÇΣ╕¬τ⌐║τÜäΦí¿σìòτö¿Σ║ÄCSRFΣ┐¥µèñ
    form = FlaskForm()

    return render_template('student/quiz.html',
                         lesson=lesson,
                         questions=questions,
                         exam_files=exam_files,
                         explanation_files=explanation_files,
                         form=form)

def _homework_image_maps(lesson_id):
    """µîëΘóÿσÅ╖σÅûΦ»òΘóÿσ¢╛πÇüΦºúµ₧Éσ¢╛ URLπÇé"""
    exam_by_page = {
        f.page_number: f.path
        for f in ExamFile.query.filter_by(lesson_id=lesson_id).all()
        if f.path
    }
    expl_by_page = {
        f.page_number: f.path
        for f in ExplanationFile.query.filter_by(lesson_id=lesson_id).all()
        if f.path
    }
    return exam_by_page, expl_by_page


def _grade_homework_question(question, user_answer, exam_by_page=None, expl_by_page=None):
    """
    Σ╜£Σ╕ÜσìòΘóÿσêñσêå∩╝ÜσàêΦºäσêÖ∩╝îΦºäσêÖσêñΘöÖµêûΦºúτ¡öΘóÿµù╢τö¿ GPT∩╝êσ»╣τàºµáçσçåτ¡öµíê + Φ»òΘóÿ/Φºúµ₧Éσ¢╛∩╝ëπÇé
    τ⌐║τ¡ö/IDK Φ┐öσ¢₧ FalseπÇé
    """
    from ai_grading import maybe_upgrade_with_ai, ai_grading_available

    ans = (user_answer or '').strip()
    if not ans or ans.upper() == 'IDK':
        return False

    exam_by_page = exam_by_page or {}
    expl_by_page = expl_by_page or {}
    qnum = question.question_number
    image_urls = [u for u in (exam_by_page.get(qnum), expl_by_page.get(qnum)) if u]
    solution_text = getattr(question, 'explanation', None) or ''
    stem = question.content or ''
    key = question.answer or ''

    if question.type == 'proof':
        if ai_grading_available():
            ok = maybe_upgrade_with_ai(
                None,
                student_answer=ans,
                correct_answer=key,
                solution=solution_text,
                stem=stem,
                question_type='proof',
                image_urls=image_urls,
                force=True,
            )
            return True if ok is None else bool(ok)
        return True

    if question.type == 'choice':
        is_correct = ans.upper() == key.upper()
    else:
        is_correct = ans.lower() == key.strip().lower()

    if is_correct:
        return True

    upgraded = maybe_upgrade_with_ai(
        False,
        student_answer=ans,
        correct_answer=key,
        solution=solution_text,
        stem=stem,
        question_type=question.type or 'fill',
        image_urls=image_urls,
    )
    return bool(upgraded) if upgraded is not None else False


@app.route('/student/lesson/<int:lesson_id>/submit_quiz', methods=['POST'])
@login_required
def submit_quiz(lesson_id):
    try:
        # µúÇµƒÑµÿ»σÉªσ╖▓τ╗Åσ«îµêÉΦ┐çΦ┐ÖΣ╕¬Φ»╛τ¿ïτÜäτ¡öΘóÿ∩╝êσÅ¬σàüΦ«╕Σ╕Çµ¼í∩╝ë
        existing_quiz = QuizHistory.query.filter_by(
            user_id=current_user.id,
            lesson_id=lesson_id
        ).order_by(QuizHistory.completed_at.asc()).first()

        if existing_quiz:
            flash('Σ╜áσ╖▓τ╗Åσ«îµêÉΦ┐çΦ┐ÖΣ╕¬Φ»╛τ¿ïτÜäτ¡öΘóÿ∩╝îΣ╕ìΦâ╜ΘçìσñìµÅÉΣ║ñ', 'warning')
            return redirect(url_for('view_history', lesson_id=lesson_id))

        # ΦÄ╖σÅûµëÇµ£ëΘóÿτ¢«
        questions = Question.query.filter_by(lesson_id=lesson_id).order_by(Question.question_number).all()
        if not questions:
            flash('µ£¬µë╛σê░Θóÿτ¢«', 'error')
            return redirect(url_for('student_dashboard'))

        # ΦÄ╖σÅûτ¡öΘóÿτö¿µù╢
        time_spent = int(request.form.get('time_spent', 0))

        # σê¢σ╗║τ¡öΘóÿσÄåσÅ▓Φ«░σ╜ò
        quiz_history = QuizHistory(
            user_id=current_user.id,
            lesson_id=lesson_id,
            total_questions=len(questions),
            correct_answers=0,  # σê¥σºïσîûΣ╕║0∩╝îσÉÄΘ¥óΣ╝Üµ¢┤µû░
            time_spent=time_spent,
            completed_at=datetime.now()
        )
        db.session.add(quiz_history)
        db.session.flush()  # ΦÄ╖σÅûquiz_history.id

        correct_count = 0
        exam_by_page, expl_by_page = _homework_image_maps(lesson_id)

        # σñäτÉåµ»ÅΣ╕¬Θóÿτ¢«τÜäτ¡öµíê
        for question in questions:
            # µúÇµƒÑµÿ»σÉªΘÇëµï⌐Σ║å"Σ╕ìΣ╝ÜσüÜ"
            idk_answer = request.form.get(f'answer_{question.id}_idk')
            user_answer = request.form.get(f'answer_{question.id}', '').strip()
            
            # σªéµ₧£ΘÇëµï⌐Σ║å"Σ╕ìΣ╝ÜσüÜ"µêûµ▓íµ£ëµÅÉΣ║ñτ¡öµíê∩╝îµáçΦ«░Σ╕║µ£¬Σ╜£τ¡ö
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

            is_correct = _grade_homework_question(
                question, user_answer, exam_by_page, expl_by_page
            )

            # σê¢σ╗║τö¿µê╖τ¡öµíêΦ«░σ╜ò
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

        # µ¢┤µû░τ¡öΘóÿσÄåσÅ▓τÜäµ¡úτí«Θóÿτ¢«µò░
        quiz_history.correct_answers = correct_count
        
        # Φ«íτ«ùµ¡úτí«τÄç
        correct_rate = (correct_count / len(questions)) * 100

        # µ¢┤µû░µêÉσ░▒Φ«íµò░σÆîσ╛╜τ½áτ¡ëτ║º
        # µÇ╗µêÉσ░▒µò░τ┤»Φ«í
        current_user.achievement_count += 1
        
        # τ«ÇσîûτÜäσ╛╜τ½áσìçτ║ºΘÇ╗Φ╛æ
        # Level 0 σê░ Level 1∩╝ÜσÅ¬ΦªüµÅÉΣ║ñΣ╜£Σ╕Üσ░▒σìçτ║º
        if current_user.badge_level == 0:
            current_user.badge_level = 1
            flash('µü¡σû£∩╝üΣ╜áΦÄ╖σ╛ùΣ║åτ¼¼Σ╕ÇΣ╕¬σ╛╜τ½á∩╝Üσ░Åµ»¢µ»¢ΦÖ½∩╝ü≡ƒÉ¢', 'success')
        # Level 1 σê░ Level 3∩╝ÜΘ£ÇΦªüΦ╛╛σê░60%∩╝îσƒ║Σ║ÄµÇ╗µêÉσ░▒µò░
        elif current_user.badge_level < 3:
            if correct_rate >= 60:
                if current_user.badge_level == 1 and current_user.achievement_count % 2 == 0:
                    current_user.badge_level = 2
                    flash(f'µü¡σû£∩╝üΣ╜áσ╖▓τ╗Åσìçτ║ºσê░ {current_user.badge_info["name"]} τ║ºσê½∩╝ü', 'success')
                elif current_user.badge_level == 2 and current_user.achievement_count % 3 == 0:
                    current_user.badge_level = 3
                    flash(f'µü¡σû£∩╝üΣ╜áσ╖▓τ╗Åσìçτ║ºσê░ {current_user.badge_info["name"]} τ║ºσê½∩╝ü', 'success')
        # Level 3 σê░ Level 8∩╝Üµ»Åτ║ºΘ£ÇΦªüΣ╕ñµ¼í80%
        elif 3 <= current_user.badge_level < 8:
            if correct_rate >= 80 and current_user.achievement_count % 2 == 0:
                current_user.badge_level += 1
                flash(f'µü¡σû£∩╝üΣ╜áσ╖▓τ╗Åσìçτ║ºσê░ {current_user.badge_info["name"]} τ║ºσê½∩╝ü', 'success')
        # Level 8Σ╗ÑΣ╕è∩╝Üµ»Åτ║ºΘ£ÇΦªüΣ║öµ¼í80%
        else:
            if correct_rate >= 80 and current_user.achievement_count % 5 == 0:
                current_user.badge_level += 1
                flash(f'σñ¬σÄëσ«│Σ║å∩╝üΣ╜áσ╖▓τ╗Åσìçτ║ºσê░ {current_user.badge_info["name"]} τ║ºσê½∩╝ü', 'success')
        
        db.session.commit()

        flash('τ¡öΘóÿσ«îµêÉ∩╝ü', 'success')
        return redirect(url_for('view_history', lesson_id=lesson_id))

    except Exception as e:
        db.session.rollback()
        print(f"Error in submit_quiz: {str(e)}")
        flash('µÅÉΣ║ñτ¡öµíêµù╢σç║ΘöÖ', 'error')
        return redirect(url_for('student_dashboard'))

@app.route('/admin/question/<int:lesson_id>/add', methods=['POST'])
@admin_required
def add_question(lesson_id):
    content = request.form.get('content')
    answer = request.form.get('answer')
    explanation = request.form.get('explanation')
    
    if not content or not answer:
        flash('Θóÿτ¢«σåàσ«╣σÆîµ¡úτí«τ¡öµíêΣ╕ìΦâ╜Σ╕║τ⌐║')
        return redirect(url_for('manage_questions', lesson_id=lesson_id))
    
    if answer not in ['A', 'B', 'C', 'D']:
        flash('µ¡úτí«τ¡öµíêσ┐àΘí╗µÿ»AπÇüBπÇüCµêûD')
        return redirect(url_for('manage_questions', lesson_id=lesson_id))
    
    new_question = Question(
        content=content,
        answer=answer,
        explanation=explanation,
        lesson_id=lesson_id
    )
    db.session.add(new_question)
    db.session.commit()
    
    flash('Θóÿτ¢«µ╖╗σèáµêÉσèƒ')
    return redirect(url_for('manage_questions', lesson_id=lesson_id))

@app.route('/admin/question/<int:question_id>/edit', methods=['POST'])
@admin_required
def edit_question(question_id):
    question = Question.query.get_or_404(question_id)
    
    # ΦÄ╖σÅûΦí¿σìòµò░µì«
    content = request.form.get('content')
    answer = request.form.get('answer')
    explanation = request.form.get('explanation')
    
    if not content or not answer:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'msg': 'Θóÿτ¢«σåàσ«╣σÆîτ¡öµíêΣ╕ìΦâ╜Σ╕║τ⌐║'})
        flash('Θóÿτ¢«σåàσ«╣σÆîτ¡öµíêΣ╕ìΦâ╜Σ╕║τ⌐║')
        return redirect(url_for('manage_questions', lesson_id=question.lesson_id))
    
    # Θ¬îΦ»üτ¡öµíêµá╝σ╝Å
    if question.type == 'choice' and answer not in ['A', 'B', 'C', 'D']:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'msg': 'ΘÇëµï⌐Θóÿτ¡öµíêσ┐àΘí╗µÿ»AπÇüBπÇüCµêûD'})
        flash('ΘÇëµï⌐Θóÿτ¡öµíêσ┐àΘí╗µÿ»AπÇüBπÇüCµêûD')
        return redirect(url_for('manage_questions', lesson_id=question.lesson_id))
    
    try:
        question.content = content
        question.answer = answer
        question.explanation = explanation
        db.session.commit()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'msg': 'Θóÿτ¢«µ¢┤µû░µêÉσèƒ'})
        flash('Θóÿτ¢«µ¢┤µû░µêÉσèƒ')
    except Exception as e:
        db.session.rollback()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'msg': f'µ¢┤µû░σñ▒Φ┤Ñ∩╝Ü{str(e)}'})
        flash(f'µ¢┤µû░σñ▒Φ┤Ñ∩╝Ü{str(e)}')
    
    return redirect(url_for('manage_questions', lesson_id=question.lesson_id))

@app.route('/admin/question/<int:question_id>/delete', methods=['POST'])
@admin_required
def delete_question(question_id):
    question = Question.query.get_or_404(question_id)
    lesson_id = question.lesson_id
    db.session.delete(question)
    db.session.commit()
    
    flash('Θóÿτ¢«σêáΘÖñµêÉσèƒ')
    return redirect(url_for('manage_questions', lesson_id=lesson_id))

@app.route('/admin/question/<int:lesson_id>/import', methods=['POST'])
@admin_required
def import_questions(lesson_id):
    if 'file' not in request.files:
        flash('µ▓íµ£ëΘÇëµï⌐µûçΣ╗╢', 'error')
        return redirect(url_for('manage_questions', lesson_id=lesson_id))
    
    file = request.files['file']
    if file.filename == '':
        flash('µ▓íµ£ëΘÇëµï⌐µûçΣ╗╢', 'error')
        return redirect(url_for('manage_questions', lesson_id=lesson_id))
    
    if not file.filename.endswith(tuple(ALLOWED_EXCEL_EXTENSIONS)):
        flash('σÅ¬µö»µîüExcelµûçΣ╗╢∩╝ê.xlsxµêû.xls∩╝ë', 'error')
        return redirect(url_for('manage_questions', lesson_id=lesson_id))
    
    try:
        df = pd.read_excel(file)
        success_count = 0
        error_count = 0
        
        for _, row in df.iterrows():
            try:
                if pd.notna(row[0]) and pd.notna(row[1]):  # τí«Σ┐¥ΘóÿσÅ╖σÆîτ¡öµíêΣ╕ìΣ╕║τ⌐║
                    question_number = int(row[0])
                    answer = str(row[1]).strip().upper()
                    content = str(row[2]) if len(row) > 2 and pd.notna(row[2]) else "Θóÿτ¢«σåàσ«╣σ╛àΦíÑσàà"
                    explanation = str(row[3]) if len(row) > 3 and pd.notna(row[3]) else None
                    
                    # µá╣µì«τ¡öµíêσêñµû¡Θóÿτ¢«τ▒╗σ₧ï
                    question_type = 'choice' if answer in ['A', 'B', 'C', 'D'] else 'fill'
                    
                    # µƒÑµë╛µÿ»σÉªσ╖▓σ¡ÿσ£¿Φ»ÑΘóÿσÅ╖τÜäΘóÿτ¢«
                    question = Question.query.filter_by(
                        lesson_id=lesson_id,
                        question_number=question_number
                    ).first()
                    
                    if question:
                        # µ¢┤µû░τÄ░µ£ëΘóÿτ¢«
                        question.type = question_type
                        question.answer = answer
                        question.content = content
                        question.explanation = explanation
                    else:
                        # σê¢σ╗║µû░Θóÿτ¢«
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
                print(f"σ»╝σàÑΘóÿτ¢«µù╢σç║ΘöÖ: {str(e)}")
                continue
        
        db.session.commit()
        flash_message = f'µêÉσèƒσ»╝σàÑ{success_count}ΘüôΘóÿτ¢«'
        if error_count > 0:
            flash_message += f'∩╝î{error_count}ΘüôΘóÿτ¢«σ»╝σàÑσñ▒Φ┤Ñ'
        flash(flash_message, 'success' if error_count == 0 else 'warning')
    except Exception as e:
        flash(f'σ»╝σàÑσñ▒Φ┤Ñ∩╝Ü{str(e)}', 'error')
    
    return redirect(url_for('manage_questions', lesson_id=lesson_id))

@app.route('/student/lesson/<int:lesson_id>/history')
@login_required
def view_history(lesson_id):
    from flask_login import current_user
    user_id = request.args.get('user_id', type=int)
    # σªéµ₧£µÿ»τ«íτÉåσæÿΣ╕öΣ╝áΣ║åuser_idσÅéµò░∩╝îσêÖµƒÑµîçσ«Üσ¡ªτöƒ∩╝îσÉªσêÖµƒÑσ╜ôσëìτö¿µê╖
    is_admin_view = hasattr(current_user, 'is_admin') and current_user.is_admin and user_id
    if hasattr(current_user, 'is_admin') and current_user.is_admin and user_id:
        target_user_id = user_id
    else:
        target_user_id = current_user.id

    lesson = Lesson.query.get_or_404(lesson_id)
    quiz_history = QuizHistory.query.filter_by(
        user_id=target_user_id,
        lesson_id=lesson_id
    ).order_by(QuizHistory.completed_at.desc()).all()
    if quiz_history:
        latest_quiz = quiz_history[0]
        # σ¢║σ«ÜµîëΘóÿσÅ╖Θí║σ║ÅΦ┐öσ¢₧∩╝îΘü┐σàìτ«íτÉåσæÿµö╣σ»╣/µö╣ΘöÖσÉÄΘí╡Θ¥óΘçìµû░σèáΦ╜╜σç║τÄ░Θóÿτ¢«Θí║σ║Åµèûσè¿
        latest_answers = (
            UserAnswer.query.filter_by(quiz_history_id=latest_quiz.id)
            .join(Question, Question.id == UserAnswer.question_id)
            .order_by(Question.question_number.asc())
            .all()
        )
        latest_questions = [answer.question for answer in latest_answers]
        exam_files = ExamFile.query.filter_by(lesson_id=lesson_id).order_by(ExamFile.page_number).all()
        explanation_files = ExplanationFile.query.filter_by(lesson_id=lesson_id).order_by(ExplanationFile.page_number).all()
        return render_template('student/quiz_history.html',
                             lesson=lesson,
                             quiz_history=quiz_history,
                             latest_questions=latest_questions,
                             latest_answers=latest_answers,
                             exam_files=exam_files,
                             explanation_files=explanation_files,
                             is_admin_view=is_admin_view)
    else:
        if not lesson.is_active:
            flash('Φ»ÑΦ»╛τ¿ïσ╜ôσëìµ£¬µ┐Çµ┤╗∩╝îΣ╕öµé¿µ▓íµ£ëσÄåσÅ▓τ¡öΘóÿΦ«░σ╜òπÇé', 'warning')
            return redirect(url_for('student_dashboard'))
        flash('Φ┐ÿµ▓íµ£ëτ¡öΘóÿΦ«░σ╜ò', 'info')
        return render_template('student/quiz_history.html', lesson=lesson, quiz_history=None, is_admin_view=is_admin_view)

@app.route('/student/quiz/detail/<int:history_id>')
@login_required
def quiz_detail(history_id):
    user = current_user
    quiz_history = QuizHistory.query.get_or_404(history_id)
    
    # Θ¬îΦ»üσÄåσÅ▓Φ«░σ╜òµÿ»σÉªσ▒₧Σ║Äσ╜ôσëìτö¿µê╖
    if quiz_history.user_id != user.id:
        flash('µùáµ¥âΦ«┐Θù«Φ»ÑΦ«░σ╜ò')
        return redirect(url_for('student_dashboard'))
    
    # ΦÄ╖σÅûΦ»Ñµ¼íτ¡öΘóÿτÜäµëÇµ£ëτ¡öµíê
    user_answers = UserAnswer.query.filter_by(
        user_id=user.id,
        lesson_id=quiz_history.lesson_id,
        created_at=quiz_history.completed_at
    ).order_by(UserAnswer.question_id).all()
    
    # ΦÄ╖σÅûµëÇµ£ëΘù«Θóÿ
    questions = Question.query.filter_by(
        lesson_id=quiz_history.lesson_id
    ).order_by(Question.question_number).all()
    
    # ΦÄ╖σÅûΦ»òσì╖µûçΣ╗╢
    exam_files = ExamFile.query.filter_by(
        lesson_id=quiz_history.lesson_id
    ).order_by(ExamFile.page_number).all()
    
    # ΦÄ╖σÅûΦºúµ₧ÉµûçΣ╗╢
    explanation_files = ExplanationFile.query.filter_by(
        lesson_id=quiz_history.lesson_id
    ).order_by(ExplanationFile.page_number).all()
    
    # σê¢σ╗║Θù«ΘóÿσÆîτ¡öµíêτÜäµÿáσ░ä∩╝êΣ╜┐τö¿µÅÉΣ║ñµù╢σåÖσàÑτÜäσêñσêåτ╗ôµ₧£∩╝îσÉ½ GPT σêñσêå∩╝ë
    question_answers = {}
    for answer in user_answers:
        question = Question.query.get(answer.question_id)
        if question:
            question_answers[question] = {
                'selected_answer': answer.answer,
                'is_correct': answer.is_correct
            }
    
    return render_template('student/detail.html',
                         quiz_history=quiz_history,
                         question_answers=question_answers,
                         exam_files=exam_files,
                         explanation_files=explanation_files)

def allowed_file(filename, allowed_extensions):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

# µûçΣ╗╢σñäτÉåσç╜µò░
def save_uploaded_file(file, allowed_extensions):
    if file and file.filename != '' and allowed_file(file.filename, allowed_extensions):
        # τí«Σ┐¥Σ╕èΣ╝áτ¢«σ╜òσ¡ÿσ£¿
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        # τöƒµêÉσ«ëσà¿τÜäµûçΣ╗╢σÉì
        filename = secure_filename(file.filename)
        # µ╖╗σèáµù╢Θù┤µê│Θü┐σàìµûçΣ╗╢σÉìσå▓τ¬ü
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
        # Σ┐¥σ¡ÿµûçΣ╗╢
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        return filename
    return None

# Φ»òσì╖τ«íτÉåτ¢╕σà│Φ╖»τö▒
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

@app.route('/admin/lesson/<int:lesson_id>/question_stats')
@admin_required
def question_stats(lesson_id):
    """Θóÿτ¢«σ╛ùσêåτÄçτ╗ƒΦ«íΘí╡Θ¥ó"""
    lesson = Lesson.query.get_or_404(lesson_id)
    questions = Question.query.filter_by(lesson_id=lesson_id).order_by(Question.question_number).all()
    
    # ΦÄ╖σÅûµëÇµ£ëτ¡öΘóÿΦ«░σ╜ò
    quiz_histories = QuizHistory.query.filter_by(lesson_id=lesson_id).all()
    
    # τ╗ƒΦ«íµ»ÅΘüôΘóÿτÜäσ╛ùσêåτÄç
    question_stats = []
    for question in questions:
        # ΦÄ╖σÅûΦ┐ÖΘüôΘóÿτÜäµëÇµ£ëτ¡öΘóÿΦ«░σ╜ò
        user_answers = UserAnswer.query.filter_by(
            lesson_id=lesson_id,
            question_id=question.id
        ).all()
        
        total_attempts = len(user_answers)
        correct_attempts = len([ua for ua in user_answers if ua.is_correct])
        
        # Φ«íτ«ùσ╛ùσêåτÄç
        success_rate = (correct_attempts / total_attempts * 100) if total_attempts > 0 else 0
        
        question_stats.append({
            'question_number': question.question_number,
            'type': question.type,
            'total_attempts': total_attempts,
            'correct_attempts': correct_attempts,
            'success_rate': round(success_rate, 2),
            'answer': question.answer
        })
    
    return render_template('admin/question_stats.html', 
                         lesson=lesson, 
                         question_stats=question_stats)

@app.route('/admin/lesson/<int:lesson_id>/question_stats_data')
@admin_required
def question_stats_data(lesson_id):
    """Φ┐öσ¢₧Θóÿτ¢«σ╛ùσêåτÄçµò░µì«τÜäJSONµÄÑσÅú"""
    lesson = Lesson.query.get_or_404(lesson_id)
    questions = Question.query.filter_by(lesson_id=lesson_id).order_by(Question.question_number).all()
    
    # τ╗ƒΦ«íµ»ÅΘüôΘóÿτÜäσ╛ùσêåτÄç
    question_stats = []
    for question in questions:
        # ΦÄ╖σÅûΦ┐ÖΘüôΘóÿτÜäµëÇµ£ëτ¡öΘóÿΦ«░σ╜ò
        user_answers = UserAnswer.query.filter_by(
            lesson_id=lesson_id,
            question_id=question.id
        ).all()
        
        total_attempts = len(user_answers)
        correct_attempts = len([ua for ua in user_answers if ua.is_correct])
        
        # Φ«íτ«ùσ╛ùσêåτÄç
        success_rate = (correct_attempts / total_attempts * 100) if total_attempts > 0 else 0
        
        question_stats.append({
            'question_number': question.question_number,
            'type': question.type,
            'total_attempts': total_attempts,
            'correct_attempts': correct_attempts,
            'success_rate': round(success_rate, 2),
            'answer': question.answer
        })
    
    return jsonify(question_stats)

def upload_to_cloudinary(file_data, resource_type='image'):
    """Σ╕èΣ╝áµûçΣ╗╢σê░ Cloudinary σ╣╢Φ┐öσ¢₧ URL∩╝êµùá print∩╝îΘü┐σàì Windows µÄºσê╢σÅ░τ╝ûτáüΘöÖΦ»»∩╝ë"""
    try:
        if isinstance(file_data, str) and file_data.startswith('data:image'):
            result = cloudinary.uploader.upload(
                file_data,
                resource_type=resource_type
            )
        else:
            result = cloudinary.uploader.upload(
                file_data,
                resource_type=resource_type
            )
        if 'secure_url' in result:
            return result['secure_url']
        return None
    except Exception:
        return None

@app.route('/admin/lesson/<int:lesson_id>/upload_exam_files', methods=['POST'])
@admin_required
def upload_exam_files(lesson_id):
    try:
        lesson = Lesson.query.get_or_404(lesson_id)
        if 'files[]' not in request.files:
            flash('µ▓íµ£ëΘÇëµï⌐µûçΣ╗╢', 'error')
            return redirect(url_for('manage_questions', lesson_id=lesson_id))
        
        files = request.files.getlist('files[]')
        print(f"µö╢σê░{len(files)}Σ╕¬µûçΣ╗╢Σ╕èΣ╝áΦ»╖µ▒é")
        
        # ΦÄ╖σÅûσ╜ôσëìµ£ÇσñºΘí╡τáü
        max_page = db.session.query(func.max(ExamFile.page_number)).filter_by(lesson_id=lesson_id).scalar() or 0
        
        success_count = 0
        for file in files:
            if file and allowed_file(file.filename, ALLOWED_PDF_EXTENSIONS.union(ALLOWED_IMAGE_EXTENSIONS)):
                try:
                    # τöƒµêÉσ«ëσà¿τÜäµûçΣ╗╢σÉì
                    original_filename = secure_filename(file.filename)
                    filename = f"{lesson_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{original_filename}"
                    
                    # Σ╕èΣ╝áσê░ Cloudinary
                    cloudinary_url = upload_to_cloudinary(file)
                    if not cloudinary_url:
                        raise Exception("Cloudinary Σ╕èΣ╝áσñ▒Φ┤Ñ")
                    
                    # σê¢σ╗║Φ»òσì╖µûçΣ╗╢Φ«░σ╜ò
                    exam_file = ExamFile(
                        filename=filename,
                        path=cloudinary_url,  # Σ╜┐τö¿ Cloudinary URL
                        lesson_id=lesson_id,
                        page_number=max_page + 1 + success_count
                    )
                    db.session.add(exam_file)
                    success_count += 1
                    
                except Exception as e:
                    print(f"Σ╕èΣ╝áσñ▒Φ┤Ñ: {str(e)}")
                    flash(f'µûçΣ╗╢ {file.filename} Σ╕èΣ╝áσñ▒Φ┤Ñ∩╝Ü{str(e)}', 'error')
                    continue
        
        if success_count > 0:
            try:
                db.session.commit()
                flash(f'µêÉσèƒΣ╕èΣ╝á{success_count}Σ╕¬µûçΣ╗╢', 'success')
            except Exception as e:
                db.session.rollback()
                print(f"Σ┐¥σ¡ÿσê░µò░µì«σ║ôσñ▒Φ┤Ñ: {str(e)}")
                flash('Σ┐¥σ¡ÿµûçΣ╗╢Φ«░σ╜òσñ▒Φ┤Ñ∩╝îΦ»╖ΘçìΦ»ò', 'error')
        
        return redirect(url_for('manage_questions', lesson_id=lesson_id))
        
    except Exception as e:
        print(f"µûçΣ╗╢Σ╕èΣ╝áΦ┐çτ¿ïσç║ΘöÖ: {str(e)}")
        flash('µûçΣ╗╢Σ╕èΣ╝áΦ┐çτ¿ïσç║ΘöÖ∩╝îΦ»╖ΘçìΦ»ò', 'error')
        return redirect(url_for('manage_questions', lesson_id=lesson_id))

@app.route('/admin/exam_file/<int:file_id>/delete', methods=['POST'])
@admin_required
def delete_exam_file(file_id):
    exam_file = ExamFile.query.get_or_404(file_id)
    lesson_id = exam_file.lesson_id
    
    try:
        # µ₧äσ╗║σ«îµò┤τÜäµûçΣ╗╢Φ╖»σ╛ä
        file_path = os.path.join('static', exam_file.path)
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # σêáΘÖñµò░µì«σ║ôΦ«░σ╜ò
        db.session.delete(exam_file)
        db.session.commit()
        flash('µûçΣ╗╢σêáΘÖñµêÉσèƒ', 'success')
    except Exception as e:
        print(f"σêáΘÖñµûçΣ╗╢σñ▒Φ┤Ñ: {str(e)}")
        flash('µûçΣ╗╢σêáΘÖñσñ▒Φ┤Ñ', 'error')
        
    return redirect(url_for('manage_questions', lesson_id=lesson_id))

@app.route('/admin/lesson/<int:lesson_id>/import_answers', methods=['POST'])
@admin_required
def import_answers(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    if 'file' not in request.files:
        flash('µ▓íµ£ëΘÇëµï⌐µûçΣ╗╢', 'error')
        return redirect(url_for('manage_exam', lesson_id=lesson_id))
    
    file = request.files['file']
    if file and file.filename.endswith('.xlsx'):
        try:
            df = pd.read_excel(file)
            for _, row in df.iterrows():
                question = Question(
                    lesson_id=lesson_id,
                    question_text=row['Θóÿτ¢«'],
                    correct_answer=row['τ¡öµíê'],
                    points=row['σêåσÇ╝']
                )
                db.session.add(question)
            db.session.commit()
            flash('τ¡öµíêσ»╝σàÑµêÉσèƒ', 'success')
        except Exception as e:
            db.session.rollback()
            flash('τ¡öµíêσ»╝σàÑσñ▒Φ┤Ñ', 'error')
    else:
        flash('Φ»╖Σ╕èΣ╝áExcelµûçΣ╗╢', 'error')
        
    return redirect(url_for('manage_exam', lesson_id=lesson_id))

@app.route('/admin/lesson/<int:lesson_id>/upload_explanation_files', methods=['POST'])
@admin_required
def upload_explanation_files(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    if 'files[]' not in request.files:
        flash('µ▓íµ£ëΘÇëµï⌐µûçΣ╗╢', 'error')
        return redirect(url_for('manage_questions', lesson_id=lesson_id))
    
    files = request.files.getlist('files[]')
    print(f"µö╢σê░{len(files)}Σ╕¬Φºúµ₧ÉµûçΣ╗╢Σ╕èΣ╝áΦ»╖µ▒é")
    
    # ΦÄ╖σÅûσ╜ôσëìµ£ÇσñºΘí╡τáü
    max_page = db.session.query(func.max(ExplanationFile.page_number)).filter_by(lesson_id=lesson_id).scalar() or 0
    
    success_count = 0
    try:
        for file in files:
            if file and allowed_file(file.filename, ALLOWED_PDF_EXTENSIONS):
                try:
                    # τöƒµêÉσ«ëσà¿τÜäµûçΣ╗╢σÉì
                    original_filename = secure_filename(file.filename)
                    filename = f"{lesson_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{original_filename}"
                    
                    # Σ╕èΣ╝áσê░ Cloudinary
                    cloudinary_url = upload_to_cloudinary(file)
                    if not cloudinary_url:
                        raise Exception("Cloudinary Σ╕èΣ╝áσñ▒Φ┤Ñ")
                    
                    # σê¢σ╗║Φºúµ₧ÉµûçΣ╗╢Φ«░σ╜ò
                    explanation_file = ExplanationFile(
                        filename=filename,
                        path=cloudinary_url,  # Σ╜┐τö¿ Cloudinary URL
                        lesson_id=lesson_id,
                        page_number=max_page + 1 + success_count
                    )
                    db.session.add(explanation_file)
                    success_count += 1
                    
                except Exception as e:
                    print(f"Σ╕èΣ╝áΦºúµ₧ÉµûçΣ╗╢σñ▒Φ┤Ñ: {str(e)}")
                    flash(f'µûçΣ╗╢ {file.filename} Σ╕èΣ╝áσñ▒Φ┤Ñ∩╝Ü{str(e)}', 'error')
                    continue
        
        if success_count > 0:
            try:
                db.session.commit()
                flash(f'µêÉσèƒΣ╕èΣ╝á{success_count}Σ╕¬Φºúµ₧ÉµûçΣ╗╢', 'success')
            except Exception as e:
                db.session.rollback()
                print(f"Σ┐¥σ¡ÿσê░µò░µì«σ║ôσñ▒Φ┤Ñ: {str(e)}")
                flash('Σ┐¥σ¡ÿµûçΣ╗╢Φ«░σ╜òσñ▒Φ┤Ñ∩╝îΦ»╖ΘçìΦ»ò', 'error')
    except Exception as e:
        print(f"µûçΣ╗╢Σ╕èΣ╝áΦ┐çτ¿ïσç║ΘöÖ: {str(e)}")
        flash('µûçΣ╗╢Σ╕èΣ╝áΦ┐çτ¿ïσç║ΘöÖ∩╝îΦ»╖ΘçìΦ»ò', 'error')
    
    return redirect(url_for('manage_questions', lesson_id=lesson_id))

@app.route('/admin/explanation_file/<int:file_id>/delete', methods=['POST'])
@admin_required
def delete_explanation_file(file_id):
    explanation_file = ExplanationFile.query.get_or_404(file_id)
    lesson_id = explanation_file.lesson_id
    
    try:
        # µ₧äσ╗║σ«îµò┤τÜäµûçΣ╗╢Φ╖»σ╛ä
        file_path = os.path.join('static', explanation_file.path)
        if os.path.exists(file_path):
            os.remove(file_path)
            
        # σêáΘÖñµò░µì«σ║ôΦ«░σ╜ò
        db.session.delete(explanation_file)
        db.session.commit()
        flash('Φºúµ₧ÉµûçΣ╗╢σêáΘÖñµêÉσèƒ', 'success')
    except Exception as e:
        print(f"σêáΘÖñµûçΣ╗╢σñ▒Φ┤Ñ: {str(e)}")
        flash('Φºúµ₧ÉµûçΣ╗╢σêáΘÖñσñ▒Φ┤Ñ', 'error')
        
    return redirect(url_for('manage_questions', lesson_id=lesson_id))

@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    """Σ╕èΣ╝áµûçΣ╗╢µ£ìσèí"""
    try:
        # µ₧äσ╗║σÅ»Φâ╜τÜäµûçΣ╗╢Φ╖»σ╛ä
        paths_to_try = [
            os.path.join(app.static_folder, 'uploads', filename),  # µáçσçåΦ╖»σ╛ä
            os.path.join(app.static_folder, filename),  # σ«îµò┤Φ╖»σ╛ä
            os.path.join('uploads', filename),  # τ¢╕σ»╣Φ╖»σ╛ä
            filename  # σÄƒσºïΦ╖»σ╛ä
        ]
        
        # σ░¥Φ»òµëÇµ£ëσÅ»Φâ╜τÜäΦ╖»σ╛ä
        for path in paths_to_try:
            print(f"σ░¥Φ»òΦ«┐Θù«Φ╖»σ╛ä: {path}")  # µ╖╗σèáΦ░âΦ»òµùÑσ┐ù
            if os.path.exists(path):
                dir_path = os.path.dirname(path)
                base_name = os.path.basename(path)
                print(f"µë╛σê░µûçΣ╗╢: {path}")  # µ╖╗σèáΦ░âΦ»òµùÑσ┐ù
                return send_from_directory(dir_path, base_name)
        
        # σªéµ₧£µëÇµ£ëΦ╖»σ╛äΘâ╜Σ╕ìσ¡ÿσ£¿∩╝îΦ«░σ╜òΘöÖΦ»»σ╣╢Φ┐öσ¢₧404
        print(f"µûçΣ╗╢Σ╕ìσ¡ÿσ£¿∩╝îσ░¥Φ»òΦ┐çΣ╗ÑΣ╕ïΦ╖»σ╛ä: {paths_to_try}")
        return f"µûçΣ╗╢Σ╕ìσ¡ÿσ£¿∩╝îσ░¥Φ»òΦ┐çΣ╗ÑΣ╕ïΦ╖»σ╛ä: {paths_to_try}", 404
        
    except Exception as e:
        print(f"Φ«┐Θù«µûçΣ╗╢σç║ΘöÖ: {str(e)}")
        return f"Φ«┐Θù«µûçΣ╗╢σç║ΘöÖ: {str(e)}", 500

@app.route('/static/<path:filename>')
def serve_static(filename):
    """σñäτÉåΘ¥ÖµÇüµûçΣ╗╢Φ»╖µ▒é"""
    # σªéµ₧£µÿ»σ«îµò┤τÜäURL∩╝êσîàµï¼ΘöÖΦ»»µá╝σ╝ÅτÜäURL∩╝ë∩╝îµÅÉσÅûσ«₧ΘÖàτÜäURLσ╣╢Θçìσ«ÜσÉæ
    if 'https://' in filename or 'http://' in filename:
        # σñäτÉåΘöÖΦ»»µá╝σ╝ÅτÜäURL∩╝êσîàσÉ½/static/σëìτ╝ÇτÜäµâàσå╡∩╝ë
        if filename.startswith('https://') or filename.startswith('http://'):
            actual_url = filename
        else:
            # Σ╗ÄΦ╖»σ╛äΣ╕¡µÅÉσÅûσ«₧ΘÖàτÜäURL
            actual_url = filename[filename.find('http'):]
        return redirect(actual_url)
        
    try:
        return send_from_directory(app.static_folder, filename)
    except Exception as e:
        print(f"Θ¥ÖµÇüµûçΣ╗╢Φ«┐Θù«ΘöÖΦ»»: {str(e)}")
        abort(404)

@app.route('/admin/lesson/<int:lesson_id>/add_questions', methods=['POST'])
@admin_required
def add_questions(lesson_id):
    try:
        print("σ╝Çσºïµ╖╗σèáΘóÿτ¢«...")  # Φ░âΦ»òµùÑσ┐ù
        
        # Θ¬îΦ»üCSRFΣ╗ñτëî
        if not request.form.get('csrf_token'):
            raise ValueError('CSRFΘ¬îΦ»üσñ▒Φ┤Ñ')
            
        # ΦÄ╖σÅûµëÇµ£ëτ¡öµíê
        answers = request.form.getlist('answers[]')
        print(f"µö╢σê░τÜäτ¡öµíêµò░ΘçÅ: {len(answers)}")  # Φ░âΦ»òµùÑσ┐ù
        
        if not answers:
            flash('µ▓íµ£ëµö╢σê░τ¡öµíêµò░µì«', 'error')
            return redirect(url_for('manage_questions', lesson_id=lesson_id))
        
        # σ╝ÇσÉ»µò░µì«σ║ôΣ║ïσèí
        success_count = 0
        error_messages = []
        
        # ΦÄ╖σÅûσ╜ôσëìΦ»╛τ¿ïτÜäµ£ÇσñºΘóÿσÅ╖
        max_number = db.session.query(func.max(Question.question_number))\
            .filter_by(lesson_id=lesson_id)\
            .scalar() or 0
        
        print(f"σ╜ôσëìµ£ÇσñºΘóÿσÅ╖: {max_number}")  # Φ░âΦ»òµùÑσ┐ù
        
        # µë╣ΘçÅµ╖╗σèáµû░Θóÿτ¢«
        for i, answer in enumerate(answers, 1):
            try:
                question_number = max_number + i
                answer = answer.strip().upper() if answer else ''  # Φ╜¼µìóΣ╕║σñºσåÖσ╣╢σÄ╗ΘÖñτ⌐║τÖ╜
                print(f"σñäτÉåτ¼¼{question_number}Θóÿτ¡öµíê: {answer}")  # Φ░âΦ»òµùÑσ┐ù
                
                # µá╣µì«τ¡öµíêσêñµû¡Θóÿτ¢«τ▒╗σ₧ï
                if not answer:  # τ⌐║τ¡öµíêΦí¿τñ║Φ»üµÿÄΘóÿ
                    question_type = 'proof'
                    answer = 'Φ»üµÿÄΘóÿ'
                elif answer in ['A', 'B', 'C', 'D', 'E']:  # ABCDEΦí¿τñ║ΘÇëµï⌐Θóÿ
                    question_type = 'choice'
                else:  # σà╢Σ╗ûµâàσå╡Σ╕║σí½τ⌐║Θóÿ
                    question_type = 'fill'
                
                print(f"Θóÿτ¢«τ▒╗σ₧ï: {question_type}")  # Φ░âΦ»òµùÑσ┐ù
                
                # µúÇµƒÑΘóÿσÅ╖µÿ»σÉªσ╖▓σ¡ÿσ£¿
                existing_question = Question.query.filter_by(
                    lesson_id=lesson_id,
                    question_number=question_number
                ).first()
                
                if existing_question:
                    error_messages.append(f"τ¼¼{question_number}Θóÿσ╖▓σ¡ÿσ£¿")
                    continue
                
                # σê¢σ╗║µû░Θóÿτ¢«
                question = Question(
                    lesson_id=lesson_id,
                    question_number=question_number,
                    type=question_type,
                    answer=answer,
                    content=f"τ¼¼{question_number}Θóÿ"  # µ╖╗σèáΘ╗ÿΦ«ñσåàσ«╣
                )
                db.session.add(question)
                success_count += 1
                print(f"µêÉσèƒµ╖╗σèáΘóÿτ¢«∩╝îΘóÿσÅ╖: {question_number}")  # Φ░âΦ»òµùÑσ┐ù
                
            except Exception as e:
                error_messages.append(f"τ¼¼{question_number}Θóÿµ╖╗σèáσñ▒Φ┤Ñ: {str(e)}")
                print(f"µ╖╗σèáΘóÿτ¢«σñ▒Φ┤Ñ: {str(e)}")  # Φ░âΦ»òµùÑσ┐ù
                continue
        
        if success_count > 0:
            try:
                db.session.commit()
                flash(f'µêÉσèƒµ╖╗σèá{success_count}ΘüôΘóÿτ¢«', 'success')
                if error_messages:
                    flash('Θâ¿σêåΘóÿτ¢«µ╖╗σèáσñ▒Φ┤Ñ∩╝Ü' + '; '.join(error_messages), 'warning')
            except Exception as e:
                db.session.rollback()
                flash(f'Σ┐¥σ¡ÿΘóÿτ¢«σñ▒Φ┤Ñ∩╝Ü{str(e)}', 'error')
                print(f"Σ┐¥σ¡ÿσê░µò░µì«σ║ôσñ▒Φ┤Ñ: {str(e)}")  # Φ░âΦ»òµùÑσ┐ù
        else:
            flash('µëÇµ£ëΘóÿτ¢«µ╖╗σèáσñ▒Φ┤Ñ∩╝Ü' + '; '.join(error_messages), 'error')
        
    except Exception as e:
        db.session.rollback()
        print(f"τ│╗τ╗ƒΘöÖΦ»»: {str(e)}")  # Φ░âΦ»òµùÑσ┐ù
        flash(f'µ╖╗σèáΘóÿτ¢«σñ▒Φ┤Ñ∩╝Üτ│╗τ╗ƒΘöÖΦ»» - {str(e)}', 'error')
    
    return redirect(url_for('manage_questions', lesson_id=lesson_id))

@app.route('/admin/lesson/<int:lesson_id>/upload_individual_exam_files', methods=['POST'])
@admin_required
def upload_individual_exam_files(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    
    try:
        # ΦÄ╖σÅûBase64σ¢╛τëçµò░µì«
        image_data = request.form.get('file')
        if not image_data or not image_data.startswith('data:image'):
            flash('µùáµòêτÜäσ¢╛τëçµò░µì«', 'error')
            return redirect(url_for('manage_questions', lesson_id=lesson_id))
        
        # ΦÄ╖σÅûσ╜ôσëìµ£ÇσñºΘí╡τáü
        max_page = db.session.query(func.max(ExamFile.page_number)).filter_by(lesson_id=lesson_id).scalar() or 0
        
        # τöƒµêÉµûçΣ╗╢σÉì
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        random_suffix = random.randint(1000, 9999)
        filename = f"{lesson_id}_{timestamp}_{random_suffix}.png"
        
        # Σ╕èΣ╝áσê░ Cloudinary
        cloudinary_url = upload_to_cloudinary(image_data)
        if not cloudinary_url:
            raise Exception("Cloudinary Σ╕èΣ╝áσñ▒Φ┤Ñ")
        
        # σê¢σ╗║Φ»òσì╖µûçΣ╗╢Φ«░σ╜ò
        exam_file = ExamFile(
            filename=filename,
            path=cloudinary_url,  # Σ╜┐τö¿ Cloudinary URL
            lesson_id=lesson_id,
            page_number=max_page + 1
        )
        db.session.add(exam_file)
        db.session.commit()
        
        flash('Φ»òΘóÿΣ╕èΣ╝áµêÉσèƒ', 'success')
        
    except Exception as e:
        db.session.rollback()
        print(f"Σ╕èΣ╝áσñ▒Φ┤Ñ: {str(e)}")
        flash(f'σ¢╛τëçΣ╕èΣ╝áσñ▒Φ┤Ñ∩╝Ü{str(e)}', 'error')
    
    return redirect(url_for('manage_questions', lesson_id=lesson_id))

@app.route('/admin/lesson/<int:lesson_id>/upload_individual_explanation_files', methods=['POST'])
@admin_required
def upload_individual_explanation_files(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    
    try:
        # ΦÄ╖σÅûBase64σ¢╛τëçµò░µì«
        image_data = request.form.get('file')
        if not image_data or not image_data.startswith('data:image'):
            flash('µùáµòêτÜäσ¢╛τëçµò░µì«', 'error')
            return redirect(url_for('manage_questions', lesson_id=lesson_id))
        
        # ΦÄ╖σÅûσ╜ôσëìµ£ÇσñºΘí╡τáü
        max_page = db.session.query(func.max(ExplanationFile.page_number)).filter_by(lesson_id=lesson_id).scalar() or 0
        
        # τöƒµêÉµûçΣ╗╢σÉì
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        random_suffix = random.randint(1000, 9999)
        filename = f"{lesson_id}_{timestamp}_{random_suffix}.png"
        
        # Σ╕èΣ╝áσê░ Cloudinary
        cloudinary_url = upload_to_cloudinary(image_data)
        if not cloudinary_url:
            raise Exception("Cloudinary Σ╕èΣ╝áσñ▒Φ┤Ñ")
        
        # σê¢σ╗║Φºúµ₧ÉµûçΣ╗╢Φ«░σ╜ò
        explanation_file = ExplanationFile(
            filename=filename,
            path=cloudinary_url,  # Σ╜┐τö¿ Cloudinary URL
            lesson_id=lesson_id,
            page_number=max_page + 1
        )
        db.session.add(explanation_file)
        db.session.commit()
        
        flash('Φºúµ₧ÉΣ╕èΣ╝áµêÉσèƒ', 'success')
        
    except Exception as e:
        db.session.rollback()
        print(f"Σ╕èΣ╝áσñ▒Φ┤Ñ: {str(e)}")
        flash(f'σ¢╛τëçΣ╕èΣ╝áσñ▒Φ┤Ñ∩╝Ü{str(e)}', 'error')
    
    return redirect(url_for('manage_questions', lesson_id=lesson_id))

@app.route('/admin/lesson/<int:lesson_id>/upload_batch_exam_files', methods=['POST'])
@admin_required
def upload_batch_exam_files(lesson_id):
    """µë╣ΘçÅΣ╕èΣ╝áΦ»òΘóÿσ¢╛τëç∩╝îΘü┐σàìσ╣╢σÅæσ»╝Φç┤τÜäpage_numberΘçìσñìΘù«Θóÿ"""
    lesson = Lesson.query.get_or_404(lesson_id)
    
    try:
        # ΦÄ╖σÅûµëÇµ£ëBase64σ¢╛τëçµò░µì«
        image_files = request.form.getlist('files[]')
        if not image_files:
            return jsonify({'success': False, 'message': 'µ▓íµ£ëµÄÑµö╢σê░σ¢╛τëçµò░µì«'}), 400
        
        # ΦÄ╖σÅûσ╜ôσëìµ£ÇσñºΘí╡τáü∩╝êσÅ¬µƒÑΦ»óΣ╕Çµ¼í∩╝ë
        max_page = db.session.query(func.max(ExamFile.page_number)).filter_by(lesson_id=lesson_id).scalar() or 0
        
        success_count = 0
        failed_count = 0
        
        # µîëΘí║σ║ÅσñäτÉåµëÇµ£ëσ¢╛τëç
        for index, image_data in enumerate(image_files):
            try:
                if not image_data or not image_data.startswith('data:image'):
                    print(f"Φ╖│Φ┐çµùáµòêτÜäσ¢╛τëçµò░µì«∩╝îτ┤óσ╝ò: {index}")
                    failed_count += 1
                    continue
                
                # τöƒµêÉµûçΣ╗╢σÉì
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
                random_suffix = random.randint(1000, 9999)
                filename = f"{lesson_id}_{timestamp}_{random_suffix}.png"
                
                # Σ╕èΣ╝áσê░ Cloudinary
                cloudinary_url = upload_to_cloudinary(image_data)
                if not cloudinary_url:
                    print(f"Cloudinary Σ╕èΣ╝áσñ▒Φ┤Ñ∩╝îτ┤óσ╝ò: {index}")
                    failed_count += 1
                    continue
                
                # σê¢σ╗║Φ»òσì╖µûçΣ╗╢Φ«░σ╜ò∩╝îΣ╜┐τö¿ΘÇÆσó₧τÜäΘí╡τáü
                exam_file = ExamFile(
                    filename=filename,
                    path=cloudinary_url,
                    lesson_id=lesson_id,
                    page_number=max_page + index + 1  # τí«Σ┐¥Θí╡τáüΦ┐₧τ╗¡Σ╕öσö»Σ╕Ç
                )
                db.session.add(exam_file)
                success_count += 1
                
            except Exception as e:
                print(f"σñäτÉåσ¢╛τëçσñ▒Φ┤Ñ∩╝îτ┤óσ╝ò {index}: {str(e)}")
                failed_count += 1
                continue
        
        # Σ╕Çµ¼íµÇºµÅÉΣ║ñµëÇµ£ëµêÉσèƒτÜäΦ«░σ╜ò
        if success_count > 0:
            db.session.commit()
            print(f"µë╣ΘçÅΣ╕èΣ╝áµêÉσèƒ: {success_count} σ╝áσ¢╛τëç")
        
        if failed_count > 0:
            print(f"Θâ¿σêåΣ╕èΣ╝áσñ▒Φ┤Ñ: {failed_count} σ╝áσ¢╛τëç")
        
        return jsonify({
            'success': True,
            'message': f'µêÉσèƒΣ╕èΣ╝á {success_count} σ╝áσ¢╛τëç' + (f'∩╝î{failed_count} σ╝áσñ▒Φ┤Ñ' if failed_count > 0 else ''),
            'success_count': success_count,
            'failed_count': failed_count
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"µë╣ΘçÅΣ╕èΣ╝áσñ▒Φ┤Ñ: {str(e)}")
        return jsonify({'success': False, 'message': f'Σ╕èΣ╝áσñ▒Φ┤Ñ∩╝Ü{str(e)}'}), 500

@app.route('/admin/lesson/<int:lesson_id>/upload_batch_explanation_files', methods=['POST'])
@admin_required
def upload_batch_explanation_files(lesson_id):
    """µë╣ΘçÅΣ╕èΣ╝áΦºúµ₧Éσ¢╛τëç∩╝îΘü┐σàìσ╣╢σÅæσ»╝Φç┤τÜäpage_numberΘçìσñìΘù«Θóÿ"""
    lesson = Lesson.query.get_or_404(lesson_id)
    
    try:
        # ΦÄ╖σÅûµëÇµ£ëBase64σ¢╛τëçµò░µì«
        image_files = request.form.getlist('files[]')
        if not image_files:
            return jsonify({'success': False, 'message': 'µ▓íµ£ëµÄÑµö╢σê░σ¢╛τëçµò░µì«'}), 400
        
        # ΦÄ╖σÅûσ╜ôσëìµ£ÇσñºΘí╡τáü∩╝êσÅ¬µƒÑΦ»óΣ╕Çµ¼í∩╝ë
        max_page = db.session.query(func.max(ExplanationFile.page_number)).filter_by(lesson_id=lesson_id).scalar() or 0
        
        success_count = 0
        failed_count = 0
        
        # µîëΘí║σ║ÅσñäτÉåµëÇµ£ëσ¢╛τëç
        for index, image_data in enumerate(image_files):
            try:
                if not image_data or not image_data.startswith('data:image'):
                    print(f"Φ╖│Φ┐çµùáµòêτÜäσ¢╛τëçµò░µì«∩╝îτ┤óσ╝ò: {index}")
                    failed_count += 1
                    continue
                
                # τöƒµêÉµûçΣ╗╢σÉì
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
                random_suffix = random.randint(1000, 9999)
                filename = f"{lesson_id}_{timestamp}_{random_suffix}.png"
                
                # Σ╕èΣ╝áσê░ Cloudinary
                cloudinary_url = upload_to_cloudinary(image_data)
                if not cloudinary_url:
                    print(f"Cloudinary Σ╕èΣ╝áσñ▒Φ┤Ñ∩╝îτ┤óσ╝ò: {index}")
                    failed_count += 1
                    continue
                
                # σê¢σ╗║Φºúµ₧ÉµûçΣ╗╢Φ«░σ╜ò∩╝îΣ╜┐τö¿ΘÇÆσó₧τÜäΘí╡τáü
                explanation_file = ExplanationFile(
                    filename=filename,
                    path=cloudinary_url,
                    lesson_id=lesson_id,
                    page_number=max_page + index + 1  # τí«Σ┐¥Θí╡τáüΦ┐₧τ╗¡Σ╕öσö»Σ╕Ç
                )
                db.session.add(explanation_file)
                success_count += 1
                
            except Exception as e:
                print(f"σñäτÉåσ¢╛τëçσñ▒Φ┤Ñ∩╝îτ┤óσ╝ò {index}: {str(e)}")
                failed_count += 1
                continue
        
        # Σ╕Çµ¼íµÇºµÅÉΣ║ñµëÇµ£ëµêÉσèƒτÜäΦ«░σ╜ò
        if success_count > 0:
            db.session.commit()
            print(f"µë╣ΘçÅΣ╕èΣ╝áµêÉσèƒ: {success_count} σ╝áσ¢╛τëç")
        
        if failed_count > 0:
            print(f"Θâ¿σêåΣ╕èΣ╝áσñ▒Φ┤Ñ: {failed_count} σ╝áσ¢╛τëç")
        
        return jsonify({
            'success': True,
            'message': f'µêÉσèƒΣ╕èΣ╝á {success_count} σ╝áσ¢╛τëç' + (f'∩╝î{failed_count} σ╝áσñ▒Φ┤Ñ' if failed_count > 0 else ''),
            'success_count': success_count,
            'failed_count': failed_count
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"µë╣ΘçÅΣ╕èΣ╝áσñ▒Φ┤Ñ: {str(e)}")
        return jsonify({'success': False, 'message': f'Σ╕èΣ╝áσñ▒Φ┤Ñ∩╝Ü{str(e)}'}), 500

@app.route('/admin/badge_rules')
@admin_required
def badge_rules():
    return render_template('admin/badge_rules.html')

@app.route('/admin/student/<int:user_id>/dashboard')
@admin_required
def student_dashboard_admin(user_id):
    # ΦÄ╖σÅûσ¡ªτöƒτö¿µê╖
    student = User.query.get_or_404(user_id)
    if student.is_admin:
        flash('µùáµ│òµƒÑτ£ïτ«íτÉåσæÿτÜäΣ╗¬Φí¿τ¢ÿ')
        return redirect(url_for('admin_users'))
    
    # ΦÄ╖σÅûΦ»Ñσ¡ªτöƒτÜäµëÇµ£ëµ╡ïΘ¬îσÄåσÅ▓Φ«░σ╜ò
    quiz_history = QuizHistory.query.filter_by(user_id=student.id).all()
    
    # Φ«íτ«ùµÇ╗µ╡ïΘ¬îµò░σÆîσ╣│σ¥çµ¡úτí«τÄç
    total_quizzes = len(quiz_history)
    if total_quizzes > 0:
        total_correct_rate = round(sum(quiz.correct_rate for quiz in quiz_history) / total_quizzes)
    else:
        total_correct_rate = 0
    
    # ΦÄ╖σÅûσÄåσÅ▓Φ»╛τ¿ïµò░µì«
    history_data = db.session.query(Lesson, QuizHistory)\
        .join(QuizHistory, Lesson.id == QuizHistory.lesson_id)\
        .filter(QuizHistory.user_id == student.id)\
        .order_by(QuizHistory.completed_at.desc())\
        .all()
    
    # ΦÄ╖σÅûσ╖▓σ«îµêÉτÜäΦ»╛τ¿ïIDσêùΦí¿
    completed_lesson_ids = [quiz.lesson_id for quiz in quiz_history]
    
    # ΦÄ╖σÅûσ╜ôσëìσÅ»τö¿τÜäΦ»╛τ¿ï∩╝êµ┐Çµ┤╗τè╢µÇüΣ╕öµ£¬σ«îµêÉτÜäΦ»╛τ¿ï∩╝ë
    available_lessons = Lesson.query.join(
        lesson_class_association,
        Lesson.id == lesson_class_association.c.lesson_id
    ).filter(
        lesson_class_association.c.class_id == student.class_id,
        Lesson.is_active == True,
        ~Lesson.id.in_(completed_lesson_ids) if completed_lesson_ids else True
    ).all()
    
    # σçåσñçΦ╢ïσè┐σ¢╛µò░µì«
    trend_data = []
    for quiz in quiz_history:
        lesson = Lesson.query.get(quiz.lesson_id)
        
        # Φ«íτ«ùΦ»ÑΦ»╛τ¿ïτÜäτÅ¡τ║ºσ╣│σ¥çµ¡úτí«τÄç
        class_avg = db.session.query(func.avg(QuizHistory.correct_answers * 100.0 / QuizHistory.total_questions))\
            .filter(QuizHistory.lesson_id == quiz.lesson_id,
                   QuizHistory.user_id != student.id)\
            .scalar() or 0
        
        trend_data.append({
            'date': quiz.completed_at.strftime('%Y-%m-%d'),
            'correct_rate': round(quiz.correct_rate),  # σÅûµò┤
            'class_avg': round(class_avg),  # σÅûµò┤
            'lesson_title': lesson.title if lesson else 'Unknown'
        })
    
    return render_template('student/dashboard.html',
                         current_user=student,  # Σ╜┐τö¿σ¡ªτöƒτö¿µê╖Σ┐íµü»
                         total_quizzes=total_quizzes,
                         average_correct_rate=total_correct_rate,
                         history_data=history_data,
                         trend_data=json.dumps(trend_data),
                         lessons=available_lessons,
                         is_admin_view=True)  # µáçΦ«░Φ┐Öµÿ»τ«íτÉåσæÿΦºåσ¢╛

@app.route('/student/wrong_questions')
@login_required
def wrong_questions():
    # ΦÄ╖σÅûτö¿µê╖µëÇµ£ëτÜäΘöÖΘóÿΦ«░σ╜ò
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

    # ΦÄ╖σÅûσîàσÉ½ΘöÖΘóÿτÜäΦ»╛τ¿ïσêùΦí¿
    lessons = list(set(wa.Lesson for wa in wrong_answers))
    lessons.sort(key=lambda x: x.id)

    # ΦÄ╖σÅûµ»ÅΣ╕¬ΘöÖΘóÿσ»╣σ║öτÜäΦ»òσì╖σÆîΦºúµ₧Éσ¢╛τëç
    images = {}
    for wa in wrong_answers:
        lesson_id = wa.Lesson.id
        question_number = wa.Question.question_number
        key = (lesson_id, question_number)
        
        if key not in images:
            # ΦÄ╖σÅûσ»╣σ║öτÜäΦ»òσì╖σ¢╛τëç
            exam_file = ExamFile.query.filter_by(
                lesson_id=lesson_id,
                page_number=question_number
            ).first()
            
            # ΦÄ╖σÅûσ»╣σ║öτÜäΦºúµ₧Éσ¢╛τëç
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
    """按 lesson_id 绑定回放链接；表单必须带该课程的固定 action，禁止依赖前端改 URL。"""
    lesson = Lesson.query.get_or_404(lesson_id)
    action = (request.form.get('action') or 'save').strip().lower()

    if action == 'clear':
        try:
            lesson.video_url = None
            db.session.commit()
            flash(f'已清除「{lesson.title}」的回放链接', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'清除失败：{str(e)}', 'error')
        return redirect(url_for('admin_lessons'))

    video_url = (request.form.get('video_url') or '').strip()
    if not video_url:
        flash('视频链接不能为空', 'error')
        return redirect(url_for('admin_lessons'))

    # 简单校验：必须是 http(s) 链接，避免误粘贴文本
    if not (video_url.startswith('http://') or video_url.startswith('https://')):
        flash('请填写以 http:// 或 https:// 开头的完整视频链接', 'error')
        return redirect(url_for('admin_lessons'))

    try:
        lesson.video_url = video_url
        db.session.commit()
        flash(f'「{lesson.title}」回放链接已更新', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'更新失败：{str(e)}', 'error')

    return redirect(url_for('admin_lessons'))


@app.route('/lesson/<int:lesson_id>/replay')
@login_required
def lesson_replay(lesson_id):
    """管理端与学生端统一入口：始终按 lesson_id 读取当前绑定的回放，避免各处硬编码 URL 不一致。"""
    lesson = Lesson.query.get_or_404(lesson_id)
    if not lesson.video_url:
        flash('该课程暂无回放', 'error')
        if current_user.is_admin:
            return redirect(url_for('admin_lessons'))
        return redirect(url_for('student_dashboard'))

    if not current_user.is_admin:
        user_class = Class.query.get(current_user.class_id) if current_user.class_id else None
        in_class = bool(user_class and user_class in (lesson.classes or []))
        has_history = QuizHistory.query.filter_by(
            user_id=current_user.id, lesson_id=lesson_id
        ).first() is not None
        if not in_class and not has_history:
            abort(403)

    return redirect(lesson.video_url)

@app.route('/admin/user/add', methods=['POST'])
@admin_required
def add_user():
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    role = request.form.get('role')
    class_ids = request.form.getlist('classes')  # ΦÄ╖σÅûσñÜΣ╕¬τÅ¡τ║ºID
    
    if not username or not email or not password:
        return redirect(url_for('admin_users'))
    
    if User.query.filter_by(username=username).first():
        return redirect(url_for('admin_users'))
    
    if User.query.filter_by(email=email).first():
        return redirect(url_for('admin_users'))
    
    # σê¢σ╗║µû░τö¿µê╖
    new_user = User(
        username=username,
        email=email,
        password=password,
        is_active=True
    )
    
    # Φ«╛τ╜«τö¿µê╖ΦºÆΦë▓
    if role == 'admin':
        new_user.is_admin = True
    elif role == 'student' and class_ids:
        # σªéµ₧£µÿ»σ¡ªτöƒ∩╝îµ╖╗σèáτÅ¡τ║ºσà│Φüö
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

@app.route('/debug/static/<path:filename>')
def debug_static(filename):
    """Φ░âΦ»òΘ¥ÖµÇüµûçΣ╗╢Φ«┐Θù«"""
    try:
        # µúÇµƒÑµûçΣ╗╢µÿ»σÉªσ¡ÿσ£¿
        file_path = os.path.join(app.static_folder, filename)
        if os.path.exists(file_path):
            return {
                'status': 'success',
                'exists': True,
                'absolute_path': file_path,
                'relative_path': filename,
                'file_size': os.path.getsize(file_path)
            }
        else:
            return {
                'status': 'error',
                'exists': False,
                'attempted_path': file_path
            }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }

@app.route('/admin/fix_file_paths')
@admin_required
def fix_file_paths():
    """Σ┐«σñìµò░µì«σ║ôΣ╕¡τÜäµûçΣ╗╢Φ╖»σ╛ä"""
    try:
        # ΦÄ╖σÅûµëÇµ£ëΦ»òσì╖µûçΣ╗╢Φ«░σ╜ò
        exam_files = ExamFile.query.all()
        fixed_count = 0
        
        for file in exam_files:
            # µúÇµƒÑµûçΣ╗╢µÿ»σÉªσ¡ÿσ£¿
            current_path = os.path.join('static', file.path)
            if not os.path.exists(current_path):
                # σ░¥Φ»òσ£¿uploads/examsτ¢«σ╜òΣ╕¡µƒÑµë╛µûçΣ╗╢
                filename = os.path.basename(file.path)
                new_path = f'uploads/exams/{filename}'
                new_full_path = os.path.join('static', new_path)
                
                if os.path.exists(new_full_path):
                    # µ¢┤µû░µò░µì«σ║ôΣ╕¡τÜäΦ╖»σ╛ä
                    file.path = new_path
                    fixed_count += 1
        
        if fixed_count > 0:
            db.session.commit()
            flash(f'µêÉσèƒΣ┐«σñì {fixed_count} Σ╕¬µûçΣ╗╢Φ╖»σ╛ä', 'success')
        else:
            flash('µ▓íµ£ëΘ£ÇΦªüΣ┐«σñìτÜäµûçΣ╗╢Φ╖»σ╛ä', 'info')
            
    except Exception as e:
        db.session.rollback()
        flash(f'Σ┐«σñìµûçΣ╗╢Φ╖»σ╛äµù╢σç║ΘöÖ∩╝Ü{str(e)}', 'error')
    
    return redirect(url_for('admin_lessons'))

@app.route('/admin/fix_render_paths')
@admin_required
def fix_render_paths():
    """Σ┐«σñì Render τ½»µò░µì«σ║ôΣ╕¡τÜäµûçΣ╗╢Φ╖»σ╛ä"""
    try:
        # ΦÄ╖σÅûµëÇµ£ëΦ»òσì╖µûçΣ╗╢Φ«░σ╜ò
        exam_files = ExamFile.query.all()
        fixed_count = 0
        
        for file in exam_files:
            # µúÇµƒÑσ╣╢Σ┐«µ¡úµûçΣ╗╢Φ╖»σ╛ä
            current_path = file.path
            filename = os.path.basename(current_path)
            
            # τí«Σ┐¥Φ╖»σ╛äµá╝σ╝Åµ¡úτí«
            if not current_path.startswith('uploads/'):
                # σªéµ₧£Φ╖»σ╛äΣ╗Ñ static/ σ╝Çσñ┤∩╝îτº╗ΘÖñσ«â
                if current_path.startswith('static/'):
                    current_path = current_path[7:]
                # σªéµ₧£Φ╖»σ╛äΣ╕ìσîàσÉ½ uploads/∩╝îµ╖╗σèáσ«â
                if not current_path.startswith('uploads/'):
                    current_path = f'uploads/exams/{filename}'
                
                # µ¢┤µû░µò░µì«σ║ôΦ«░σ╜ò
                file.path = current_path
                fixed_count += 1
                print(f"Σ┐«σñìµûçΣ╗╢Φ╖»σ╛ä: {file.path} -> {current_path}")
        
        if fixed_count > 0:
            db.session.commit()
            flash(f'µêÉσèƒΣ┐«σñì {fixed_count} Σ╕¬µûçΣ╗╢Φ╖»σ╛ä', 'success')
        else:
            flash('µ▓íµ£ëΘ£ÇΦªüΣ┐«σñìτÜäµûçΣ╗╢Φ╖»σ╛ä', 'info')
            
    except Exception as e:
        db.session.rollback()
        flash(f'Σ┐«σñìµûçΣ╗╢Φ╖»σ╛äµù╢σç║ΘöÖ∩╝Ü{str(e)}', 'error')
        print(f"Σ┐«σñìµûçΣ╗╢Φ╖»σ╛äµù╢σç║ΘöÖ: {str(e)}")
    
    return redirect(url_for('admin_lessons'))

@app.route('/admin/fix_db_paths')
@admin_required
def fix_db_paths():
    """Σ┐«σñìµò░µì«σ║ôΣ╕¡τÜäµûçΣ╗╢Φ╖»σ╛äΦ«░σ╜ò"""
    try:
        # ΦÄ╖σÅûµëÇµ£ëΦ»òσì╖µûçΣ╗╢Φ«░σ╜ò
        exam_files = ExamFile.query.all()
        explanation_files = ExplanationFile.query.all()
        
        exam_fixed = 0
        explanation_fixed = 0
        
        # Σ┐«σñìΦ»òσì╖µûçΣ╗╢Φ╖»σ╛ä
        for file in exam_files:
            if 'uploads/uploads/' in file.path:
                file.path = file.path.replace('uploads/uploads/', 'uploads/')
                exam_fixed += 1
        
        # Σ┐«σñìΦºúµ₧ÉµûçΣ╗╢Φ╖»σ╛ä
        for file in explanation_files:
            if 'uploads/uploads/' in file.path:
                file.path = file.path.replace('uploads/uploads/', 'uploads/')
                explanation_fixed += 1
        
        if exam_fixed > 0 or explanation_fixed > 0:
            db.session.commit()
            flash(f'µêÉσèƒΣ┐«σñì {exam_fixed} Σ╕¬Φ»òσì╖µûçΣ╗╢σÆî {explanation_fixed} Σ╕¬Φºúµ₧ÉµûçΣ╗╢τÜäΦ╖»σ╛ä', 'success')
        else:
            flash('µ▓íµ£ëΘ£ÇΦªüΣ┐«σñìτÜäµûçΣ╗╢Φ╖»σ╛ä', 'info')
        
        return redirect(url_for('admin_lessons'))
        
    except Exception as e:
        flash(f'Σ┐«σñìµûçΣ╗╢Φ╖»σ╛äµù╢σç║ΘöÖ∩╝Ü{str(e)}', 'error')
        return redirect(url_for('admin_lessons'))

@app.route('/debug/check_file/<path:filename>')
def debug_check_file(filename):
    """µúÇµƒÑτë╣σ«ÜµûçΣ╗╢τÜäΦ«┐Θù«µâàσå╡"""
    try:
        # µ₧äσ╗║µëÇµ£ëσÅ»Φâ╜τÜäΦ╖»σ╛ä
        possible_paths = [
            os.path.join(app.static_folder, 'uploads', 'exams', filename),
            os.path.join(app.static_folder, 'uploads', filename),
            os.path.join(app.static_folder, filename),
            filename
        ]
        
        results = []
        for path in possible_paths:
            result = {
                'path': path,
                'exists': os.path.exists(path),
                'is_file': os.path.isfile(path) if os.path.exists(path) else False,
                'size': os.path.getsize(path) if os.path.exists(path) else None,
                'absolute_path': os.path.abspath(path)
            }
            results.append(result)
            
        # µúÇµƒÑµò░µì«σ║ôΣ╕¡τÜäΦ«░σ╜ò
        exam_file = ExamFile.query.filter(
            ExamFile.path.like(f'%{filename}')
        ).first()
        
        db_info = None
        if exam_file:
            db_info = {
                'id': exam_file.id,
                'filename': exam_file.filename,
                'path': exam_file.path,
                'lesson_id': exam_file.lesson_id
            }
        
        return {
            'filename': filename,
            'static_folder': app.static_folder,
            'paths_checked': results,
            'database_record': db_info
        }
        
    except Exception as e:
        return {
            'error': str(e),
            'filename': filename
        }

@app.route('/debug/file_paths')
def debug_file_paths():
    """Φ░âΦ»òµûçΣ╗╢Φ╖»σ╛äΘù«Θóÿ"""
    try:
        # ΦÄ╖σÅûµëÇµ£ëΦ»òσì╖σÆîΦºúµ₧ÉµûçΣ╗╢Φ«░σ╜ò
        exam_files = ExamFile.query.all()
        explanation_files = ExplanationFile.query.all()
        
        results = {
            'exam_files': [],
            'explanation_files': [],
            'static_folder': app.static_folder,
            'upload_folder': UPLOAD_FOLDER
        }
        
        # µúÇµƒÑΦ»òσì╖µûçΣ╗╢
        for file in exam_files:
            file_info = {
                'id': file.id,
                'filename': file.filename,
                'stored_path': file.path,
                'lesson_id': file.lesson_id,
                'page_number': file.page_number
            }
            
            # µúÇµƒÑΣ╕ìσÉîτÜäσÅ»Φâ╜Φ╖»σ╛ä
            possible_paths = [
                os.path.join(app.static_folder, file.path),
                os.path.join(app.static_folder, 'uploads', file.filename),
                os.path.join('static', file.path)
            ]
            
            file_info['path_checks'] = [
                {
                    'path': path,
                    'exists': os.path.exists(path),
                    'is_file': os.path.isfile(path) if os.path.exists(path) else False
                }
                for path in possible_paths
            ]
            
            results['exam_files'].append(file_info)
        
        # µúÇµƒÑΦºúµ₧ÉµûçΣ╗╢
        for file in explanation_files:
            file_info = {
                'id': file.id,
                'filename': file.filename,
                'stored_path': file.path,
                'lesson_id': file.lesson_id,
                'page_number': file.page_number
            }
            
            # µúÇµƒÑΣ╕ìσÉîτÜäσÅ»Φâ╜Φ╖»σ╛ä
            possible_paths = [
                os.path.join(app.static_folder, file.path),
                os.path.join(app.static_folder, 'uploads', file.filename),
                os.path.join('static', file.path)
            ]
            
            file_info['path_checks'] = [
                {
                    'path': path,
                    'exists': os.path.exists(path),
                    'is_file': os.path.isfile(path) if os.path.exists(path) else False
                }
                for path in possible_paths
            ]
            
            results['explanation_files'].append(file_info)
        
        return jsonify(results)
        
    except Exception as e:
        return jsonify({
            'error': str(e)
        }), 500

# µ╕àτÉåσÄåσÅ▓µò░µì«∩╝ÜσÅ¬Σ┐¥τòÖµ»ÅΣ╕¬σ¡ªτöƒµ»ÅΘù¿Φ»╛τÜäτ¼¼Σ╕Çµ¼íτ¡öΘóÿΦ«░σ╜ò∩╝îσà╢Σ╜Öσà¿Θâ¿σêáΘÖñ
def clean_duplicate_quiz_history():
    from sqlalchemy import and_
    all_histories = QuizHistory.query.order_by(QuizHistory.user_id, QuizHistory.lesson_id, QuizHistory.completed_at.asc()).all()
    seen = set()
    to_delete = []
    for qh in all_histories:
        key = (qh.user_id, qh.lesson_id)
        if key in seen:
            to_delete.append(qh)
        else:
            seen.add(key)
    for qh in to_delete:
        # σêáΘÖñτ¢╕σà│τÜä UserAnswer
        UserAnswer.query.filter_by(quiz_history_id=qh.id).delete()
        db.session.delete(qh)
    db.session.commit()

@app.route('/admin/mark_answer/<int:user_answer_id>', methods=['POST'])
@admin_required
def mark_answer(user_answer_id):
    user_answer = UserAnswer.query.get_or_404(user_answer_id)
    is_correct_str = request.form.get('is_correct', 'false')
    is_correct = str(is_correct_str).lower() == 'true'
    user_answer.is_correct = is_correct

    # Θçìµû░τ╗ƒΦ«íΦ»Ñµ¼íΣ╜£Σ╕ÜτÜäµ¡úτí«Θóÿµò░
    quiz_history = QuizHistory.query.get(user_answer.quiz_history_id)
    quiz_history.correct_answers = UserAnswer.query.filter_by(
        quiz_history_id=quiz_history.id, is_correct=True
    ).count()
    db.session.commit()
    flash('σêñσ«Üσ╖▓Σ┐«µö╣', 'success')
    return redirect(request.referrer or url_for('admin_dashboard'))


@app.route('/admin/quiz_history/<int:quiz_history_id>/ai_regrade', methods=['POST'])
@admin_required
def ai_regrade_quiz(quiz_history_id):
    """τ«íτÉåσæÿσ»╣σ╖▓µÅÉΣ║ñΣ╜£Σ╕Üτö¿ GPT Θçìσêñ∩╝êΣ╕╗Φªüτö¿Σ║ÄσåÖµ│òΣ╕ìσÉîΦó½Φ»»σêñΣ╕║ΘöÖτÜäΘóÿ∩╝ëπÇé"""
    from ai_grading import ai_grading_available

    if not ai_grading_available():
        flash('µ£¬Θàìτ╜« OPENAI_API_KEY∩╝îµùáµ│òΣ╜┐τö¿ AI Θçìσêñ', 'error')
        return redirect(request.referrer or url_for('admin_dashboard'))

    quiz_history = QuizHistory.query.get_or_404(quiz_history_id)
    answers = (
        UserAnswer.query.filter_by(quiz_history_id=quiz_history.id)
        .join(Question, Question.id == UserAnswer.question_id)
        .order_by(Question.question_number.asc())
        .all()
    )
    exam_by_page, expl_by_page = _homework_image_maps(quiz_history.lesson_id)
    changed = 0
    for ua in answers:
        q = ua.question
        if not q:
            continue
        raw = (ua.answer or '').strip()
        if not raw or raw.upper() == 'IDK':
            if ua.is_correct:
                ua.is_correct = False
                changed += 1
            continue
        # σ╖▓σêñσ»╣τÜäΘÇëµï⌐Θóÿ/σí½τ⌐║ΘóÿΦ╖│Φ┐ç∩╝êτ£üΦ┤╣τö¿∩╝ë∩╝¢Φºúτ¡öΘóÿΣ╕ÄσêñΘöÖΘóÿΘçìσêñ
        if ua.is_correct and q.type != 'proof':
            continue
        new_ok = _grade_homework_question(q, raw, exam_by_page, expl_by_page)
        if bool(ua.is_correct) != bool(new_ok):
            ua.is_correct = new_ok
            changed += 1

    quiz_history.correct_answers = UserAnswer.query.filter_by(
        quiz_history_id=quiz_history.id, is_correct=True
    ).count()
    db.session.commit()
    flash(f'AI Θçìσêñσ«îµêÉ∩╝îµ¢┤µû░Σ║å {changed} Θóÿσêñσ«Ü', 'success')
    return redirect(request.referrer or url_for(
        'view_history', lesson_id=quiz_history.lesson_id, user_id=quiz_history.user_id
    ))


def _can_access_user_answer(user_answer):
    """µ£¼Σ║║µêûτ«íτÉåσæÿσÅ»Φ«┐Θù«Φ»Ñτ¡öΘóÿΦ«░σ╜òπÇé"""
    if not current_user.is_authenticated:
        return False
    if getattr(current_user, 'is_admin', False):
        return True
    return user_answer.user_id == current_user.id


def _tutor_context_for_answer(user_answer):
    """τ╗äΦúàσ»╝σ¡ªΣ╕èΣ╕ïµûç∩╝¢µùáµ¥âµêûΣ╕ìσ¡ÿσ£¿Φ┐öσ¢₧ (None, error_response)πÇé"""
    q = user_answer.question
    if not q:
        return None, (jsonify({'ok': False, 'reply': 'Φ»ÑΘóÿΘ£ÇΦªüΦ»óΘù«ΦÇüσ╕êτ¡öτûæ', 'can_teach': False, 'done': True}), 404)
    exam_by_page, expl_by_page = _homework_image_maps(user_answer.lesson_id)
    qnum = q.question_number
    image_urls = [u for u in (exam_by_page.get(qnum), expl_by_page.get(qnum)) if u]
    ctx = {
        'question_type': q.type or 'fill',
        'stem': q.content or '',
        'correct_answer': q.answer or '',
        'student_answer': user_answer.answer or '',
        'was_correct': bool(user_answer.is_correct) if user_answer.is_correct is not None else None,
        'image_urls': image_urls,
        'qnum': qnum,
    }
    return ctx, None


@app.route('/student/ai_tutor/start', methods=['POST'])
@login_required
def ai_tutor_start():
    from ai_tutor import tutor_available, start_tutor, MAX_STUDENT_TURNS, TEACHER_FALLBACK

    data = request.get_json(silent=True) or {}
    answer_id = data.get('user_answer_id') or request.form.get('user_answer_id', type=int)
    try:
        answer_id = int(answer_id)
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'reply': TEACHER_FALLBACK, 'can_teach': False, 'done': True}), 400

    ua = UserAnswer.query.get_or_404(answer_id)
    if not _can_access_user_answer(ua):
        return jsonify({'ok': False, 'reply': 'µùáµ¥âΦ«┐Θù«', 'can_teach': False, 'done': True}), 403

    if not tutor_available():
        return jsonify({
            'ok': False,
            'reply': TEACHER_FALLBACK,
            'can_teach': False,
            'done': True,
            'turns_used': 0,
            'turns_max': MAX_STUDENT_TURNS,
        })

    ctx, err = _tutor_context_for_answer(ua)
    if err:
        return err

    result = start_tutor(
        question_type=ctx['question_type'],
        stem=ctx['stem'],
        correct_answer=ctx['correct_answer'],
        student_answer=ctx['student_answer'],
        was_correct=ctx['was_correct'],
        image_urls=ctx['image_urls'],
    )
    return jsonify({
        'ok': result.get('ok', False),
        'reply': result.get('reply') or TEACHER_FALLBACK,
        'can_teach': bool(result.get('can_teach')),
        'done': bool(result.get('done')),
        'turns_used': 0,
        'turns_max': MAX_STUDENT_TURNS,
        'qnum': ctx['qnum'],
    })


@app.route('/student/ai_tutor/chat', methods=['POST'])
@login_required
def ai_tutor_chat():
    from ai_tutor import tutor_available, continue_tutor, MAX_STUDENT_TURNS, TEACHER_FALLBACK

    data = request.get_json(silent=True) or {}
    answer_id = data.get('user_answer_id')
    try:
        answer_id = int(answer_id)
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'reply': TEACHER_FALLBACK, 'can_teach': False, 'done': True}), 400

    student_message = (data.get('student_message') or '').strip()
    history = data.get('messages') or []
    if not isinstance(history, list):
        history = []

    ua = UserAnswer.query.get_or_404(answer_id)
    if not _can_access_user_answer(ua):
        return jsonify({'ok': False, 'reply': 'µùáµ¥âΦ«┐Θù«', 'can_teach': False, 'done': True}), 403

    # σ¡ªτöƒσÅæΦ¿Çµ¼íµò░ = history Σ╕¡ user µ¥íµò░ + µ£¼µ¥í
    prior_user = sum(1 for h in history if isinstance(h, dict) and h.get('role') == 'user')
    turns_used = prior_user + 1
    if turns_used > MAX_STUDENT_TURNS:
        return jsonify({
            'ok': False,
            'reply': 'µ£¼Φ»╛σ»╝σ¡ªσ¢₧σÉêσ╖▓τö¿σ«îπÇé' + TEACHER_FALLBACK,
            'can_teach': False,
            'done': True,
            'turns_used': MAX_STUDENT_TURNS,
            'turns_max': MAX_STUDENT_TURNS,
        })

    if not tutor_available():
        return jsonify({
            'ok': False,
            'reply': TEACHER_FALLBACK,
            'can_teach': False,
            'done': True,
            'turns_used': turns_used,
            'turns_max': MAX_STUDENT_TURNS,
        })

    ctx, err = _tutor_context_for_answer(ua)
    if err:
        return err

    clean_history = []
    for h in history:
        if not isinstance(h, dict):
            continue
        role = h.get('role')
        content = (h.get('content') or '').strip()
        if role in ('assistant', 'user') and content:
            clean_history.append({'role': role, 'content': content})

    result = continue_tutor(
        question_type=ctx['question_type'],
        stem=ctx['stem'],
        correct_answer=ctx['correct_answer'],
        student_answer=ctx['student_answer'],
        was_correct=ctx['was_correct'],
        image_urls=ctx['image_urls'],
        history=clean_history,
        student_message=student_message,
        student_turns_used=turns_used,
    )
    return jsonify({
        'ok': result.get('ok', False),
        'reply': result.get('reply') or TEACHER_FALLBACK,
        'can_teach': bool(result.get('can_teach')),
        'done': bool(result.get('done')),
        'turns_used': turns_used,
        'turns_max': MAX_STUDENT_TURNS,
        'qnum': ctx['qnum'],
    })


class CoursewareFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    path = db.Column(db.String(255), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    lesson = db.relationship('Lesson', backref=db.backref('courseware_files', lazy=True))

@app.route('/admin/lesson/<int:lesson_id>/upload_courseware', methods=['POST'])
@admin_required
def upload_courseware(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    file = request.files.get('courseware')
    if not file or not (file.filename.endswith('.ppt') or file.filename.endswith('.pptx')):
        flash('Φ»╖Σ╕èΣ╝áPPTµûçΣ╗╢', 'error')
        return redirect(url_for('admin_lessons'))
    filename = secure_filename(file.filename)
    # Σ╕èΣ╝áσê░ Cloudinary
    result = cloudinary.uploader.upload(
        file,
        resource_type='raw',
        folder=f"courseware/{lesson_id}/"
    )
    courseware = CoursewareFile(
        lesson_id=lesson_id,
        filename=filename,
        path=result['secure_url']
    )
    db.session.add(courseware)
    db.session.commit()
    flash('Φ»╛Σ╗╢Σ╕èΣ╝áµêÉσèƒ', 'success')
    return redirect(url_for('admin_lessons'))

@app.route('/admin/lesson/<int:lesson_id>/courseware')
@admin_required
def view_lesson_courseware(lesson_id):
    """τ«íτÉåσæÿµƒÑτ£ïµƒÉΦ»╛τ¿ïΣ╕ïσ╖▓Σ╕èΣ╝áτÜäΦ»╛Σ╗╢σêùΦí¿∩╝îσÅ»Σ╕ïΦ╜╜µêûτ╗ºτ╗¡Σ╕èΣ╝áπÇé"""
    lesson = Lesson.query.get_or_404(lesson_id)
    files = lesson.courseware_files or []
    return render_template('admin/lesson_courseware.html', lesson=lesson, courseware_files=files)

@app.route('/courseware/<int:courseware_id>/download')
@login_required
def download_courseware(courseware_id):
    courseware = CoursewareFile.query.get_or_404(courseware_id)
    # Σ╗Ä Cloudinary µïëσÅûµûçΣ╗╢σåàσ«╣
    response = requests.get(courseware.path)
    file_stream = BytesIO(response.content)
    # τö¿ send_file Φ┐öσ¢₧∩╝îΦç¬σè¿σ╕ªΣ╕èσÄƒσºïµûçΣ╗╢σÉì
    return send_file(
        file_stream,
        as_attachment=True,
        download_name=courseware.filename  # Flask 2.0+ µÄ¿ΦìÉτö¿ download_name
    )

@app.route('/admin/user/<int:user_id>/edit', methods=['POST'])
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.is_admin:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'msg': 'Σ╕ìΦâ╜τ╝ûΦ╛æτ«íτÉåσæÿΦ┤ªµê╖'})
        flash('Σ╕ìΦâ╜τ╝ûΦ╛æτ«íτÉåσæÿΦ┤ªµê╖', 'error')
        return redirect(url_for('admin_users'))

    username = request.form.get('username')
    class_id = request.form.get('class_id')
    report_link = (request.form.get('report_link') or '').strip() or None

    if not username or not class_id:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'msg': 'τö¿µê╖σÉìσÆîτÅ¡τ║ºΣ╕ìΦâ╜Σ╕║τ⌐║'})
        flash('τö¿µê╖σÉìσÆîτÅ¡τ║ºΣ╕ìΦâ╜Σ╕║τ⌐║', 'error')
        return redirect(url_for('admin_users'))

    # µúÇµƒÑτö¿µê╖σÉìµÿ»σÉªσ╖▓σ¡ÿσ£¿∩╝êµÄÆΘÖñσ╜ôσëìτö¿µê╖∩╝ë
    existing_user = User.query.filter(User.username == username, User.id != user_id).first()
    if existing_user:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'msg': 'τö¿µê╖σÉìσ╖▓σ¡ÿσ£¿'})
        flash('τö¿µê╖σÉìσ╖▓σ¡ÿσ£¿', 'error')
        return redirect(url_for('admin_users'))

    user.username = username
    user.class_id = class_id
    user.report_link = report_link
    
    try:
        db.session.commit()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'msg': 'τö¿µê╖Σ┐íµü»µ¢┤µû░µêÉσèƒ'})
        flash('τö¿µê╖Σ┐íµü»µ¢┤µû░µêÉσèƒ', 'success')
    except Exception as e:
        db.session.rollback()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'msg': f'µ¢┤µû░σñ▒Φ┤Ñ: {e}'})
        flash(f'µ¢┤µû░σñ▒Φ┤Ñ: {e}', 'error')

    return redirect(url_for('admin_users'))

@app.route('/admin/lesson/<int:lesson_id>/students')
@admin_required
def lesson_students(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    # ΦÄ╖σÅûµëÇµ£ëτÅ¡τ║ºτÜäσ¡ªτöƒ
    students = []
    for c in lesson.classes:
        students.extend(c.users)
    students = list(set(students))  # σÄ╗Θçì
    # µƒÑΦ»óσ╖▓σ«îµêÉΦ»ÑΦ»╛τ¿ïτÜäσ¡ªτöƒ
    completed_histories = QuizHistory.query.filter_by(lesson_id=lesson_id).all()
    completed_students = set(h.user for h in completed_histories)
    completed = [s for s in students if s in completed_students]
    # µ£¬σ«îµêÉ∩╝ÜΦ┐çµ╗ñµÄëσ╖▓Φó½σü£τö¿∩╝êµ£¬µ┐Çµ┤╗∩╝ëτÜäσ¡ªτöƒ
    not_completed = [s for s in students if s not in completed_students and getattr(s, 'is_active', True)]

    # τ╗ƒΦ«íµ»ÅΣ╕¬σ╖▓σ«îµêÉσ¡ªτöƒτÜäσ╛ùσêå
    completed_scores = []
    for student in completed:
        # σÅ¬σÅûΦ»Ñτöƒτ¼¼Σ╕Çµ¼íσ«îµêÉΦ»ÑΦ»╛τ¿ïτÜäΦ«░σ╜ò
        quiz = QuizHistory.query.filter_by(user_id=student.id, lesson_id=lesson_id).order_by(QuizHistory.completed_at.asc()).first()
        if quiz:
            score = round(quiz.correct_answers / quiz.total_questions * 100, 1) if quiz.total_questions > 0 else 0
            completed_scores.append({
                'student': student,
                'score': score
            })
    # µîëσ╛ùσêåΘÖìσ║ÅµÄÆσ║Å
    completed_scores.sort(key=lambda x: x['score'], reverse=True)

    # τ╗ƒΦ«íΘóÿτ¢«σ╛ùσêåτÄç
    questions = Question.query.filter_by(lesson_id=lesson_id).order_by(Question.question_number).all()
    question_stats = []
    for question in questions:
        user_answers = UserAnswer.query.filter_by(
            lesson_id=lesson_id,
            question_id=question.id
        ).all()
        total_attempts = len(user_answers)
        correct_attempts = len([ua for ua in user_answers if ua.is_correct])
        success_rate = (correct_attempts / total_attempts * 100) if total_attempts > 0 else 0
        question_stats.append({
            'question_number': question.question_number,
            'type': question.type,
            'total_attempts': total_attempts,
            'correct_attempts': correct_attempts,
            'success_rate': round(success_rate, 2),
            'answer': question.answer
        })

    return render_template('admin/students.html', lesson=lesson, completed_scores=completed_scores, not_completed=not_completed, question_stats=question_stats)


@app.route('/admin/lesson/<int:lesson_id>/student/<int:user_id>/reset', methods=['POST'])
@admin_required
def admin_reset_student_lesson_status(lesson_id, user_id):
    """σ░åµîçσ«Üσ¡ªτöƒσ£¿Φ»Ñ lesson τÜäσ«îµêÉτè╢µÇüΘçìτ╜«Σ╕║µ£¬σ«îµêÉπÇé"""
    lesson = Lesson.query.get_or_404(lesson_id)
    user = User.query.get_or_404(user_id)

    quiz_histories = QuizHistory.query.filter_by(
        lesson_id=lesson_id,
        user_id=user_id
    ).all()

    if not quiz_histories:
        flash(f'{user.username} σ╜ôσëìµ▓íµ£ëΦ»ÑΣ╜£Σ╕ÜτÜäσ«îµêÉΦ«░σ╜òπÇé', 'info')
        return redirect(url_for('lesson_students', lesson_id=lesson_id))

    deleted_answers = 0
    deleted_quizzes = 0
    for qh in quiz_histories:
        deleted_answers += UserAnswer.query.filter_by(quiz_history_id=qh.id).delete()
        db.session.delete(qh)
        deleted_quizzes += 1

    db.session.commit()
    flash(
        f'σ╖▓Θçìτ╜« {user.username} σ£¿πÇè{lesson.title}πÇïτÜäΣ╜£Σ╕Üτè╢µÇü∩╝êσêáΘÖñ {deleted_quizzes} µ¥íΣ╜£Σ╕ÜΦ«░σ╜ò∩╝î{deleted_answers} µ¥íτ¡öΘóÿΦ«░σ╜ò∩╝ëπÇé',
        'success'
    )
    return redirect(url_for('lesson_students', lesson_id=lesson_id))


@app.route('/admin/lesson/<int:lesson_id>/question/<int:question_number>/mark_all_correct', methods=['POST'])
@admin_required
def admin_mark_all_question_correct(lesson_id, question_number):
    """
    σ░åµƒÉΘüôΘóÿσ£¿Φ»Ñ lesson Σ╕ïτÜäµëÇµ£ë UserAnswer τ╜«Σ╕║µ¡úτí«∩╝î
    σ╣╢σÉîµ¡ÑΘçìτ«ùµ»ÅΣ╕¬σÅùσ╜▒σôìσ¡ªτöƒ∩╝êQuizHistory∩╝ëτÜä correct_answers∩╝îΣ╗ÄΦÇîµ¢┤µû░µÇ╗σêå/µ¡úτí«τÄçπÇé
    """
    question = Question.query.filter_by(lesson_id=lesson_id, question_number=question_number).first()
    if not question:
        return jsonify({'success': False, 'msg': 'µ£¬µë╛σê░Φ»ÑΘóÿ'}), 404

    user_answers = UserAnswer.query.filter_by(
        lesson_id=lesson_id,
        question_id=question.id
    ).all()

    if not user_answers:
        return jsonify({'success': False, 'msg': 'Φ»ÑΘóÿµÜéµùáτ¡öΘóÿΦ«░σ╜ò∩╝îµùáµ│òτ║áµ¡úπÇé'}), 404

    affected_quiz_ids = set()
    changed_count = 0
    for ua in user_answers:
        if not ua.is_correct:
            ua.is_correct = True
            changed_count += 1
        affected_quiz_ids.add(ua.quiz_history_id)

    # Θçìτ«ùµ»ÅΣ╕¬σÅùσ╜▒σôì QuizHistory τÜä correct_answers
    for qh_id in affected_quiz_ids:
        qh = QuizHistory.query.get(qh_id)
        if not qh:
            continue
        qh.correct_answers = UserAnswer.query.filter_by(
            quiz_history_id=qh_id,
            is_correct=True
        ).count()

    db.session.commit()

    return jsonify({
        'success': True,
        'msg': 'σ╖▓σ░åΦ»ÑΘóÿµáçΦ«░Σ╕║σà¿σæÿµ¡úτí«',
        'question_number': question_number,
        'changed_answers': changed_count,
        'affected_quiz_histories': len(affected_quiz_ids),
    })

# Φ»èµû¡µ¿íσ¥ùΦô¥σ¢╛∩╝êτï¼τ½ïΦ╖»τö▒Σ╕ÄΦí¿∩╝îΣ╕ìσ╜▒σôìτÄ░µ£ëΣ╕Üσèí∩╝ë
from diagnostic.routes import diagnostic_bp
from diagnostic.admin_routes import diagnostic_admin_bp
from diagnostic.billing import billing_bp
app.register_blueprint(diagnostic_bp, url_prefix='/diagnostic')
app.register_blueprint(diagnostic_admin_bp)
app.register_blueprint(billing_bp)

if __name__ == '__main__':
    # init_db()  # µ│¿ΘçèµÄëΦç¬σè¿σê¥σºïσîû∩╝îΘü┐σàìµ»Åµ¼íσÉ»σè¿Θâ╜µ╕àτ⌐║µò░µì«
    with app.app_context():
        import subprocess
        r = subprocess.run(['flask', 'db', 'upgrade'], capture_output=True, text=True, env={**os.environ, 'FLASK_APP': 'app.py'})
        if r.returncode != 0:
            # Φ┐üτº╗σñ▒Φ┤Ñµù╢ stamp σ¢₧σê¥σºïτëêµ£¼σÉÄΘçìΦ»ò∩╝êσñäτÉåΦí¿σ╖▓σ¡ÿσ£¿Σ╜åτëêµ£¼Σ╕ìσÉîµ¡Ñ∩╝ë
            subprocess.run(['flask', 'db', 'stamp', 'b4fefe386c31'], check=False, env={**os.environ, 'FLASK_APP': 'app.py'})
            r = subprocess.run(['flask', 'db', 'upgrade'], capture_output=True, text=True, env={**os.environ, 'FLASK_APP': 'app.py'})
        if r.returncode != 0:
            print('DB upgrade σñ▒Φ┤Ñ:', r.stderr or r.stdout)
            raise SystemExit(1)
        clean_duplicate_quiz_history()  # Φç¬σè¿µ╕àτÉåΘçìσñìτ¡öΘóÿΦ«░σ╜ò
    app.run(debug=True, host='0.0.0.0', port=5000) 
