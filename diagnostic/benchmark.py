# 诊断系统参考样本分布服务。仅 diagnostic 使用，不影响作业网站。
# 冷启动用 seed；真实数据够多后可逐步替代。

from datetime import datetime


def get_benchmark_summary(contest_key, student_score, db):
    """
    根据 contest_key 与当前学生得分，返回参考样本统计。
    - 优先 real；real 不足 20 则 real+seed 混合；无 real 则仅 seed。
    返回: sample_count, mean_score, median_score, percentile_estimate, source_mode
    """
    from app import DiagnosticBenchmarkSample
    from diagnostic.seed_benchmark import run_seed_benchmark
    if not contest_key or student_score is None:
        return None
    contest_key = str(contest_key).strip().lower()
    real_rows = db.session.query(DiagnosticBenchmarkSample).filter(
        DiagnosticBenchmarkSample.contest_key == contest_key,
        DiagnosticBenchmarkSample.source_type == 'real',
        DiagnosticBenchmarkSample.is_active == True,
    ).all()
    seed_rows = db.session.query(DiagnosticBenchmarkSample).filter(
        DiagnosticBenchmarkSample.contest_key == contest_key,
        DiagnosticBenchmarkSample.source_type == 'seed',
        DiagnosticBenchmarkSample.is_active == True,
    ).all()
    scores = []
    source_mode = 'seed'
    if len(real_rows) >= 20:
        scores = [r.score for r in real_rows]
        source_mode = 'real'
    elif len(real_rows) > 0:
        scores = [r.score for r in real_rows] + [r.score for r in seed_rows]
        source_mode = 'mixed'
    else:
        scores = [r.score for r in seed_rows]
    if not scores:
        # 冷启动：若尚无任何样本，执行一次 seed 后重试
        run_seed_benchmark(db)
        real_rows = db.session.query(DiagnosticBenchmarkSample).filter(
            DiagnosticBenchmarkSample.contest_key == contest_key,
            DiagnosticBenchmarkSample.source_type == 'real',
            DiagnosticBenchmarkSample.is_active == True,
        ).all()
        seed_rows = db.session.query(DiagnosticBenchmarkSample).filter(
            DiagnosticBenchmarkSample.contest_key == contest_key,
            DiagnosticBenchmarkSample.source_type == 'seed',
            DiagnosticBenchmarkSample.is_active == True,
        ).all()
        if len(real_rows) >= 20:
            scores = [r.score for r in real_rows]
            source_mode = 'real'
        elif len(real_rows) > 0:
            scores = [r.score for r in real_rows] + [r.score for r in seed_rows]
            source_mode = 'mixed'
        else:
            scores = [r.score for r in seed_rows]
    if not scores:
        return None
    scores_sorted = sorted(scores)
    n = len(scores_sorted)
    mean_score = round(sum(scores) / n, 1)
    mid = n // 2
    median_score = round((scores_sorted[mid] if n % 2 else (scores_sorted[mid - 1] + scores_sorted[mid]) / 2), 1)
    # 粗略百分位：比当前分数低（严格小于）的比例
    count_below = sum(1 for s in scores_sorted if s < student_score)
    percentile_estimate = round(100.0 * count_below / n, 1)
    return {
        'sample_count': n,
        'mean_score': mean_score,
        'median_score': median_score,
        'percentile_estimate': percentile_estimate,
        'source_mode': source_mode,
    }


def sync_real_attempt_to_benchmark(attempt, db):
    """
    预留：未来当学生完成真实试卷后，将成绩写入 diagnostic_benchmark_samples(source_type='real')。
    当前不自动批量回填旧数据，仅预留接口。
    """
    # from app import DiagnosticBenchmarkSample
    # from diagnostic.roadmap_config import infer_contest_key
    # exam = getattr(attempt, 'exam', None)
    # if not exam:
    #     return
    # comp = getattr(exam, 'competition', None)
    # comp_name = getattr(comp, 'name', None) if comp else None
    # exam_title = getattr(exam, 'title', None) or ''
    # contest_key = infer_contest_key(comp_name, exam_title)
    # if not contest_key:
    #     return
    # st = _attempt_quick_stats(attempt, db)  # 需要从 routes 传入或复用
    # score, score_max = st.get('score', 0), st.get('score_max', 1)
    # row = DiagnosticBenchmarkSample(
    #     contest_key=contest_key.lower(),
    #     score=float(score),
    #     max_score=float(score_max),
    #     source_type='real',
    #     is_active=True,
    # )
    # db.session.add(row)
    # db.session.commit()
    pass
