#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入模型
from app import app, db, User, Class, Lesson, Question, QuizHistory, UserAnswer

def quick_init():
    """快速初始化数据库"""
    with app.app_context():
        try:
            print("开始快速初始化数据库...")
            
            # 创建所有表
            db.create_all()
            print("✅ 数据库表创建成功")
            
            # 检查管理员是否存在
            admin = User.query.filter_by(username='admin').first()
            if not admin:
                # 创建默认管理员
                admin = User(
                    username='admin',
                    email='admin@example.com',
                    is_admin=True,
                    badge_level=0,
                    achievement_count=0
                )
                admin.set_password('admin123')
                db.session.add(admin)
                print("✅ 创建默认管理员账户: admin/admin123")
            else:
                print("✅ 管理员账户已存在")
            
            # 检查是否有班级
            if not Class.query.first():
                # 创建默认班级
                default_class = Class(
                    name='默认班级',
                    description='系统默认班级',
                    is_active=True
                )
                db.session.add(default_class)
                print("✅ 创建默认班级")
            
            # 提交所有更改
            db.session.commit()
            print("✅ 数据库初始化完成！")
            print("✅ 管理员账户: admin / admin123")
            print("✅ 现在可以访问网站重新添加数据了")
            
        except Exception as e:
            print(f"❌ 初始化失败: {str(e)}")
            db.session.rollback()

if __name__ == '__main__':
    quick_init()






