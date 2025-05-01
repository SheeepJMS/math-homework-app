from app import app, db, Class, User

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
        print(f"ID: {u.id}, 用户名: {u.username}, 姓名: {u.name}, 班级ID: {u.class_id}, 是否激活: {u.is_active}, 是否是管理员: {u.is_admin}") 