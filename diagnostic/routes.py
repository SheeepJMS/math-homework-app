# 诊断模块对外路由：/diagnostic/*，独立 cookie 认证
from flask import Blueprint, request, redirect, url_for, render_template, flash, make_response, abort, current_app, jsonify
from datetime import datetime, timedelta
from functools import wraps
import os
import re
import secrets
import json
import random
import math
import statistics
from werkzeug.security import generate_password_hash, check_password_hash


def _points_for_exam(score_scheme_json, num_questions):
    """根据竞赛分段分值计算每题得分。返回 (points_per_question, total_max)。题号 1-based。
    若试卷/竞赛未设置 score_scheme，默认一题一分，满分 = 题数。"""
    if not num_questions:
        return ([], 0)
    # 默认：一题一分，满分 = 题数
    default_pts = [1] * num_questions
    default_max = num_questions
    if not score_scheme_json or not str(score_scheme_json).strip():
        return (default_pts, default_max)
    try:
        scheme = json.loads(score_scheme_json)
    except Exception:
        return (default_pts, default_max)
    if not isinstance(scheme, list) or len(scheme) == 0:
        return (default_pts, default_max)
    points = []
    for i in range(num_questions):
        q_num = i + 1
        p = 1
        for seg in scheme:
            start = seg.get('start', 0)
            end = seg.get('end', 0)
            if start <= q_num <= end:
                p = int(seg.get('points', 1))
                break
        points.append(p)
    total = sum(points)
    # 若解析结果总分为 0，回退为默认一题一分
    if total <= 0:
        return (default_pts, default_max)
    return (points, total)


def _avg_score_per_question_all_students(db, order, finished_ids):
    """计算每题在所有已完成学生中的平均得分率（0-100%）。"""
    from app import DiagAttemptAnswer
    if not order or not finished_ids:
        return [0] * len(order)
    n_finished = len(finished_ids)
    result = []
    for eq in order:
        correct_count = db.session.query(DiagAttemptAnswer).filter(
            DiagAttemptAnswer.attempt_id.in_(finished_ids),
            DiagAttemptAnswer.question_id == eq.question_id,
            DiagAttemptAnswer.is_correct == True,
        ).count()
        result.append(round(100 * correct_count / n_finished, 1))
    return result


def _get_db():
    """使用当前请求的 app 的 db，避免 debug reloader 下 _app_engines KeyError（与 admin_routes 一致）"""
    from flask import current_app
    return current_app.extensions['sqlalchemy']


def _get_db_and_models():
    from flask import current_app
    db = current_app.extensions['sqlalchemy']
    from app import (
        DiagUser, DiagSession, DiagCompetition, DiagExam, DiagQuestion, DiagExamQuestion,
        DiagAttempt, DiagAttemptAnswer, DiagKnowledgePoint, DiagQuestionTag,
        DiagBankQuestion, DiagBankQuestionTag, DiagQuestionBankLink, DiagQuestionPracticeConfig,
        DiagPracticeSet, DiagPracticeSetItem,
    )
    return (db, DiagUser, DiagSession, DiagCompetition, DiagExam, DiagQuestion, DiagExamQuestion,
            DiagAttempt, DiagAttemptAnswer, DiagKnowledgePoint, DiagQuestionTag,
            DiagBankQuestion, DiagBankQuestionTag, DiagQuestionBankLink, DiagQuestionPracticeConfig,
            DiagPracticeSet, DiagPracticeSetItem)

DIAG_COOKIE_NAME = os.environ.get('DIAG_COOKIE_NAME', 'diag_session')
DIAG_SESSION_DAYS = int(os.environ.get('DIAG_SESSION_DAYS', '7'))
RETRY_COOLDOWN_DAYS = 120  # 4 个月，同一试卷两次完成需间隔

diagnostic_bp = Blueprint('diagnostic', __name__, template_folder='../templates/diagnostic')


def _compute_retry_policy(last_finished_at):
    """计算重做冷却策略。last_finished_at 为最近一次 finished 的 finished_at。"""
    if last_finished_at is None:
        return {'can_retry': True, 'next_retry_at': None, 'cooldown_days_remaining': None}
    now = datetime.utcnow()
    delta = now - (last_finished_at if hasattr(last_finished_at, 'date') else last_finished_at)
    days_passed = delta.days if hasattr(delta, 'days') else 0
    if days_passed >= RETRY_COOLDOWN_DAYS:
        return {'can_retry': True, 'next_retry_at': None, 'cooldown_days_remaining': None}
    next_at = last_finished_at + timedelta(days=RETRY_COOLDOWN_DAYS) if hasattr(last_finished_at, '__add__') else now
    remaining = max(0, RETRY_COOLDOWN_DAYS - days_passed)
    return {'can_retry': False, 'next_retry_at': next_at, 'cooldown_days_remaining': remaining}


def _build_exam_card(exam, in_progress_att, last_finished_att, db):
    """构建单份试卷的展示数据：in_progress、last_finished、retry_policy。"""
    exam_id = exam.id
    exam_title = getattr(exam, 'title', None) or 'N/A'
    card = {
        'exam_id': exam_id,
        'exam_title': exam_title,
        'in_progress': None,
        'last_finished': None,
        'retry_policy': {'can_retry': True, 'next_retry_at': None, 'cooldown_days_remaining': None},
    }
    if in_progress_att:
        from app import DiagExamQuestion, DiagAttemptAnswer
        order = db.session.query(DiagExamQuestion).filter_by(exam_id=exam_id).order_by(DiagExamQuestion.q_index).all()
        answers = db.session.query(DiagAttemptAnswer).filter_by(attempt_id=in_progress_att.id).all()
        answered = sum(1 for a in answers if (a.answer or '').strip())
        total = len(order) or 1
        time_sec = round((in_progress_att.total_time_ms or 0) / 1000, 0)
        card['in_progress'] = {
            'attempt_id': in_progress_att.id,
            'answered': answered,
            'total': total,
            'time_sec': time_sec,
        }
        card['status'] = 'in_progress'
    elif last_finished_att:
        st = _attempt_quick_stats(last_finished_att, db)
        fin_at = getattr(last_finished_att, 'finished_at', None)
        total_time_sec = round((last_finished_att.total_time_ms or 0) / 1000, 0)
        card['last_finished'] = {
            'attempt_id': last_finished_att.id,
            'finished_at': fin_at,
            'finished_at_str': fin_at.strftime('%Y-%m-%d') if fin_at and hasattr(fin_at, 'strftime') else 'N/A',
            'score': st['score'],
            'total': st['score_max'],
            'accuracy_percent': st['accuracy_percent'],
            'total_time_sec': total_time_sec,
        }
        card['retry_policy'] = _compute_retry_policy(fin_at)
        card['status'] = 'completed'
    else:
        card['status'] = 'not_started'
    return card


@diagnostic_bp.app_template_filter('format_date')
def format_date(dt):
    """日期格式化为 YYYY-MM-DD，None 返回空字符串。"""
    if dt is None:
        return ''
    if hasattr(dt, 'strftime'):
        return dt.strftime('%Y-%m-%d')
    return str(dt)[:10] if dt else ''


@diagnostic_bp.app_template_filter('format_time_sec')
def format_time_sec(sec):
    """秒数格式化为 '8.2 s' / '206 s'（竞赛风格，统一单位）。"""
    if sec is None:
        return 'N/A'
    try:
        v = float(sec)
    except Exception:
        return 'N/A'
    if v < 0:
        v = 0
    if v >= 100:
        return f"{int(round(v, 0))} s"
    return f"{v:.1f} s"


@diagnostic_bp.app_template_filter('format_percent1')
def format_percent1(val):
    """百分比统一为 1 位小数：20.0%"""
    if val is None:
        return 'N/A'
    try:
        v = float(val)
    except Exception:
        return 'N/A'
    return f"{v:.1f}%"


@diagnostic_bp.app_template_filter('estimate_grade')
def estimate_grade(birth_year):
    """根据出生年份粗略估算年级（仅展示用）。"""
    if birth_year is None:
        return 'N/A'
    try:
        by = int(birth_year)
    except Exception:
        return 'N/A'
    y = datetime.utcnow().year
    age = y - by
    # 经验：6岁≈1年级 → grade = age - 5
    g = age - 5
    if g <= 0:
        return '学前'
    if g >= 13:
        return '12年级+'
    return f'{g}年级'


def require_plan(required_plan='pro', feature_name=None, user=None):
    """订阅/权限预埋：当前不拦截，仅记录未来应被 gate 的功能。"""
    try:
        uname = getattr(user, 'username', None) if user else None
        current_app.logger.info(
            "[paywall] require_plan(%s) feature=%s user=%s -> allow (placeholder)",
            required_plan, feature_name, uname
        )
    except Exception:
        pass
    return True


def _sample_report_mock():
    """生成不依赖数据库的示例报告数据（用于展示模板给客户看）。"""
    total_q = 25
    correct = 18
    blank = 2
    wrong = max(0, total_q - correct - blank)
    total_time_sec = 28 * 60
    avg_time = round(total_time_sec / total_q, 0)
    # 图表数据（示例）
    radar_labels = ['代数', '几何', '数论', '概率', '组合', '函数']
    radar_values = [78, 70, 58, 62, 66, 73]
    line_x = [str(i) for i in range(1, total_q + 1)]
    line_y = [86, 82, 80, 62, 74, 71, 79, 77, 58, 75, 81, 83, 78, 72, 69, 55, 76, 80, 82, 79, 73, 70, 68, 74, 78]
    bar_labels = line_x[:]
    bar_time = [52, 64, 49, 95, 63, 78, 56, 61, 110, 58, 60, 62, 70, 67, 74, 120, 59, 55, 66, 72, 71, 68, 75, 62, 57]
    detail_rows = []
    correct_set = set([1, 2, 3, 5, 6, 7, 8, 10, 11, 12, 14, 17, 18, 19, 20, 22, 24, 25])
    blank_set = set([13, 21])
    for i in range(1, total_q + 1):
        is_blank = i in blank_set
        is_correct = (i in correct_set) and not is_blank
        detail_rows.append({
            'qnum': i,
            'is_blank': is_blank,
            'is_correct': is_correct,
        })
    return {
        'exam_title': 'Gauss 7 2025（示例）',
        'submitted_at_str': datetime.utcnow().strftime('%Y-%m-%d'),
        'user_display_name': '示例学员',
        'total_questions': total_q,
        'correct_count': correct,
        'wrong_count': wrong,
        'blank_count': blank,
        'accuracy_percent': round(100 * correct / total_q, 1),
        'total_time_sec': int(total_time_sec),
        'total_time_min': int(round(total_time_sec / 60, 0)),
        'avg_time_sec': int(avg_time),
        'rank_top_percent': 25,
        'slow_wrong_qnums': [4, 9, 16],
        'practice_summary': {'exists': True, 'count': 10, 'est_minutes': 12},
        'answer_analysis': {
            'fast_wrong_qnums': [9],
            'slow_wrong_qnums': [4, 16],
            'common_errors': [
                {'tag': '读题遗漏', 'count': 3},
                {'tag': '计算失误', 'count': 2},
                {'tag': '概念不清', 'count': 2},
            ],
        },
        'chart': {
            'chart_radar_labels': radar_labels,
            'chart_radar_values': radar_values,
            'chart_line_x': line_x,
            'chart_line_y': line_y,
            'chart_bar_labels': bar_labels,
            'chart_bar_time': bar_time,
            'has_custom_score_scheme': False,
        },
        'detail_rows': detail_rows,
        'kp_weak_top': [
            {'kp_name': '代数（方程与变量）', 'wrong_count': 4, 'n_questions': 8},
            {'kp_name': '概率', 'wrong_count': 3, 'n_questions': 6},
            {'kp_name': '数论', 'wrong_count': 2, 'n_questions': 5},
        ],
    }


@diagnostic_bp.context_processor
def inject_diag_user():
    try:
        user = get_diag_user_from_cookie()
        static_v = os.environ.get('RENDER_GIT_COMMIT') or os.environ.get('GIT_COMMIT') or ''
        static_v = (static_v or '')[:12] or datetime.utcnow().strftime('%Y%m%d%H%M')
        return {
            'user': user,
            'diag_static_v': static_v,
            'diag_require_plan': lambda required_plan='pro', feature_name=None: require_plan(required_plan, feature_name, user),
        }
    except Exception:
        static_v = os.environ.get('RENDER_GIT_COMMIT') or os.environ.get('GIT_COMMIT') or ''
        static_v = (static_v or '')[:12] or datetime.utcnow().strftime('%Y%m%d%H%M')
        return {
            'user': None,
            'diag_static_v': static_v,
            'diag_require_plan': lambda required_plan='pro', feature_name=None: require_plan(required_plan, feature_name, None),
        }


def get_diag_user_from_cookie():
    """从 cookie diag_session 解析 token，返回 DiagUser 或 None。不写 DB。"""
    token = request.cookies.get(DIAG_COOKIE_NAME)
    if not token:
        return None
    db, DiagUser, DiagSession, *_ = _get_db_and_models()
    sess = db.session.query(DiagSession).filter_by(token=token).first()
    if not sess or sess.expires_at < datetime.utcnow():
        return None
    return db.session.get(DiagUser, sess.user_id)


def require_diag_login(f):
    """要求已登录诊断用户，否则重定向到诊断登录页。"""
    @wraps(f)
    def wrapped(*args, **kwargs):
        user = get_diag_user_from_cookie()
        if not user:
            flash('请先登录诊断系统', 'warning')
            return redirect(url_for('diagnostic.login'))
        return f(*args, **kwargs)
    return wrapped


@diagnostic_bp.route('/')
def index():
    user = get_diag_user_from_cookie()
    if user:
        db = _get_db()
        dashboard = _build_dashboard_data(user, db)
        return render_template('diagnostic/dashboard.html', user=user, **dashboard)
    return render_template('diagnostic/index.html')


@diagnostic_bp.route('/api/roadmap', methods=['GET'])
def api_roadmap():
    """GET /diagnostic/api/roadmap — Competition Roadmap data for the logged-in student. Diagnostic-only."""
    user = get_diag_user_from_cookie()
    if not user:
        return jsonify({'error': 'unauthorized'}), 401
    db = _get_db()
    try:
        data = _build_roadmap_data(user, db)
        return jsonify(data)
    except Exception as e:
        current_app.logger.warning('roadmap api error: %s', e)
        return jsonify({'error': 'roadmap_build_failed', 'message': str(e)}), 500


@diagnostic_bp.route('/register', methods=['GET', 'POST'])
def register():
    db, DiagUser, DiagSession, *_ = _get_db_and_models()
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        confirm = request.form.get('confirm_password') or ''
        birth_year_raw = (request.form.get('birth_year') or '').strip()
        school = (request.form.get('school') or '').strip()
        province = (request.form.get('province') or 'BC').strip() or 'BC'
        if not username or not password:
            flash('用户名和密码不能为空', 'error')
            return render_template('diagnostic/register.html', sample_report=_sample_report_mock())
        if password != confirm:
            flash('两次密码不一致', 'error')
            return render_template('diagnostic/register.html', sample_report=_sample_report_mock())
        if db.session.query(DiagUser).filter_by(username=username).first():
            flash('用户名已存在', 'error')
            return render_template('diagnostic/register.html', sample_report=_sample_report_mock())
        birth_year = None
        if birth_year_raw:
            try:
                birth_year = int(birth_year_raw)
                y = datetime.utcnow().year
                if birth_year < 1900 or birth_year > y:
                    birth_year = None
            except Exception:
                birth_year = None
        user = DiagUser(
            username=username,
            password_hash=generate_password_hash(password, method='pbkdf2:sha256'),
            birth_year=birth_year,
            school=school or None,
            province=province or 'BC',
        )
        db.session.add(user)
        db.session.commit()
        flash('注册成功，请登录', 'success')
        return redirect(url_for('diagnostic.login'))
    return render_template('diagnostic/register.html', sample_report=_sample_report_mock())


@diagnostic_bp.route('/login', methods=['GET', 'POST'])
def login():
    db = _get_db()
    from app import DiagUser, DiagSession
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        user = db.session.query(DiagUser).filter_by(username=username).first()
        if not user or not check_password_hash(user.password_hash, password):
            flash('用户名或密码错误', 'error')
            return render_template('diagnostic/login.html', sample_report=_sample_report_mock())
        if not getattr(user, 'is_active', True):
            flash('该账号已被停用，请联系管理员', 'error')
            return render_template('diagnostic/login.html', sample_report=_sample_report_mock())
        token = secrets.token_urlsafe(32)
        expires = datetime.utcnow() + timedelta(days=DIAG_SESSION_DAYS)
        sess = DiagSession(user_id=user.id, token=token, expires_at=expires)
        db.session.add(sess)
        db.session.commit()
        resp = make_response(redirect(url_for('diagnostic.index')))
        resp.set_cookie(DIAG_COOKIE_NAME, token, max_age=DIAG_SESSION_DAYS * 86400, httponly=True, samesite='Lax')
        flash('登录成功', 'success')
        return resp
    return render_template('diagnostic/login.html', sample_report=_sample_report_mock())


@diagnostic_bp.route('/sample-report')
def sample_report():
    """示例报告：用于营销展示模板，不依赖数据库。"""
    user = get_diag_user_from_cookie()
    s = _sample_report_mock()

    # 构造 report.html 所需的完整字段（示例数据）
    total = int(s.get('total_questions') or 0)
    correct = int(s.get('correct_count') or 0)
    blank = int(s.get('blank_count') or 0)
    wrong = max(0, total - correct - blank)
    total_time_sec = int(s.get('total_time_sec') or 0)
    avg_time_sec = int(s.get('avg_time_sec') or (round(total_time_sec / total, 0) if total else 0))
    avg_time_ms = int(avg_time_sec * 1000)

    kp_weak_top = s.get('kp_weak_top') or []
    kp_has_data = True if kp_weak_top else False

    # 逐题详情（示例）：提供原题/解析文本，避免空白
    detail_rows = []
    for r in (s.get('detail_rows') or []):
        qnum = int(r.get('qnum') or 0)
        is_blank = bool(r.get('is_blank'))
        is_correct = bool(r.get('is_correct'))
        speed = '慢' if qnum in (s.get('slow_wrong_qnums') or []) else ('快' if qnum in ((s.get('answer_analysis') or {}).get('fast_wrong_qnums') or []) else '中')
        kp_primary_name = (kp_weak_top[0].get('kp_name') if kp_weak_top else '代数')
        kp_secondary_names = ['概念', '读题', '计算'][:2]
        error_tag = '读题遗漏' if (not is_correct and not is_blank and qnum in (4, 9)) else ('计算失误' if (not is_correct and not is_blank) else 'unknown')
        error_type = None
        if error_tag != 'unknown':
            if '计算' in error_tag:
                error_type = 'arithmetic_error'
            elif '概念' in error_tag:
                error_type = 'concept_misunderstanding'
            elif '建模' in error_tag:
                error_type = 'modeling_error'
            elif '时间' in error_tag:
                error_type = 'time_management'
            else:
                error_type = 'careless_error'
        detail_rows.append({
            'qnum': qnum,
            'points': 1,
            'is_blank': is_blank,
            'is_correct': is_correct,
            'speed': speed,
            'kp_primary_name': kp_primary_name,
            'kp_secondary_names': kp_secondary_names,
            'error_type': error_type,
            'error_tag': error_tag,
            'user_answer': ('—' if is_blank else ('A' if is_correct else 'C')),
            'correct_answer': 'B',
            'time_sec': int((s.get('chart') or {}).get('chart_bar_time', [avg_time_sec] * total)[qnum - 1]) if qnum >= 1 and (s.get('chart') or {}).get('chart_bar_time') else avg_time_sec,
            'avg_time_ms': avg_time_ms,
            'avg_score_percent': int((s.get('chart') or {}).get('chart_line_y', [75] * total)[qnum - 1]) if qnum >= 1 and (s.get('chart') or {}).get('chart_line_y') else 75,
            'stem_image_url': None,
            'stem_text': f'示例题目 {qnum}：这是一道用于展示报告结构的题干文本（可替换为真实题干/截图）。',
            'solution_text': f'示例解析：给出关键思路与步骤（第 {qnum} 题）。',
            'solution_image_url': None,
        })

    # slow_wrong / fast_wrong 用于摘要文案
    slow_wrong = [{'qnum': x} for x in (s.get('slow_wrong_qnums') or [])]
    fast_wrong = [{'qnum': x} for x in ((s.get('answer_analysis') or {}).get('fast_wrong_qnums') or [])]

    ch = s.get('chart') or {}
    kp_radar = []
    for i, lab in enumerate(ch.get('chart_radar_labels') or []):
        try:
            v = float((ch.get('chart_radar_values') or [0] * 10)[i])
        except Exception:
            v = 0
        kp_radar.append({'category': lab, 'value_0to100': v, 'n_questions': 0})
    expert_diag = _compute_expert_diagnosis({
        'total_questions': total,
        'accuracy_percent': s.get('accuracy_percent'),
        'score_percent': s.get('score_percent') or s.get('accuracy_percent'),
        'score_max': total,
        'blank_count': blank,
        'detail_rows': detail_rows,
        'kp_radar': kp_radar,
    })
    from diagnostic.benchmark import get_benchmark_summary
    db = _get_db()
    sample_benchmark_score = 39.0
    benchmark_summary = get_benchmark_summary('gauss7', sample_benchmark_score, db)
    display_rank_top_percent = round(100 - benchmark_summary['percentile_estimate'], 1) if benchmark_summary else None
    return render_template(
        'diagnostic/report.html',
        user=user,
        admin_view=False,
        exam_title=s.get('exam_title'),
        competition_name='N/A',
        submitted_at_str=s.get('submitted_at_str'),
        user_display_name=s.get('user_display_name'),
        # 顶部指标
        has_custom_score_scheme=False,
        score=0,
        score_max=0,
        score_percent=0,
        correct_count=correct,
        total_questions=total,
        blank_count=blank,
        accuracy_percent=s.get('accuracy_percent'),
        total_time_sec=total_time_sec,
        avg_time_sec=avg_time_sec,
        rank_top_percent=s.get('rank_top_percent'),
        # 摘要/练习包
        kp_has_data=kp_has_data,
        kp_weak_top=kp_weak_top,
        slow_wrong=slow_wrong,
        fast_wrong=fast_wrong,
        practice_summary=s.get('practice_summary') or {'exists': True, 'count': 10, 'est_minutes': 12},
        practice_set=None,
        # 图表
        chart_radar_labels=ch.get('chart_radar_labels') or [],
        chart_radar_values=ch.get('chart_radar_values') or [],
        chart_line_x=ch.get('chart_line_x') or [],
        chart_line_y=ch.get('chart_line_y') or [],
        chart_bar_labels=ch.get('chart_bar_labels') or [],
        chart_bar_time=ch.get('chart_bar_time') or [],
        chart_bar_correct=[],
        # 逐题
        detail_rows=detail_rows,
        chart_bar_labels_slow_indices=[],
        expert_diag=expert_diag,
        benchmark_summary=benchmark_summary,
        display_rank_top_percent=display_rank_top_percent,
    )


@diagnostic_bp.route('/billing')
@require_diag_login
def billing_coming_soon():
    """订阅/套餐页（预埋 Stripe 接入点，当前仅占位）。"""
    user = get_diag_user_from_cookie()
    return render_template('diagnostic/billing_coming_soon.html', user=user, title='订阅与套餐')


@diagnostic_bp.route('/legal/terms')
def legal_terms():
    """预留：服务条款页面。"""
    user = get_diag_user_from_cookie()
    return render_template('diagnostic/legal/terms.html', user=user)


@diagnostic_bp.route('/legal/privacy')
def legal_privacy():
    """预留：隐私政策页面。"""
    user = get_diag_user_from_cookie()
    return render_template('diagnostic/legal/privacy.html', user=user)


@diagnostic_bp.route('/legal/data-request')
def legal_data_request():
    """预留：数据删除/导出请求入口。当前占位，不执行删除。"""
    user = get_diag_user_from_cookie()
    return render_template('diagnostic/legal/data_request_placeholder.html', user=user)


@diagnostic_bp.route('/support')
def support_placeholder():
    """预留：帮助/客服入口。DIAG_SHOW_HELP_BUTTON 开启时显示。"""
    user = get_diag_user_from_cookie()
    return render_template('diagnostic/legal/support_placeholder.html', user=user)


@diagnostic_bp.route('/logout')
def logout():
    resp = make_response(redirect(url_for('diagnostic.index')))
    resp.set_cookie(DIAG_COOKIE_NAME, '', max_age=0)
    flash('已退出登录', 'info')
    return resp


@diagnostic_bp.route('/exams')
@require_diag_login
def exams():
    """试卷中心：展示四级树结构 + 待考试卷列表。"""
    db = _get_db()
    user = get_diag_user_from_cookie()
    dashboard = _build_dashboard_data(user, db)
    return render_template('diagnostic/exam_center.html', user=user,
                          exams_grouped=dashboard.get('exams_grouped', []),
                          exam_tree=dashboard.get('exam_tree', []))


@diagnostic_bp.route('/history')
@require_diag_login
def history():
    """重定向到报告中心。"""
    return redirect(url_for('diagnostic.reports'))


@diagnostic_bp.route('/reports')
@require_diag_login
def reports():
    """报告中心：搜索、过滤、分页、delta 对比、同卷历史。"""
    db = _get_db()
    from app import DiagAttempt, DiagExam, DiagCompetition, DiagPracticeSet
    user = get_diag_user_from_cookie()

    q = (request.args.get('q') or '').strip()
    competition_id = request.args.get('competition', type=int)
    exam_id = request.args.get('exam', type=int)
    range_val = request.args.get('range', 'all')  # 7d, 30d, all
    sort_val = request.args.get('sort', 'latest')  # latest, best_accuracy, fastest
    include_in_progress = request.args.get('include_in_progress', '0') == '1'
    page = max(1, request.args.get('page', 1, type=int))
    page_size = min(50, max(10, request.args.get('page_size', 15, type=int)))

    base = db.session.query(DiagAttempt).filter(DiagAttempt.user_id == user.id)
    if not include_in_progress:
        base = base.filter(DiagAttempt.status == 'finished')
    else:
        base = base.filter(DiagAttempt.status.in_(['finished', 'in_progress']))

    cutoff = None
    if range_val == '7d':
        cutoff = datetime.utcnow() - timedelta(days=7)
    elif range_val == '30d':
        cutoff = datetime.utcnow() - timedelta(days=30)
    if cutoff:
        from sqlalchemy import or_
        base = base.filter(
            or_(
                DiagAttempt.finished_at >= cutoff,
                (DiagAttempt.finished_at.is_(None)) & (DiagAttempt.started_at >= cutoff)
            )
        )

    need_join = competition_id or exam_id or q
    if need_join:
        base = base.join(DiagExam, DiagAttempt.exam_id == DiagExam.id).join(
            DiagCompetition, DiagExam.competition_id == DiagCompetition.id)
        if competition_id:
            base = base.filter(DiagExam.competition_id == competition_id)
        if exam_id:
            base = base.filter(DiagAttempt.exam_id == exam_id)
        if q:
            q_like = '%' + q.replace('%', '\\%').replace('_', '\\_') + '%'
            base = base.filter(
                (DiagExam.title.ilike(q_like)) | (DiagCompetition.name.ilike(q_like)) |
                (DiagCompetition.category.ilike(q_like))
            )

    total_count = base.count()
    if sort_val == 'best_accuracy':
        attempts = base.order_by(DiagAttempt.finished_at.desc().nullslast()).all()
        attempts = sorted(attempts, key=lambda a: (-_attempt_quick_stats(a, db)['accuracy_percent'], (a.finished_at or a.started_at or datetime.min).isoformat()), reverse=True)
    elif sort_val == 'fastest':
        attempts = base.order_by(DiagAttempt.finished_at.desc().nullslast()).all()
        attempts = sorted(attempts, key=lambda a: (a.total_time_ms or 999999999, -(a.finished_at or a.started_at or datetime.min).timestamp()))
    else:
        attempts = base.order_by(DiagAttempt.finished_at.desc().nullslast(), DiagAttempt.started_at.desc()).all()

    total_pages = (total_count + page_size - 1) // page_size if total_count else 1
    start = (page - 1) * page_size
    attempts = attempts[start:start + page_size]

    exam_ids = set(a.exam_id for a in attempts)
    prev_by_exam = {}
    exam_history_by_exam = {}
    for att in db.session.query(DiagAttempt).filter(
        DiagAttempt.user_id == user.id,
        DiagAttempt.status == 'finished',
        DiagAttempt.exam_id.in_(exam_ids)
    ).order_by(DiagAttempt.finished_at.desc()).all():
        if att.exam_id not in prev_by_exam:
            prev_by_exam[att.exam_id] = []
        prev_by_exam[att.exam_id].append(att)
        if att.exam_id not in exam_history_by_exam:
            exam_history_by_exam[att.exam_id] = []
        if len(exam_history_by_exam[att.exam_id]) < 10:
            st_h = _attempt_quick_stats(att, db)
            sub_h = getattr(att, 'finished_at', None)
            exam_history_by_exam[att.exam_id].append({
                'attempt_id': att.id,
                'submitted_at_str': sub_h.strftime('%Y-%m-%d %H:%M') if sub_h and hasattr(sub_h, 'strftime') else 'N/A',
                'accuracy_percent': st_h['accuracy_percent'],
                'total_time_sec': round((att.total_time_ms or 0) / 1000, 0),
            })

    items = []
    for att in attempts:
        st = _attempt_quick_stats(att, db)
        sub = getattr(att, 'finished_at', None) or getattr(att, 'started_at', None)
        exam = att.exam
        comp = getattr(exam, 'competition', None) if exam else None
        comp_name = (getattr(comp, 'name_cn', None) or getattr(comp, 'category', None) or (comp.name if comp else None)) or 'N/A'

        delta = None
        prev_list = prev_by_exam.get(att.exam_id) or []
        prev_candidates = [p for p in prev_list if p.id != att.id and (p.finished_at or datetime.min) < (sub or datetime.max)]
        prev_same = max(prev_candidates, key=lambda p: p.finished_at or datetime.min) if prev_candidates else None
        if prev_same and att.status == 'finished':
            prev_st = _attempt_quick_stats(prev_same, db)
            delta = {
                'accuracy_delta': round(st['accuracy_percent'] - prev_st['accuracy_percent'], 1),
                'time_delta': round((att.total_time_ms or 0) / 1000 - (prev_same.total_time_ms or 0) / 1000, 0),
            }

        ps = att.practice_sets[-1] if att.practice_sets else None
        practice_info = {'exists': ps is not None, 'practice_set_id': ps.id if ps else None}

        exam_title = getattr(exam, 'title', None) or 'N/A'
        if att.status != 'finished':
            exam_title += ' (进行中)'

        exam_history = exam_history_by_exam.get(att.exam_id) or []
        items.append({
            'attempt_id': att.id,
            'exam_id': att.exam_id,
            'exam_title': exam_title,
            'competition_name': comp_name,
            'submitted_at': sub,
            'submitted_at_str': sub.strftime('%Y-%m-%d %H:%M') if sub and hasattr(sub, 'strftime') else 'N/A',
            'score': st['score'],
            'total': st['score_max'],
            'accuracy_percent': st['accuracy_percent'],
            'total_time_sec': round((att.total_time_ms or 0) / 1000, 0),
            'delta_vs_prev': delta,
            'practice': practice_info,
            'status': att.status,
            'exam_history': exam_history[:5],
        })

    competitions = db.session.query(DiagCompetition).order_by(DiagCompetition.id).all()
    exams_by_comp = {}
    for c in competitions:
        exams_by_comp[c.id] = db.session.query(DiagExam).filter_by(competition_id=c.id, is_published=True).order_by(DiagExam.created_at.desc()).all()

    reports_view = {
        'items': items,
        'pagination': {
            'page': page,
            'page_size': page_size,
            'total': total_count,
            'total_pages': total_pages,
            'has_next': page < total_pages,
            'has_prev': page > 1,
        },
        'filters': {
            'q': q,
            'competition': competition_id,
            'exam': exam_id,
            'range': range_val,
            'sort': sort_val,
            'include_in_progress': include_in_progress,
        },
        'competitions': competitions,
        'exams_by_comp': exams_by_comp,
    }
    return render_template('diagnostic/report_center.html', reports_view=reports_view, user=user)


@diagnostic_bp.route('/exams/<int:exam_id>/start', methods=['GET', 'POST'])
@require_diag_login
def start_exam(exam_id):
    db = _get_db()
    from app import DiagExam, DiagExamQuestion, DiagAttempt, DiagAttemptAnswer
    exam = db.session.get(DiagExam, exam_id)
    if not exam:
        abort(404)
    if not exam.is_published:
        flash('该试卷未发布', 'error')
        return redirect(url_for('diagnostic.exams'))
    user = get_diag_user_from_cookie()

    in_progress = db.session.query(DiagAttempt).filter_by(
        user_id=user.id, exam_id=exam_id, status='in_progress'
    ).first()
    if in_progress:
        return redirect(url_for('diagnostic.attempt', attempt_id=in_progress.id))

    last_finished = db.session.query(DiagAttempt).filter_by(
        user_id=user.id, exam_id=exam_id, status='finished'
    ).order_by(DiagAttempt.finished_at.desc()).first()
    retry_policy = _compute_retry_policy(last_finished.finished_at if last_finished else None)
    if not retry_policy['can_retry'] and last_finished:
        next_str = retry_policy['next_retry_at'].strftime('%Y-%m-%d') if retry_policy.get('next_retry_at') and hasattr(retry_policy['next_retry_at'], 'strftime') else 'N/A'
        flash('距离上次完成不足 4 个月，可在 %s 后重做。每份试卷每 4 个月可重做一次。' % next_str, 'warning')
        return redirect(url_for('diagnostic.report', attempt_id=last_finished.id))

    if request.method == 'POST':
        # 创建 attempt 和空白 answer 记录
        order = db.session.query(DiagExamQuestion).filter_by(exam_id=exam_id).order_by(DiagExamQuestion.q_index).all()
        if not order:
            flash('该试卷暂无题目', 'error')
            return redirect(url_for('diagnostic.exams'))
        attempt = DiagAttempt(user_id=user.id, exam_id=exam_id, status='in_progress')
        db.session.add(attempt)
        db.session.flush()
        for eq in order:
            aa = DiagAttemptAnswer(attempt_id=attempt.id, question_id=eq.question_id)
            db.session.add(aa)
        db.session.commit()
        return redirect(url_for('diagnostic.attempt', attempt_id=attempt.id, q=0))
    return render_template('diagnostic/start_exam.html', exam=exam)


@diagnostic_bp.route('/attempt/<int:attempt_id>', methods=['GET', 'POST'])
@require_diag_login
def attempt(attempt_id):
    db = _get_db()
    from app import DiagAttempt, DiagAttemptAnswer, DiagExam, DiagExamQuestion, DiagQuestion
    att = db.session.get(DiagAttempt, attempt_id)
    if not att:
        abort(404)
    user = get_diag_user_from_cookie()
    if att.user_id != user.id:
        flash('无权访问该答题记录', 'error')
        return redirect(url_for('diagnostic.exams'))
    if att.status != 'in_progress':
        return redirect(url_for('diagnostic.report', attempt_id=attempt_id))

    order = db.session.query(DiagExamQuestion).filter_by(exam_id=att.exam_id).order_by(DiagExamQuestion.q_index).all()
    if not order:
        flash('试卷无题目', 'error')
        return redirect(url_for('diagnostic.exams'))

    q_index = request.args.get('q', 0, type=int)
    if q_index < 0:
        q_index = 0
    if q_index >= len(order):
        q_index = len(order) - 1

    current_eq = order[q_index]
    question = db.session.get(DiagQuestion, current_eq.question_id)
    answer_rec = db.session.query(DiagAttemptAnswer).filter_by(attempt_id=attempt_id, question_id=question.id).first()

    if request.method == 'POST':
        action = request.form.get('action', 'next')
        answer_val = request.form.get('answer', '').strip()
        time_spent_ms = request.form.get('time_spent_ms', type=int) or 0
        if answer_rec is not None:
            answer_rec.answer = answer_val if answer_val else None
            answer_rec.time_spent_ms = (answer_rec.time_spent_ms or 0) + time_spent_ms
            answer_rec.updated_at = datetime.utcnow()
        att.total_time_ms = (att.total_time_ms or 0) + time_spent_ms
        db.session.commit()

        if action == 'submit':
            att.status = 'finished'
            att.finished_at = datetime.utcnow()
            _grade_attempt(attempt_id)
            _build_practice_set(attempt_id)
            db.session.commit()
            return redirect(url_for('diagnostic.report', attempt_id=attempt_id))
        if action == 'next':
            next_i = min(q_index + 1, len(order) - 1)
            return redirect(url_for('diagnostic.attempt', attempt_id=attempt_id, q=next_i))
        if action == 'prev':
            prev_i = max(q_index - 1, 0)
            return redirect(url_for('diagnostic.attempt', attempt_id=attempt_id, q=prev_i))

    choices = []
    if question.choices_json:
        try:
            raw = json.loads(question.choices_json)
            if isinstance(raw, dict):
                choices = [{'key': k, 'text': v} for k, v in raw.items()]
            elif isinstance(raw, list):
                choices = raw
        except Exception:
            pass
    if not choices:
        choices = [{'key': c, 'text': c} for c in ('A', 'B', 'C', 'D', 'E')]

    answers_map = {}
    for aa in db.session.query(DiagAttemptAnswer).filter_by(attempt_id=attempt_id).all():
        answers_map[aa.question_id] = bool((aa.answer or '').strip())

    return render_template(
        'diagnostic/attempt.html',
        attempt=att,
        exam=att.exam,
        order=order,
        question=question,
        q_index=q_index,
        total=len(order),
        answer_rec=answer_rec,
        choices=choices,
        answers_map=answers_map,
    )


def _grade_attempt(attempt_id):
    db = _get_db()
    from app import DiagAttempt, DiagAttemptAnswer, DiagQuestion, DiagExamQuestion, DiagQuestionAnswer
    att = db.session.get(DiagAttempt, attempt_id)
    if not att:
        return
    answers = db.session.query(DiagAttemptAnswer).filter_by(attempt_id=attempt_id).all()
    qidx_map = {}
    for eq in db.session.query(DiagExamQuestion).filter_by(exam_id=att.exam_id).all():
        qidx_map[eq.question_id] = eq.q_index
    imported = {r.q_index: r for r in db.session.query(DiagQuestionAnswer).filter_by(exam_id=att.exam_id).all()}
    for aa in answers:
        q = db.session.get(DiagQuestion, aa.question_id)
        q_index = qidx_map.get(aa.question_id)
        imp = imported.get(q_index) if q_index is not None else None
        key = None
        if imp and imp.correct_answer:
            key = (imp.correct_answer or '').strip().upper()
        elif q:
            key = (q.answer_key or '').strip().upper()
        ans = (aa.answer or '').strip().upper()
        aa.is_correct = (key == ans) if key else None


def _build_practice_set(attempt_id):
    db = _get_db()
    from app import (
        DiagAttempt, DiagAttemptAnswer, DiagExamQuestion, DiagQuestionPracticeItem,
        DiagExamQuestionPracticeConfig, DiagPracticeSet, DiagPracticeSetItem,
    )
    from sqlalchemy.sql import func
    att = db.session.get(DiagAttempt, attempt_id)
    if not att:
        return
    wrong_question_ids = [
        aa.question_id for aa in db.session.query(DiagAttemptAnswer).filter_by(attempt_id=attempt_id, is_correct=False).all()
        if aa.is_correct is False
    ]
    if not wrong_question_ids:
        return
    ps = DiagPracticeSet(user_id=att.user_id, attempt_id=att.id)
    db.session.add(ps)
    db.session.flush()
    seen = set()
    idx = 0
    qid_to_qindex = {}
    for eq in db.session.query(DiagExamQuestion).filter_by(exam_id=att.exam_id).all():
        qid_to_qindex[eq.question_id] = eq.q_index

    for qid in wrong_question_ids:
        q_index = qid_to_qindex.get(qid)
        csv_items = []
        if q_index is not None:
            csv_items = db.session.query(DiagQuestionPracticeItem).filter_by(
                exam_id=att.exam_id, q_index=q_index
            ).order_by(DiagQuestionPracticeItem.item_index).all()
        if csv_items:
            cfg = db.session.query(DiagExamQuestionPracticeConfig).filter_by(
                exam_id=att.exam_id, q_index=q_index
            ).first()
            count = cfg.practice_count_default if cfg else 3
            count = min(count, len(csv_items))
            sample = random.sample(csv_items, count)
            for pi in sample:
                key = ('csv_practice', pi.id)
                if key not in seen:
                    seen.add(key)
                    db.session.add(DiagPracticeSetItem(
                        practice_set_id=ps.id, source_type='csv_practice',
                        source_question_id=pi.id, q_index=idx
                    ))
                    idx += 1


def _attempt_quick_stats(att, db):
    """计算单次 attempt 的得分/正确率/耗时。用于 dashboard。"""
    from app import DiagAttemptAnswer, DiagExamQuestion, DiagQuestion
    exam = att.exam
    competition = getattr(exam, 'competition', None) if exam else None
    order = db.session.query(DiagExamQuestion).filter_by(exam_id=att.exam_id).order_by(DiagExamQuestion.q_index).all()
    answers = db.session.query(DiagAttemptAnswer).filter_by(attempt_id=att.id).all()
    answers_dict = {aa.question_id: aa for aa in answers}
    total = len(order) or 1
    score_scheme = getattr(competition, 'score_scheme', None) if competition else None
    blank_bonus = int(getattr(competition, 'blank_bonus', 0) or 0) if competition else 0
    points_per_question, score_max = _points_for_exam(score_scheme, total)
    if not score_scheme or not str(score_scheme).strip():
        score_max = total
        points_per_question = [1] * total
    score_earned = sum(
        points_per_question[i] for i in range(total)
        if answers_dict.get(order[i].question_id) and answers_dict[order[i].question_id].is_correct is True
    )
    blank_count = sum(1 for i in range(total) if not answers_dict.get(order[i].question_id) or not ((answers_dict[order[i].question_id].answer or '').strip()))
    score_earned += blank_count * blank_bonus
    correct_count = sum(1 for aa in answers if aa.is_correct is True)
    accuracy_percent = round(100 * correct_count / total, 1) if total else 0
    total_time_ms = att.total_time_ms or 0
    avg_time_sec = round(total_time_ms / 1000 / total, 1) if total else 0
    return {'score': score_earned, 'score_max': score_max, 'accuracy_percent': accuracy_percent, 'total': total, 'avg_time_sec': avg_time_sec}


def _build_exam_tree(competitions, in_progress_by_exam, last_finished_by_exam, db):
    """构建 Subject -> Category -> Contest -> Year 四级树结构，年份行含 exam_card。"""
    from app import DiagExam
    tree = []
    seen_subjects = {}
    for comp in competitions:
        sub = getattr(comp, 'subject', None) or '未分类'
        cat = getattr(comp, 'category', None) or '未分类'
        contest = getattr(comp, 'name_cn', None) or getattr(comp, 'name', None) or comp.name or 'N/A'
        exams = db.session.query(DiagExam).filter_by(competition_id=comp.id, is_published=True).order_by(DiagExam.year.desc().nullslast(), DiagExam.created_at.desc()).all()
        if not exams:
            continue
        sub_node = seen_subjects.get(sub)
        if sub_node is None:
            sub_node = {'subject': sub, 'categories': [], '_cats': {}}
            seen_subjects[sub] = sub_node
            tree.append(sub_node)
        cat_node = sub_node['_cats'].get(cat)
        if cat_node is None:
            cat_node = {'category': cat, 'contests': [], '_contests': {}}
            sub_node['_cats'][cat] = cat_node
            sub_node['categories'].append(cat_node)
        contest_node = cat_node['_contests'].get(contest)
        if contest_node is None:
            contest_node = {'contest': contest, 'years': []}
            cat_node['_contests'][contest] = contest_node
            cat_node['contests'].append(contest_node)
        for exam in exams:
            card = _build_exam_card(exam, in_progress_by_exam.get(exam.id), last_finished_by_exam.get(exam.id), db)
            yr = {
                'exam_id': exam.id, 'exam_title': exam.title, 'year': exam.year,
                'status': card['status'],
                'last_attempt_id': card['last_finished']['attempt_id'] if card.get('last_finished') else None,
                'in_progress_attempt_id': card['in_progress']['attempt_id'] if card.get('in_progress') else None,
                'in_progress': card.get('in_progress'),
                'last_finished': card.get('last_finished'),
                'retry_policy': card.get('retry_policy', {}),
            }
            contest_node['years'].append(yr)
    for s in tree:
        del s['_cats']
    for s in tree:
        for c in s['categories']:
            del c['_contests']
    return tree


def _build_roadmap_data(user, db):
    """Build Competition Roadmap JSON for GET /diagnostic/api/roadmap. Uses existing attempts + contest catalog."""
    from app import DiagAttempt, DiagExam, DiagCompetition
    from diagnostic.roadmap_config import (
        PATH_CANADA, PATH_AMC,
        get_catalog_by_key, get_sequence_for_path, infer_contest_key,
        grade_eligible, months_near, CONTEST_CATALOG,
        AIME_AMC10_THRESHOLD, AIME_AMC12_THRESHOLD,
        get_corresponding_amc,
    )
    as_of = datetime.utcnow()
    # Infer grade from birth_year (North America: grade 1 ≈ age 6–7)
    grade = None
    if getattr(user, 'birth_year', None) is not None:
        try:
            age = as_of.year - int(user.birth_year)
            if 5 <= age <= 22:
                grade = age - 6  # grade 1 at 7 yo
                if grade < 1:
                    grade = 1
                if grade > 12:
                    grade = 12
        except (TypeError, ValueError):
            pass

    # Finished attempts with exam + competition
    finished = db.session.query(DiagAttempt).filter(
        DiagAttempt.user_id == user.id,
        DiagAttempt.status == 'finished'
    ).order_by(DiagAttempt.finished_at.desc()).all()

    # Map attempt -> (contest_key, score, date)
    attempt_contest_scores = []
    for att in finished:
        exam = getattr(att, 'exam', None)
        if not exam:
            continue
        comp = getattr(exam, 'competition', None)
        comp_name = getattr(comp, 'name', None) if comp else None
        exam_title = getattr(exam, 'title', None) or ''
        ckey = infer_contest_key(comp_name, exam_title)
        if not ckey:
            continue
        st = _attempt_quick_stats(att, db)
        fin_at = getattr(att, 'finished_at', None) or getattr(att, 'started_at', None)
        attempt_contest_scores.append({
            'contest_key': ckey,
            'score': st['score'],
            'score_max': st['score_max'],
            'finished_at': fin_at,
        })

    catalog = get_catalog_by_key()

    def build_path(path_id):
        sequence = get_sequence_for_path(path_id)
        if not sequence:
            return {
                'sequence': [],
                'completed': [],
                'current_stage': None,
                'next_target': None,
                'recommended_practice': [],
                'training_path': [],
                'confidence': 'low',
            }
        completed = list(dict.fromkeys([
            a['contest_key'] for a in attempt_contest_scores
            if a['contest_key'] in sequence
        ]))
        # Keep order of first occurrence (most recent per contest)
        completed_ordered = [c for c in sequence if c in completed]
        current_stage = completed_ordered[-1] if completed_ordered else None
        # Next target: first in sequence after current_stage that is grade-eligible; prefer season-near
        candidates = []
        for ckey in sequence:
            if ckey == current_stage:
                continue
            if current_stage and sequence.index(ckey) <= sequence.index(current_stage):
                continue
            if not grade_eligible(ckey, grade):
                continue
            candidates.append(ckey)
        next_target = None
        if candidates:
            # Prefer contest whose month is within next 0–3 months
            for c in candidates:
                if months_near(c, as_of, 3):
                    next_target = c
                    break
            if not next_target:
                next_target = candidates[0]
        elif not current_stage:
            # No completion yet: first grade-eligible in sequence
            for c in sequence:
                if grade_eligible(c, grade):
                    next_target = c
                    break

        # AMC 路径不再独立给“下一目标”，仅用于展示对应 AMC 水平；主下一目标只来自 Waterloo
        if path_id == PATH_AMC:
            next_target = None
            next_target_month_name = None
            month_num = None

        # AIME override for AMC path (only when we still compute AMC next_target; now disabled above)
        if path_id == PATH_AMC and sequence == get_sequence_for_path(PATH_AMC) and next_target:
            cutoff_12m = as_of - timedelta(days=365)
            for a in attempt_contest_scores:
                if a['contest_key'] not in ('AMC10', 'AMC12') or (a.get('finished_at') and a['finished_at'] < cutoff_12m):
                    continue
                if a['contest_key'] == 'AMC10' and a.get('score', 0) >= AIME_AMC10_THRESHOLD:
                    next_target = 'AIME'
                    break
                if a['contest_key'] == 'AMC12' and a.get('score', 0) >= AIME_AMC12_THRESHOLD:
                    next_target = 'AIME'
                    break

        # Recommended practice: max 3 per path (labels + query for 试卷中心)
        recommended_practice = []
        if next_target:
            c = catalog.get(next_target)
            if c:
                display_name = c.get('display_name', next_target)
                recommended_practice.append({
                    'label': display_name + ' 近年真题',
                    'contest': next_target,
                    'search_query': display_name,
                    'years': 5,
                })
        for ckey in reversed(sequence):
            if ckey == next_target or len(recommended_practice) >= 3:
                continue
            if ckey in completed_ordered and ckey not in [p['contest'] for p in recommended_practice]:
                c = catalog.get(ckey)
                if c:
                    display_name = c.get('display_name', ckey)
                    recommended_practice.append({
                        'label': display_name + ' 巩固',
                        'contest': ckey,
                        'search_query': display_name,
                        'years': 3,
                    })
        recommended_practice = recommended_practice[:3]

        # Training path bullets (3–5)
        training_path = []
        if next_target:
            c = catalog.get(next_target)
            name = c.get('display_name', next_target) if c else next_target
            training_path.append('下一步目标：' + name)
        training_path.append('按年级与赛历选择下一场竞赛，保持节奏练习。')
        training_path.append('完成试卷后可在报告中心查看薄弱知识点。')
        if not grade:
            training_path.append('填写出生年份后可获得更精准的年级推荐。')
        training_path = training_path[:5]

        confidence = 'high' if (grade is not None and attempt_contest_scores) else ('medium' if grade is not None else 'low')

        month_num = (catalog.get(next_target, {}).get('months') or [None])[0] if next_target else None
        month_names = ('', '一月', '二月', '三月', '四月', '五月', '六月', '七月', '八月', '九月', '十月', '十一月', '十二月')
        next_target_month_name = month_names[month_num] if isinstance(month_num, int) and 1 <= month_num <= 12 else None

        return {
            'sequence': [{'contest_key': k, 'display_name': catalog.get(k, {}).get('display_name', k)} for k in sequence],
            'completed': completed_ordered,
            'current_stage': current_stage,
            'next_target': next_target,
            'next_target_month': month_num,
            'next_target_month_name': next_target_month_name,
            'recommended_practice': recommended_practice,
            'training_path': training_path,
            'confidence': confidence,
        }

    paths = {
        PATH_CANADA: build_path(PATH_CANADA),
        PATH_AMC: build_path(PATH_AMC),
    }
    # 单目标逻辑：仅 Waterloo 提供“下一目标”；AMC 只作“对应 AMC 水平”展示
    canada = paths[PATH_CANADA]
    next_key = canada.get('current_stage') or canada.get('next_target')
    corresponding_amc_key = get_corresponding_amc(next_key)
    corresponding_amc_cfg = catalog.get(corresponding_amc_key, {})
    canada['corresponding_amc_level'] = corresponding_amc_key
    canada['corresponding_amc_display_name'] = corresponding_amc_cfg.get('display_name', corresponding_amc_key)

    # 推荐理由（一句或两句）
    if canada.get('next_target'):
        canada['recommendation_reason'] = (
            '当前阶段更适合先完成 Waterloo 路线基础准备。'
            '对应 AMC 水平为 %s，可作为补充训练方向。' % canada['corresponding_amc_display_name']
        )
    elif next_key:
        canada['recommendation_reason'] = (
            '你已完成当前阶段，建议巩固后再进阶。'
            '对应 AMC 水平为 %s，可作为补充训练方向。' % canada['corresponding_amc_display_name']
        )
    else:
        canada['recommendation_reason'] = (
            '根据当前年级与赛历，建议从 Waterloo 路线入门。'
            '完成试卷后系统将为你推荐下一阶段目标。'
        )

    # 训练建议（短句列表）
    training_suggestions = []
    if canada.get('next_target'):
        next_name = catalog.get(canada['next_target'], {}).get('display_name', canada['next_target'])
        training_suggestions.append('优先完成 %s 基础卷' % next_name)
        training_suggestions.append('再做 2 套近年真题巩固')
    else:
        training_suggestions.append('建议继续当前阶段练习')
    training_suggestions.append('同步强化报告中的薄弱知识点')
    if not grade:
        training_suggestions.append('填写出生年份后可获得更精准的年级推荐')
    canada['training_suggestions'] = training_suggestions[:4]

    # 推荐练习：Canada 已有最多 3 条；可补一条对应 AMC 补充（总不超过 3 条，或保持 3+1 共 4 条展示）
    rp = canada.get('recommended_practice') or []
    amc_label = canada['corresponding_amc_display_name'] + ' 补充训练'
    if len(rp) < 3 and amc_label not in [p.get('label') for p in rp]:
        rp.append({
            'label': amc_label,
            'contest': corresponding_amc_key,
            'search_query': canada['corresponding_amc_display_name'],
            'type': '补充',
        })
    canada['recommended_practice'] = rp[:3]

    current_app.logger.info(
        'roadmap built user_id=%s grade=%s waterloo_next=%s amc_level=%s',
        user.id, grade,
        canada.get('next_target'),
        corresponding_amc_key,
    )
    return {
        'student_grade': grade,
        'grade_missing_hint': grade is None,
        'as_of_date': as_of.isoformat() + 'Z',
        'paths': paths,
    }


def _build_dashboard_data(user, db):
    """组装 dashboard 数据：指标卡、趋势、弱点、最近报告、试卷分组。"""
    from sqlalchemy import func
    from app import (
        DiagAttempt, DiagAttemptAnswer, DiagExam, DiagExamQuestion, DiagCompetition,
        DiagQuestion, DiagQuestionKp, DiagKnowledgePoint, DiagPracticeSet, DiagPracticeSetItem,
    )
    user_display_name = getattr(user, 'username', None) or 'N/A'
    cutoff_30d = datetime.utcnow() - timedelta(days=30)

    # 最近 6 次完成记录（用于趋势）
    finished = db.session.query(DiagAttempt).filter(
        DiagAttempt.user_id == user.id,
        DiagAttempt.status == 'finished'
    ).order_by(DiagAttempt.finished_at.desc()).limit(10).all()

    last_attempt = None
    last_submitted = None
    trend = []
    stats_30d = None
    recent_reports = []
    weak_kps = []
    hero = {}
    chart_bar_labels = []
    chart_bar_time = []
    chart_bar_slow_indices = []

    in_progress_att = db.session.query(DiagAttempt).filter(
        DiagAttempt.user_id == user.id,
        DiagAttempt.status == 'in_progress'
    ).order_by(DiagAttempt.started_at.desc()).first()

    if finished:
        last = finished[0]
        st = _attempt_quick_stats(last, db)
        submitted = getattr(last, 'finished_at', None) or getattr(last, 'started_at', None)
        last_attempt = {
            'exam_title': getattr(last.exam, 'title', None) or 'N/A',
            'submitted_at': submitted,
            'submitted_at_str': submitted.strftime('%Y-%m-%d %H:%M') if submitted and hasattr(submitted, 'strftime') else 'N/A',
            'score': st['score'], 'score_max': st['score_max'], 'accuracy_percent': st['accuracy_percent'],
        }
        last_submitted = submitted
        for i, att in enumerate(finished[:6]):
            st = _attempt_quick_stats(att, db)
            trend.append({'label': '第%d次' % (i + 1), 'accuracy_percent': st['accuracy_percent']})
        trend.reverse()
        for att in finished[:5]:
            st = _attempt_quick_stats(att, db)
            sub = getattr(att, 'finished_at', None) or getattr(att, 'started_at', None)
            total_time_sec = round((att.total_time_ms or 0) / 1000, 0)
            ps = att.practice_sets[-1] if att.practice_sets else None
            recent_reports.append({
                'attempt_id': att.id,
                'exam_title': getattr(att.exam, 'title', None) or 'N/A',
                'submitted_at': sub,
                'submitted_at_str': sub.strftime('%Y-%m-%d %H:%M') if sub and hasattr(sub, 'strftime') else 'N/A',
                'score': st['score'], 'score_max': st['score_max'], 'accuracy_percent': st['accuracy_percent'],
                'total_time_sec': total_time_sec,
                'practice_set_id': ps.id if ps else None,
            })

        finished_30d_all = db.session.query(DiagAttempt).filter(
            DiagAttempt.user_id == user.id,
            DiagAttempt.status == 'finished',
            DiagAttempt.finished_at >= cutoff_30d
        ).order_by(DiagAttempt.finished_at.desc()).all()
        cutoff_60d = datetime.utcnow() - timedelta(days=60)
        finished_prev_30d = db.session.query(DiagAttempt).filter(
            DiagAttempt.user_id == user.id,
            DiagAttempt.status == 'finished',
            DiagAttempt.finished_at >= cutoff_60d,
            DiagAttempt.finished_at < cutoff_30d
        ).all()
        if finished_30d_all:
            acc_sum = sum(_attempt_quick_stats(a, db)['accuracy_percent'] for a in finished_30d_all)
            time_sum = sum(_attempt_quick_stats(a, db)['avg_time_sec'] * _attempt_quick_stats(a, db)['total'] for a in finished_30d_all)
            total_q = sum(_attempt_quick_stats(a, db)['total'] for a in finished_30d_all)
            avg_acc = round(acc_sum / len(finished_30d_all), 1)
            avg_time = round(time_sum / total_q, 1) if total_q else 0
            acc_trend = 0
            if finished_prev_30d:
                prev_acc = sum(_attempt_quick_stats(a, db)['accuracy_percent'] for a in finished_prev_30d) / len(finished_prev_30d)
                acc_trend = round(avg_acc - prev_acc, 1)
            stats_30d = {
                'avg_accuracy_percent': avg_acc,
                'avg_time_per_q_sec': avg_time,
                'attempts_count': len(finished_30d_all),
                'accuracy_trend': acc_trend,
            }

        kp_wrong = {}
        kp_total = {}
        imported_kp_by_exam = {}
        for att in finished[:5]:
            if att.exam_id not in imported_kp_by_exam:
                imported_kp_by_exam[att.exam_id] = {r.q_index: r for r in db.session.query(DiagQuestionKp).filter_by(exam_id=att.exam_id).all()}
            kp_map = imported_kp_by_exam[att.exam_id]
            order = db.session.query(DiagExamQuestion).filter_by(exam_id=att.exam_id).order_by(DiagExamQuestion.q_index).all()
            for eq in order:
                kp_row = kp_map.get(eq.q_index)
                kp_name = (kp_row.kp_primary or 'N/A') if kp_row and kp_row.kp_primary else None
                if kp_name:
                    kp_total[kp_name] = kp_total.get(kp_name, 0) + 1
            qid_to_qindex = {eq.question_id: eq.q_index for eq in order}
            answers = db.session.query(DiagAttemptAnswer).filter_by(attempt_id=att.id, is_correct=False).all()
            for aa in answers:
                if aa.is_correct is False:
                    q_index = qid_to_qindex.get(aa.question_id)
                    kp_row = kp_map.get(q_index) if q_index is not None else None
                    kp_name = (kp_row.kp_primary or 'N/A') if kp_row and kp_row.kp_primary else None
                    if kp_name:
                        kp_wrong[kp_name] = kp_wrong.get(kp_name, 0) + 1
        weak_kps = sorted([
            {'kp_name': k, 'wrong_count': kp_wrong.get(k, 0), 'n_questions': kp_total.get(k, 1)}
            for k in set(kp_wrong.keys()) | set(kp_total.keys())
        ], key=lambda x: -x['wrong_count'])[:3]

        last = finished[0]
        order = db.session.query(DiagExamQuestion).filter_by(exam_id=last.exam_id).order_by(DiagExamQuestion.q_index).all()
        answers_map = {aa.question_id: aa for aa in db.session.query(DiagAttemptAnswer).filter_by(attempt_id=last.id).all()}
        q_times = []
        for eq in order:
            aa = answers_map.get(eq.question_id)
            ms = (aa.time_spent_ms or 0) if aa else 0
            q_times.append((len(q_times) + 1, round(ms / 1000, 1)))
        chart_bar_labels = ['#%d' % i for i, _ in q_times]
        chart_bar_time = [t for _, t in q_times]
        sorted_by_time = sorted(enumerate(q_times), key=lambda x: -x[1][1])
        chart_bar_slow_indices = [i for i, _ in sorted_by_time[:3]]

    competitions = db.session.query(DiagCompetition).order_by(DiagCompetition.id).all()
    all_attempts = db.session.query(DiagAttempt).filter(DiagAttempt.user_id == user.id).order_by(DiagAttempt.finished_at.desc().nullslast(), DiagAttempt.started_at.desc()).all()
    in_progress_by_exam = {}
    last_finished_by_exam = {}
    for att in all_attempts:
        if att.status == 'in_progress' and att.exam_id not in in_progress_by_exam:
            in_progress_by_exam[att.exam_id] = att
        if att.status == 'finished' and att.exam_id not in last_finished_by_exam:
            last_finished_by_exam[att.exam_id] = att
    last_by_exam = {}
    for att in all_attempts:
        if att.exam_id not in last_by_exam:
            last_by_exam[att.exam_id] = att

    # 首页“开始新试卷”三层结构：竞赛大类(category) -> 具体竞赛(contest) -> 年份试卷
    from collections import OrderedDict
    grouped = OrderedDict()  # {category_name: OrderedDict({contest_name: [exam_cards]})}
    for comp in competitions:
        exams = db.session.query(DiagExam).filter_by(
            competition_id=comp.id, is_published=True
        ).order_by(
            DiagExam.year.desc().nullslast(), DiagExam.created_at.desc()
        ).all()
        if not exams:
            continue
        comp_exams = []
        for exam in exams:
            card = _build_exam_card(exam, in_progress_by_exam.get(exam.id), last_finished_by_exam.get(exam.id), db)
            comp_exams.append(card)
        if not comp_exams:
            continue
        category_name = (getattr(comp, 'category', None) or '').strip() or '未分类'
        contest_name = (getattr(comp, 'name_cn', None) or '').strip() or (comp.name or 'N/A')
        if category_name not in grouped:
            grouped[category_name] = OrderedDict()
        grouped[category_name][contest_name] = comp_exams

    exams_grouped = []
    for category_name, contests in grouped.items():
        contests_out = []
        for contest_name, contest_exams in contests.items():
            contests_out.append({'contest_name': contest_name, 'exams': contest_exams})
        exams_grouped.append({'category_name': category_name, 'contests': contests_out})

    weak_kp_names = [w['kp_name'] for w in weak_kps]
    practice_minutes = 10
    if last_attempt and weak_kp_names:
        hero_summary = '本次正确率 %.1f%%，薄弱点集中在 %s。' % (last_attempt['accuracy_percent'], '、'.join(weak_kp_names[:3]))
    elif last_attempt:
        hero_summary = '本次正确率 %.1f%%。暂无知识点标签，完成试卷后可为题目标注知识点以获取薄弱点分析。' % last_attempt['accuracy_percent']
    else:
        hero_summary = '暂无测验记录，去完成一次诊断即可获得专属分析。'

    # 首页 AI 训练包：取最近一次报告的 practice_set
    practice_pack_home = {'exists': False, 'practice_set_id': None, 'count': 0, 'est_minutes': 0, 'weak_kp_names': weak_kp_names[:3]}
    if recent_reports and recent_reports[0].get('practice_set_id'):
        ps_id = recent_reports[0]['practice_set_id']
        pack_count = db.session.query(DiagPracticeSetItem).filter_by(practice_set_id=ps_id).count()
        practice_pack_home = {
            'exists': True,
            'practice_set_id': ps_id,
            'count': pack_count,
            'est_minutes': round(pack_count * 0.5, 1) if pack_count else 0,
            'weak_kp_names': weak_kp_names[:3],
        }

    hero_action_line = '建议先完成一组 %d 分钟基础训练，再进入下一阶段竞赛练习。' % (practice_pack_home.get('est_minutes') or practice_minutes)

    recommended_exam = None
    for cat in exams_grouped:
        for cont in cat.get('contests', []):
            for ex in cont.get('exams', []):
                if ex.get('status') == 'in_progress' and ex.get('in_progress'):
                    recommended_exam = {'type': 'continue', 'exam_id': ex['exam_id'], 'attempt_id': ex['in_progress']['attempt_id'], 'title': ex.get('exam_title')}
                    break
                if ex.get('status') == 'completed' and ex.get('retry_policy', {}).get('can_retry') and recommended_exam is None:
                    recommended_exam = {'type': 'retry', 'exam_id': ex['exam_id'], 'title': ex.get('exam_title')}
                if ex.get('status') == 'not_started' and recommended_exam is None:
                    recommended_exam = {'type': 'start', 'exam_id': ex['exam_id'], 'title': ex.get('exam_title')}
            if recommended_exam and recommended_exam.get('type') == 'continue':
                break
        if recommended_exam and recommended_exam.get('type') == 'continue':
            break

    cta_primary = '继续上次试卷' if in_progress_att else (
        '开始针对性训练' if practice_pack_home.get('exists') and practice_pack_home.get('practice_set_id') else '开始推荐试卷'
    )
    hero = {
        'summary_text': hero_summary,
        'action_line': hero_action_line,
        'in_progress_attempt': {'attempt_id': in_progress_att.id, 'exam_title': getattr(in_progress_att.exam, 'title', None)} if in_progress_att else None,
        'recommended_exam': recommended_exam,
        'practice_pack_home': practice_pack_home,
        'cta_primary': cta_primary,
        'cta_secondary': '查看最近报告',
    }

    cutoff_7d = datetime.utcnow() - timedelta(days=7)
    finished_7d = db.session.query(DiagAttempt).filter(
        DiagAttempt.user_id == user.id,
        DiagAttempt.status == 'finished',
        DiagAttempt.finished_at >= cutoff_7d
    ).all()
    days_active = len(set((att.finished_at or att.started_at).date() for att in finished_7d if (att.finished_at or att.started_at)))
    weekly_participation = {
        'days_active': days_active,
        'total_days': 7,
        'percentage': round(100 * days_active / 7, 0),
    }

    exam_tree = _build_exam_tree(competitions, in_progress_by_exam, last_finished_by_exam, db)

    return {
        'user_display_name': user_display_name,
        'last_attempt': last_attempt,
        'last_submitted': last_submitted,
        'stats_30d': stats_30d,
        'trend': trend,
        'weak_kps': weak_kps,
        'recent_reports': recent_reports,
        'recent_reports_first_2': recent_reports[:2],
        'exams_grouped': exams_grouped,
        'chart_trend_labels': [t['label'] for t in trend],
        'chart_trend_values': [t['accuracy_percent'] for t in trend],
        'chart_bar_labels': chart_bar_labels,
        'chart_bar_time': chart_bar_time,
        'chart_bar_slow_indices': chart_bar_slow_indices,
        'hero': hero,
        'practice_pack_home': practice_pack_home,
        'weekly_participation': weekly_participation,
        'exam_tree': exam_tree,
    }


def _parse_choices(choices_json):
    """解析 choices_json 为 [{'key': k, 'text': v}, ...]"""
    if not choices_json:
        return [{'key': c, 'text': c} for c in ('A', 'B', 'C', 'D', 'E')]
    try:
        raw = json.loads(choices_json)
        if isinstance(raw, dict):
            return [{'key': k, 'text': v} for k, v in raw.items()]
        if isinstance(raw, list):
            return raw
    except Exception:
        pass
    return [{'key': c, 'text': c} for c in ('A', 'B', 'C', 'D', 'E')]


def _safe_mean(xs):
    xs = [float(x) for x in (xs or []) if x is not None]
    if not xs:
        return 0.0
    return float(sum(xs)) / float(len(xs))


def _safe_stdev(xs):
    xs = [float(x) for x in (xs or []) if x is not None]
    if len(xs) < 2:
        return 0.0
    try:
        return float(statistics.stdev(xs))
    except Exception:
        return 0.0


def _time_stability_score(time_secs):
    """时间稳定度：使用 CV=stdev/mean，将其映射到 0~100（越高越稳定）。"""
    xs = [float(t) for t in (time_secs or []) if t is not None and float(t) > 0]
    if len(xs) < 3:
        return {'score_0to100': None, 'cv': None}
    m = _safe_mean(xs)
    if m <= 0:
        return {'score_0to100': None, 'cv': None}
    sd = _safe_stdev(xs)
    cv = sd / m
    score = int(round(max(0.0, 1.0 - min(1.0, cv)) * 100, 0))
    return {'score_0to100': score, 'cv': float(cv)}


def _level_from_metrics(accuracy_percent, score_percent, time_stability_score):
    """能力等级：1~5。核心依据：正确率/得分率/时间稳定度（缺失时降级）。"""
    acc = float(accuracy_percent or 0.0)
    sp = float(score_percent or 0.0)
    ts = time_stability_score if time_stability_score is not None else 60.0
    composite = 0.45 * sp + 0.45 * acc + 0.10 * float(ts)
    if composite >= 85:
        level = 5
    elif composite >= 70:
        level = 4
    elif composite >= 55:
        level = 3
    elif composite >= 40:
        level = 2
    else:
        level = 1
    labels = {
        1: '基础待强化',
        2: '基础提升期',
        3: '中等水平',
        4: '具备竞赛潜力',
        5: '冲刺高分水平',
    }
    stages = {
        1: '先补基础概念与常见题型，建立稳定解题流程',
        2: '专项练习 + 纠错复盘，减少低级失分',
        3: '分模块强化 + 套题训练，提升综合迁移能力',
        4: '套卷训练 + 策略优化，追求稳定高分',
        5: '冲刺阶段：稳定输出 + 难题突破与心态管理',
    }
    return {'level_score': level, 'level_label': labels[level], 'prep_stage': stages[level], 'composite': composite}


def _predicted_range(score_max, level_score):
    """预测得分区间（基于 level 的经验区间，输出数值范围）。"""
    try:
        mx = float(score_max or 0)
    except Exception:
        mx = 0
    if mx <= 0:
        return None
    pct_ranges = {
        1: (10, 35),
        2: (25, 50),
        3: (45, 70),
        4: (65, 88),
        5: (80, 98),
    }
    lo, hi = pct_ranges.get(int(level_score or 1), (30, 60))
    a = int(round(mx * lo / 100.0, 0))
    b = int(round(mx * hi / 100.0, 0))
    if a > b:
        a, b = b, a
    return {'low': a, 'high': b, 'max': int(round(mx, 0))}


def _median(xs):
    xs = [float(x) for x in (xs or []) if x is not None]
    if not xs:
        return None
    xs = sorted(xs)
    n = len(xs)
    mid = n // 2
    if n % 2 == 1:
        return xs[mid]
    return (xs[mid - 1] + xs[mid]) / 2.0


def _compute_style_profile(detail_rows):
    """答题风格画像：四象限统计 + 3条风格描述。"""
    rows = detail_rows or []
    time_list = [r.get('time_sec') for r in rows if not r.get('is_blank')]
    t_med = _median([t for t in time_list if t and float(t) > 0])
    if t_med is None:
        t_med = _safe_mean([t for t in time_list if t and float(t) > 0]) or 0

    quad = {'fast_wrong': 0, 'slow_wrong': 0, 'fast_correct': 0, 'slow_correct': 0}
    total_attempted = 0
    for r in rows:
        if r.get('is_blank'):
            continue
        total_attempted += 1
        t = float(r.get('time_sec') or 0)
        is_fast = (t_med > 0 and t <= t_med)
        is_correct = bool(r.get('is_correct'))
        if is_fast and is_correct:
            quad['fast_correct'] += 1
        elif (not is_fast) and is_correct:
            quad['slow_correct'] += 1
        elif is_fast and (not is_correct):
            quad['fast_wrong'] += 1
        else:
            quad['slow_wrong'] += 1

    denom = max(1, total_attempted)
    fw = quad['fast_wrong'] / denom
    sw = quad['slow_wrong'] / denom
    fc = quad['fast_correct'] / denom

    if fw >= 0.30 and (fw > sw):
        style = '冲动型'
        desc = [
            '容易快速作答但出现非必要错误，建议先“审题-列式-再计算”。',
            '每题最后留 3~5 秒做反向检查（单位/符号/边界）。',
            '优先训练“易错题型清单”，把快错转化为快对。',
        ]
    elif sw >= 0.30 and (sw >= fw):
        style = '理解困难型'
        desc = [
            '慢+错占比较高，通常卡在模型建立或关键概念上。',
            '建议把错题按知识点拆分，先补“定义/典型例题/变式”。',
            '限时做“同类题 3 题”，训练从题面到模型的提取速度。',
        ]
    elif fc >= 0.45 and (fw + sw) <= 0.20:
        style = '熟练型'
        desc = [
            '快+对占比较高，说明基础题与常规题型掌握扎实。',
            '建议把节省时间用于 1~2 道压轴题的策略尝试。',
            '保持稳定输出，避免追求速度导致粗心。',
        ]
    else:
        style = '稳健型'
        desc = [
            '整体节奏相对均衡，说明你能在速度与正确之间权衡。',
            '建议把慢题拆解为“卡点清单”，逐步降低慢错比例。',
            '通过套卷训练形成固定节奏：先稳拿基础分，再冲高分。',
        ]

    calc_stability = '高' if (fw + sw) <= 0.25 else ('中' if (fw + sw) <= 0.45 else '低')
    ts = _time_stability_score([r.get('time_sec') for r in rows if not r.get('is_blank')]).get('score_0to100')
    time_level = '高' if (ts is not None and ts >= 75) else ('中' if (ts is not None and ts >= 55) else '低')

    return {
        'quadrants': quad,
        'style_label': style,
        'calculation_stability': calc_stability,
        'time_allocation_stability': time_level,
        'descriptions': desc,
        'slow_wrong_ratio': sw,
    }


def _compute_error_type_stats(detail_rows):
    """错因分类统计：基于每题的 error_type（若无则尝试从 error_tag 推断）。"""
    rows = detail_rows or []
    allowed = [
        'arithmetic_error',
        'concept_misunderstanding',
        'modeling_error',
        'careless_error',
        'time_management',
    ]
    labels = {
        'arithmetic_error': '计算失误',
        'concept_misunderstanding': '概念误解',
        'modeling_error': '建模错误',
        'careless_error': '粗心失误',
        'time_management': '时间管理',
    }
    counts = {k: 0 for k in allowed}
    total = 0
    for r in rows:
        if r.get('is_blank') or r.get('is_correct'):
            continue
        et = (r.get('error_type') or '').strip()
        if not et:
            tag = (r.get('error_tag') or '').strip()
            # 兼容现有系统：没有持久化 error_type 时，根据 error_tag 做最小推断
            if '算' in tag or '计算' in tag:
                et = 'arithmetic_error'
            elif '概念' in tag:
                et = 'concept_misunderstanding'
            elif '建模' in tag or '模型' in tag:
                et = 'modeling_error'
            elif '时间' in tag:
                et = 'time_management'
            elif tag and tag != 'unknown':
                et = 'careless_error'
        if not et:
            continue
        if et not in counts:
            continue
        counts[et] += 1
        total += 1
    if total <= 0:
        return None
    items = []
    for k in allowed:
        n = counts.get(k, 0)
        if n <= 0:
            continue
        pct = round(100 * n / total, 0)
        items.append({'key': k, 'label': labels.get(k, k), 'count': n, 'percent': int(pct)})
    items = sorted(items, key=lambda x: -x['count'])
    return {'total_tagged': total, 'items': items}


def _compute_risk(accuracy_percent, blank_count, slow_wrong_ratio):
    acc = float(accuracy_percent or 0.0)
    blanks = int(blank_count or 0)
    swr = float(slow_wrong_ratio or 0.0)
    flags = []
    if acc < 30:
        flags.append('正确率偏低（<30%）')
    if blanks > 3:
        flags.append('空题偏多（>3）')
    if swr >= 0.30:
        flags.append('慢+错比例偏高')
    score = len(flags)
    if score >= 3:
        level = '高'
        tone = 'danger'
    elif score == 2:
        level = '中'
        tone = 'warning'
    else:
        level = '低'
        tone = 'success'
    return {'risk_level': level, 'tone': tone, 'reasons': flags}


def _compute_growth(kp_radar):
    """成长潜力：找优势知识点并生成一句专家鼓励语。"""
    items = kp_radar or []
    items = [x for x in items if (x.get('category') or '').strip() and x.get('category') != '暂无']
    if not items:
        return None
    top = sorted(items, key=lambda x: -(float(x.get('value_0to100') or 0)))[:2]
    names = [t.get('category') for t in top if float(t.get('value_0to100') or 0) >= 60]
    if not names:
        return None
    if len(names) == 1:
        text = f'在「{names[0]}」相关题目中表现相对更稳定，说明该模块的解题结构已具备基础优势。建议保持优势并向相邻模块迁移。'
    else:
        text = f'在「{names[0]}」与「{names[1]}」题型中表现较好，说明逻辑结构理解能力具备基础优势。建议以此为支点，带动薄弱模块提升。'
    return {'strength_kps': names, 'message': text}


def _compute_expert_diagnosis(ctx):
    """专家诊断型报告：返回 5 个模块数据；无数据的模块返回 None。"""
    total = int(ctx.get('total_questions') or 0)
    if total <= 0:
        return None
    detail_rows = ctx.get('detail_rows') or []
    acc = float(ctx.get('accuracy_percent') or 0.0)
    sp = float(ctx.get('score_percent') or 0.0) or float(acc)
    time_stab = _time_stability_score([r.get('time_sec') for r in detail_rows if not r.get('is_blank')])
    level_meta = _level_from_metrics(acc, sp, time_stab.get('score_0to100'))
    pr = _predicted_range(ctx.get('score_max') or ctx.get('total_questions'), level_meta['level_score'])
    module1 = {
        'level_score': level_meta['level_score'],
        'level_label': level_meta['level_label'],
        'predicted_range': pr,
        'prep_stage': level_meta['prep_stage'],
        'time_stability_score': time_stab.get('score_0to100'),
    }

    style = _compute_style_profile(detail_rows)
    module2 = {
        'quadrants': style['quadrants'],
        'style_label': style['style_label'],
        'calculation_stability': style['calculation_stability'],
        'time_allocation_stability': style['time_allocation_stability'],
        'descriptions': style['descriptions'],
    }

    module3 = _compute_error_type_stats(detail_rows)
    module4 = _compute_risk(acc, ctx.get('blank_count'), style.get('slow_wrong_ratio'))
    module5 = _compute_growth(ctx.get('kp_radar') or [])

    return {
        'ability_level': module1,
        'answer_style': module2,
        'error_type_stats': module3,
        'learning_risk': module4,
        'growth_potential': module5,
    }


def _build_report_data(att, user, db):
    """组装报告数据结构，缺失字段安全降级为 N/A 或空。优先使用 CSV 导入的答案/解析/知识点。"""
    from sqlalchemy import func
    from app import (DiagAttempt, DiagAttemptAnswer, DiagExamQuestion, DiagQuestion,
                     DiagKnowledgePoint, DiagPracticeSetItem, DiagQuestionAnswer, DiagQuestionKp)
    exam = att.exam
    competition = getattr(exam, 'competition', None) if exam else None
    answers = db.session.query(DiagAttemptAnswer).filter_by(attempt_id=att.id).order_by(DiagAttemptAnswer.question_id).all()
    order = db.session.query(DiagExamQuestion).filter_by(exam_id=att.exam_id).order_by(DiagExamQuestion.q_index).all()
    q_map = {eq.question_id: db.session.get(DiagQuestion, eq.question_id) for eq in order}
    answers_dict = {aa.question_id: aa for aa in answers}
    total = len(order) or 1
    total_time_ms = att.total_time_ms or 0
    total_time_sec = round(total_time_ms / 1000, 1)
    avg_time_sec = round(total_time_ms / 1000 / total, 1) if total else 0
    score_scheme = getattr(competition, 'score_scheme', None) if competition else None
    blank_bonus = int(getattr(competition, 'blank_bonus', 0) or 0) if competition else 0
    points_per_question, score_max = _points_for_exam(score_scheme, total)
    has_custom_score_scheme = bool(score_scheme and str(score_scheme).strip())
    # 试卷未设置分数时：默认一题一分，满分 = 题数
    if not has_custom_score_scheme:
        score_max = total
        points_per_question = [1] * total
    score_earned = sum(
        points_per_question[i] for i in range(total)
        if answers_dict.get(order[i].question_id) and answers_dict[order[i].question_id].is_correct is True
    )
    blank_count = sum(1 for i in range(total) if not answers_dict.get(order[i].question_id) or not ((answers_dict[order[i].question_id].answer or '').strip()))
    score_earned += blank_count * blank_bonus
    correct_count = sum(1 for aa in answers if aa.is_correct is True)
    accuracy_percent = round(100 * correct_count / total, 1) if total else 0
    score_percent = round(100 * score_earned / score_max, 0) if score_max else 0
    submitted_at = getattr(att, 'finished_at', None) or getattr(att, 'started_at', None)
    submitted_at_str = submitted_at.strftime('%Y-%m-%d %H:%M') if submitted_at and hasattr(submitted_at, 'strftime') else (str(submitted_at) if submitted_at else 'N/A')
    exam_title = getattr(exam, 'title', None) or 'N/A'
    competition_name = getattr(competition, 'name_cn', None) or getattr(competition, 'category', None) or 'N/A'
    user_display_name = getattr(user, 'username', None) or 'N/A'
    time_secs = []
    for i, eq in enumerate(order):
        aa = answers_dict.get(eq.question_id)
        ms = (aa.time_spent_ms or 0) if aa else 0
        time_secs.append(ms / 1000)
    sorted_times = sorted([t for t in time_secs if t > 0]) or [0]
    n_t = len(sorted_times)
    p75_idx = int(n_t * 0.75) if n_t else 0
    p25_idx = int(n_t * 0.25) if n_t else 0
    p75 = sorted_times[min(p75_idx, n_t - 1)] if n_t else 0
    p25 = sorted_times[p25_idx] if n_t else 0
    slow_wrong = []
    fast_wrong = []
    per_question = []
    kp_stats = {}
    finished_ids = [r[0] for r in db.session.query(DiagAttempt.id).filter(
        DiagAttempt.exam_id == att.exam_id,
        DiagAttempt.status == 'finished'
    ).all()]
    avg_time_by_q = {}
    if finished_ids:
        for r in db.session.query(
            DiagAttemptAnswer.question_id,
            func.avg(DiagAttemptAnswer.time_spent_ms).label('avg_ms')
        ).filter(
            DiagAttemptAnswer.attempt_id.in_(finished_ids),
            DiagAttemptAnswer.time_spent_ms.isnot(None)
        ).group_by(DiagAttemptAnswer.question_id).all():
            avg_time_by_q[r.question_id] = float(r.avg_ms or 0)
    imported_answers = {r.q_index: r for r in db.session.query(DiagQuestionAnswer).filter_by(exam_id=att.exam_id).all()}
    imported_kp = {r.q_index: r for r in db.session.query(DiagQuestionKp).filter_by(exam_id=att.exam_id).all()}
    for i, eq in enumerate(order):
        q = q_map.get(eq.question_id)
        aa = answers_dict.get(eq.question_id)
        my_ms = (aa.time_spent_ms or 0) if aa else 0
        time_sec = round(my_ms / 1000, 1)
        is_blank = not aa or not ((aa.answer or '').strip())
        is_correct = aa and aa.is_correct is True
        if not is_blank and not is_correct and p75 > 0 and time_sec > p75:
            slow_wrong.append({'qnum': i + 1, 'time_sec': time_sec})
        if not is_blank and not is_correct and p25 > 0 and time_sec < p25:
            fast_wrong.append({'qnum': i + 1, 'time_sec': time_sec})
        primary_kp = None
        secondary_kps = []
        imp_ans = imported_answers.get(eq.q_index)
        imp_kp = imported_kp.get(eq.q_index)
        if imp_kp and imp_kp.kp_primary:
            primary_kp = imp_kp.kp_primary
            secondary_kps = [x.strip() for x in (imp_kp.kp_secondary or '').replace('\uff1b', ',').replace(';', ',').split(',') if x.strip()]
            kp_id = 'imported:' + (imp_kp.kp_primary or '')
            if kp_id not in kp_stats:
                kp_stats[kp_id] = {'kp_name': imp_kp.kp_primary, 'wrong_count': 0, 'n_questions': 0, 'total_time_ms': 0}
            kp_stats[kp_id]['n_questions'] += 1
            kp_stats[kp_id]['total_time_ms'] += my_ms
            if not is_blank and not is_correct:
                kp_stats[kp_id]['wrong_count'] += 1
        correct_ans = (imp_ans.correct_answer or '').strip() if imp_ans and imp_ans.correct_answer else ((q.answer_key or '').strip() if q else '')
        solution_txt = (imp_ans.solution_explain or '') if imp_ans and imp_ans.solution_explain else (q.solution_text if q else '')
        pq = {
            'qnum': i + 1,
            'is_correct': is_correct,
            'is_blank': is_blank,
            'time_sec': time_sec,
            'user_answer': (aa.answer or '').strip() if aa else '',
            'correct_answer': correct_ans,
            'kp_primary_name': primary_kp or 'N/A',
            'kp_secondary_names': secondary_kps,
            'error_tag': getattr(aa, 'error_tag', None) or 'unknown',
            'solution_text': solution_txt,
            'solution_image_url': getattr(q, 'solution_image_url', None) if q else None,
            'stem_text': q.stem_text if q else '',
            'stem_image_url': getattr(q, 'stem_image_url', None) if q else None,
            'choices': _parse_choices(q.choices_json if q else None),
            'points': points_per_question[i] if i < len(points_per_question) else 1,
            'eq': eq,
            'aa': aa,
            'speed': '慢' if p75 > 0 and time_sec > p75 else ('快' if p25 > 0 and time_sec < p25 else '中'),
            'avg_time_ms': avg_time_by_q.get(eq.question_id, 0),
        }
        per_question.append(pq)
    kp_radar = []
    kp_weak_top = []
    for kp_id, s in kp_stats.items():
        n = s['n_questions'] or 1
        wrong = s['wrong_count']
        avg_s = round(s['total_time_ms'] / 1000 / n, 1)
        mastery = round(max(0, 100 * (1 - wrong / n)), 0)
        kp_radar.append({'category': s['kp_name'][:8], 'value_0to100': mastery, 'n_questions': n})
        kp_weak_top.append({'kp_name': s['kp_name'], 'wrong_count': wrong, 'n_questions': n, 'avg_time_sec': avg_s})
    kp_radar = sorted(kp_radar, key=lambda x: -x['value_0to100'])[:6]
    kp_weak_top = sorted(kp_weak_top, key=lambda x: -x['wrong_count'])[:5]
    kp_has_data = bool(kp_stats)
    if not kp_radar:
        kp_radar = [{'category': '暂无', 'value_0to100': 0, 'n_questions': 0}]
    practice_set = att.practice_sets[-1] if att.practice_sets else None
    practice_items = db.session.query(DiagPracticeSetItem).filter_by(practice_set_id=practice_set.id).all() if practice_set else []
    ps_count = len(practice_items)
    est_minutes = max(1, ps_count * 2)
    ps_kps = list(set(kp_stats.keys()))[:5]
    # 总排名位置（百分比）：同试卷已完成尝试中，得分率超过多少比例的人 → 显示为「前 X%」
    rank_top_percent = None
    if len(finished_ids) > 1:
        others = [aid for aid in finished_ids if aid != att.id]
        n_better = 0
        for oid in others:
            o_att = db.session.get(DiagAttempt, oid)
            if not o_att:
                continue
            st = _attempt_quick_stats(o_att, db)
            o_score_max = st.get('score_max') or 1
            o_sp = round(100 * st.get('score', 0) / o_score_max, 0)
            if o_sp < score_percent:
                n_better += 1
        rank_top_percent = round(100 - 100 * n_better / len(others), 1)
        rank_top_percent = max(0, min(100, rank_top_percent))
    return {
        'exam_title': exam_title,
        'competition_name': competition_name,
        'submitted_at': submitted_at,
        'submitted_at_str': submitted_at_str,
        'user_display_name': user_display_name,
        'score': score_earned,
        'score_max': score_max,
        'total_questions': total,
        'accuracy_percent': accuracy_percent,
        'score_percent': score_percent,
        'total_time_sec': total_time_sec,
        'avg_time_sec': avg_time_sec,
        'rank_top_percent': rank_top_percent,
        'blank_count': blank_count,
        'skip_count': blank_count,
        'correct_count': correct_count,
        'has_custom_score_scheme': has_custom_score_scheme,
        'per_question': per_question,
        'kp_radar': kp_radar,
        'kp_weak_top': kp_weak_top,
        'slow_wrong': slow_wrong,
        'fast_wrong': fast_wrong,
        'practice_summary': {
            'exists': practice_set is not None,
            'practice_set_id': practice_set.id if practice_set else None,
            'count': ps_count,
            'est_minutes': est_minutes,
            'kps': ps_kps,
        },
        'chart_line_x': [pq['qnum'] for pq in per_question],
        'chart_line_y': _avg_score_per_question_all_students(db, order, finished_ids) if order else [],
        'chart_bar_labels': [str(pq['qnum']) for pq in per_question],
        'chart_bar_time': [pq['time_sec'] for pq in per_question],
        'chart_bar_correct': [1 if pq['is_correct'] else 0 for pq in per_question],
        'detail_rows': per_question,
        'practice_set': practice_set,
        'kp_has_data': kp_has_data,
    }


@diagnostic_bp.route('/report/<int:attempt_id>')
@require_diag_login
def report(attempt_id):
    db = _get_db()
    from app import DiagAttempt
    att = db.session.get(DiagAttempt, attempt_id)
    if not att:
        abort(404)
    user = get_diag_user_from_cookie()
    if att.user_id != user.id:
        flash('无权访问', 'error')
        return redirect(url_for('diagnostic.exams'))
    report_data = _build_report_data(att, user, db)
    report_data['attempt'] = att
    report_data['chart_radar_labels'] = [r['category'] for r in report_data['kp_radar']]
    report_data['chart_radar_values'] = [r['value_0to100'] for r in report_data['kp_radar']]
    report_data['expert_diag'] = _compute_expert_diagnosis(report_data)
    # 参考样本位置（diagnostic benchmark）
    from diagnostic.roadmap_config import infer_contest_key
    from diagnostic.benchmark import get_benchmark_summary
    exam = getattr(att, 'exam', None)
    comp = getattr(exam, 'competition', None) if exam else None
    comp_name = getattr(comp, 'name', None) if comp else None
    exam_title = getattr(exam, 'title', None) or ''
    contest_key = infer_contest_key(comp_name, exam_title)
    if contest_key and report_data.get('score') is not None:
        report_data['benchmark_summary'] = get_benchmark_summary(contest_key, float(report_data['score']), db)
    else:
        report_data['benchmark_summary'] = None
    # 总排名位置与参考样本位置统一：优先用参考样本百分位，避免两处数据不一致
    if report_data.get('benchmark_summary'):
        report_data['display_rank_top_percent'] = round(100 - report_data['benchmark_summary']['percentile_estimate'], 1)
    else:
        report_data['display_rank_top_percent'] = report_data.get('rank_top_percent')
    return render_template('diagnostic/report.html', **report_data)


def _parse_practice_choices(choices_str):
    """解析练习题的 choices 文本。支持多种格式。"""
    if not choices_str or not str(choices_str).strip():
        return []
    s = str(choices_str).strip()
    try:
        raw = json.loads(s)
        if isinstance(raw, dict):
            return [{'key': k, 'text': str(v)} for k, v in raw.items()]
        if isinstance(raw, list) and all(isinstance(x, dict) and 'key' in x for x in raw):
            return raw
        if isinstance(raw, list):
            return [{'key': c.get('key', c), 'text': str(c.get('text', c))} for c in raw]
    except Exception:
        pass
    # 格式 "A) value B) value" 或 "A. value B. value"：支持 ) 或 . 作为分隔符，[A-Z] 支持更多选项
    for pattern in [
        r'([A-Z])\)\s*(.*?)(?=\s*[A-Z]\)|$)',
        r'([A-Z])\.\s*(.*?)(?=\s*[A-Z]\.|$)',
        r'([A-Z]):\s*(.*?)(?=\s*[A-Z]:|$)',
    ]:
        parts = re.findall(pattern, s, re.DOTALL)
        if parts:
            result = [{'key': k, 'text': v.strip().rstrip(',').strip()} for k, v in parts if v.strip()]
            if result:
                return result
    # 纯值列表 "20, 30, 60, 120" 或 "20；30；60"：按逗号/分号/空格分隔后赋 A,B,C,D
    if ',' in s or ';' in s or '；' in s:
        sep = re.compile(r'[,;\uff1b\s]+')
        vals = [x.strip() for x in sep.split(s) if x.strip() and len(x.strip()) < 50]
        if 2 <= len(vals) <= 10:
            letters = list('ABCDEFGHIJ')[:len(vals)]
            return [{'key': letters[i], 'text': vals[i]} for i in range(len(vals))]
    return []


def _practice_questions_from_items(db, items):
    from app import DiagBankQuestion, DiagQuestionPracticeItem
    from app import Question as HomeworkQuestion
    from types import SimpleNamespace
    questions = []
    for it in items:
        if it.source_type == 'csv_practice':
            pi = db.session.get(DiagQuestionPracticeItem, it.source_question_id)
            if not pi:
                continue
            choices = _parse_practice_choices(pi.choices)
            # 仅有空字符串或解析失败且无有效选项时保持 []，模板会显示文本输入框
            # 避免显示无意义的 A/B/C/D/E 单选（无选项值）
            if not choices:
                pass
            fake_q = SimpleNamespace(stem_text=pi.stem, stem_image_url=None, content=pi.stem)
            questions.append({
                'item': it, 'source': 'csv_practice', 'question': fake_q,
                'choices': choices,
                'correct_answer': (pi.answer or '').strip() if pi else None,
                'solution_text': pi.explain if pi else None,
            })
        elif it.source_type == 'bank':
            q = db.session.get(DiagBankQuestion, it.source_question_id)
            choices = []
            if q and q.choices_json:
                try:
                    raw = json.loads(q.choices_json)
                    if isinstance(raw, dict):
                        choices = [{'key': k, 'text': v} for k, v in raw.items()]
                    elif isinstance(raw, list):
                        choices = raw
                except Exception:
                    pass
            if not choices:
                choices = [{'key': c, 'text': c} for c in ('A', 'B', 'C', 'D', 'E')]
            questions.append({
                'item': it, 'source': 'bank', 'question': q,
                'choices': choices,
                'correct_answer': (q.answer_key or '').strip() if q else None,
                'solution_text': q.solution_text if q else None,
            })
        else:
            q = db.session.get(HomeworkQuestion, it.source_question_id)
            questions.append({
                'item': it, 'source': 'homework', 'question': q,
                'choices': [],
                'correct_answer': (q.answer or '').strip() if q else None,
                'solution_text': None,
            })
    return questions


@diagnostic_bp.route('/practice/<int:practice_set_id>')
@require_diag_login
def practice(practice_set_id):
    db = _get_db()
    from app import DiagPracticeSet, DiagPracticeSetItem, DiagBankQuestion, DiagPracticeAttempt
    from app import Question as HomeworkQuestion
    ps = db.session.get(DiagPracticeSet, practice_set_id)
    if not ps:
        abort(404)
    user = get_diag_user_from_cookie()
    if ps.user_id != user.id:
        flash('无权访问', 'error')
        return redirect(url_for('diagnostic.exams'))
    items = db.session.query(DiagPracticeSetItem).filter_by(practice_set_id=practice_set_id).order_by(DiagPracticeSetItem.q_index).all()
    # 是否已提交过：每人每练习包只能提交一次
    attempt = db.session.query(DiagPracticeAttempt).filter_by(
        practice_set_id=practice_set_id, user_id=user.id
    ).first()
    if attempt:
        # 已完成：直接显示得分与每题对错、答案、解析
        answers_map = {}
        if attempt.answers_json:
            try:
                answers_map = json.loads(attempt.answers_json)
            except Exception:
                pass
        questions = _practice_questions_from_items(db, items)
        result_rows = []
        score_earned = 0
        for qdata in questions:
            it = qdata['item']
            correct = (qdata['correct_answer'] or '').strip()
            user_ans = (answers_map.get(str(it.id)) or '').strip()
            is_correct = (correct and user_ans and correct.upper() == user_ans.upper())
            if is_correct:
                score_earned += 1
            result_rows.append({
                'item': it,
                'question': qdata['question'],
                'source': qdata['source'],
                'user_answer': user_ans or '—',
                'correct_answer': correct or '—',
                'is_correct': is_correct,
                'solution_text': qdata.get('solution_text'),
            })
        score_max = len(result_rows)
        return render_template(
            'diagnostic/practice.html',
            practice_set=ps,
            questions=questions,
            completed=True,
            attempt=attempt,
            result_rows=result_rows,
            score_earned=score_earned,
            score_max=score_max,
        )
    questions = _practice_questions_from_items(db, items)
    return render_template(
        'diagnostic/practice.html',
        practice_set=ps,
        questions=questions,
        completed=False,
    )


@diagnostic_bp.route('/practice/<int:practice_set_id>/submit', methods=['POST'])
@require_diag_login
def practice_submit(practice_set_id):
    """练习包提交：保存答案，每人每包只能提交一次。"""
    db = _get_db()
    from app import DiagPracticeSet, DiagPracticeSetItem, DiagPracticeAttempt
    ps = db.session.get(DiagPracticeSet, practice_set_id)
    if not ps:
        abort(404)
    user = get_diag_user_from_cookie()
    if ps.user_id != user.id:
        flash('无权访问', 'error')
        return redirect(url_for('diagnostic.exams'))
    existing = db.session.query(DiagPracticeAttempt).filter_by(
        practice_set_id=practice_set_id, user_id=user.id
    ).first()
    if existing:
        flash('该练习包已提交过，不可重复提交。', 'info')
        return redirect(url_for('diagnostic.practice', practice_set_id=practice_set_id))
    items = db.session.query(DiagPracticeSetItem).filter_by(practice_set_id=practice_set_id).order_by(DiagPracticeSetItem.q_index).all()
    answers = {}
    for it in items:
        val = request.form.get('answer_%s' % it.id)
        if val is not None:
            answers[str(it.id)] = str(val).strip()
    attempt = DiagPracticeAttempt(
        practice_set_id=practice_set_id,
        user_id=user.id,
        answers_json=json.dumps(answers, ensure_ascii=False),
    )
    db.session.add(attempt)
    db.session.commit()
    flash('已提交。', 'success')
    return redirect(url_for('diagnostic.practice', practice_set_id=practice_set_id))
