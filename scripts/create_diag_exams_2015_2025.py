# -*- coding: utf-8 -*-
"""
批量创建诊断竞赛试卷 2015-2025 年
- 根据 contest_names.js 中的 CONTEST_BY_CATEGORY
- 每个竞赛每年创建一个 DiagExam，未发布
- 已存在的竞赛和试卷不修改、不覆盖
"""
import os
import sys

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CONTEST_BY_CATEGORY = {
    "滑铁卢数学竞赛": [
        "Gauss 7", "Gauss 8", "Pascal", "Cayley", "Fermat", "Euclid",
        "Fryer", "Galois", "Hypatia", "CIMC", "CSMC", "COMC", "CTMC", "Team Up"
    ],
    "AMC美国数学竞赛": [
        "AMC 8", "AMC 10A", "AMC 10B", "AMC 12A", "AMC 12B", "AIME I", "AIME II", "USAJMO", "USAMO"
    ],
    "UBC数学竞赛": [
        "ELMACON 5 笔试", "ELMACON 5 竞答", "ELMACON 6 笔试", "ELMACON 6 竞答", "ELMACON 7 笔试", "ELMACON 7 竞答",
        "Math Challengers 8 笔试", "Math Challengers 8 竞答", "Math Challengers 9 笔试", "Math Challengers 9 竞答", "Math Challengers 10 笔试", "Math Challengers 10 竞答"
    ]
}

def main():
    from app import app, db, DiagCompetition, DiagExam
    subject = '数学竞赛'
    years = list(range(2015, 2026))  # 2015-2025
    created_comp = 0
    created_exam = 0
    skipped_comp = 0
    skipped_exam = 0
    with app.app_context():
        for category, comp_names in CONTEST_BY_CATEGORY.items():
            for comp_name in comp_names:
                comp = db.session.query(DiagCompetition).filter_by(
                    subject=subject, category=category, name=comp_name
                ).first()
                if not comp:
                    comp = DiagCompetition(subject=subject, category=category, name=comp_name)
                    db.session.add(comp)
                    db.session.flush()
                    created_comp += 1
                else:
                    skipped_comp += 1
                for year in years:
                    title = '%s %s' % (comp_name, year)
                    existing = db.session.query(DiagExam).filter_by(
                        competition_id=comp.id, title=title
                    ).first()
                    if not existing:
                        exam = DiagExam(
                            competition_id=comp.id,
                            title=title,
                            year=year,
                            is_published=False
                        )
                        db.session.add(exam)
                        created_exam += 1
                    else:
                        skipped_exam += 1
        db.session.commit()
    print('Done. Created comps: %d, skipped comps: %d' % (created_comp, skipped_comp))
    print('Created exams: %d, skipped exams: %d' % (created_exam, skipped_exam))

if __name__ == '__main__':
    main()
