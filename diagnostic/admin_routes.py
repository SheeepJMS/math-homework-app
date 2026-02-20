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
        DiagQuestionPracticeConfig, DiagQuestionAnswer, DiagQuestionKp,
        DiagQuestionPracticeItem, DiagExamQuestionPracticeConfig,
        Lesson, Question as HomeworkQuestion,
    )
    return (DiagCompetition, DiagExam, DiagQuestion, DiagExamQuestion, DiagKnowledgePoint,
            DiagQuestionTag, DiagBankQuestion, DiagBankQuestionTag, DiagQuestionBankLink,
            DiagQuestionPracticeConfig, DiagQuestionAnswer, DiagQuestionKp,
            DiagQuestionPracticeItem, DiagExamQuestionPracticeConfig,
            Lesson, HomeworkQuestion)


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


def _exam_image_status(db):
    """返回 {exam_id: 'ok'|'need'}：绿色=图齐全，红色=有题需补图"""
    from app import DiagExamQuestion, DiagQuestionAnswer, DiagQuestion
    status = {}
    # 注意：reserved_1 是 SQLAlchemy 列对象，不能在 filter 里对它调用 .strip()
    needs_img = db.session.query(DiagQuestionAnswer).filter(
        DiagQuestionAnswer.reserved_1 == '1'
    ).all()
    for ans in needs_img:
        eq = db.session.query(DiagExamQuestion).filter_by(
            exam_id=ans.exam_id, q_index=ans.q_index
        ).first()
        if not eq:
            continue
        q = db.session.get(DiagQuestion, eq.question_id)
        has_img = q and (q.stem_image_url or q.solution_image_url)
        eid = ans.exam_id
        if eid not in status:
            status[eid] = 'ok'
        if not has_img:
            status[eid] = 'need'
    return status


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
    exam_image_status = _exam_image_status(db)
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
        exam_image_status=exam_image_status,
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
    DiagQuestionAnswer, DiagQuestionKp, DiagQuestionPracticeConfig, Lesson = M[10], M[11], M[9], M[14]
    exam = db.session.get(DiagExam, id)
    if exam is None:
        abort(404)
    order = db.session.query(DiagExamQuestion).filter(DiagExamQuestion.exam_id == id).order_by(DiagExamQuestion.q_index).all()
    questions = [db.session.get(DiagQuestion, eq.question_id) for eq in order]
    kp_list = db.session.query(DiagKnowledgePoint).filter_by(competition_id=exam.competition_id).all()
    lessons = db.session.query(Lesson).order_by(Lesson.title).all()
    imported_answers = {r.q_index: r for r in db.session.query(DiagQuestionAnswer).filter_by(exam_id=id).all()}
    imported_kp = {r.q_index: r for r in db.session.query(DiagQuestionKp).filter_by(exam_id=id).all()}
    q_tags = {}  # question_id -> {primary: str, secondary: str}
    q_config = {}  # question_id -> config
    lesson_titles = {l.id: l.title for l in lessons}
    for eq in order:
        q = db.session.get(DiagQuestion, eq.question_id)
        if not q:
            continue
        primary, secondary = '', ''
        kp_row = imported_kp.get(eq.q_index)
        if kp_row and kp_row.kp_primary:
            primary = kp_row.kp_primary
            sec_parts = [x.strip() for x in (kp_row.kp_secondary or '').replace('\uff1b', ',').replace(';', ',').split(',') if x.strip()][:2]
            secondary = ','.join(sec_parts)
        q_tags[q.id] = {'primary': primary, 'secondary': secondary}
        cfg = db.session.query(DiagQuestionPracticeConfig).filter_by(question_id=q.id).first()
        hw_id = cfg.homework_assignment_id if cfg and cfg.homework_assignment_id else None
        q_config[q.id] = {
            'config': cfg,
            'homework_assignment_id': hw_id,
            'homework_title': lesson_titles.get(hw_id, '') if hw_id else '',
        }
    return render_template('admin/diagnostic/exam_detail.html',
        exam=exam, order=order, questions=questions,
        imported_answers=imported_answers, kp_list=kp_list, lessons=lessons, q_tags=q_tags, q_config=q_config)


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


@diagnostic_admin_bp.route('/competitions/<int:comp_id>/bulk_publish', methods=['POST'])
@admin_required
def competition_bulk_publish(comp_id):
    """该竞赛下全部年份试卷一键发布"""
    db = _db()
    DiagCompetition, DiagExam = _models()[0], _models()[1]
    comp = db.session.get(DiagCompetition, comp_id)
    if comp is None:
        abort(404)
    exams = db.session.query(DiagExam).filter_by(competition_id=comp_id).all()
    for e in exams:
        e.is_published = True
    db.session.commit()
    flash('已发布「{}」下 {} 份试卷'.format(comp.name, len(exams)), 'success')
    return redirect(url_for('diagnostic_admin.exams'))


@diagnostic_admin_bp.route('/competitions/<int:comp_id>/bulk_unpublish', methods=['POST'])
@admin_required
def competition_bulk_unpublish(comp_id):
    """该竞赛下全部年份试卷一键取消发布"""
    db = _db()
    DiagCompetition, DiagExam = _models()[0], _models()[1]
    comp = db.session.get(DiagCompetition, comp_id)
    if comp is None:
        abort(404)
    exams = db.session.query(DiagExam).filter_by(competition_id=comp_id).all()
    for e in exams:
        e.is_published = False
    db.session.commit()
    flash('已取消发布「{}」下 {} 份试卷'.format(comp.name, len(exams)), 'success')
    return redirect(url_for('diagnostic_admin.exams'))


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
    DiagQuestionAnswer, DiagQuestionKp, DiagQuestionPracticeItem, DiagExamQuestionPracticeConfig = M[10], M[11], M[12], M[13]
    question = db.session.get(DiagQuestion, id)
    if question is None:
        abort(404)
    eq = db.session.query(DiagExamQuestion).filter(DiagExamQuestion.question_id == id).first()
    if eq:
        db.session.query(DiagQuestionAnswer).filter_by(exam_id=eq.exam_id, q_index=eq.q_index).delete()
        db.session.query(DiagQuestionKp).filter_by(exam_id=eq.exam_id, q_index=eq.q_index).delete()
        db.session.query(DiagQuestionPracticeItem).filter_by(exam_id=eq.exam_id, q_index=eq.q_index).delete()
        db.session.query(DiagExamQuestionPracticeConfig).filter_by(exam_id=eq.exam_id, q_index=eq.q_index).delete()
    db.session.query(DiagQuestionTag).filter(DiagQuestionTag.question_id == id).delete()
    db.session.query(DiagQuestionPracticeConfig).filter(DiagQuestionPracticeConfig.question_id == id).delete()
    db.session.query(DiagQuestionBankLink).filter(DiagQuestionBankLink.question_id == id).delete()
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


@diagnostic_admin_bp.route('/exams/<int:id>/upload_question_images_bulk', methods=['POST'])
@admin_required
def upload_question_images_bulk(id):
    """批量模式：按题目逐行粘贴的题干图、解析图，写入对应 DiagQuestion"""
    from flask import jsonify
    from app import upload_to_cloudinary
    db = _db()
    DiagExam, DiagQuestion, DiagExamQuestion = _models()[1], _models()[2], _models()[3]
    exam = db.session.get(DiagExam, id)
    if exam is None:
        abort(404)
    try:
        data = request.get_json()
        items = data.get('items') if isinstance(data, dict) else []
        if not items:
            return jsonify({'success': False, 'message': '没有接收到图片数据'}), 400
        success_stem, success_solution = 0, 0
        for it in items:
            qid = it.get('question_id')
            if not qid:
                continue
            q = db.session.get(DiagQuestion, int(qid))
            if q is None:
                continue
            eq = db.session.query(DiagExamQuestion).filter_by(
                exam_id=id, question_id=q.id
            ).first()
            if not eq:
                continue
            stem_data = it.get('stem_image')
            if stem_data and str(stem_data).startswith('data:image'):
                url = upload_to_cloudinary(stem_data)
                if url:
                    q.stem_image_url = url
                    success_stem += 1
            sol_data = it.get('solution_image')
            if sol_data and str(sol_data).startswith('data:image'):
                url = upload_to_cloudinary(sol_data)
                if url:
                    q.solution_image_url = url
                    success_solution += 1
        if success_stem > 0 or success_solution > 0:
            db.session.commit()
        msg = '成功添加'
        parts = []
        if success_stem:
            parts.append('{} 题题干图'.format(success_stem))
        if success_solution:
            parts.append('{} 题解析图'.format(success_solution))
        if parts:
            msg += '：' + '、'.join(parts)
        return jsonify({'success': True, 'message': msg})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


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
    """重定向到增强版模板（旧入口保留兼容）"""
    return redirect(url_for('diagnostic_admin.import_csv_enhanced_sample'))


@diagnostic_admin_bp.route('/csv_format')
@admin_required
def csv_format():
    """CSV 格式说明页"""
    return render_template('admin/diagnostic/csv_format.html')


@diagnostic_admin_bp.route('/import_csv_enhanced/sample')
@admin_required
def import_csv_enhanced_sample():
    """下载增强版 CSV 模板（答案 + 知识点 + 错题练习集 5-8 题）"""
    sample_path = os.path.join(current_app.static_folder or 'static', 'diagnostic', 'diagnostic_import_enhanced_sample.csv')
    if not os.path.isfile(sample_path):
        abort(404)
    return send_file(
        sample_path,
        mimetype='text/csv',
        as_attachment=True,
        download_name='diagnostic_import_enhanced_sample.csv',
    )


def _col(row, *keys, default=''):
    for k in keys:
        if k in row and (row[k] or '').strip():
            return (row[k] or '').strip()
    return default


def _parse_enhanced_csv(raw):
    """解析增强 CSV，返回 (rows, errors)。errors 为 [(row_index, msg), ...]"""
    errors = []
    rows = []
    try:
        reader = csv.DictReader(io.StringIO(raw))
        fieldnames = reader.fieldnames or []
        for i, row in enumerate(reader):
            row_errors = []
            comp_name = _col(row, 'competition_name', 'competition')
            exam_title = _col(row, 'exam_title', 'exam_title')
            exam_id_val = _col(row, 'exam_id')
            q_index_val = _col(row, 'q_index', 'question_index', '题号')
            if not comp_name and not exam_id_val:
                row_errors.append('缺少 competition_name 或 exam_id')
            if not exam_title and not exam_id_val:
                row_errors.append('缺少 exam_title 或 exam_id')
            if q_index_val == '':
                row_errors.append('缺少 q_index')
            try:
                q_idx = int(q_index_val) if q_index_val else i + 1
                if q_idx >= 1:
                    q_idx -= 1
            except ValueError:
                q_idx = i
                row_errors.append('q_index 非整数，使用行序')
            practice_count = 3
            try:
                pc = _col(row, 'practice_count_default') or '3'
                practice_count = max(1, min(10, int(pc)))
            except ValueError:
                pass
            practice_pool = []
            for j in range(1, 9):
                stem = _col(row, 'p{}_stem'.format(j))
                answer = _col(row, 'p{}_answer'.format(j))
                if stem and answer:
                    choices = _col(row, 'p{}_choices'.format(j))
                    explain = _col(row, 'p{}_explain'.format(j))
                    source = _col(row, 'p{}_source'.format(j)) or 'generated'
                    practice_pool.append({
                        'stem': stem, 'choices': choices, 'answer': answer, 'explain': explain, 'source': source,
                    })
            pool_size_val = _col(row, 'practice_pool_size')
            if pool_size_val:
                try:
                    ps = int(pool_size_val)
                    if len(practice_pool) < max(5, ps):
                        row_errors.append('练习题少于 5 道或 practice_pool_size')
                except ValueError:
                    pass
            if len(practice_pool) < 5 and practice_pool:
                row_errors.append('练习题至少需 5 道（当前 {} 道）'.format(len(practice_pool)))
            if practice_count > len(practice_pool) and practice_pool:
                row_errors.append('practice_count_default({}) 不能大于练习题数({})'.format(practice_count, len(practice_pool)))
            for e in row_errors:
                errors.append((i + 2, e))
            stem_text_val = _col(row, 'stem_text', 'stem')
            needs_image_val = _col(row, 'needs_image', 'has_image', '有图')
            needs_image = str(needs_image_val).lower() in ('1', 'yes', 'true', '有', '有图', 'y', '需要')
            rows.append({
                'comp_name': comp_name,
                'exam_title': exam_title,
                'exam_id': exam_id_val,
                'q_index': q_idx,
                'stem_text': stem_text_val,
                'correct_answer': _col(row, 'correct_answer'),
                'solution_explain': _col(row, 'solution_explain'),
                'answer_format': _col(row, 'answer_format') or 'mcq',
                'kp_primary': _col(row, 'kp_primary'),
                'kp_secondary': _col(row, 'kp_secondary'),
                'needs_image': needs_image,
                'reserved_1': _col(row, 'reserved_1'),
                'reserved_2': _col(row, 'reserved_2'),
                'reserved_3': _col(row, 'reserved_3'),
                'practice_count_default': practice_count,
                'practice_pool': practice_pool,
                'row': row,
            })
    except Exception as e:
        errors.append((0, '解析失败: {}'.format(str(e))))
    return rows, errors


def _write_csv_rows(db, rows, M, force_exam_id=None):
    """将解析后的 CSV 行写入数据库，返回成功更新的题数。不提交，由调用方 commit。
    force_exam_id: 若提供（如从试卷详情页上传），则所有行强制使用该试卷，忽略 CSV 的 competition_name/exam_title。"""
    DiagCompetition, DiagExam, DiagQuestion, DiagExamQuestion = M[0], M[1], M[2], M[3]
    DiagQuestionAnswer, DiagQuestionKp, DiagQuestionPracticeItem, DiagExamQuestionPracticeConfig = M[10], M[11], M[12], M[13]
    updated = 0
    forced_exam = None
    if force_exam_id and str(force_exam_id).isdigit():
        forced_exam = db.session.get(DiagExam, int(force_exam_id))
    for r in rows:
        exam = forced_exam
        q_index = r['q_index']
        if exam is None:
            comp_name = r['comp_name']
            exam_title = r['exam_title']
            exam_id_val = r['exam_id']
            if not comp_name and not exam_id_val:
                continue
            comp = db.session.query(DiagCompetition).filter(DiagCompetition.name == comp_name).first() if comp_name else None
            if not comp and exam_id_val:
                exam = db.session.get(DiagExam, int(exam_id_val)) if str(exam_id_val).isdigit() else None
                if exam:
                    comp = db.session.get(DiagCompetition, exam.competition_id)
            if not comp and exam is None:
                continue
            if exam is None:
                if exam_id_val and str(exam_id_val).isdigit():
                    exam = db.session.get(DiagExam, int(exam_id_val))
                if not exam and comp:
                    exam = db.session.query(DiagExam).filter_by(
                        competition_id=comp.id, title=exam_title
                    ).first()
            if not exam:
                continue
        eq = db.session.query(DiagExamQuestion).filter_by(
            exam_id=exam.id, q_index=q_index
        ).first()
        if not eq and forced_exam and (r.get('stem_text') or '').strip():
            q = DiagQuestion(
                competition_id=exam.competition_id,
                stem_text=(r.get('stem_text') or '').strip(),
                stem_image_url=None,
                choices_json=None,
                answer_key=r.get('correct_answer') or None,
                solution_text=r.get('solution_explain') or None,
                solution_image_url=None,
            )
            db.session.add(q)
            db.session.flush()
            eq = DiagExamQuestion(exam_id=exam.id, question_id=q.id, q_index=q_index)
            db.session.add(eq)
            db.session.flush()
        elif not eq:
            continue
        updated += 1
        needs_img = bool(r.get('needs_image', False))
        res1 = '1' if needs_img else (r.get('reserved_1') or None)
        res2, res3 = r.get('reserved_2') or None, r.get('reserved_3') or None
        ans_row = db.session.query(DiagQuestionAnswer).filter_by(
            exam_id=exam.id, q_index=q_index
        ).first()
        if ans_row:
            ans_row.correct_answer = r['correct_answer'] or None
            ans_row.solution_explain = r['solution_explain'] or None
            ans_row.answer_format = r['answer_format'] or None
            ans_row.reserved_1, ans_row.reserved_2, ans_row.reserved_3 = res1, res2, res3
        else:
            db.session.add(DiagQuestionAnswer(
                exam_id=exam.id, q_index=q_index,
                correct_answer=r['correct_answer'] or None,
                solution_explain=r['solution_explain'] or None,
                answer_format=r['answer_format'] or None,
                reserved_1=res1, reserved_2=res2, reserved_3=res3,
            ))
        kp_row = db.session.query(DiagQuestionKp).filter_by(
            exam_id=exam.id, q_index=q_index
        ).first()
        if kp_row:
            kp_row.kp_primary = r['kp_primary'] or None
            kp_row.kp_secondary = r['kp_secondary'] or None
            kp_row.reserved_1, kp_row.reserved_2, kp_row.reserved_3 = res1, res2, res3
        else:
            db.session.add(DiagQuestionKp(
                exam_id=exam.id, q_index=q_index,
                kp_primary=r['kp_primary'] or None,
                kp_secondary=r['kp_secondary'] or None,
                reserved_1=res1, reserved_2=res2, reserved_3=res3,
            ))
        cfg_row = db.session.query(DiagExamQuestionPracticeConfig).filter_by(
            exam_id=exam.id, q_index=q_index
        ).first()
        if cfg_row:
            cfg_row.practice_count_default = r['practice_count_default']
            cfg_row.reserved_1, cfg_row.reserved_2, cfg_row.reserved_3 = res1, res2, res3
        else:
            db.session.add(DiagExamQuestionPracticeConfig(
                exam_id=exam.id, q_index=q_index,
                practice_count_default=r['practice_count_default'],
                reserved_1=res1, reserved_2=res2, reserved_3=res3,
            ))
        db.session.query(DiagQuestionPracticeItem).filter_by(
            exam_id=exam.id, q_index=q_index
        ).delete()
        for idx, p in enumerate(r['practice_pool']):
            db.session.add(DiagQuestionPracticeItem(
                exam_id=exam.id, q_index=q_index, item_index=idx + 1,
                stem=p['stem'], choices=p.get('choices'),
                answer=p.get('answer'), explain=p.get('explain'),
                source=p.get('source'),
            ))
    return updated


@diagnostic_admin_bp.route('/import_csv_enhanced', methods=['GET', 'POST'])
@admin_required
def import_csv_enhanced():
    """增强版 CSV 导入：答案 + 知识点 + 错题练习集（5-8 题），支持预览与确认写入"""
    from flask import jsonify, session
    db = _db()
    M = _models()
    (DiagCompetition, DiagExam, DiagQuestion, DiagExamQuestion,
     DiagQuestionAnswer, DiagQuestionKp, DiagQuestionPracticeItem,
     DiagExamQuestionPracticeConfig) = (
        M[0], M[1], M[2], M[3], M[10], M[11], M[12], M[13],
    )

    if request.method == 'GET':
        return render_template('admin/diagnostic/import_enhanced.html')

    if request.form.get('action') != 'confirm_write':
        if 'file' not in request.files or not request.files['file'].filename:
            flash('请选择 CSV 文件', 'error')
            return redirect(url_for('diagnostic_admin.import_csv_enhanced'))
        file = request.files['file']
        if not file.filename.lower().endswith('.csv'):
            flash('仅支持 UTF-8 CSV 文件', 'error')
            return redirect(url_for('diagnostic_admin.import_csv_enhanced'))
        try:
            raw = file.read().decode('utf-8-sig').strip()
        except Exception as e:
            flash('读取文件失败：{}'.format(str(e)), 'error')
            return redirect(url_for('diagnostic_admin.import_csv_enhanced'))
        rows, parse_errors = _parse_enhanced_csv(raw)
        if not rows and not parse_errors:
            flash('CSV 为空或无表头', 'error')
            return redirect(url_for('diagnostic_admin.import_csv_enhanced'))

        from_exam = request.form.get('from_exam') or request.args.get('from_exam')
        if from_exam and str(from_exam).isdigit():
            updated = _write_csv_rows(db, rows, M, force_exam_id=int(from_exam))
            try:
                db.session.commit()
                flash('导入成功，已更新 {} 题。'.format(updated), 'success')
                return redirect(url_for('diagnostic_admin.exam_detail', id=int(from_exam), csv_ok=1, updated=updated))
            except Exception as e:
                db.session.rollback()
                flash('导入失败：{}'.format(str(e)), 'error')
                return redirect(url_for('diagnostic_admin.exam_detail', id=int(from_exam), csv_err=1))

        session['csv_import_preview_rows'] = [{k: v for k, v in r.items() if k != 'row'} for r in rows]
        return render_template('admin/diagnostic/import_enhanced.html',
            preview=True,
            rows=rows,
            parse_errors=parse_errors,
        )

    if request.form.get('action') == 'confirm_write':
        rows = session.pop('csv_import_preview_rows', None)
        if not rows:
            flash('预览已过期，请重新上传 CSV 文件', 'error')
            return redirect(url_for('diagnostic_admin.import_csv_enhanced'))
        from_exam_confirm = request.args.get('from_exam') or request.form.get('from_exam')
        force_id = int(from_exam_confirm) if from_exam_confirm and str(from_exam_confirm).isdigit() else None
        updated = _write_csv_rows(db, rows, M, force_exam_id=force_id)
        try:
            db.session.commit()
            flash('导入成功，已更新 {} 题。'.format(updated), 'success')
            from_exam = request.args.get('from_exam') or request.form.get('from_exam')
            if from_exam and str(from_exam).isdigit():
                return redirect(url_for('diagnostic_admin.exam_detail', id=int(from_exam), csv_ok=1, updated=updated))
            return redirect(url_for('diagnostic_admin.import_csv_enhanced'))
        except Exception as e:
            db.session.rollback()
            flash('写入失败：{}'.format(str(e)), 'error')
            session['csv_import_preview_rows'] = rows
            return redirect(url_for('diagnostic_admin.import_csv_enhanced'))


@diagnostic_admin_bp.route('/import', methods=['GET', 'POST'])
@admin_required
def import_csv():
    """重定向到增强版导入（旧入口保留兼容）"""
    from_exam = request.args.get('from_exam') or request.form.get('from_exam')
    target = url_for('diagnostic_admin.import_csv_enhanced')
    if from_exam:
        target += '?from_exam=' + str(from_exam)
    return redirect(target)


@diagnostic_admin_bp.route('/questions/<int:id>/config_save', methods=['POST'])
@admin_required
def question_config_save(id):
    """AJAX：快速保存题目配置（主知识点），写入 DiagQuestionKp"""
    from flask import jsonify
    db = _db()
    M = _models()
    DiagQuestion, DiagKnowledgePoint, DiagExamQuestion, DiagQuestionKp, DiagQuestionPracticeConfig = M[2], M[4], M[3], M[11], M[9]
    question = db.session.get(DiagQuestion, id)
    if question is None:
        return jsonify({'success': False, 'message': '题目不存在'}), 404
    try:
        primary_kp = (request.form.get('kp_primary') or '').strip()
        secondary_raw = (request.form.get('kp_secondary') or '').strip().split(',')[:2]
        secondary = ','.join([x.strip() for x in secondary_raw if x.strip()])
        exam_link = db.session.query(DiagExamQuestion).filter(DiagExamQuestion.question_id == id).first()
        if exam_link:
            if primary_kp and not db.session.get(DiagKnowledgePoint, primary_kp):
                db.session.add(DiagKnowledgePoint(kp_id=primary_kp, competition_id=question.competition_id, name_cn=primary_kp))
                db.session.flush()
            kp_row = db.session.query(DiagQuestionKp).filter_by(exam_id=exam_link.exam_id, q_index=exam_link.q_index).first()
            if kp_row:
                kp_row.kp_primary = primary_kp or None
                kp_row.kp_secondary = secondary or None
            else:
                db.session.add(DiagQuestionKp(exam_id=exam_link.exam_id, q_index=exam_link.q_index, kp_primary=primary_kp or None, kp_secondary=secondary or None))
        config = db.session.query(DiagQuestionPracticeConfig).filter_by(question_id=id).first()
        if config:
            hw_val = (request.form.get('homework_assignment_id') or '').strip()
            hw_id = int(hw_val) if hw_val.isdigit() else None
            config.practice_mode = request.form.get('practice_mode') or 'bank_by_kp'
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
    DiagQuestionPracticeConfig = M[9]
    DiagQuestionAnswer, DiagQuestionPracticeItem, DiagQuestionKp = M[10], M[12], M[11]
    Lesson = M[14]
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

        exam_link_for_post = db.session.query(DiagExamQuestion).filter(DiagExamQuestion.question_id == id).first()
        if exam_link_for_post:
            kp_row = db.session.query(DiagQuestionKp).filter_by(exam_id=exam_link_for_post.exam_id, q_index=exam_link_for_post.q_index).first()
            if kp_row:
                kp_row.kp_primary = primary_kp or None
                kp_row.kp_secondary = ','.join(secondary) if secondary else None
            else:
                db.session.add(DiagQuestionKp(exam_id=exam_link_for_post.exam_id, q_index=exam_link_for_post.q_index, kp_primary=primary_kp or None, kp_secondary=','.join(secondary) if secondary else None))

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

    config = db.session.query(DiagQuestionPracticeConfig).filter_by(question_id=id).first()
    exam_link = db.session.query(DiagExamQuestion).filter(DiagExamQuestion.question_id == id).first()
    primary_kp, secondary_kps = '', []
    csv_practice_items = []
    csv_kp = None
    needs_image = False
    if exam_link:
        csv_kp = db.session.query(DiagQuestionKp).filter_by(exam_id=exam_link.exam_id, q_index=exam_link.q_index).first()
        if csv_kp and csv_kp.kp_primary:
            primary_kp = csv_kp.kp_primary
            sec_raw = (csv_kp.kp_secondary or '').replace('\uff1b', ',').replace(';', ',').split(',')
            secondary_kps = [x.strip() for x in sec_raw if x.strip()][:2]
        csv_practice_items = db.session.query(DiagQuestionPracticeItem).filter_by(
            exam_id=exam_link.exam_id, q_index=exam_link.q_index
        ).order_by(DiagQuestionPracticeItem.item_index).all()
        csv_answer = db.session.query(DiagQuestionAnswer).filter_by(
            exam_id=exam_link.exam_id, q_index=exam_link.q_index
        ).first()
        if csv_answer and (csv_answer.reserved_1 or '').strip() == '1':
            needs_image = True
    return render_template(
        'admin/diagnostic/question_config.html',
        question=question,
        comp=comp,
        kp_list=kp_list,
        lessons=lessons,
        config=config,
        primary_kp=primary_kp,
        secondary_kps=','.join(secondary_kps[:2]),
        exam_id=exam_link.exam_id if exam_link else None,
        csv_practice_items=csv_practice_items,
        needs_image=needs_image,
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
    Lesson = _models()[14]
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
