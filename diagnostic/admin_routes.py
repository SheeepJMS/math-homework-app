# 诊断后台：/admin/diagnostic/*，使用现有 admin_required（Flask-Login）
from flask import Blueprint, request, redirect, url_for, render_template, flash, current_app, abort, send_file
from datetime import datetime
from werkzeug.security import generate_password_hash
import csv
import io
import json
import os

diagnostic_admin_bp = Blueprint('diagnostic_admin', __name__, url_prefix='/admin/diagnostic', template_folder='../templates/admin/diagnostic')


def _db():
    """使用当前 app 的 db，避免 Flask-SQLAlchemy 在 reloader 下 _app_engines KeyError"""
    return current_app.extensions['sqlalchemy']


def _models():
    from app import (
        DiagCompetition, DiagExam, DiagQuestion, DiagExamQuestion, DiagKnowledgePoint,
        DiagQuestionTag, DiagBankQuestion, DiagBankQuestionTag, DiagQuestionBankLink,
        DiagQuestionPracticeConfig, Lesson, Question as HomeworkQuestion,
    )
    return (DiagCompetition, DiagExam, DiagQuestion, DiagExamQuestion, DiagKnowledgePoint,
            DiagQuestionTag, DiagBankQuestion, DiagBankQuestionTag, DiagQuestionBankLink,
            DiagQuestionPracticeConfig, Lesson, HomeworkQuestion)


def admin_required(f):
    from functools import wraps
    from flask_login import current_user
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('请先登录', 'warning')
            return redirect(url_for('login'))
        if not getattr(current_user, 'is_admin', False):
            flash('需要管理员权限', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return wrapped


@diagnostic_admin_bp.route('/exams')
@admin_required
def exams():
    db = _db()
    DiagCompetition, DiagExam, *_ = _models()
    comps = db.session.query(DiagCompetition).order_by(
        DiagCompetition.subject, DiagCompetition.category, DiagCompetition.name
    ).all()
    # 层级：学科 → 大类 → 具体竞赛 → [试卷(年份+标题)]
    from collections import OrderedDict
    hierarchy = OrderedDict()
    for c in comps:
        sub_key = (c.subject or '未分类', c.category or '未分类')
        if sub_key not in hierarchy:
            hierarchy[sub_key] = {}
        comp_key = c.name
        if comp_key not in hierarchy[sub_key]:
            hierarchy[sub_key][comp_key] = {'comp': c, 'exams': []}
        exams_in_comp = db.session.query(DiagExam).filter_by(competition_id=c.id).order_by(
            DiagExam.year.desc(), DiagExam.created_at.desc()
        ).all()
        hierarchy[sub_key][comp_key]['exams'] = exams_in_comp
    # 已有竞赛列表供新建时选择
    existing_comps = comps
    return render_template('admin/diagnostic/exams.html',
        hierarchy=hierarchy,
        existing_comps=existing_comps,
    )


@diagnostic_admin_bp.route('/exams/create', methods=['POST'])
@admin_required
def exam_create():
    db = _db()
    DiagCompetition, DiagExam, *_ = _models()
    subject = (request.form.get('subject') or '').strip()
    category = (request.form.get('category') or '').strip()
    comp_name = (request.form.get('comp_name') or request.form.get('competition_name') or '').strip()
    year_val = request.form.get('year')
    year = None
    if year_val is not None and str(year_val).strip():
        try:
            year = int(str(year_val).strip())
        except ValueError:
            pass
    if not comp_name:
        flash('具体竞赛不能为空', 'error')
        return redirect(url_for('diagnostic_admin.exams'))
    title = '%s %s' % (comp_name, year) if year else comp_name
    comp = db.session.query(DiagCompetition).filter_by(
        subject=subject or '', category=category or '', name=comp_name
    ).first()
    if not comp:
        comp = DiagCompetition(subject=subject or '', category=category or '', name=comp_name)
        db.session.add(comp)
        db.session.flush()
    if db.session.query(DiagExam).filter_by(competition_id=comp.id, title=title).first():
        flash('该竞赛下已存在同名试卷', 'error')
        return redirect(url_for('diagnostic_admin.exams'))
    exam = DiagExam(competition_id=comp.id, title=title, year=year, is_published=False)
    db.session.add(exam)
    db.session.commit()
    flash('试卷已创建', 'success')
    return redirect(url_for('diagnostic_admin.exam_detail', id=exam.id))


@diagnostic_admin_bp.route('/exams/<int:id>')
@admin_required
def exam_detail(id):
    db = _db()
    M = _models()
    DiagCompetition, DiagExam, DiagQuestion, DiagExamQuestion, DiagKnowledgePoint = M[0], M[1], M[2], M[3], M[4]
    DiagQuestionTag, DiagQuestionPracticeConfig, Lesson = M[5], M[9], M[10]
    exam = db.session.get(DiagExam, id)
    if exam is None:
        abort(404)
    order = db.session.query(DiagExamQuestion).filter(DiagExamQuestion.exam_id == id).order_by(DiagExamQuestion.q_index).all()
    questions = [db.session.get(DiagQuestion, eq.question_id) for eq in order]
    kp_list = db.session.query(DiagKnowledgePoint).filter_by(competition_id=exam.competition_id).all()
    lessons = db.session.query(Lesson).order_by(Lesson.title).all()
    q_tags = {}  # question_id -> {primary: str, secondary: [str]}
    q_config = {}  # question_id -> config
    lesson_titles = {l.id: l.title for l in lessons}
    for q in questions:
        if not q:
            continue
        tags = db.session.query(DiagQuestionTag).filter_by(question_id=q.id).all()
        primary, secondary = '', []
        for t in tags:
            if t.weight >= 0.99:
                primary = t.kp_id
            else:
                secondary.append(t.kp_id)
        q_tags[q.id] = {'primary': primary, 'secondary': ','.join(secondary[:2])}
        cfg = db.session.query(DiagQuestionPracticeConfig).filter_by(question_id=q.id).first()
        hw_id = cfg.homework_assignment_id if cfg and cfg.homework_assignment_id else None
        q_config[q.id] = {
            'config': cfg,
            'homework_assignment_id': hw_id,
            'homework_title': lesson_titles.get(hw_id, '') if hw_id else '',
        }
    return render_template('admin/diagnostic/exam_detail.html',
        exam=exam, order=order, questions=questions,
        kp_list=kp_list, lessons=lessons, q_tags=q_tags, q_config=q_config)


@diagnostic_admin_bp.route('/exams/<int:id>/publish', methods=['POST'])
@admin_required
def exam_publish(id):
    db = _db()
    _, DiagExam, *_ = _models()
    exam = db.session.get(DiagExam, id)
    if exam is None:
        abort(404)
    exam.is_published = not exam.is_published
    db.session.commit()
    flash('已{}发布'.format('' if exam.is_published else '取消'), 'success')
    return redirect(url_for('diagnostic_admin.exam_detail', id=id))


@diagnostic_admin_bp.route('/exams/<int:id>/delete', methods=['POST'])
@admin_required
def exam_delete(id):
    db = _db()
    M = _models()
    DiagExam, DiagExamQuestion = M[1], M[3]
    exam = db.session.get(DiagExam, id)
    if exam is None:
        abort(404)
    db.session.query(DiagExamQuestion).filter(DiagExamQuestion.exam_id == id).delete()
    db.session.delete(exam)
    db.session.commit()
    flash('试卷已删除', 'success')
    return redirect(url_for('diagnostic_admin.exams'))


@diagnostic_admin_bp.route('/competitions')
@admin_required
def competitions():
    """竞赛列表与分段分值设置。按 学科→竞赛大类→具体竞赛 层级展示。"""
    db = _db()
    DiagCompetition, *_ = _models()
    comps = db.session.query(DiagCompetition).order_by(
        DiagCompetition.subject, DiagCompetition.category, DiagCompetition.name
    ).all()
    segments_by_comp = {}
    for c in comps:
        segs = {}
        if c.score_scheme:
            try:
                scheme = json.loads(c.score_scheme)
                for s in scheme if isinstance(scheme, list) else []:
                    start, end = s.get('start'), s.get('end')
                    pts = s.get('points', 1)
                    if start is not None and end is not None:
                        segs['%s_%s' % (start, end)] = pts
            except Exception:
                pass
        segments_by_comp[c.id] = segs
    # 按 (subject, category) 分组，每组下列出具体竞赛 (name)
    from collections import OrderedDict
    hierarchy = OrderedDict()
    for c in comps:
        key = (c.subject or '未分类', c.category or '未分类')
        if key not in hierarchy:
            hierarchy[key] = []
        hierarchy[key].append(c)
    return render_template('admin/diagnostic/competitions.html',
        competitions=comps,
        segments_by_comp=segments_by_comp,
        hierarchy=hierarchy,
    )


@diagnostic_admin_bp.route('/competitions/<int:comp_id>/score_scheme', methods=['POST'])
@admin_required
def competition_score_scheme(comp_id):
    """保存某竞赛的分段分值。表单项：seg_1_10, seg_11_20, seg_21_30, seg_31_40, seg_41_50（每题段分值，留空表示不设）"""
    db = _db()
    DiagCompetition, *_ = _models()
    comp = db.session.get(DiagCompetition, comp_id)
    if not comp:
        abort(404)
    scheme = []
    segments = [
        (1, 10, request.form.get('seg_1_10')),
        (11, 20, request.form.get('seg_11_20')),
        (21, 30, request.form.get('seg_21_30')),
        (31, 40, request.form.get('seg_31_40')),
        (41, 50, request.form.get('seg_41_50')),
    ]
    for start, end, val in segments:
        if val is not None and str(val).strip() != '':
            try:
                p = int(str(val).strip())
                if p >= 0:
                    scheme.append({'start': start, 'end': end, 'points': p})
            except ValueError:
                pass
    blank_val = request.form.get('blank_bonus')
    try:
        comp.blank_bonus = int(str(blank_val).strip()) if blank_val is not None and str(blank_val).strip() != '' else 0
    except ValueError:
        comp.blank_bonus = 0
    comp.score_scheme = json.dumps(scheme, ensure_ascii=False) if scheme else None
    db.session.commit()
    flash('分值已保存，该竞赛下所有试卷共用此设置。', 'success')
    return redirect(url_for('diagnostic_admin.competitions'))


@diagnostic_admin_bp.route('/exams/<int:id>/upload_question_images', methods=['POST'])
@admin_required
def upload_question_images(id):
    """逐个/批量粘贴试题图片上传，每张图对应一题（与作业系统一致）"""
    from flask import jsonify
    from app import upload_to_cloudinary
    import random
    db = _db()
    DiagExam, DiagQuestion, DiagExamQuestion = _models()[1], _models()[2], _models()[3]
    exam = db.session.get(DiagExam, id)
    if exam is None:
        abort(404)
    try:
        image_files = request.form.getlist('files[]')
        if not image_files:
            return jsonify({'success': False, 'message': '没有接收到图片数据'}), 400
        order_list = db.session.query(DiagExamQuestion).filter(DiagExamQuestion.exam_id == id).all()
        next_q_index = (max(eq.q_index for eq in order_list) + 1) if order_list else 0
        success_count = 0
        for index, image_data in enumerate(image_files):
            if not image_data or not str(image_data).startswith('data:image'):
                continue
            cloudinary_url = upload_to_cloudinary(image_data)
            if not cloudinary_url:
                continue
            q = DiagQuestion(
                competition_id=exam.competition_id,
                stem_text='第{}题'.format(next_q_index + index + 1),
                stem_image_url=cloudinary_url,
            )
            db.session.add(q)
            db.session.flush()
            db.session.add(DiagExamQuestion(exam_id=id, question_id=q.id, q_index=next_q_index + index))
            success_count += 1
        if success_count > 0:
            db.session.commit()
        return jsonify({'success': True, 'message': '成功上传 {} 道题目'.format(success_count), 'success_count': success_count})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@diagnostic_admin_bp.route('/questions/<int:id>/delete', methods=['POST'])
@admin_required
def question_delete(id):
    """删除一道诊断题（先删关联再删题目）"""
    db = _db()
    M = _models()
    DiagQuestion, DiagExamQuestion, DiagQuestionTag, DiagQuestionPracticeConfig, DiagQuestionBankLink = M[2], M[3], M[5], M[9], M[8]
    question = db.session.get(DiagQuestion, id)
    if question is None:
        abort(404)
    db.session.query(DiagQuestionTag).filter(DiagQuestionTag.question_id == id).delete()
    db.session.query(DiagQuestionPracticeConfig).filter(DiagQuestionPracticeConfig.question_id == id).delete()
    db.session.query(DiagQuestionBankLink).filter(DiagQuestionBankLink.question_id == id).delete()
    eq = db.session.query(DiagExamQuestion).filter(DiagExamQuestion.question_id == id).first()
    exam_id = eq.exam_id if eq else None
    db.session.query(DiagExamQuestion).filter(DiagExamQuestion.question_id == id).delete()
    db.session.delete(question)
    db.session.commit()
    flash('题目已删除', 'success')
    return redirect(url_for('diagnostic_admin.exam_detail', id=exam_id) if exam_id else redirect(url_for('diagnostic_admin.exams')))


@diagnostic_admin_bp.route('/exams/<int:id>/save_answers', methods=['POST'])
@admin_required
def save_answers(id):
    """第二步：按题号顺序保存每题的答案到 DiagQuestion.answer_key"""
    from flask import jsonify
    db = _db()
    DiagExam, DiagQuestion, DiagExamQuestion = _models()[1], _models()[2], _models()[3]
    exam = db.session.get(DiagExam, id)
    if exam is None:
        abort(404)
    try:
        answers = request.form.getlist('answers[]')
        if not answers:
            flash('没有收到答案数据', 'error')
            return redirect(url_for('diagnostic_admin.exam_detail', id=id))
        order = db.session.query(DiagExamQuestion).filter(DiagExamQuestion.exam_id == id).order_by(DiagExamQuestion.q_index).all()
        updated = 0
        for i, eq in enumerate(order):
            if i >= len(answers):
                break
            q = db.session.get(DiagQuestion, eq.question_id)
            if q is None:
                continue
            raw = (answers[i] or '').strip()
            q.answer_key = raw.upper() if raw else None
            updated += 1
        db.session.commit()
        flash('已保存 {} 题答案'.format(updated), 'success')
    except Exception as e:
        db.session.rollback()
        flash('保存答案失败：{}'.format(str(e)), 'error')
    return redirect(url_for('diagnostic_admin.exam_detail', id=id))


@diagnostic_admin_bp.route('/exams/<int:id>/upload_solution_images', methods=['POST'])
@admin_required
def upload_solution_images(id):
    """第三步：粘贴解析图片，按题号顺序写入各题的 solution_image_url"""
    from flask import jsonify
    from app import upload_to_cloudinary
    db = _db()
    DiagExam, DiagQuestion, DiagExamQuestion = _models()[1], _models()[2], _models()[3]
    exam = db.session.get(DiagExam, id)
    if exam is None:
        abort(404)
    try:
        image_files = request.form.getlist('files[]')
        if not image_files:
            return jsonify({'success': False, 'message': '没有接收到图片数据'}), 400
        order = db.session.query(DiagExamQuestion).filter(DiagExamQuestion.exam_id == id).order_by(DiagExamQuestion.q_index).all()
        success_count = 0
        for index, image_data in enumerate(image_files):
            if not image_data or not str(image_data).startswith('data:image'):
                continue
            if index >= len(order):
                break
            eq = order[index]
            q = db.session.get(DiagQuestion, eq.question_id)
            if q is None:
                continue
            cloudinary_url = upload_to_cloudinary(image_data)
            if not cloudinary_url:
                continue
            q.solution_image_url = cloudinary_url
            success_count += 1
        if success_count > 0:
            db.session.commit()
        return jsonify({'success': True, 'message': '成功上传 {} 道解析'.format(success_count), 'success_count': success_count})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@diagnostic_admin_bp.route('/import/sample')
@admin_required
def import_csv_sample():
    """下载示例 CSV（UTF-8）"""
    sample_path = os.path.join(current_app.static_folder or 'static', 'diagnostic', 'diagnostic_import_sample.csv')
    if not os.path.isfile(sample_path):
        abort(404)
    return send_file(
        sample_path,
        mimetype='text/csv',
        as_attachment=True,
        download_name='diagnostic_import_sample.csv',
    )


@diagnostic_admin_bp.route('/import', methods=['GET', 'POST'])
@admin_required
def import_csv():
    db = _db()
    (DiagCompetition, DiagExam, DiagQuestion, DiagExamQuestion, DiagKnowledgePoint,
     DiagQuestionTag, DiagBankQuestion, DiagBankQuestionTag, DiagQuestionBankLink,
     DiagQuestionPracticeConfig, *_) = _models()

    if request.method == 'GET':
        return render_template('admin/diagnostic/import.html')

    if 'file' not in request.files or not request.files['file'].filename:
        flash('请选择 CSV 文件', 'error')
        return redirect(url_for('diagnostic_admin.import_csv'))

    file = request.files['file']
    if not file.filename.lower().endswith('.csv'):
        flash('仅支持 UTF-8 CSV 文件', 'error')
        return redirect(url_for('diagnostic_admin.import_csv'))

    try:
        raw = file.read().decode('utf-8-sig').strip()
        reader = csv.DictReader(io.StringIO(raw))
        rows = list(reader)
    except Exception as e:
        flash('解析 CSV 失败：{}'.format(str(e)), 'error')
        return redirect(url_for('diagnostic_admin.import_csv'))

    if not rows:
        flash('CSV 为空或无表头', 'error')
        return redirect(url_for('diagnostic_admin.import_csv'))

    def col(r, *keys, default=''):
        for k in keys:
            if k in r and (r[k] or '').strip():
                return (r[k] or '').strip()
        return default

    created_exams = 0
    updated_questions = 0
    from_exam_id = request.form.get('from_exam') or request.args.get('from_exam')
    from_exam_id = int(from_exam_id) if from_exam_id and str(from_exam_id).isdigit() else None
    exam_from_page = db.session.get(DiagExam, from_exam_id) if from_exam_id else None

    for row_index, row in enumerate(rows):
        if exam_from_page:
            exam = exam_from_page
            comp = db.session.get(DiagCompetition, exam.competition_id)
        else:
            comp_name = col(row, 'competition', 'competition_name', '竞赛')
            exam_title = col(row, 'exam_title', 'exam_title', '试卷标题')
            if not comp_name or not exam_title:
                continue
            comp = db.session.query(DiagCompetition).filter_by(name=comp_name).first()
            if not comp:
                comp = DiagCompetition(name=comp_name)
                db.session.add(comp)
                db.session.flush()
            exam = db.session.query(DiagExam).filter_by(competition_id=comp.id, title=exam_title).first()
            if not exam:
                time_limit = col(row, 'time_limit_sec', 'time_limit')
                exam = DiagExam(
                    competition_id=comp.id,
                    title=exam_title,
                    time_limit_sec=int(time_limit) if time_limit.isdigit() else None,
                    is_published=False,
                )
                db.session.add(exam)
                db.session.flush()
                created_exams += 1

        q_index_val = col(row, 'q_index', 'question_index', '题号')
        if q_index_val == '' or q_index_val is None:
            q_index = row_index
        else:
            try:
                q_index = int(q_index_val)
            except ValueError:
                q_index = row_index
        eq = db.session.query(DiagExamQuestion).filter(DiagExamQuestion.exam_id == exam.id, DiagExamQuestion.q_index == q_index).first()
        if not eq:
            continue
        q = db.session.get(DiagQuestion, eq.question_id)
        if not q:
            continue
        updated_questions += 1

        kp_primary = col(row, 'kp_primary_id', 'kp_primary')
        if kp_primary:
            if not db.session.get(DiagKnowledgePoint, kp_primary):
                db.session.add(DiagKnowledgePoint(kp_id=kp_primary, competition_id=comp.id, name_cn=kp_primary))
                db.session.flush()
            if not db.session.query(DiagQuestionTag).filter_by(question_id=q.id, kp_id=kp_primary).first():
                db.session.add(DiagQuestionTag(question_id=q.id, kp_id=kp_primary, weight=1.0))
        for sec in (col(row, 'kp_secondary_ids', 'kp_secondary') or '').split(','):
            sec = sec.strip()
            if not sec:
                continue
            if not db.session.get(DiagKnowledgePoint, sec):
                db.session.add(DiagKnowledgePoint(kp_id=sec, competition_id=comp.id, name_cn=sec))
                db.session.flush()
            if not db.session.query(DiagQuestionTag).filter_by(question_id=q.id, kp_id=sec).first():
                db.session.add(DiagQuestionTag(question_id=q.id, kp_id=sec, weight=0.5))

        practice_count_default = int(col(row, 'practice_count_default', 'practice_count') or 3)
        config = db.session.query(DiagQuestionPracticeConfig).filter_by(question_id=q.id).first()
        if not config:
            db.session.add(DiagQuestionPracticeConfig(
                question_id=q.id, practice_mode='bank_by_kp', random_count=min(10, max(1, practice_count_default))
            ))
            db.session.flush()

        bank_ids = []
        for i in range(1, 4):
            p_stem = col(row, 'bank_p{}_stem'.format(i), 'p{}_stem'.format(i))
            p_choices = col(row, 'bank_p{}_choices'.format(i), 'p{}_choices'.format(i))
            p_answer = col(row, 'bank_p{}_answer'.format(i), 'p{}_answer'.format(i))
            if not p_stem:
                continue
            bq = DiagBankQuestion(
                competition_id=comp.id,
                stem_text=p_stem,
                choices_json=p_choices or None,
                answer_key=p_answer or None,
            )
            db.session.add(bq)
            db.session.flush()
            bank_ids.append((bq.id, i))
            if kp_primary:
                if not db.session.query(DiagBankQuestionTag).filter_by(bank_question_id=bq.id, kp_id=kp_primary).first():
                    db.session.add(DiagBankQuestionTag(bank_question_id=bq.id, kp_id=kp_primary, weight=1.0))
        for bqid, link_order in bank_ids:
            if not db.session.query(DiagQuestionBankLink).filter_by(question_id=q.id, bank_question_id=bqid).first():
                db.session.add(DiagQuestionBankLink(question_id=q.id, bank_question_id=bqid, link_order=link_order))

    try:
        db.session.commit()
        flash('导入成功：创建试卷 {} 个，更新 {} 题的知识点与练习题集。'.format(created_exams, updated_questions), 'success')
        from_exam = request.form.get('from_exam') or request.args.get('from_exam')
        if from_exam and str(from_exam).isdigit():
            return redirect(url_for('diagnostic_admin.exam_detail', id=int(from_exam), csv_ok=1, updated=updated_questions))
        return redirect(url_for('diagnostic_admin.import_csv'))
    except Exception as e:
        db.session.rollback()
        flash('导入失败：{}'.format(str(e)), 'error')
        from_exam = request.form.get('from_exam') or request.args.get('from_exam')
        if from_exam and str(from_exam).isdigit():
            return redirect(url_for('diagnostic_admin.exam_detail', id=int(from_exam), csv_err=1))
        return redirect(url_for('diagnostic_admin.import_csv'))


@diagnostic_admin_bp.route('/questions/<int:id>/config_save', methods=['POST'])
@admin_required
def question_config_save(id):
    """AJAX：快速保存题目配置（主知识点、章节/作业），不跳转"""
    from flask import jsonify
    db = _db()
    M = _models()
    DiagQuestion, DiagKnowledgePoint, DiagQuestionTag, DiagQuestionPracticeConfig = M[2], M[4], M[5], M[9]
    question = db.session.get(DiagQuestion, id)
    if question is None:
        return jsonify({'success': False, 'message': '题目不存在'}), 404
    try:
        primary_kp = (request.form.get('kp_primary') or '').strip()
        hw_val = (request.form.get('homework_assignment_id') or '').strip()
        hw_id = int(hw_val) if hw_val.isdigit() else None
        practice_mode = request.form.get('practice_mode') or 'bank_by_kp'
        for t in db.session.query(DiagQuestionTag).filter_by(question_id=id).all():
            db.session.delete(t)
        if primary_kp:
            if not db.session.get(DiagKnowledgePoint, primary_kp):
                db.session.add(DiagKnowledgePoint(kp_id=primary_kp, competition_id=question.competition_id, name_cn=primary_kp))
                db.session.flush()
            db.session.add(DiagQuestionTag(question_id=id, kp_id=primary_kp, weight=1.0, manual_override=True))
        config = db.session.query(DiagQuestionPracticeConfig).filter_by(question_id=id).first()
        if not config:
            config = DiagQuestionPracticeConfig(question_id=id)
            db.session.add(config)
            db.session.flush()
        config.practice_mode = practice_mode
        config.random_count = int(request.form.get('random_count') or 3)
        config.homework_assignment_id = hw_id
        config.updated_at = datetime.utcnow()
        db.session.commit()
        return jsonify({'success': True, 'message': '已保存'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@diagnostic_admin_bp.route('/questions/<int:id>', methods=['GET', 'POST'])
@admin_required
def question_config(id):
    db = _db()
    M = _models()
    DiagCompetition, DiagExam, DiagQuestion, DiagExamQuestion, DiagKnowledgePoint = M[0], M[1], M[2], M[3], M[4]
    DiagQuestionTag, DiagBankQuestion, DiagBankQuestionTag, DiagQuestionBankLink, DiagQuestionPracticeConfig = M[5], M[6], M[7], M[8], M[9]
    Lesson, HomeworkQuestion = M[10], M[11]
    question = db.session.get(DiagQuestion, id)
    if question is None:
        abort(404)
    comp = db.session.get(DiagCompetition, question.competition_id)
    kp_list = db.session.query(DiagKnowledgePoint).filter_by(competition_id=question.competition_id).all()
    lessons = db.session.query(Lesson).order_by(Lesson.title).all()

    if request.method == 'POST':
        primary_kp = (request.form.get('kp_primary') or '').strip()
        secondary = (request.form.get('kp_secondary') or '').strip().split(',')[:2]
        secondary = [x.strip() for x in secondary if x.strip()]

        for t in db.session.query(DiagQuestionTag).filter_by(question_id=id).all():
            db.session.delete(t)
        if primary_kp:
            if not db.session.get(DiagKnowledgePoint, primary_kp):
                db.session.add(DiagKnowledgePoint(kp_id=primary_kp, competition_id=question.competition_id, name_cn=primary_kp))
                db.session.flush()
            db.session.add(DiagQuestionTag(question_id=id, kp_id=primary_kp, weight=1.0, manual_override=True))
        for kp in secondary:
            if not db.session.get(DiagKnowledgePoint, kp):
                db.session.add(DiagKnowledgePoint(kp_id=kp, competition_id=question.competition_id, name_cn=kp))
                db.session.flush()
            db.session.add(DiagQuestionTag(question_id=id, kp_id=kp, weight=0.5, manual_override=True))

        config = db.session.query(DiagQuestionPracticeConfig).filter_by(question_id=id).first()
        if not config:
            config = DiagQuestionPracticeConfig(question_id=id)
            db.session.add(config)
            db.session.flush()
        config.practice_mode = request.form.get('practice_mode') or 'bank_by_kp'
        config.random_count = int(request.form.get('random_count') or 3)
        config.is_capstone = request.form.get('is_capstone') == 'on'
        hw_id = request.form.get('homework_assignment_id')
        config.homework_assignment_id = int(hw_id) if hw_id and str(hw_id).isdigit() else None
        config.curated_homework_question_ids = (request.form.get('curated_homework_question_ids') or '').strip() or None
        config.updated_at = datetime.utcnow()
        db.session.commit()
        flash('已保存', 'success')
        return redirect(url_for('diagnostic_admin.question_config', id=id))

    tags = db.session.query(DiagQuestionTag).filter_by(question_id=id).all()
    config = db.session.query(DiagQuestionPracticeConfig).filter_by(question_id=id).first()
    primary_kp = ''
    secondary_kps = []
    for t in tags:
        if t.weight >= 0.99:
            primary_kp = t.kp_id
        else:
            secondary_kps.append(t.kp_id)
    exam_link = db.session.query(DiagExamQuestion).filter(DiagExamQuestion.question_id == id).first()
    bank_items = []
    for link in db.session.query(DiagQuestionBankLink).filter_by(question_id=id).order_by(DiagQuestionBankLink.link_order).all():
        bq = db.session.get(DiagBankQuestion, link.bank_question_id)
        if bq:
            bank_items.append((link.link_order, bq))
    hw_curated_list = []
    if config and config.curated_homework_question_ids:
        for sid in config.curated_homework_question_ids.strip().split(','):
            sid = sid.strip()
            if not sid or not sid.isdigit():
                continue
            hwq = db.session.get(HomeworkQuestion, int(sid))
            hw_curated_list.append((sid, hwq))
    return render_template(
        'admin/diagnostic/question_config.html',
        question=question,
        comp=comp,
        kp_list=kp_list,
        lessons=lessons,
        tags=tags,
        config=config,
        primary_kp=primary_kp,
        secondary_kps=','.join(secondary_kps[:2]),
        exam_id=exam_link.exam_id if exam_link else None,
        bank_items=bank_items,
        hw_curated_list=hw_curated_list,
    )


@diagnostic_admin_bp.route('/search/kp')
@admin_required
def search_kp():
    """搜索主知识点（诊断知识点库）"""
    from flask import jsonify
    db = _db()
    DiagKnowledgePoint = _models()[4]
    q = (request.args.get('q') or '').strip()[:50]
    comp_id = request.args.get('competition_id', type=int)
    query = db.session.query(DiagKnowledgePoint)
    if comp_id:
        query = query.filter_by(competition_id=comp_id)
    if q:
        query = query.filter(
            (DiagKnowledgePoint.kp_id.ilike('%' + q + '%')) |
            (DiagKnowledgePoint.name_cn.ilike('%' + q + '%')) |
            (DiagKnowledgePoint.name_en.ilike('%' + q + '%'))
        )
    items = query.limit(20).all()
    return jsonify([{'id': x.kp_id, 'text': x.name_cn or x.name_en or x.kp_id} for x in items])


@diagnostic_admin_bp.route('/search/lessons')
@admin_required
def search_lessons():
    from flask import jsonify
    db = _db()
    Lesson = _models()[10]
    q = (request.args.get('q') or '').strip()[:50]
    query = db.session.query(Lesson)
    if q:
        query = query.filter(Lesson.title.ilike('%' + q + '%'))
    items = query.order_by(Lesson.title).limit(30).all()
    return jsonify([{'id': x.id, 'text': x.title} for x in items])


def _diag_attempt_quick_stats(att, db):
    """计算 attempt 得分/正确率等。"""
    from app import DiagAttemptAnswer, DiagExamQuestion, DiagCompetition
    from diagnostic.routes import _points_for_exam
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
    total_time_sec = round((att.total_time_ms or 0) / 1000, 0)
    return {'score': score_earned, 'score_max': score_max, 'accuracy_percent': accuracy_percent, 'total': total, 'total_time_sec': total_time_sec}


@diagnostic_admin_bp.route('/diag-users')
@admin_required
def diag_users():
    """测评用户列表。"""
    db = _db()
    from app import DiagUser, DiagAttempt
    users = db.session.query(DiagUser).order_by(DiagUser.created_at.desc()).all()
    attempt_counts = {}
    for u in users:
        cnt = db.session.query(DiagAttempt).filter_by(user_id=u.id, status='finished').count()
        attempt_counts[u.id] = cnt
    return render_template('admin/diagnostic/diag_users.html', users=users, attempt_counts=attempt_counts)


@diagnostic_admin_bp.route('/diag-users/<int:user_id>')
@admin_required
def diag_user_detail(user_id):
    """测评用户详情：试卷、报告等。"""
    db = _db()
    from app import DiagUser, DiagAttempt, DiagExam, DiagCompetition
    user = db.session.get(DiagUser, user_id)
    if not user:
        abort(404)
    attempts = db.session.query(DiagAttempt).filter_by(user_id=user_id).order_by(
        DiagAttempt.finished_at.desc().nullslast(), DiagAttempt.started_at.desc()
    ).all()
    report_items = []
    for att in attempts:
        if att.status == 'finished':
            st = _diag_attempt_quick_stats(att, db)
            exam = att.exam
            comp = getattr(exam, 'competition', None) if exam else None
            comp_name = (getattr(comp, 'name_cn', None) or getattr(comp, 'category', None) or comp.name if comp else None) or 'N/A'
            sub = getattr(att, 'finished_at', None) or getattr(att, 'started_at', None)
            report_items.append({
                'attempt_id': att.id,
                'exam_title': getattr(exam, 'title', None) or 'N/A',
                'competition_name': comp_name,
                'submitted_at_str': sub.strftime('%Y-%m-%d %H:%M') if sub and hasattr(sub, 'strftime') else 'N/A',
                'score': st['score'], 'score_max': st['score_max'], 'accuracy_percent': st['accuracy_percent'],
                'total_time_sec': st['total_time_sec'],
            })
    return render_template('admin/diagnostic/diag_user_detail.html',
        user=user, attempts=attempts, report_items=report_items)


@diagnostic_admin_bp.route('/diag-users/<int:user_id>/toggle-active', methods=['POST'])
@admin_required
def diag_user_toggle_active(user_id):
    """停号/启用。"""
    db = _db()
    from app import DiagUser
    user = db.session.get(DiagUser, user_id)
    if not user:
        abort(404)
    user.is_active = not getattr(user, 'is_active', True)
    db.session.commit()
    flash('已%s该账号' % ('启用' if user.is_active else '停用'), 'success')
    return redirect(url_for('diagnostic_admin.diag_user_detail', user_id=user_id))


@diagnostic_admin_bp.route('/report/<int:attempt_id>')
@admin_required
def admin_report_view(attempt_id):
    """管理员查看任意学员的报告。"""
    db = _db()
    from app import DiagAttempt
    from diagnostic.routes import _build_report_data
    att = db.session.get(DiagAttempt, attempt_id)
    if not att:
        abort(404)
    user = att.user
    report_data = _build_report_data(att, user, db)
    report_data['attempt'] = att
    report_data['chart_radar_labels'] = [r['category'] for r in report_data['kp_radar']]
    report_data['chart_radar_values'] = [r['value_0to100'] for r in report_data['kp_radar']]
    report_data['admin_view'] = True
    return render_template('diagnostic/report.html', **report_data)


@diagnostic_admin_bp.route('/diag-users/<int:user_id>/reset-password', methods=['POST'])
@admin_required
def diag_user_reset_password(user_id):
    """重置密码。"""
    db = _db()
    from app import DiagUser
    user = db.session.get(DiagUser, user_id)
    if not user:
        abort(404)
    new_password = (request.form.get('new_password') or '').strip()
    if not new_password or len(new_password) < 4:
        flash('新密码至少 4 位', 'error')
        return redirect(url_for('diagnostic_admin.diag_user_detail', user_id=user_id))
    user.password_hash = generate_password_hash(new_password, method='pbkdf2:sha256')
    db.session.commit()
    flash('密码已重置', 'success')
    return redirect(url_for('diagnostic_admin.diag_user_detail', user_id=user_id))
