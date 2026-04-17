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


def _resolve_database_uri():
    explicit_uri = os.environ.get("SCF_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if explicit_uri:
        return explicit_uri
    return _build_sqlite_uri(_resolve_db_path())


def _resolve_runtime_root():
    runtime_root = os.environ.get("SCF_RUNTIME_ROOT")
    if runtime_root:
        abs_root = os.path.abspath(runtime_root)
        os.makedirs(abs_root, exist_ok=True)
        return abs_root
    return os.path.dirname(os.path.abspath(_resolve_db_path()))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'python-teaching-website-secret-key'
    SQLALCHEMY_DATABASE_URI = _resolve_database_uri()
    SCF_RUNTIME_ROOT = _resolve_runtime_root()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TESTING = False
    OA_EXTERNAL_API_KEY = 'scf233'
    OPENCLAW_INTEGRATION_TOKEN = os.environ.get('OPENCLAW_INTEGRATION_TOKEN') or 'openclaw233'
    ALIYUN_SMS_ENABLED = os.environ.get('ALIYUN_SMS_ENABLED', '').strip().lower() in {'1', 'true', 'yes', 'on'}
    ALIYUN_SMS_ACCESS_KEY_ID = os.environ.get('ALIYUN_SMS_ACCESS_KEY_ID', '')
    ALIYUN_SMS_ACCESS_KEY_SECRET = os.environ.get('ALIYUN_SMS_ACCESS_KEY_SECRET', '')
    ALIYUN_SMS_SIGN_NAME = os.environ.get('ALIYUN_SMS_SIGN_NAME', '')
    ALIYUN_SMS_TEMPLATE_CODE_ONLINE = os.environ.get('ALIYUN_SMS_TEMPLATE_CODE_ONLINE', '')
    ALIYUN_SMS_TEMPLATE_CODE_OFFLINE = os.environ.get('ALIYUN_SMS_TEMPLATE_CODE_OFFLINE', '')
    ALIYUN_SMS_ENDPOINT = os.environ.get('ALIYUN_SMS_ENDPOINT', 'https://dysmsapi.aliyuncs.com/')
    SMS_REMINDER_LEAD_MINUTES = int(os.environ.get('SMS_REMINDER_LEAD_MINUTES', '120') or 120)
    SMS_REMINDER_SCAN_WINDOW_MINUTES = int(os.environ.get('SMS_REMINDER_SCAN_WINDOW_MINUTES', '10') or 10)
    SCF_REMINDER_JOB_TOKEN = os.environ.get('SCF_REMINDER_JOB_TOKEN', '')
    TENCENT_MEETING_ENABLED = os.environ.get('TENCENT_MEETING_ENABLED', '').strip().lower() in {'1', 'true', 'yes', 'on'}
    TENCENT_MEETING_API_HOST = os.environ.get('TENCENT_MEETING_API_HOST', 'https://api.meeting.qq.com')
    TENCENT_MEETING_APP_ID = os.environ.get('TENCENT_MEETING_APP_ID', '')
    TENCENT_MEETING_SDK_ID = os.environ.get('TENCENT_MEETING_SDK_ID', '')
    TENCENT_MEETING_SECRET_ID = os.environ.get('TENCENT_MEETING_SECRET_ID', '')
    TENCENT_MEETING_SECRET_KEY = os.environ.get('TENCENT_MEETING_SECRET_KEY', '')
    TENCENT_MEETING_CREATOR_USERID = os.environ.get('TENCENT_MEETING_CREATOR_USERID', '')
    TENCENT_MEETING_CREATOR_INSTANCE_ID = int(
        os.environ.get('TENCENT_MEETING_CREATOR_INSTANCE_ID', '1') or 1
    )
    TENCENT_MEETING_WEBHOOK_TOKEN = os.environ.get('TENCENT_MEETING_WEBHOOK_TOKEN', '')
    TENCENT_MEETING_WEBHOOK_AES_KEY = os.environ.get('TENCENT_MEETING_WEBHOOK_AES_KEY', '')
    TENCENT_MEETING_CREATE_LEAD_MINUTES = int(
        os.environ.get('TENCENT_MEETING_CREATE_LEAD_MINUTES', '120') or 120
    )
    TENCENT_MEETING_CREATE_WINDOW_MINUTES = int(
        os.environ.get('TENCENT_MEETING_CREATE_WINDOW_MINUTES', '10') or 10
    )
    TENCENT_MEETING_JOB_TOKEN = os.environ.get('TENCENT_MEETING_JOB_TOKEN', '')
    COURSE_FEEDBACK_AI_PROVIDER = os.environ.get('COURSE_FEEDBACK_AI_PROVIDER', 'zhipu')
    FEEDBACK_SHARE_LINK_TTL_DAYS = int(os.environ.get('FEEDBACK_SHARE_LINK_TTL_DAYS', '30') or 30)

    # 代码执行配置
    CODE_EXECUTION_TIMEOUT = 5  # 秒

    # AI 提供商密钥 (从环境变量读取)
    DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
    ZHIPU_API_KEY = os.environ.get('ZHIPU_API_KEY', '')
    MINIMAX_API_KEY = os.environ.get('MINIMAX_API_KEY', '')
    DOUBAO_VISION_ENABLED = os.environ.get('DOUBAO_VISION_ENABLED', '').strip().lower() in {'1', 'true', 'yes', 'on'}
    DOUBAO_VISION_API_KEY = os.environ.get('DOUBAO_VISION_API_KEY', '')
    DOUBAO_VISION_MODEL = os.environ.get('DOUBAO_VISION_MODEL', 'doubao-seed-2-0-pro-260215')
    DOUBAO_VISION_RESPONSES_URL = os.environ.get(
        'DOUBAO_VISION_RESPONSES_URL',
        'https://ark.cn-beijing.volces.com/api/v3/responses',
    )
    DOUBAO_VISION_TIMEOUT_SECONDS = int(os.environ.get('DOUBAO_VISION_TIMEOUT_SECONDS', '20') or 20)

    # 存储
    HANDBOOK_STORAGE_ROOT = os.environ.get('HANDBOOK_STORAGE_ROOT', '')

    # 启动期副作用开关
    SCF_AUTO_MIGRATE_COLUMNS = True
    SCF_AUTO_INIT_DATA = True
    SCF_AUTO_BACKFILL_SCHEDULE_LINKS = True
    SCF_AUTO_CLEANUP_EXPIRED = True
    SCF_RUN_ONCE_MIGRATIONS = True


class TestingConfig(Config):
    TESTING = True
    SCF_AUTO_MIGRATE_COLUMNS = False
    SCF_AUTO_INIT_DATA = False
    SCF_AUTO_BACKFILL_SCHEDULE_LINKS = False
    SCF_AUTO_CLEANUP_EXPIRED = False
    SCF_RUN_ONCE_MIGRATIONS = False
