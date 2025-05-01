from app import app, db, User, Class, Lesson, Question

with app.app_context():
    # 查看所有班级
    print("\n所有班级：")
    classes = Class.query.all()
    for c in classes:
        print(f"ID: {c.id}, 名称: {c.name}, 描述: {c.description}, 是否激活: {c.is_active}")

    # 查看所有用户
    print("\n所有用户：")
    users = User.query.all()
    for u in users:
        print(f"ID: {u.id}, 用户名: {u.username}, 邮箱: {u.email}, 班级ID: {u.class_id}, 是否激活: {u.is_active}, 是否是管理员: {u.is_admin}")

    print("\n所有课程：")
    lessons = Lesson.query.all()
    for l in lessons:
        print(f"ID: {l.id}, 标题: {l.title}, 描述: {l.description}, 是否激活: {l.is_active}")
        
        print("  题目：")
        questions = Question.query.filter_by(lesson_id=l.id).order_by(Question.question_number).all()
        for q in questions:
            print(f"    题号: {q.question_number}, 类型: {q.type}, 答案: {q.answer}") 