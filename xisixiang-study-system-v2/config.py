'''
@Project: config.py
@Author: 郗禄辉
@Date: 2025/6/22 14:29
'''

import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or os.urandom(24).hex()
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///site.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')
    ADMIN_DISPLAY_NAME = os.environ.get('ADMIN_DISPLAY_NAME', '管理员')
    QUESTIONS_FILE = os.environ.get('QUESTIONS_FILE', 'data/questions.txt')
    PER_PAGE = int(os.environ.get('PER_PAGE', 20))