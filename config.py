import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'python-teaching-website-secret-key'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///database.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 代码执行配置
    CODE_EXECUTION_TIMEOUT = 5  # 秒
