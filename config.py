import os


def _resolve_db_path():
    db_path = os.environ.get("SCF_DB_PATH")
    if db_path:
        return db_path
    return os.path.join("/data", "database.db")


def _build_sqlite_uri(db_path):
    abs_path = os.path.abspath(db_path)
    directory = os.path.dirname(abs_path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    normalized = abs_path.replace("\\", "/")
    return f"sqlite:///{normalized}"

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'python-teaching-website-secret-key'
    SQLALCHEMY_DATABASE_URI = _build_sqlite_uri(_resolve_db_path())
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 代码执行配置
    CODE_EXECUTION_TIMEOUT = 5  # 秒

    # AI 提供商密钥 (从环境变量读取)
    DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
    ZHIPU_API_KEY = os.environ.get('ZHIPU_API_KEY', '')
    MINIMAX_API_KEY = os.environ.get('MINIMAX_API_KEY', '')

    # 存储
    HANDBOOK_STORAGE_ROOT = os.environ.get('HANDBOOK_STORAGE_ROOT', '')
