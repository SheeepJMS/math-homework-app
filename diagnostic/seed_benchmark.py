# 诊断系统参考样本 seed 数据初始化。仅 diagnostic 使用。
# 运行方式：在项目根目录执行
#   python -m diagnostic.seed_benchmark
# 或由 Flask app context 调用 run_seed_benchmark(app)

# contest_key -> (list of scores, max_score)
BENCHMARK_SEED = {
    'gauss7': ([18, 24, 31, 37, 42, 48, 55, 63, 71, 79, 88, 97, 108, 121, 136], 150),
    'gauss8': ([20, 27, 34, 39, 45, 52, 58, 66, 74, 82, 91, 101, 112, 124, 138], 150),
    'pascal': ([15, 21, 28, 34, 40, 47, 54, 61, 69, 77, 86, 96, 107, 119, 132], 150),
    'cayley': ([12, 18, 24, 30, 36, 43, 50, 58, 66, 75, 85, 96, 108, 121, 135], 150),
    'fermat': ([10, 15, 21, 27, 34, 41, 49, 57, 66, 76, 87, 99, 112, 126, 140], 150),
    'euclid': ([8, 12, 17, 22, 28, 35, 43, 52, 62, 74, 87, 101, 116, 132, 145], 150),
    'fgh': ([18, 26, 34, 42, 50, 59, 68, 78, 89, 101, 114, 128], 150),
    'csmc': ([9, 14, 20, 27, 35, 44, 54, 65, 77, 91, 106, 122], 150),
    'cimc': ([11, 17, 24, 31, 39, 48, 58, 69, 81, 95, 110, 126], 150),
    'ctmc': ([22, 31, 41, 52, 64, 77, 91, 106, 122, 139], 150),
    'amc8': ([4, 5, 6, 7, 8, 9, 10, 12, 13, 15, 17, 19, 21, 23, 24], 25),
    'amc10': ([24, 31, 38, 45, 53, 61, 70, 79, 89, 100, 112, 124, 135, 142, 148], 150),
    'amc12': ([18, 25, 32, 40, 48, 57, 67, 78, 90, 103, 117, 130, 140, 146, 150], 150),
    'aime': ([1, 2, 3, 4, 5, 6, 7, 9, 11, 13], 15),
}


def run_seed_benchmark(db):
    """向 diagnostic_benchmark_samples 写入 seed 数据（若已存在则跳过，避免重复）。"""
    from app import DiagnosticBenchmarkSample
    existing = db.session.query(DiagnosticBenchmarkSample).filter(
        DiagnosticBenchmarkSample.source_type == 'seed'
    ).count()
    if existing > 0:
        return existing, 0
    added = 0
    for contest_key, (scores, max_score) in BENCHMARK_SEED.items():
        for s in scores:
            row = DiagnosticBenchmarkSample(
                contest_key=contest_key,
                score=float(s),
                max_score=float(max_score),
                source_type='seed',
                is_active=True,
            )
            db.session.add(row)
            added += 1
    db.session.commit()
    return 0, added


if __name__ == '__main__':
    import sys
    sys.path.insert(0, '.')
    from app import app, db
    with app.app_context():
        before, added = run_seed_benchmark(db)
        print('Seed benchmark: existing=%s, added=%s' % (before, added))
